#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PID=$(pgrep -f "financial-services-bot/bot.py")

if [ -n "$PID" ]; then
    echo "🟢 FinBot 狀態：運行中 (PID: $PID)"
    echo "──────── 最近 15 行日誌 ────────"
    tail -n 15 "$DIR/bot.log" 2>/dev/null || true
else
    echo "🔴 FinBot 狀態：未運行"
fi
