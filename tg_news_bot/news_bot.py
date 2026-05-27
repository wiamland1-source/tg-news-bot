#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TG News Bot
Поиск новостей → Рерайт через Claude → Одобрение → Публикация в Telegram

Запуск:
  python3 news_bot.py ved        # ВЭД / Импорт-Экспорт (12:00)
  python3 news_bot.py goszakaz   # Государственные закупки (16:00)
"""

import sys
import os
import json
import time
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from anthropic import Anthropic

# ─── КОНФИГУРАЦИЯ ────────────────────────────────────────────────────────────

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    """Читает конфиг из config.json (локально) или переменных окружения (GitHub Actions)."""
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    return cfg

cfg = load_config()

# Приоритет: переменные окружения (GitHub Actions) → config.json (локально)
BOT_TOKEN     = os.environ.get("BOT_TOKEN")     or cfg.get("bot_token", "")
CHANNEL_ID    = os.environ.get("CHANNEL_ID")    or cfg.get("channel_id", "@tdamanati")
REVIEWER_ID   = os.environ.get("REVIEWER_CHAT_ID") or cfg.get("reviewer_chat_id", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY") or cfg.get("anthropic_api_key", "")

if not BOT_TOKEN or not REVIEWER_ID:
    print("❌ Не указаны BOT_TOKEN или REVIEWER_CHAT_ID. Проверь config.json или secrets.")
    sys.exit(1)

# ─── ТЕМЫ ────────────────────────────────────────────────────────────────────

TOPICS = {
    "ved": {
        "label":   "ВЭД / Импорт-Экспорт",
        "emoji":   "🌐",
        "queries": [
            "ВЭД импорт экспорт 2026",
            "внешнеэкономическая деятельность Россия",
            "таможня пошлины экспорт"
        ],
        "prompt": (
            "Тема: внешнеэкономическая деятельность, импорт, экспорт, таможня, пошлины. "
            "Аудитория: предприниматели и компании, работающие в сфере ВЭД."
        )
    },
    "goszakaz": {
        "label":   "Государственные закупки",
        "emoji":   "🏛️",
        "queries": [
            "госзакупки тендер 2026",
            "государственный заказ 44-ФЗ 223-ФЗ",
            "государственные закупки изменения"
        ],
        "prompt": (
            "Тема: государственные закупки, тендеры, контрактная система, 44-ФЗ, 223-ФЗ. "
            "Аудитория: поставщики и участники государственных тендеров."
        )
    }
}

# ─── ПОИСК НОВОСТЕЙ ──────────────────────────────────────────────────────────

def fetch_news(topic_key):
    """Загрузить статьи из Google News RSS за последние 24 часа."""
    topic = TOPICS[topic_key]
    articles = []
    seen_links = set()

    for query in topic["queries"]:
        encoded = requests.utils.quote(query)
        url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded}&hl=ru&gl=RU&ceid=RU:ru"
        )
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    age_h = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
                    if age_h > 24:
                        continue

                link = entry.get("link", "")
                if link in seen_links:
                    continue
                seen_links.add(link)

                articles.append({
                    "title":     entry.get("title", "").strip(),
                    "link":      link,
                    "published": entry.get("published", ""),
                    "source":    entry.get("source", {}).get("title", "Источник неизвестен"),
                    "summary":   BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(),
                    "score":     0
                })
        except Exception as e:
            print(f"  [RSS] Ошибка для '{query}': {e}")

    return articles


def score_article(article):
    """Оценить статью по ключевым словам и авторитетности источника."""
    score = 0
    title  = article["title"].lower()
    source = article["source"].lower()

    trusted_sources = [
        "rbc", "rбк", "коммерсант", "ведомости", "interfax", "интерфакс",
        "tass", "тасс", "ria", "риа", "минфин", "минэкономразвития",
        "федеральная", "правительство", "минпромторг"
    ]
    for src in trusted_sources:
        if src in source:
            score += 3

    important_keywords = [
        "изменени", "поправк", "закон", "постановлени", "приказ",
        "вступил в силу", "принят", "санкци", "пошлин", "квот",
        "льгот", "субсиди", "запрет", "разрешен", "реестр", "аукцион",
        "контракт", "поставк"
    ]
    for kw in important_keywords:
        if kw in title:
            score += 2

    return score


def fetch_article_text(url, max_chars=4000):
    """Извлечь основной текст статьи."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        # Приоритет: article > main > body
        for selector in ["article", "main", "[class*='article']", "[class*='content']"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(" ", strip=True)
                if len(text) > 200:
                    return text[:max_chars]

        return soup.get_text(" ", strip=True)[:max_chars]
    except Exception as e:
        print(f"  [Fetch] Не удалось загрузить статью: {e}")
        return ""


def pick_best_article(articles):
    """Выбрать статью с наибольшим score."""
    for a in articles:
        a["score"] = score_article(a)
    return max(articles, key=lambda x: x["score"])

# ─── ГЕНЕРАЦИЯ ПОСТА ─────────────────────────────────────────────────────────

def generate_post(article, topic_key):
    """Сгенерировать Telegram-пост через Claude API."""
    topic = TOPICS[topic_key]

    full_text = fetch_article_text(article["link"])
    content = full_text if len(full_text) > 300 else article.get("summary", article["title"])

    if not ANTHROPIC_KEY:
        # Простой шаблон без AI
        summary = content[:700].rstrip() + ("…" if len(content) > 700 else "")
        return (
            f"{topic['emoji']} *{article['title']}*\n\n"
            f"{summary}\n\n"
            f"📎 Источник: {article['source']}\n"
            f"{article['link']}"
        )

    client = Anthropic(api_key=ANTHROPIC_KEY)

    system_prompt = """Ты — практик в сфере бизнеса, который ведёт Telegram-канал для коллег. Пишешь как живой человек: иногда с иронией, иногда с лёгким раздражением от бюрократии, всегда по делу. Никакого официоза, никаких клише вроде «в условиях современных реалий» или «данный аспект». Пишешь так, как объяснил бы другу за кофе — но другу, который в теме."""

    user_prompt = f"""Напиши пост для Telegram-канала на основе этой новости. Аудитория: {topic["prompt"]}

Как писать (обязательно):
— Заголовок: {topic["emoji"]} + <b>цепляющая фраза своими словами</b>, не пересказ названия статьи
— Начни с сути или с проблемы, которую это создаёт для читателя — без вступлений и «сегодня стало известно»
— Объясни что изменилось, как это работает на практике и кого касается — конкретно, без воды
— Можно одно короткое личное замечание или вывод в конце — что с этим делать
— Последняя строка: «📎 [название источника]:» и на следующей строке — ссылка
— Форматирование: только HTML-теги (<b> для заголовка), остальное — обычный текст без списков и буллетов
— Длина: 900–1100 символов
— Язык: живой русский, разговорный, без канцелярита

Чего избегать категорически:
— «В условиях», «данный», «осуществляется», «в рамках», «необходимо отметить»
— Перечисления через тире или цифры
— Пассивный залог там, где можно активный
— Очевидных AI-паттернов: «Давайте разберёмся», «Итак,», «Таким образом»

Новость:
Заголовок: {article["title"]}
Источник: {article["source"]} ({article["link"]})
Текст: {content}"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        print(f"  [Claude API] Ошибка: {e}")
        summary = content[:700].rstrip() + ("…" if len(content) > 700 else "")
        return (
            f"{topic['emoji']} <b>{article['title']}</b>\n\n"
            f"{summary}\n\n"
            f"📎 {article['source']}:\n"
            f"{article['link']}"
        )

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def tg(method, data=None):
    """Вызов Telegram Bot API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        r = requests.post(url, json=data or {}, timeout=15)
        return r.json()
    except Exception as e:
        print(f"  [TG] Ошибка запроса {method}: {e}")
        return {}


def send_draft(post_text, topic_label):
    """Отправить черновик ревьюеру с кнопками одобрения."""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    header = f"📝 *Черновик поста — {topic_label}*\n_Создан: {now}_\n\n"
    footer = "\n\n─────────────────\n_Нажми кнопку для принятия решения:_"

    markup = {
        "inline_keyboard": [[
            {"text": "✅ Опубликовать", "callback_data": "approve"},
            {"text": "❌ Отклонить",    "callback_data": "reject"}
        ]]
    }

    result = tg("sendMessage", {
        "chat_id":    REVIEWER_ID,
        "text":       header + post_text + footer,
        "parse_mode": "HTML",
        "reply_markup": markup,
        "disable_web_page_preview": True
    })
    return result.get("result", {}).get("message_id")


def wait_for_decision(timeout_hours=4):
    """Ждать решения ревьюера через polling. Возвращает 'approve', 'reject' или 'timeout'."""
    deadline = time.time() + timeout_hours * 3600
    offset = 0

    print(f"  Ожидаю решение (до {timeout_hours}ч)...", flush=True)

    while time.time() < deadline:
        result = tg("getUpdates", {
            "offset": offset,
            "timeout": 30,
            "allowed_updates": ["callback_query"]
        })
        for upd in result.get("result", []):
            offset = upd["update_id"] + 1
            cb = upd.get("callback_query")
            if cb and str(cb["from"]["id"]) == str(REVIEWER_ID):
                tg("answerCallbackQuery", {"callback_query_id": cb["id"]})
                return cb["data"]
        time.sleep(3)

    return "timeout"


def publish(post_text):
    """Опубликовать пост в канал."""
    result = tg("sendMessage", {
        "chat_id":    CHANNEL_ID,
        "text":       post_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    })
    return result.get("ok", False)


def notify(text):
    """Отправить уведомление ревьюеру."""
    tg("sendMessage", {
        "chat_id": REVIEWER_ID,
        "text":    text
    })

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in TOPICS:
        print("Использование: python3 news_bot.py [ved|goszakaz]")
        sys.exit(1)

    topic_key = sys.argv[1]
    topic     = TOPICS[topic_key]
    ts        = datetime.now().strftime("%d.%m.%Y %H:%M")

    print(f"\n{'='*50}")
    print(f"  TG News Bot | {topic['label']} | {ts}")
    print(f"{'='*50}\n")

    # 1. Поиск новостей
    print("1. Ищу свежие статьи за 24ч...")
    articles = fetch_news(topic_key)
    print(f"   Найдено: {len(articles)} статей")

    if not articles:
        msg = f"⚠️ Нет свежих новостей по теме «{topic['label']}» за последние 24 часа."
        print(f"   {msg}")
        notify(msg)
        return

    # 2. Выбор лучшей
    print("2. Оцениваю вовлечённость...")
    best = pick_best_article(articles)
    print(f"   Выбрана: {best['title'][:80]}")
    print(f"   Источник: {best['source']} | Score: {best['score']}")

    # 3. Генерация поста
    print("3. Генерирую пост...")
    post = generate_post(best, topic_key)
    print(f"   Пост готов ({len(post)} символов)")

    # 4. Отправка на одобрение
    print("4. Отправляю черновик ревьюеру...")
    msg_id = send_draft(post, topic["label"])
    if not msg_id:
        print("   ❌ Не удалось отправить черновик!")
        return
    print(f"   Отправлено (message_id={msg_id})")

    # 5. Ожидание решения
    decision = wait_for_decision(timeout_hours=4)
    print(f"\n5. Решение: {decision}")

    if decision == "approve":
        ok = publish(post)
        if ok:
            print(f"   ✅ Пост опубликован в {CHANNEL_ID}")
            notify(f"✅ Пост «{topic['label']}» опубликован в {CHANNEL_ID}")
        else:
            print("   ❌ Ошибка публикации")
            notify("❌ Ошибка при публикации. Проверь права бота в канале.")

    elif decision == "reject":
        print("   🗑️ Пост отклонён")
        notify(f"🗑️ Пост «{topic['label']}» отклонён — не опубликован.")

    else:
        print("   ⏰ Время ожидания истекло")
        notify(
            f"⏰ Время ожидания истекло (4ч).\n"
            f"Пост «{topic['label']}» не опубликован."
        )

    print("\nГотово.\n")


if __name__ == "__main__":
    main()
