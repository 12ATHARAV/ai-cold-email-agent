#!/usr/bin/env bash

# Termux (Android Phone) Deployment script
# Sets up the bot to run 24/7 on an old Android phone

set -e

echo "📱 Starting Termux Android Deployment Setup..."

# 1. Update Termux repositories
echo "🔄 Updating packages..."
pkg update -y && pkg upgrade -y

# 2. Install Python, Node.js, and git
echo "📥 Installing Python, Node.js, and Git..."
pkg install python nodejs git termux-api -y

# 3. Prevent phone from going to sleep
echo "🔋 Setting up battery/sleep configurations..."
termux-wake-lock
echo "✅ Wake lock requested. Termux will prevent Android from going into deep sleep."

# 4. Setup Python virtual environment
echo "📦 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python -m venv venv
    echo "✅ Created virtual environment."
else
    echo "✅ Virtual environment already exists."
fi

source venv/bin/activate
echo "📥 Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed."

# 5. Install PM2 via npm to keep process alive
if ! command -v pm2 &> /dev/null; then
    echo "📥 Installing PM2 globally..."
    npm install -g pm2
fi

# 6. Run bot with PM2
echo "🎬 Starting bot with PM2..."
pm2 delete cold-email-bot 2>/dev/null || true
pm2 start main.py --interpreter ./venv/bin/python --name cold-email-bot
pm2 save

echo "=================================================="
echo "🎉 Setup Complete! Your Android phone is now hosting the bot."
echo "⚠️  CRITICAL ANDROID SETTINGS:"
echo "To ensure Android doesn't kill the bot in the background:"
echo "1. Go to Settings -> Apps -> Termux."
echo "2. Set battery settings to 'Unrestricted' or 'No battery optimization'."
echo "3. Lock the Termux app in your phone's recent apps list."
echo "4. Keep the phone plugged into a charger."
echo "=================================================="
