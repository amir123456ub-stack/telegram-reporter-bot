#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Mass Reporting Bot - Version 3.0
Professional Edition for Termux
Developer: Senior Python Developer
Lines: ~3200
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import random
import string
import hashlib
import json
import time
from pathlib import Path

# Third-party imports
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
)
from pyrogram.enums import ParseMode, ChatType, ChatMemberStatus
from pyrogram.errors import (
    FloodWait, BadRequest, Unauthorized, SessionPasswordNeeded,
    PhoneCodeInvalid, PhoneCodeExpired, UserNotParticipant
)
import aiosqlite
from cryptography.fernet import Fernet
import aiohttp
from dotenv import load_dotenv

# Local imports
from config_manager import ConfigManager
from session_manager import SessionManager
from report_engine import ReportEngine
from anti_detection import AntiDetectionSystem
from connection_pool import ConnectionPool
from scheduler import ReportScheduler
from admin_panel import AdminPanel
from database import DatabaseManager
from telethon_clients import TelethonManager

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramReporterBot:
    def __init__(self):
        """Initialize the main bot instance"""
        self.config = ConfigManager()
        self.db = DatabaseManager()
        self.session_manager = SessionManager(self.config)
        self.anti_detection = AntiDetectionSystem()
        self.connection_pool = ConnectionPool(self.config, self.session_manager)
        self.report_engine = ReportEngine(self.connection_pool, self.anti_detection)
        self.scheduler = ReportScheduler(self.report_engine)
        self.admin_panel = AdminPanel(self.db, self.config)
        self.telethon_manager = TelethonManager(self.config)
        
        # Bot clients
        self.bot_client = None
        self.user_clients = {}
        
        # State management
        self.user_states = {}
        self.temp_data = {}
        self.active_reports = {}
        
        # Statistics
        self.stats = {
            "total_reports": 0,
            "successful_reports": 0,
            "failed_reports": 0,
            "active_users": 0,
            "active_accounts": 0
        }
        
        # Initialize database
        self._init_database()
        
    def _init_database(self):
        """Initialize database tables"""
        async def init():
            await self.db.init_tables()
        asyncio.run(init())
    
    async def start_bot(self):
        """Start the bot"""
        try:
            # Initialize bot client
            self.bot_client = Client(
                name="report_bot",
                api_id=self.config.API_ID,
                api_hash=self.config.API_HASH,
                bot_token=self.config.BOT_TOKEN,
                in_memory=True
            )
            
            # Register handlers
            self._register_handlers()
            
            # Start connection pool
            await self.connection_pool.initialize()
            
            # Start scheduler
            await self.scheduler.start()
            
            # Start bot
            await self.bot_client.start()
            logger.info("✅ Bot started successfully")
            
            # Send startup message to admin
            await self._notify_admin("🤖 ربات گزارش‌گیری با موفقیت راه‌اندازی شد")
            
            # Run idle
            await idle()
            
        except Exception as e:
            logger.error(f"❌ Failed to start bot: {e}")
            sys.exit(1)
    
    def _register_handlers(self):
        """Register all message handlers"""
        
        # Start command
        @self.bot_client.on_message(filters.command("start"))
        async def start_handler(client: Client, message: Message):
            await self.handle_start(message)
        
        # Main menu
        @self.bot_client.on_message(filters.regex("^📋 منوی اصلی$"))
        async def main_menu_handler(client: Client, message: Message):
            await self.show_main_menu(message)
        
        # Report handlers
        @self.bot_client.on_message(filters.regex("^📢 گزارش کانال$"))
        async def channel_report_handler(client: Client, message: Message):
            await self.start_channel_report(message)
        
        @self.bot_client.on_message(filters.regex("^👥 گزارش گروه$"))
        async def group_report_handler(client: Client, message: Message):
            await self.start_group_report(message)
        
        @self.bot_client.on_message(filters.regex("^📝 گزارش پست$"))
        async def post_report_handler(client: Client, message: Message):
            await self.start_post_report(message)
        
        @self.bot_client.on_message(filters.regex("^👤 گزارش کاربر$"))
        async def user_report_handler(client: Client, message: Message):
            await self.start_user_report(message)
        
        # Other handlers
        @self.bot_client.on_message(filters.regex("^📊 آمار$"))
        async def stats_handler(client: Client, message: Message):
            await self.show_stats(message)
        
        @self.bot_client.on_message(filters.regex("^🔧 مدیریت حساب$"))
        async def account_manager_handler(client: Client, message: Message):
            await self.show_account_manager(message)
        
        @self.bot_client.on_message(filters.regex("^⚙️ پنل ادمین$"))
        async def admin_panel_handler(client: Client, message: Message):
            await self.show_admin_panel(message)
        
        # Callback handlers
        @self.bot_client.on_callback_query()
        async def callback_handler(client: Client, callback_query: CallbackQuery):
            await self.handle_callback(callback_query)
        
        # Text message handler
        @self.bot_client.on_message(filters.text & ~filters.command)
        async def text_message_handler(client: Client, message: Message):
            await self.handle_text_message(message)
        
        # Admin commands
        @self.bot_client.on_message(filters.command("admin") & filters.user(self.config.ADMIN_IDS))
        async def admin_command_handler(client: Client, message: Message):
            await self.handle_admin_command(message)
    
    async def handle_start(self, message: Message):
        """Handle /start command"""
        user_id = message.from_user.id
        
        # Check if user is banned
        if await self.db.is_user_banned(user_id):
            await message.reply("⛔ شما از استفاده از ربات مسدود شده‌اید.")
            return
        
        # Register or update user
        await self.db.register_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        # Check subscription
        has_sub = await self.db.check_subscription(user_id)
        
        if has_sub:
            # Show main menu
            await self.show_main_menu(message)
        else:
            # Show subscription required
            await self.show_subscription_required(message)
    
    async def show_main_menu(self, message: Message):
        """Show main menu with buttons"""
        keyboard = ReplyKeyboardMarkup(
            [
                ["📢 گزارش کانال", "👥 گزارش گروه"],
                ["📝 گزارش پست", "👤 گزارش کاربر"],
                ["👁️ مشاهده + گزارش", "⏰ گزارش زمان‌بندی"],
                ["➕ عضویت+گزارش", "🔗 گزارش از فوروارد"],
                ["⚠️ گزارش NotoScam", "📜 تاریخچه گزارش"],
                ["🔧 مدیریت حساب", "📊 آمار"],
                ["⚙️ پنل ادمین"]
            ],
            resize_keyboard=True,
            selective=True
        )
        
        await message.reply(
            "🎛️ **منوی اصلی ربات گزارش‌گیری**\n\n"
            "لطفا گزینه مورد نظر را انتخاب کنید:",
            reply_markup=keyboard
        )
    
    async def start_channel_report(self, message: Message):
        """Start channel reporting process"""
        user_id = message.from_user.id
        
        # Check subscription
        if not await self.db.check_subscription(user_id):
            await self.show_subscription_required(message)
            return
        
        # Check rate limit
        if not await self.db.check_rate_limit(user_id):
            await message.reply(
                "⚠️ شما به محدودیت گزارش در ساعت رسیده‌اید.\n"
                "لطفا 1 ساعت دیگر تلاش کنید."
            )
            return
        
        # Set user state
        self.user_states[user_id] = {
            "state": "awaiting_channel_link",
            "type": "channel",
            "step": 1
        }
        
        await message.reply(
            "📤 لطفا لینک کانال را ارسال کنید:\n\n"
            "مثال:\n"
            "• https://t.me/channel_name\n"
            "• @channel_name\n"
            "• t.me/channel_name"
        )
    
    async def handle_text_message(self, message: Message):
        """Handle text messages based on user state"""
        user_id = message.from_user.id
        
        if user_id not in self.user_states:
            return
        
        state_data = self.user_states[user_id]
        state = state_data.get("state")
        
        if state == "awaiting_channel_link":
            await self.process_channel_link(message, state_data)
        elif state == "awaiting_group_link":
            await self.process_group_link(message, state_data)
        elif state == "awaiting_post_link":
            await self.process_post_link(message, state_data)
        elif state == "awaiting_username":
            await self.process_username(message, state_data)
        elif state == "awaiting_reason":
            await self.process_reason(message, state_data)
        elif state == "awaiting_account_count":
            await self.process_account_count(message, state_data)
        elif state == "awaiting_custom_reason":
            await self.process_custom_reason(message, state_data)
    
    async def process_channel_link(self, message: Message, state_data: dict):
        """Process channel link input"""
        user_id = message.from_user.id
        link = message.text.strip()
        
        # Validate link
        if not await self._validate_telegram_link(link, "channel"):
            await message.reply(
                "❌ لینک نامعتبر است.\n"
                "لطفا یک لینک معتبر کانال تلگرام ارسال کنید."
            )
            return
        
        # Store target
        self.temp_data[user_id] = {
            "target": link,
            "type": "channel",
            "start_time": datetime.now()
        }
        
        # Update state
        self.user_states[user_id]["state"] = "awaiting_reason"
        
        # Show reason selection
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("خشونت", callback_data="reason_violence"),
                InlineKeyboardButton("سوء استفاده کودک", callback_data="reason_child_abuse")
            ],
            [
                InlineKeyboardButton("پورنوگرافی", callback_data="reason_porn"),
                InlineKeyboardButton("مواد مخدر", callback_data="reason_drugs")
            ],
            [
                InlineKeyboardButton("اطلاعات شخصی", callback_data="reason_personal_info"),
                InlineKeyboardButton("اسپم", callback_data="reason_spam")
            ],
            [
                InlineKeyboardButton("کلاهبرداری", callback_data="reason_scam"),
                InlineKeyboardButton("اکانت جعلی", callback_data="reason_fake")
            ],
            [
                InlineKeyboardButton("کپی رایت", callback_data="reason_copyright"),
                InlineKeyboardButton("دیگر", callback_data="reason_other")
            ]
        ])
        
        await message.reply(
            "📝 **دلیل گزارش را انتخاب کنید:**",
            reply_markup=keyboard
        )
    
    async def handle_callback(self, callback_query: CallbackQuery):
        """Handle callback queries"""
        user_id = callback_query.from_user.id
        data = callback_query.data
        
        if data.startswith("reason_"):
            await self.handle_reason_selection(callback_query, data)
        elif data.startswith("confirm_report_"):
            await self.handle_report_confirmation(callback_query, data)
        elif data.startswith("cancel_report_"):
            await self.handle_report_cancellation(callback_query, data)
        elif data.startswith("admin_"):
            await self.admin_panel.handle_callback(callback_query, data)
        
        await callback_query.answer()
    
    async def handle_reason_selection(self, callback_query: CallbackQuery, data: str):
        """Handle reason selection"""
        user_id = callback_query.from_user.id
        reason_map = {
            "reason_violence": "خشونت",
            "reason_child_abuse": "سوء استفاده کودک",
            "reason_porn": "پورنوگرافی",
            "reason_drugs": "مواد مخدر",
            "reason_personal_info": "اطلاعات شخصی",
            "reason_spam": "اسپم",
            "reason_scam": "کلاهبرداری",
            "reason_fake": "اکانت جعلی",
            "reason_copyright": "کپی رایت",
            "reason_other": "دیگر"
        }
        
        reason = reason_map.get(data)
        
        if not reason:
            await callback_query.message.edit_text("❌ دلیل نامعتبر")
            return
        
        # Store reason
        if user_id in self.temp_data:
            self.temp_data[user_id]["reason"] = reason
        
        # If "other" selected, ask for custom text
        if data == "reason_other":
            self.user_states[user_id] = {
                "state": "awaiting_custom_reason",
                "type": self.temp_data[user_id]["type"]
            }
            
            await callback_query.message.edit_text(
                "📝 لطفا دلیل گزارش را به صورت متن وارد کنید:"
            )
        else:
            # Show account count selection
            await self.show_account_selection(callback_query.message, user_id)
    
    async def show_account_selection(self, message: Message, user_id: int):
        """Show account count selection"""
        # Get available accounts
        available_accounts = await self.connection_pool.get_available_accounts_count()
        
        # Create keyboard with account options
        buttons = []
        row = []
        
        # Suggested counts: 1, 3, 5, 10, max/2, max
        suggestions = [1, 3, 5, 10]
        if available_accounts > 20:
            suggestions.append(available_accounts // 2)
            suggestions.append(available_accounts)
        
        suggestions = sorted(set(suggestions))
        
        for count in suggestions:
            if count <= available_accounts:
                row.append(InlineKeyboardButton(str(count), callback_data=f"acc_{count}"))
                if len(row) == 3:
                    buttons.append(row)
                    row = []
        
        if row:
            buttons.append(row)
        
        # Add custom input button
        buttons.append([InlineKeyboardButton("✏️ تعداد دلخواه", callback_data="acc_custom")])
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        await message.edit_text(
            f"👥 **انتخاب تعداد حساب‌ها**\n\n"
            f"حساب‌های فعال: {available_accounts}\n"
            f"لطفا تعداد حساب‌ها برای گزارش را انتخاب کنید:",
            reply_markup=keyboard
        )
    
    async def process_account_count(self, message: Message, state_data: dict):
        """Process account count input"""
        user_id = message.from_user.id
        
        try:
            count = int(message.text.strip())
            
            # Validate count
            available = await self.connection_pool.get_available_accounts_count()
            max_allowed = min(available, 50)  # Max 50 accounts per report
            
            if count < 1:
                await message.reply("❌ تعداد باید حداقل 1 باشد.")
                return
            
            if count > max_allowed:
                await message.reply(f"❌ حداکثر تعداد مجاز: {max_allowed}")
                return
            
            # Store count
            if user_id in self.temp_data:
                self.temp_data[user_id]["account_count"] = count
            
            # Show confirmation
            await self.show_report_confirmation(message, user_id)
            
        except ValueError:
            await message.reply("❌ لطفا یک عدد معتبر وارد کنید.")
    
    async def show_report_confirmation(self, message: Message, user_id: int):
        """Show report confirmation"""
        if user_id not in self.temp_data:
            await message.reply("❌ اطلاعات گزارش یافت نشد.")
            return
        
        data = self.temp_data[user_id]
        
        text = (
            f"✅ **تأیید نهایی گزارش**\n\n"
            f"🔗 هدف: `{data['target']}`\n"
            f"📁 نوع: {data['type']}\n"
            f"📝 دلیل: {data.get('reason', 'ندارد')}\n"
            f"👥 تعداد حساب: {data.get('account_count', 1)}\n\n"
            f"آیا می‌خواهید گزارش را شروع کنید؟"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ بله، شروع کن", 
                                   callback_data=f"confirm_report_{user_id}"),
                InlineKeyboardButton("❌ خیر، انصراف", 
                                   callback_data=f"cancel_report_{user_id}")
            ]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def handle_report_confirmation(self, callback_query: CallbackQuery, data: str):
        """Handle report confirmation"""
        user_id = int(data.split("_")[-1])
        
        if user_id not in self.temp_data:
            await callback_query.message.edit_text("❌ اطلاعات گزارش یافت نشد.")
            return
        
        # Start reporting process
        await self.start_reporting_process(callback_query.message, user_id)
    
    async def start_reporting_process(self, message: Message, user_id: int):
        """Start the actual reporting process"""
        data = self.temp_data.get(user_id)
        
        if not data:
            await message.edit_text("❌ اطلاعات گزارش یافت نشد.")
            return
        
        # Update message
        await message.edit_text(
            f"🚀 **شروع فرآیند گزارش‌گیری**\n\n"
            f"در حال آماده‌سازی {data['account_count']} حساب...\n"
            f"لطفا صبر کنید..."
        )
        
        try:
            # Start report
            report_id = await self.report_engine.start_report(
                user_id=user_id,
                target=data['target'],
                target_type=data['type'],
                reason=data.get('reason', ''),
                account_count=data['account_count']
            )
            
            # Store report ID
            self.active_reports[user_id] = report_id
            
            # Start progress updates
            asyncio.create_task(self.update_report_progress(message, report_id, user_id))
            
        except Exception as e:
            logger.error(f"Report failed: {e}")
            await message.edit_text(f"❌ خطا در شروع گزارش: {str(e)}")
    
    async def update_report_progress(self, message: Message, report_id: int, user_id: int):
        """Update report progress in real-time"""
        try:
            last_progress = 0
            
            while True:
                # Get report status
                status = await self.report_engine.get_report_status(report_id)
                
                if status["status"] in ["completed", "failed"]:
                    # Final update
                    success = status.get("successful", 0)
                    failed = status.get("failed", 0)
                    total = status.get("total", 0)
                    elapsed = status.get("elapsed", 0)
                    
                    elapsed_str = str(timedelta(seconds=int(elapsed)))
                    
                    text = (
                        f"🏁 **گزارش تکمیل شد**\n\n"
                        f"✅ موفق: {success}\n"
                        f"❌ ناموفق: {failed}\n"
                        f"📊 مجموع: {total}\n"
                        f"⏱ زمان: {elapsed_str}\n\n"
                        f"🆔 کد گزارش: `REP-{report_id:06d}`"
                    )
                    
                    await message.edit_text(text)
                    
                    # Cleanup
                    if user_id in self.temp_data:
                        del self.temp_data[user_id]
                    if user_id in self.user_states:
                        del self.user_states[user_id]
                    
                    break
                
                else:
                    # In progress
                    progress = status.get("progress", 0)
                    current = status.get("current", 0)
                    total = status.get("total", 0)
                    
                    if progress != last_progress:
                        # Create progress bar
                        bar_length = 20
                        filled = int(bar_length * progress / 100)
                        bar = "█" * filled + "░" * (bar_length - filled)
                        
                        text = (
                            f"📊 **در حال گزارش‌گیری**\n\n"
                            f"پیشرفت: {progress}%\n"
                            f"[{bar}]\n"
                            f"حساب‌های انجام شده: {current}/{total}\n"
                            f"⏳ لطفا صبر کنید..."
                        )
                        
                        await message.edit_text(text)
                        last_progress = progress
                
                await asyncio.sleep(2)  # Update every 2 seconds
                
        except Exception as e:
            logger.error(f"Progress update error: {e}")
            await message.edit_text(f"❌ خطا در بروزرسانی وضعیت: {str(e)}")
    
    async def show_subscription_required(self, message: Message):
        """Show subscription required message"""
        user_id = message.from_user.id
        admin_username = await self._get_admin_username()
        
        text = (
            "⚠️ **نیاز به اشتراک دارید**\n\n"
            f"برای استفاده از ربات، لطفا با ادمین تماس بگیرید:\n"
            f"@{admin_username}\n\n"
            f"🆔 کد کاربری شما: `{user_id}`\n\n"
            "پس از خرید اشتراک، ادمین دسترسی شما را فعال خواهد کرد."
        )
        
        await message.reply(text)
    
    async def _get_admin_username(self) -> str:
        """Get admin username"""
        try:
            admin_id = self.config.ADMIN_IDS[0]
            user = await self.bot_client.get_users(admin_id)
            return user.username or "admin"
        except:
            return "admin"
    
    async def _validate_telegram_link(self, link: str, expected_type: str) -> bool:
        """Validate Telegram link"""
        # Remove protocol
        link = link.replace("https://", "").replace("http://", "")
        
        # Check formats
        patterns = {
            "channel": ["t.me/", "@"],
            "group": ["t.me/", "@", "+"],
            "user": ["t.me/", "@"],
            "post": ["t.me/c/", "t.me/"]
        }
        
        for pattern in patterns.get(expected_type, []):
            if pattern in link:
                return True
        
        return False
    
    async def _notify_admin(self, message: str):
        """Notify admin"""
        for admin_id in self.config.ADMIN_IDS:
            try:
                await self.bot_client.send_message(admin_id, message)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

async def main():
    """Main entry point"""
    bot = TelegramReporterBot()
    await bot.start_bot()

if __name__ == "__main__":
    # Termux optimization
    if sys.platform == "linux":
        # Reduce memory usage
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (150 * 1024 * 1024, -1))
    
    # Run bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        sys.exit(1)