#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 檢查是否已在運行
PID=$(pgrep -f "financial-services-bot/bot.py")
if [ -n "$PID" ]; then
    echo "⚠️ FinBot 已經在運行中 (PID: $PID)"
    exit 0
fi

echo "🚀 正在啟動 FinBot..."
nohup python3 "$DIR/bot.py" > "$DIR/nohup.out" 2>&1 &
NEW_PID=$!
sleep 1

if ps -p $NEW_PID > /dev/null; then
    echo "✅ FinBot 啟動成功！PID: $NEW_PID"
    echo "日誌輸出：$DIR/bot.log"
else
    echo "❌ 啟動失敗，請檢查 $DIR/nohup.out 或 $DIR/bot.log"
fi
