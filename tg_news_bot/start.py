#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TG News Bot — Запуск и установка
=====================================
Запусти один раз: python3 start.py
Скрипт сделает всё сам:
  1. Установит зависимости
  2. Получит твой Telegram chat_id
  3. Отправит два тестовых поста на одобрение
  4. Установит ежедневный автозапуск (12:00 и 16:00)
"""

import sys
import os
import subprocess
import time
import json

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE  = os.path.join(SCRIPT_DIR, "config.json")
BOT_TOKEN    = "8614778289:AAECh0PMhNfOobcC_R0qOUt0gv_VEGoH5c4"
CHANNEL_ID   = "@tdamanati"

# ─── ДВА ГОТОВЫХ ТЕСТОВЫХ ПОСТА ──────────────────────────────────────────────

TEST_POST_VED = """🌐 <b>Импортёрам из ЕАЭС — новые обязательства уже в мае</b>

С 6 апреля по 27 мая 2026 года система СПОТ (Система подтверждения ожидания товаров) работает в тестовом режиме — но подавать ДОПП (документ о планируемой поставке) уже нужно. Если не подать — таможня фиксирует нарушение. Обеспечительный платёж пока не требуется.

С 1 июня система переходит в полноценный режим: все, кто ввозит товары автотранспортом из стран ЕАЭС (Беларусь, Казахстан, Армения, Кыргызстан), обязаны заранее подавать ДОПП в ФНС и вносить обеспечительный платёж.

Как работает на практике: перед поставкой — уведомить ФНС о сроках и параметрах груза, получить QR-код, и только потом пускать машину. Без QR-кода — задержка на границе.

Кого касается: импортёры и посредники, работающие с поставщиками из ЕАЭС через автотранспорт.

📎 Источник: Контур.Экстерн
https://www.kontur-extern.ru/info/83601-sistema_podtverzhdeniya_ozhidaniya_tovarov"""

TEST_POST_GOSZAKAZ = """🏛 <b>Госзакупки-2026: что важно знать поставщику прямо сейчас</b>

С начала года закон о госзакупках обновился в трёх волнах. Вот что уже работает и что придёт летом.

С января действует «легальное дробление»: официально разрешено несколько малых закупок у одного поставщика в пределах годового лимита. Это упрощает работу небольших поставщиков с госзаказчиками.

С марта при закупках ПО приоритет получают продукты из реестра доверенного российского ПО. Иностранный софт без такой отметки проходит по более жёстким правилам. Участникам также больше не нужно прикладывать ряд документов — система сама подтягивает данные из реестров.

С июля в реестре контрактов появятся сведения о большинстве сделок — это повышает прозрачность. Антидемпинговые требования упрощены: увеличенное обеспечение только если это прямо указано в извещении.

📎 Источник: ГАРАНТ.РУ
https://www.garant.ru/article/1929007/"""

# ─── УТИЛИТЫ ─────────────────────────────────────────────────────────────────

def step(n, total, text):
    print(f"\n[{n}/{total}] {text}")
    print("─" * 50)

def ok(msg):
    print(f"  ✅ {msg}")

def err(msg):
    print(f"  ❌ {msg}")

def info(msg):
    print(f"  ℹ️  {msg}")

# ─── ШАГИ ────────────────────────────────────────────────────────────────────

def install_deps():
    step(1, 5, "Установка зависимостей")
    packages = ["requests", "feedparser", "beautifulsoup4", "anthropic", "lxml"]
    for pkg in packages:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "-q"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok(pkg)
        else:
            err(f"{pkg}: {result.stderr.strip()[:80]}")
    print()

def get_chat_id():
    import requests as req

    step(2, 5, "Получение твоего Telegram chat_id")
    bot_username = req.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10
    ).json().get("result", {}).get("username", "твой_бот")

    print(f"  Открой Telegram и напиши боту @{bot_username} команду:")
    print()
    print("       /start")
    print()
    input("  Нажми Enter после отправки... ")

    print("  Получаю твой chat_id", end="", flush=True)
    for attempt in range(20):
        print(".", end="", flush=True)
        try:
            upd = req.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                json={"offset": -20, "limit": 20}, timeout=10
            ).json()
            for u in reversed(upd.get("result", [])):
                msg = u.get("message", {})
                if msg.get("text") in ["/start", "start"]:
                    chat_id = msg["chat"]["id"]
                    username = msg["from"].get("username", "")
                    print()
                    ok(f"chat_id получен: {chat_id} (@{username})")
                    return chat_id
        except Exception as e:
            pass
        time.sleep(3)

    print()
    err("Не получил /start за отведённое время.")
    print("  Запусти скрипт снова и сразу напиши /start боту.\n")
    sys.exit(1)


