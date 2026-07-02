#!/usr/bin/env bash

# Serv00.com Python Telegram Bot Deployment Script
# Deploys the bot 24/7 on Serv00 free tier hosting (FreeBSD-based)

set -e

echo "🚀 Starting Serv00.com Deployment Setup..."

# 1. Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed or not in PATH."
    exit 1
fi

# 2. Check virtualenv
echo "📦 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Created virtual environment in 'venv/'."
else
    echo "✅ Virtual environment already exists."
fi

# Activate virtualenv and install dependencies
source venv/bin/activate
echo "📥 Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed."

# 3. Create logs directory
mkdir -p logs

# 4. Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️ Warning: .env file not found."
    if [ -f ".env.example" ]; then
        echo "📄 Copying .env.example to .env..."
        cp .env.example .env
        echo "👉 Please edit .env file and add your actual API keys and credentials!"
    else
        echo "❌ Error: Neither .env nor .env.example exists."
        exit 1
    fi
else
    echo "✅ .env file found."
fi

# 5. Check if PM2 is installed via npm
echo "🔄 Checking PM2 process manager..."
if ! command -v pm2 &> /dev/null; then
    echo "📥 Installing PM2 globally for your user..."
    npm install -g pm2 || {
        echo "⚠️ npm install failed. Make sure Node.js is enabled in Serv00 panel."
        echo "Alternatively, you can run the bot in background using nohup:"
        echo "  nohup ./venv/bin/python main.py > logs/app.log 2>&1 &"
        exit 0
    }
fi

# 6. Run with PM2
echo "🎬 Starting Telegram Bot with PM2..."
pm2 delete cold-email-bot 2>/dev/null || true
pm2 start main.py --interpreter ./venv/bin/python --name cold-email-bot
pm2 save

echo "🎉 Deployment setup complete!"
echo "--------------------------------------------------"
echo "📊 PM2 Commands for Management:"
echo "  • View status: pm2 status"
echo "  • View logs:   pm2 logs cold-email-bot"
echo "  • Restart bot: pm2 restart cold-email-bot"
echo "  • Stop bot:    pm2 stop cold-email-bot"
echo "--------------------------------------------------"
echo "⚠️  IMPORTANT SERV00 STEP:"
echo "Log into your Serv00 Web Panel (https://panel.serv00.com/):"
echo "1. Go to 'Additional services' -> 'Cron'"
echo "2. Add a cron job to keep PM2 alive on server reboots:"
echo "   Command: /home/YOUR_USERNAME/.npm-global/bin/pm2 resurrect"
echo "   Time: At reboot"
echo "--------------------------------------------------"
