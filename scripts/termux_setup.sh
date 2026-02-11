#!/data/data/com.termux/files/usr/bin/bash
# -*- coding: utf-8 -*-
"""
Termux Setup Script - Automated installation for Termux
Lines: ~200
"""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         Telegram Reporter Pro - Termux Installer          ║"
echo "║                      Version 3.0.0                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running on Termux
if [ ! -d /data/data/com.termux ]; then
    echo -e "${RED}❌ This script must be run on Termux for Android${NC}"
    exit 1
fi

# Function to print status
print_status() {
    echo -e "${YELLOW}[*] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

# Request storage permission
print_status "Requesting storage permission..."
termux-setup-storage
sleep 2

# Update packages
print_status "Updating Termux packages..."
pkg update -y && pkg upgrade -y
if [ $? -eq 0 ]; then
    print_success "Packages updated successfully"
else
    print_error "Failed to update packages"
    exit 1
fi

# Install required packages
print_status "Installing required packages..."
pkg install -y \
    python \
    python-pip \
    git \
    sqlite \
    openssl \
    clang \
    libffi \
    libjpeg-turbo \
    libwebp \
    libxml2 \
    libxslt \
    ncurses-utils \
    termux-api \
    nano \
    curl \
    wget

if [ $? -eq 0 ]; then
    print_success "Packages installed successfully"
else
    print_error "Failed to install packages"
    exit 1
fi

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip
if [ $? -eq 0 ]; then
    print_success "Pip upgraded successfully"
else
    print_error "Failed to upgrade pip"
fi

# Clone repository
print_status "Cloning Telegram Reporter Pro..."
if [ -d "telegram-reporter-pro" ]; then
    print_status "Directory exists, updating..."
    cd telegram-reporter-pro
    git pull
else
    git clone https://github.com/yourusername/telegram-reporter-pro.git
    cd telegram-reporter-pro
fi

if [ $? -eq 0 ]; then
    print_success "Repository cloned successfully"
else
    print_error "Failed to clone repository"
    exit 1
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

if [ $? -eq 0 ]; then
    print_success "Python dependencies installed successfully"
else
    print_error "Failed to install Python dependencies"
    exit 1
fi

# Create directories
print_status "Creating required directories..."
mkdir -p sessions
mkdir -p logs
mkdir -p backups
mkdir -p database

print_success "Directories created successfully"

# Setup configuration
print_status "Setting up configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    print_success "Configuration file created: .env"
    echo -e "${YELLOW}⚠️  Please edit .env file with your API credentials${NC}"
else
    print_status "Configuration file already exists"
fi

# Initialize database
print_status "Initializing database..."
python scripts/init_db.py

if [ $? -eq 0 ]; then
    print_success "Database initialized successfully"
else
    print_error "Failed to initialize database"
fi

# Create start script
print_status "Creating start script..."
cat > start_bot.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/telegram-reporter-pro
python bot.py
EOF

chmod +x start_bot.sh
print_success "Start script created: ./start_bot.sh"

# Create background service script
print_status "Creating background service script..."
cat > start_bot_background.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/telegram-reporter-pro
nohup python bot.py > bot.log 2>&1 &
echo "✅ Bot started in background with PID $!"
EOF

chmod +x start_bot_background.sh
print_success "Background service script created: ./start_bot_background.sh"

# Create stop script
print_status "Creating stop script..."
cat > stop_bot.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
pkill -f "python bot.py"
echo "✅ Bot stopped"
EOF

chmod +x stop_bot.sh
print_success "Stop script created: ./stop_bot.sh"

# Create log viewer script
print_status "Creating log viewer script..."
cat > view_logs.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
tail -f bot.log
EOF

chmod +x view_logs.sh
print_success "Log viewer script created: ./view_logs.sh"

# Create backup script
print_status "Creating backup script..."
cat > backup.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/telegram-reporter-pro
python scripts/backup.py --type full
EOF

chmod +x backup.sh
print_success "Backup script created: ./backup.sh"

# Create termux-boot script (for auto-start)
print_status "Setting up auto-start (Termux:Boot)..."
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/telegram-reporter << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd ~/telegram-reporter-pro
nohup python bot.py > bot.log 2>&1 &
EOF

chmod +x ~/.termux/boot/telegram-reporter
print_success "Auto-start configured for Termux:Boot"

# Check storage space
print_status "Checking storage space..."
storage_info=$(df -h /data | tail -1)
echo -e "${BLUE}Storage: $storage_info${NC}"

# Final message
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║           Installation Completed Successfully!            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}📋 Next Steps:${NC}"
echo "1. Edit configuration file: nano .env"
echo "2. Start bot: ./start_bot.sh"
echo "3. Run in background: ./start_bot_background.sh"
echo "4. View logs: ./view_logs.sh"
echo "5. Stop bot: ./stop_bot.sh"
echo "6. Create backup: ./backup.sh"
echo ""
echo -e "${YELLOW}📁 Project Directory:${NC} ~/telegram-reporter-pro"
echo -e "${YELLOW}📝 Log File:${NC} bot.log"
echo -e "${YELLOW}🔧 Configuration:${NC} .env"
echo ""
echo -e "${YELLOW}⚠️  Important:${NC}"
echo "- Edit .env file with your API_ID, API_HASH, BOT_TOKEN"
echo "- Add your Telegram user ID to ADMIN_IDS"
echo "- Change ENCRYPTION_KEY to a secure random string"
echo ""
echo -e "${GREEN}✅ Installation complete!${NC}"

# Ask to edit configuration
read -p "Do you want to edit the configuration file now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    nano .env
fi

# Ask to start bot
read -p "Do you want to start the bot now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./start_bot.sh
fi