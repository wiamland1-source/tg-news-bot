#!/bin/bash
# TG News Bot — установка зависимостей и настройка автозапуска (macOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=$(which python3)
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
LOG_DIR="$SCRIPT_DIR/logs"

echo ""
echo "=================================================="
echo "  TG News Bot — Установка"
echo "=================================================="
echo ""

# ─── Зависимости ─────────────────────────────────────
echo "1. Устанавливаю Python-зависимости..."
pip3 install -r "$SCRIPT_DIR/requirements.txt" --quiet
echo "   ✅ Готово"
echo ""

# ─── Логи ────────────────────────────────────────────
echo "2. Создаю папку для логов..."
mkdir -p "$LOG_DIR"
echo "   ✅ $LOG_DIR"
echo ""

# ─── LaunchAgent: ВЭД (12:00) ────────────────────────
echo "3. Создаю задачу автозапуска: ВЭД в 12:00..."
mkdir -p "$LAUNCH_AGENTS"

cat > "$LAUNCH_AGENTS/com.tgnewsbot.ved.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tgnewsbot.ved</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/news_bot.py</string>
        <string>ved</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>12</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/ved.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/ved.error.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

launchctl unload "$LAUNCH_AGENTS/com.tgnewsbot.ved.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS/com.tgnewsbot.ved.plist"
echo "   ✅ ВЭД — каждый день в 12:00"
echo ""

# ─── LaunchAgent: Гос закупки (16:00) ────────────────
echo "4. Создаю задачу автозапуска: Гос закупки в 16:00..."

cat > "$LAUNCH_AGENTS/com.tgnewsbot.goszakaz.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tgnewsbot.goszakaz</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/news_bot.py</string>
        <string>goszakaz</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>16</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/goszakaz.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/goszakaz.error.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

launchctl unload "$LAUNCH_AGENTS/com.tgnewsbot.goszakaz.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS/com.tgnewsbot.goszakaz.plist"
echo "   ✅ Гос закупки — каждый день в 16:00"
echo ""

# ─── Итог ────────────────────────────────────────────
echo "=================================================="
echo "  Установка завершена!"
echo ""
echo "  Расписание:"
echo "  • 12:00 — ВЭД / Импорт-Экспорт"
echo "  • 16:00 — Государственные закупки"
echo ""
echo "  Логи:"
echo "  • $LOG_DIR/ved.log"
echo "  • $LOG_DIR/goszakaz.log"
echo ""
echo "  Тест прямо сейчас:"
echo "  python3 $SCRIPT_DIR/news_bot.py ved"
echo "=================================================="
echo ""
