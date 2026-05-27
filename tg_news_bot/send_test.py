#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отправляет два тестовых поста на одобрение и публикует в канал.
Запускать ПОСЛЕ start.py (config.json уже создан).
"""

import json, os, time, sys
import requests

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

with open(CONFIG_FILE, encoding="utf-8") as f:
    cfg = json.load(f)

BOT_TOKEN   = cfg["bot_token"]
CHANNEL_ID  = cfg["channel_id"]
REVIEWER_ID = cfg["reviewer_chat_id"]

POSTS = [
    (
        "🌐 ВЭД / Импорт-Экспорт",
        """🌐 <b>СПОТ — новая головная боль для импортёров из ЕАЭС</b>

Если вы завозите товары из Беларуси, Казахстана или других стран ЕАЭС автотранспортом — с мая у вас появилась новая обязанность, о которой многие ещё не знают.

Называется СПОТ — система подтверждения ожидания товаров. Суть простая: до того как фура пересечёт границу, вы обязаны уведомить ФНС о предстоящей поставке и получить QR-код. Без него — машину завернут.

Прямо сейчас (до 27 мая) идёт тестовый режим: деньги вносить не надо, но сам документ — ДОПП — подавать уже обязательно. Те, кто этого не делает, уже получают фиксацию нарушений от таможни.

С 1 июня — всё по-взрослому: и ДОПП, и обеспечительный платёж. Поэтому лучше разобраться сейчас, пока штрафов ещё нет, чем потом в авральном режиме.

📎 Контур.Экстерн — подробно о том, как это работает:
https://www.kontur-extern.ru/info/83601-sistema_podtverzhdeniya_ozhidaniya_tovarov"""
    ),
    (
        "🏛 Государственные закупки",
        """🏛 <b>Три волны изменений в госзакупках — и одна уже прошла мимо вас</b>

В этом году 44-ФЗ менялся трижды. Январь уже позади, март тоже — разбираемся, что из этого реально влияет на поставщиков.

Главное из того, что уже работает: теперь можно легально дробить малые закупки у одного поставщика несколько раз в год в пределах лимита. Раньше это грозило проблемами, теперь — норма. Хорошая новость для тех, кто работает с небольшими заказчиками.

С марта добавился приоритет для российского ПО в реестре «доверенного». Если ваш продукт туда не попал — вы автоматически в менее выгодной позиции. Стоит проверить.

Плюс упростили документооборот: часть справок, которые раньше прикладывали к заявке, система теперь подтягивает сама из реестров. Меньше бумаги — быстрее участие.

С июля ждём ещё одну волну: реестр контрактов станет публичнее, а антидемпинговые требования — чуть мягче.

📎 Полный разбор от ГАРАНТ.РУ:
https://www.garant.ru/article/1929007/"""
    ),
]

def tg(method, data, timeout=20):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        json=data, timeout=timeout
    )
    return r.json()

def send_and_wait(label, post_text):
    print(f"\n{'='*50}")
    print(f"Пост: {label}")
    print('='*50)

    header = f"📝 <b>Черновик — {label}</b>\n<i>Нажми кнопку:</i>\n\n"
    res = tg("sendMessage", {
        "chat_id":    REVIEWER_ID,
        "text":       header + post_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": [[
            {"text": "✅ Опубликовать", "callback_data": "approve"},
            {"text": "❌ Отклонить",    "callback_data": "reject"}
        ]]}
    })

    if not res.get("ok"):
        print(f"❌ Ошибка отправки: {res.get('description')}")
        return

    print("✅ Черновик отправлен тебе в Telegram")
    print("⏳ Жду твоего решения (до 2 часов)...")

    offset, deadline = 0, time.time() + 7200
    decision = "timeout"

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
                if str(cb.get("from", {}).get("id")) == str(REVIEWER_ID):
                    tg("answerCallbackQuery", {"callback_query_id": cb["id"]})
                    decision = cb.get("data", "reject")
                    break
            if decision != "timeout":
                break
        except Exception as e:
            print(f"  (polling error: {e}, retry...)")
            time.sleep(3)

    if decision == "approve":
        pub = tg("sendMessage", {
            "chat_id":    CHANNEL_ID,
            "text":       post_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        })
        if pub.get("ok"):
            print(f"✅ Опубликовано в {CHANNEL_ID}!")
            tg("sendMessage", {"chat_id": REVIEWER_ID,
                "text": f"✅ Пост «{label}» опубликован в {CHANNEL_ID}"})
        else:
            print(f"❌ Ошибка публикации: {pub.get('description')}")
    elif decision == "reject":
        print("🗑  Пост отклонён — не опубликован")
        tg("sendMessage", {"chat_id": REVIEWER_ID,
            "text": f"🗑 Пост «{label}» отклонён."})
    else:
        print("⏰ Время истекло — пост не опубликован")

if __name__ == "__main__":
    print("\nTG News Bot — Отправка тестовых постов")
    print(f"Ревьюер: {REVIEWER_ID} | Канал: {CHANNEL_ID}\n")
    for label, text in POSTS:
        send_and_wait(label, text)
    print("\nГотово!")
