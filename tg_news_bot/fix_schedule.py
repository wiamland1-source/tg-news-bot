#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Устанавливает расписание автозапуска и проверяет что всё работает.
Запускать из Терминала: python3 fix_schedule.py
"""

import os, sys, subprocess, json

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
BOT_SCRIPT  = os.path.join(SCRIPT_DIR, "news_bot.py")
PYTHON      = sys.executable
LAUNCH_DIR  = os.path.expanduser("~/Library/LaunchAgents")
LOG_DIR     = os.path.join(SCRIPT_DIR, "logs")

os.makedirs(LAUNCH_DIR, exist_ok=True)
os.makedirs(LOG_DIR,    exist_ok=True)

TASKS = [
    ("com.tgnewsbot.ved",      "ved",      12, "ВЭД / Импорт-Экспорт"),
    ("com.tgnewsbot.goszakaz", "goszakaz", 16, "Государственные закупки"),
]

print("\n=== Установка расписания TG News Bot ===\n")

for label, arg, hour, name in TASKS:
    plist_path = os.path.join(LAUNCH_DIR, f"{label}.plist")

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON}</string>
        <string>{BOT_SCRIPT}</string>
        <string>{arg}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>{hour}</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>{LOG_DIR}/{arg}.log</string>
    <key>StandardErrorPath</key><string>{LOG_DIR}/{arg}.error.log</string>
    <key>RunAtLoad</key><false/>
</dict>
</plist>"""

    with open(plist_path, "w") as f:
        f.write(plist)

    subprocess.run(["launchctl", "unload", plist_path], capture_output=True)
    result = subprocess.run(["launchctl", "load",   plist_path], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  ✅ {name} — каждый день в {hour}:00")
    else:
        print(f"  ❌ Ошибка: {result.stderr.strip()}")

print(f"\n  Логи: {LOG_DIR}/")
print(f"  Скрипт: {BOT_SCRIPT}")
print(f"  Python: {PYTHON}")

# Проверка config.json
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    print(f"\n  Канал:   {cfg.get('channel_id')}")
    print(f"  Ревьюер: {cfg.get('reviewer_chat_id')}")
    print(f"  Anthropic API: {'✅ есть' if cfg.get('anthropic_api_key') else '⚠️  не указан (посты будут без AI-рерайта)'}")
else:
    print("\n  ⚠️  config.json не найден!")

print("\n=== Готово! Расписание установлено. ===\n")
