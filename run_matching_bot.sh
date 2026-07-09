#!/bin/bash
# =====================================================
# Run B2B Matching Bot
# =====================================================
# Bot scrapes Facebook groups → filters buyer intent →
# matches against 9,600+ businesses → sends results to Discord
# =====================================================

cd "$(dirname "$0")"

# Activate virtual environment (sử dụng venv từ DiscordBot)
VENV_PATH="../DiscordBot/.venv"
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
    echo "✅ Activated venv: $VENV_PATH"
else
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "   Please create one or adjust the path."
    exit 1
fi

# Kiểm tra dependencies
python -c "import sentence_transformers, discord, bs4, pyppeteer, dotenv" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ Installing missing dependencies..."
    pip install sentence-transformers discord.py python-dotenv beautifulsoup4 pyppeteer
fi

# Kiểm tra file dữ liệu
if [ ! -f "Business_dataset.csv" ]; then
    echo "❌ Business_dataset.csv not found!"
    exit 1
fi

# Kiểm tra file .env
ENV_FILE="../DiscordBot/.env.bot.facebook"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ .env.bot.facebook not found at $ENV_FILE"
    exit 1
fi

echo "🚀 Starting B2B Matching Bot..."
echo "   📄 Dataset: Business_dataset.csv"
echo "   🔧 Config: $ENV_FILE"
echo ""

python fb_matching_bot.py -e "$ENV_FILE"
