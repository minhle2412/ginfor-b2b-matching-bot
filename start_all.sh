#!/bin/bash
# start_all.sh - Khởi chạy Discord Bot và Dashboard Server dưới nền hệ thống

# Di chuyển đến thư mục của script này
CWD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CWD"

echo "================================================================="
echo "⚙️  Khởi chạy B2B Matching Bot & Dashboard Server dưới nền"
echo "================================================================="

# 1. Dọn dẹp tiến trình cũ
echo "🧹 Đang dọn dẹp các tiến trình cũ..."
pkill -f fb_matching_bot.py
pkill -f app.py
sleep 1

# 2. Khởi chạy Discord Bot
echo "🤖 Khởi chạy Discord Bot..."
nohup /Users/lenhatminh/Downloads/DiscordBot/.venv/bin/python fb_matching_bot.py -e ../DiscordBot/.env.bot.facebook > bot_discord.log 2>&1 &
PID_BOT=$!

# 3. Khởi chạy Dashboard Server
echo "🔥 Khởi chạy Dashboard Server..."
nohup ./run_prototype.sh > dashboard.log 2>&1 &
PID_DASHBOARD=$!

sleep 2

# 4. Kiểm tra trạng thái
echo "-----------------------------------------------------------------"
echo "📊 Trạng thái tiến trình:"
if ps -p $PID_BOT > /dev/null; then
    echo "  ✅ Discord Bot đang chạy dưới nền (PID: $PID_BOT)"
    echo "     -> Log: tail -f bot_discord.log"
else
    echo "  ❌ Discord Bot KHÔNG khởi chạy thành công. Vui lòng kiểm tra log: cat bot_discord.log"
fi

# Tìm PID của app.py do run_prototype.sh sinh ra
PID_APP=$(pgrep -f app.py)
if [ ! -z "$PID_APP" ]; then
    echo "  ✅ Dashboard Server đang chạy dưới nền (PID: $PID_APP)"
    echo "     -> Log: tail -f dashboard.log"
else
    echo "  ❌ Dashboard Server KHÔNG khởi chạy thành công. Vui lòng kiểm tra log: cat dashboard.log"
fi
echo "================================================================="
