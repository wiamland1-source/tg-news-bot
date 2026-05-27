#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TG News Bot — Первоначальная настройка
Запусти один раз: python3 setup.py
"""

import json
import os
import time
import sys
import requests

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def tg_get(token, method, data=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    r = requests.post(url, json=data or {}, timeout=15)
    return r.json()

def clear():
    os.system("clear")

def header():
    print("=" * 52)
    print("   TG News Bot — Настройка")
    print("=" * 52)
    print()

def main():
    clear()
    header()
    print("Привет! Этот скрипт настроит бота за 3 минуты.\n")

    # ─── Шаг 1: Токен ────────────────────────────────────
    print("Шаг 1 / 4 — Токен бота")
    print("-" * 40)
    default_token = "8614778289:AAECh0PMhNfOobcC_R0qOUt0gv_VEGoH5c4"
    print(f"Токен уже известен: {default_token[:20]}...")
    inp = input("Нажми Enter для подтверждения или введи другой токен: ").strip()
    token = inp if inp else default_token

    # Проверяем токен
    result = tg_get(token, "getMe")
    if not result.get("ok"):
        print(f"\n❌ Ошибка: {result.get('description', 'Неверный токен')}")
        sys.exit(1)
    bot_name = result["result"]["username"]
    print(f"✅ Бот подключён: @{bot_name}\n")

    # ─── Шаг 2: ID ревьюера ─────────────────────────────
    print("Шаг 2 / 4 — Твой Telegram ID")
    print("-" * 40)
    print(f"Открой Telegram и напиши своему боту @{bot_name} команду /start")
    print("(если уже написал — просто нажми Enter)\n")
    input("Нажми Enter после того как написал /start боту...")

    print("Получаю твой chat_id...")
    reviewer_id = None
    for attempt in range(10):
        updates = tg_get(token, "getUpdates", {"offset": -10, "limit": 20})
        for upd in reversed(updates.get("result", [])):
            msg = upd.get("message", {})
            if msg.get("text") in ["/start", "start"]:
                reviewer_id = msg["chat"]["id"]
                username = msg["from"].get("username", "")
                first_name = msg["from"].get("first_name", "")
                break
        if reviewer_id:
            break
        print(f"  Попытка {attempt+1}/10... (жду /start от тебя)")
        time.sleep(3)

    if not reviewer_id:
        print("\n❌ Не получил /start. Попробуй ещё раз запустить setup.py")
        sys.exit(1)

    print(f"✅ Твой chat_id: {reviewer_id} (@{username or first_name})\n")

    # Тестовое сообщение
    tg_get(token, "sendMessage", {
        "chat_id": reviewer_id,
        "text": "✅ Настройка прошла успешно! Я буду присылать тебе черновики постов для одобрения."
    })

    # ─── Шаг 3: Канал ────────────────────────────────────
    print("Шаг 3 / 4 — Канал для публикации")
    print("-" * 40)
    print("Убедись что бот добавлен как администратор в канал @tdamanati")
    inp = input("Введи username канала (Enter = @tdamanati): ").strip()
    channel = inp if inp else "@tdamanati"

    # Проверяем доступ к каналу
    test = tg_get(token, "sendMessage", {
        "chat_id": channel,
        "text": "🔧 Тест подключения бота к каналу. Это сообщение можно удалить."
    })
    if test.get("ok"):
        print(f"✅ Бот успешно написал в {channel}\n")
    else:
        print(f"⚠️  Ошибка доступа к каналу: {test.get('description', '')}")
        print("   Убедись что бот добавлен как администратор с правом публикации.")
        ans = input("   Продолжить всё равно? (y/n): ").strip().lower()
        if ans != "y":
            sys.exit(1)
        print()

    # ─── Шаг 4: Anthropic API ────────────────────────────
    print("Шаг 4 / 4 — Claude API (для качественного рерайта)")
    print("-" * 40)
    print("Получи API-ключ на https://console.anthropic.com")
    print("Если нет ключа — нажми Enter, пост будет в базовом формате\n")
    anthropic_key = input("Введи Anthropic API key (или Enter чтобы пропустить): ").strip()

    if anthropic_key:
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=anthropic_key)
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            print("✅ Anthropic API ключ работает\n")
        except Exception as e:
            print(f"⚠️  Ошибка проверки ключа: {e}")
            ans = input("   Сохранить ключ всё равно? (y/n): ").strip().lower()
            if ans != "y":
                anthropic_key = ""
            print()
    else:
        print("⚠️  Ключ не указан — будет базовый формат поста\n")

    # ─── Сохранение конфига ───────────────────────────────
    config = {
        "bot_token":        token,
        "channel_id":       channel,
        "reviewer_chat_id": reviewer_id,
        "anthropic_api_key": anthropic_key
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print("=" * 52)
    print("✅ Настройка завершена! config.json сохранён.")
    print()
    print("Следующий шаг — установить автозапуск:")
    print("  bash install.sh")
    print()
    print("Или запустить вручную прямо сейчас:")
    print("  python3 news_bot.py ved        # тест ВЭД")
    print("  python3 news_bot.py goszakaz   # тест Гос закупки")
    print("=" * 52)

if __name__ == "__main__":
    main()
