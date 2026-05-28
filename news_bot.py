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

def fetch_news(topic_key, max_age_hours=48):
    """Загрузить статьи из Google News RSS за последние max_age_hours часов."""
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
            print(f"  [RSS] Запрос: {query}")
            feed = feedparser.parse(url)
            print(f"  [RSS] Получено записей: {len(feed.entries)}")
            added = 0
            for entry in feed.entries[:20]:
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    age_h = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
                    if age_h > max_age_hours:
                        continue
                else:
                    # Если дата не указана — берём статью (на случай странного RSS)
                    pass

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
                added += 1
            print(f"  [RSS] Добавлено новых: {added}")
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

def tg(method, data=None, timeout=15):
    """Вызов Telegram Bot API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        r = requests.post(url, json=data or {}, timeout=timeout)
        result = r.json()
        if not result.get("ok") and method != "getUpdates":
            print(f"  [TG] API ошибка {method}: {result.get('description', result)}")
        return result
    except Exception as e:
        print(f"  [TG] Ошибка запроса {method}: {e}")
        return {}


def send_draft(post_text, topic_label, prefix=""):
    """Отправить черновик ревьюеру с кнопками одобрения."""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    prefix_line = f"{prefix}\n" if prefix else ""
    header = f"📝 <b>Черновик — {topic_label}</b>\n<i>{prefix_line}Создан: {now}</i>\n\n"
    footer = "\n\n─────────────────\n<i>Нажми кнопку:</i>"

    markup = {
        "inline_keyboard": [[
            {"text": "✅ Опубликовать", "callback_data": "approve"},
            {"text": "❌ Другой вариант", "callback_data": "reject"}
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


def drain_old_updates():
    """Сбросить все накопившиеся старые апдейты перед началом ожидания."""
    result = tg("getUpdates", {"offset": -1, "timeout": 0}, timeout=10)
    updates = result.get("result", [])
    if updates:
        last_id = updates[-1]["update_id"]
        tg("getUpdates", {"offset": last_id + 1, "timeout": 0}, timeout=10)
        print(f"  [drain] Сброшено старых апдейтов: {len(updates)}", flush=True)


def wait_for_decision(timeout_hours=4):
    """Ждать решения ревьюера через polling. Возвращает 'approve', 'reject' или 'timeout'."""
    # Сначала дренируем все накопившиеся старые нажатия кнопок
    drain_old_updates()

    deadline = time.time() + timeout_hours * 3600
    offset = 0
    poll_timeout = 25  # секунд для Telegram long polling
    start_time = time.time()

    print(f"  Ожидаю решение (до {timeout_hours}ч)...", flush=True)

    while time.time() < deadline:
        try:
            result = tg("getUpdates", {
                "offset": offset,
                "timeout": poll_timeout,
                "allowed_updates": ["callback_query"]
            }, timeout=poll_timeout + 10)
        except Exception as e:
            print(f"  [polling] Ошибка: {e}, retry...")
            time.sleep(3)
            continue

        for upd in result.get("result", []):
            offset = upd["update_id"] + 1
            cb = upd.get("callback_query")
            if not cb:
                continue
            # Игнорируем callbacks старше 60 секунд до старта бота
            cb_time = cb.get("message", {}).get("date", 0)
            if cb_time and cb_time < start_time - 60:
                print(f"  [drain] Пропущен старый callback (возраст {int(start_time - cb_time)}с)")
                continue
            if str(cb["from"]["id"]) == str(REVIEWER_ID):
                tg("answerCallbackQuery", {"callback_query_id": cb["id"]})
                decision = cb["data"]
                print(f"  Получено решение: {decision}", flush=True)
                return decision

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
    result = tg("sendMessage", {
        "chat_id": REVIEWER_ID,
        "text":    text
    })
    return result

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

    # 1. Поиск новостей (сначала 24ч, fallback на 48ч)
    print("1. Ищу свежие статьи за 24ч...")
    articles = fetch_news(topic_key, max_age_hours=24)
    print(f"   Найдено за 24ч: {len(articles)} статей")

    if not articles:
        print("   Нет статей за 24ч, расширяю до 48ч...")
        articles = fetch_news(topic_key, max_age_hours=48)
        print(f"   Найдено за 48ч: {len(articles)} статей")

    if not articles:
        msg = f"⚠️ Нет свежих новостей по теме «{topic['label']}» за последние 48 часов."
        print(f"   {msg}")
        result = notify(msg)
        print(f"   notify result: {result}")
        return

    # 2. Сортируем все статьи по score
    print("2. Оцениваю вовлечённость...")
    for a in articles:
        a["score"] = score_article(a)
    articles.sort(key=lambda x: x["score"], reverse=True)
    print(f"   Отсортировано {len(articles)} статей")

    # 3. Цикл: генерируем → отправляем → ждём решения
    used_links = set()
    attempt = 0

    for article in articles:
        if article["link"] in used_links:
            continue
        used_links.add(article["link"])
        attempt += 1

        print(f"\n--- Попытка {attempt} ---")
        print(f"   Статья: {article['title'][:80]}")
        print(f"   Источник: {article['source']} | Score: {article['score']}")

        print("   Генерирую пост...")
        post = generate_post(article, topic_key)
        print(f"   Пост готов ({len(post)} символов)")

        print("   Отправляю черновик ревьюеру...")
        prefix = f"📄 Вариант {attempt}" if attempt > 1 else ""
        msg_id = send_draft(post, topic["label"], prefix)
        if not msg_id:
            print("   ❌ Не удалось отправить черновик!")
            continue
        print(f"   Отправлено (message_id={msg_id})")

        decision = wait_for_decision(timeout_hours=4)
        print(f"   Решение: {decision}")

        if decision == "approve":
            ok = publish(post)
            if ok:
                print(f"   ✅ Пост опубликован в {CHANNEL_ID}")
                notify(f"✅ Пост «{topic['label']}» (вариант {attempt}) опубликован в {CHANNEL_ID}")
            else:
                print("   ❌ Ошибка публикации")
                notify("❌ Ошибка при публикации. Проверь права бота в канале.")
            print("\nГотово.\n")
            return

        elif decision == "reject":
            remaining = len(articles) - attempt
            if remaining > 0:
                notify(f"🔄 Генерирую новый вариант ({remaining} статей осталось)...")
                print(f"   Отклонён. Пробую следующую статью...")
            else:
                notify(f"😔 Все {attempt} варианты отклонены — больше статей нет.")
                print("   Все статьи использованы.")
                print("\nГотово.\n")
                return

        else:  # timeout
            notify(
                f"⏰ Время ожидания истекло (4ч).\n"
                f"Пост «{topic['label']}» не опубликован."
            )
            print("\nГотово.\n")
            return

    notify(f"😔 Все варианты отклонены — новых статей по теме «{topic['label']}» нет.")
    print("\nГотово.\n")


if __name__ == "__main__":
    main()