def save_config(reviewer_id):
    step(3, 5, "Сохранение конфигурации")
    config = {
        "bot_token":         BOT_TOKEN,
        "channel_id":        CHANNEL_ID,
        "reviewer_chat_id":  reviewer_id,
        "anthropic_api_key": ""
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    ok(f"config.json сохранён")
    ok(f"Канал: {CHANNEL_ID}")
    ok(f"Ревьюер chat_id: {reviewer_id}")


def send_test_posts(reviewer_id):
    import requests as req

    step(4, 5, "Отправка тестовых постов на одобрение")

    posts = [
        ("🌐 ВЭД / Импорт-Экспорт", TEST_POST_VED),
        ("🏛️ Государственные закупки", TEST_POST_GOSZAKAZ),
    ]

    def tg(method, data, timeout=20):
        return req.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json=data, timeout=timeout
        ).json()

    for label, post_text in posts:
        print(f"\n  Пост: {label}")

        # Отправить черновик
        header = f"📝 <b>Тестовый пост — {label}</b>\n<i>Нажми кнопку для принятия решения:</i>\n\n"
        result = tg("sendMessage", {
            "chat_id":    reviewer_id,
            "text":       header + post_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "✅ Опубликовать", "callback_data": "approve"},
                    {"text": "❌ Отклонить",    "callback_data": "reject"}
                ]]
            }
        })

        if not result.get("ok"):
            err(f"Не удалось отправить черновик: {result.get('description')}")
            continue

        ok(f"Черновик отправлен тебе в Telegram")
        info("Жду твоего решения (до 2 часов)...")

        # Polling
        decision = "timeout"
        offset   = 0
        deadline = time.time() + 7200

        while time.time() < deadline:
            try:
                upd = tg("getUpdates", {
                    "offset": offset,
                    "timeout": 25,
                    "allowed_updates": ["callback_query"]
                }, timeout=35)
                for u in upd.get("result", []):
                    offset = u["update_id"] + 1
                    cb = u.get("callback_query", {})
                    if str(cb.get("from", {}).get("id")) == str(reviewer_id):
                        tg("answerCallbackQuery", {"callback_query_id": cb["id"]})
                        decision = cb.get("data", "reject")
                        break
                if decision != "timeout":
                    break
            except Exception:
                time.sleep(3)

        if decision == "approve":
            pub = tg("sendMessage", {
                "chat_id":    CHANNEL_ID,
                "text":       post_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            })
            if pub.get("ok"):
                ok(f"Пост опубликован в {CHANNEL_ID} ✅")
                tg("sendMessage", {"chat_id": reviewer_id,
                    "text": f"✅ Пост «{label}» опубликован в {CHANNEL_ID}"})
            else:
                err(f"Ошибка публикации: {pub.get('description')}")
        elif decision == "reject":
            ok("Пост отклонён — не опубликован")
            tg("sendMessage", {"chat_id": reviewer_id,
                "text": f"🗑 Пост «{label}» отклонён."})
        else:
            info("Время ожидания истекло — пост не опубликован")

        print()


def install_schedule():
    import requests as req

    step(5, 5, "Установка ежедневного расписания")

    python_bin  = sys.executable
    bot_script  = os.path.join(SCRIPT_DIR, "news_bot.py")
    launch_dir  = os.path.expanduser("~/Library/LaunchAgents")
    log_dir     = os.path.join(SCRIPT_DIR, "logs")
    os.makedirs(log_dir,    exist_ok=True)
    os.makedirs(launch_dir, exist_ok=True)

    tasks = [
        ("com.tgnewsbot.ved",      "ved",      12, "ВЭД / Импорт-Экспорт"),
        ("com.tgnewsbot.goszakaz", "goszakaz", 16, "Государственные закупки"),
    ]

    for label, arg, hour, name in tasks:
        plist_path = os.path.join(launch_dir, f"{label}.plist")
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>{bot_script}</string>
        <string>{arg}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>{hour}</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>{log_dir}/{arg}.log</string>
    <key>StandardErrorPath</key><string>{log_dir}/{arg}.error.log</string>
    <key>RunAtLoad</key><false/>
</dict>
</plist>"""
        with open(plist_path, "w") as f:
            f.write(plist)

        subprocess.run(["launchctl", "unload", plist_path],
                       capture_output=True)
        result = subprocess.run(["launchctl", "load", plist_path],
                                capture_output=True, text=True)
        if result.returncode == 0:
            ok(f"{name} — каждый день в {hour}:00")
        else:
            err(f"Не удалось зарегистрировать {name}: {result.stderr.strip()}")

    print()
    ok(f"Логи: {log_dir}/")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 50)
    print("  TG News Bot — Первый запуск")
    print("=" * 50)

    install_deps()

    reviewer_id = get_chat_id()
    save_config(reviewer_id)
    send_test_posts(reviewer_id)
    install_schedule()

    print("=" * 50)
    print("  Всё готово! 🎉")
    print()
    print("  Расписание:")
    print("  • 12:00 — ВЭД / Импорт-Экспорт")
    print("  • 16:00 — Государственные закупки")
    print()
    print("  Запустить вручную:")
    print(f"  python3 {os.path.join(SCRIPT_DIR, 'news_bot.py')} ved")
    print(f"  python3 {os.path.join(SCRIPT_DIR, 'news_bot.py')} goszakaz")
    print("=" * 50)
    print()


if __name__ == "__main__":
    main()
