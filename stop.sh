#!/bin/bash
PID=$(pgrep -f "financial-services-bot/bot.py")
if [ -z "$PID" ]; then
    echo "ℹ️ FinBot 目前未在運行。"
else
    echo "🛑 正在停止 FinBot (PID: $PID)..."
    kill $PID
    sleep 1
    echo "✅ FinBot 已停止。"
fi
