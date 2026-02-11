#!/data/data/com.termux/files/usr/bin/bash
"""
Termux:Boot Setup - Auto-start bot on device boot
"""

echo "🔧 Setting up Termux:Boot auto-start..."

# Install Termux:Boot if not installed
if ! pm list packages | grep -q com.termux.boot; then
    echo "📲 Please install Termux:Boot from F-Droid first"
    echo "   https://f-droid.org/en/packages/com.termux.boot/"
    exit 1
fi

# Create boot directory
mkdir -p ~/.termux/boot

# Create boot script
cat > ~/.termux/boot/telegram-reporter << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash

# Acquire wake lock to prevent sleep
termux-wake-lock

# Wait for network
sleep 30

# Change to bot directory
cd ~/telegram-reporter-pro

# Start bot
nohup python bot.py > bot.log 2>&1 &

# Log start time
echo "Bot started at $(date)" >> boot.log
EOF

# Make executable
chmod +x ~/.termux/boot/telegram-reporter

echo "✅ Termux:Boot configured successfully"
echo "📱 Bot will start automatically on device boot"
echo "⏱️  (30 second delay for network)"