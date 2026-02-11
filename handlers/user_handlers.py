#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User Handlers - Handle user commands and messages
Lines: ~400
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode

from config_manager import get_config
from database import DatabaseManager
from utils.validators import validate_telegram_link, validate_phone_number, validate_account_count
from utils.helpers import extract_username, format_number, time_ago, truncate_text

logger = logging.getLogger(__name__)

class UserHandlers:
    """Handle user-related commands and interactions"""
    
    def __init__(self, bot_client: Client, db: DatabaseManager):
        self.bot = bot_client
        self.db = db
        self.config = get_config()
        
        # User states for multi-step operations
        self.user_states: Dict[int, Dict] = {}
        
        # Register handlers
        self._register_handlers()
        
        logger.info("User handlers initialized")
    
    def _register_handlers(self):
        """Register user message handlers"""
        
        @self.bot.on_message(filters.command("start"))
        async def start_handler(client: Client, message: Message):
            await self.handle_start(message)
        
        @self.bot.on_message(filters.command("help"))
        async def help_handler(client: Client, message: Message):
            await self.handle_help(message)
        
        @self.bot.on_message(filters.command("profile"))
        async def profile_handler(client: Client, message: Message):
            await self.handle_profile(message)
        
        @self.bot.on_message(filters.command("subscription"))
        async def subscription_handler(client: Client, message: Message):
            await self.handle_subscription(message)
        
        @self.bot.on_message(filters.regex("^📋 منوی اصلی$"))
        async def main_menu_handler(client: Client, message: Message):
            await self.show_main_menu(message)
        
        @self.bot.on_message(filters.regex("^📊 آمار من$"))
        async def my_stats_handler(client: Client, message: Message):
            await self.show_user_stats(message)
        
        @self.bot.on_message(filters.regex("^📜 تاریخچه گزارش$"))
        async def history_handler(client: Client, message: Message):
            await self.show_report_history(message)
        
        @self.bot.on_message(filters.regex("^⚙️ تنظیمات$"))
        async def settings_handler(client: Client, message: Message):
            await self.show_settings(message)
        
        @self.bot.on_message(filters.regex("^📞 پشتیبانی$"))
        async def support_handler(client: Client, message: Message):
            await self.handle_support(message)
    
    async def handle_start(self, message: Message):
        """Handle /start command"""
        user_id = message.from_user.id
        
        # Check if user is banned
        if await self.db.is_user_banned(user_id):
            await message.reply(
                "⛔ **شما از دسترسی به ربات مسدود شده‌اید.**\n\n"
                "در صورت نیاز به پشتیبانی با ادمین تماس بگیرید."
            )
            return
        
        # Register/update user
        await self.db.register_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        # Check subscription
        has_sub = await self.db.check_subscription(user_id)
        
        # Welcome message
        welcome_text = (
            f"👋 **خوش آمدید {message.from_user.first_name}!**\n\n"
            "🤖 این ربات برای گزارش‌گیری حرفه‌ای از محتوای تلگرام طراحی شده است.\n\n"
            "📌 **امکانات ربات:**\n"
            "• گزارش کانال، گروه، کاربر و پست\n"
            "• گزارش زمان‌بندی شده\n"
            "• گزارش با چندین حساب همزمان\n"
            "• عضویت خودکار و گزارش\n"
            "• مشاهده و گزارش\n\n"
        )
        
        if has_sub:
            welcome_text += "✅ **اشتراک شما فعال است.**\nاز منوی اصلی استفاده کنید."
            await self.show_main_menu(message)
        else:
            welcome_text += (
                "⚠️ **شما اشتراک فعال ندارید.**\n"
                "برای خرید اشتراک با ادمین تماس بگیرید."
            )
            await self.show_subscription_required(message)
        
        await message.reply(welcome_text)
    
    async def handle_help(self, message: Message):
        """Handle /help command"""
        help_text = (
            "📚 **راهنمای استفاده از ربات**\n\n"
            
            "**🔹 گزارش‌گیری:**\n"
            "1️⃣ گزینه مورد نظر را از منوی اصلی انتخاب کنید\n"
            "2️⃣ لینک هدف را ارسال کنید\n"
            "3️⃣ دلیل گزارش را انتخاب کنید\n"
            "4️⃣ تعداد حساب‌ها را مشخص کنید\n"
            "5️⃣ گزارش شروع می‌شود\n\n"
            
            "**🔸 انواع گزارش:**\n"
            "• **کانال/گروه**: ارسال لینک یا آیدی\n"
            "• **پست**: ارسال لینک پست\n"
            "• **کاربر**: ارسال آیدی یا یوزرنیم\n"
            "• **عضویت+گزارش**: عضویت و گزارش خودکار\n"
            "• **مشاهده+گزارش**: مشاهده پست قبل از گزارش\n\n"
            
            "**🔹 محدودیت‌ها:**\n"
            "• حداکثر ۱۰ گزارش در ساعت\n"
            "• حداکثر ۵۰ حساب در هر گزارش\n"
            "• فاصله زمانی بین گزارش‌ها: ۱-۵ ثانیه\n\n"
            
            "**🔸 اشتراک:**\n"
            "• برای خرید اشتراک با @admin تماس بگیرید\n"
            "• پس از خرید، اشتراک شما فعال می‌شود\n\n"
            
            "📞 **پشتیبانی:** @support"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 منوی اصلی", callback_data="menu_main")],
            [InlineKeyboardButton("📞 تماس با پشتیبانی", url="https://t.me/support")]
        ])
        
        await message.reply(help_text, reply_markup=keyboard)
    
    async def handle_profile(self, message: Message):
        """Show user profile"""
        user_id = message.from_user.id
        user_data = await self.db.get_user(user_id)
        
        if not user_data:
            await message.reply("❌ اطلاعات کاربری یافت نشد.")
            return
        
        # Get subscription info
        sub_info = await self.db.get_subscription_info(user_id)
        
        # Format dates
        created_at = user_data.get('created_at', datetime.now())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        last_active = user_data.get('last_active', datetime.now())
        if isinstance(last_active, str):
            last_active = datetime.fromisoformat(last_active.replace('Z', '+00:00'))
        
        profile_text = (
            f"👤 **پروفایل کاربری**\n\n"
            f"🆔 آیدی: `{user_id}`\n"
            f"👤 نام: {user_data.get('first_name', '')} {user_data.get('last_name', '')}\n"
            f"📱 یوزرنیم: @{user_data.get('username', 'ندارد')}\n\n"
            
            f"💳 **وضعیت اشتراک:**\n"
        )
        
        if sub_info.get('has_active_subscription'):
            end_date = sub_info.get('subscription_end')
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            
            days_left = (end_date - datetime.now()).days
            
            profile_text += (
                f"✅ فعال\n"
                f"📅 تاریخ انقضا: {end_date.strftime('%Y-%m-%d')}\n"
                f"⏳ روزهای باقی‌مانده: {days_left}\n"
            )
        else:
            profile_text += "❌ اشتراک فعال ندارد\n"
        
        profile_text += (
            f"\n📊 **آمار:**\n"
            f"• کل گزارش‌ها: {format_number(user_data.get('total_reports', 0))}\n"
            f"• گزارش‌های امروز: {format_number(user_data.get('reports_today', 0))}\n"
            f"• تاریخ ثبت‌نام: {created_at.strftime('%Y-%m-%d')}\n"
            f"• آخرین فعالیت: {time_ago(last_active)}\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 منوی اصلی", callback_data="menu_main")]
        ])
        
        await message.reply(profile_text, reply_markup=keyboard)
    
    async def handle_subscription(self, message: Message):
        """Handle subscription command"""
        user_id = message.from_user.id
        sub_info = await self.db.get_subscription_info(user_id)
        
        text = "💳 **وضعیت اشتراک**\n\n"
        
        if sub_info.get('has_active_subscription'):
            end_date = sub_info.get('subscription_end')
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            
            days_left = (end_date - datetime.now()).days
            
            text += (
                f"✅ اشتراک شما فعال است\n\n"
                f"📅 تاریخ انقضا: {end_date.strftime('%Y-%m-%d')}\n"
                f"⏳ روزهای باقی‌مانده: {days_left}\n"
            )
        else:
            text += (
                "❌ شما اشتراک فعال ندارید\n\n"
                "برای خرید اشتراک با ادمین تماس بگیرید:\n"
                "🆔 @admin"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 تماس با ادمین", url="https://t.me/admin")],
            [InlineKeyboardButton("📋 منوی اصلی", callback_data="menu_main")]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def show_main_menu(self, message: Message):
        """Show main menu with buttons"""
        user_id = message.from_user.id
        has_sub = await self.db.check_subscription(user_id)
        
        if not has_sub:
            await self.show_subscription_required(message)
            return
        
        # Persian keyboard layout
        keyboard = [
            ["📢 گزارش کانال", "👥 گزارش گروه"],
            ["📝 گزارش پست", "👤 گزارش کاربر"],
            ["👁️ مشاهده + گزارش", "➕ عضویت+گزارش"],
            ["⏰ گزارش زمان‌بندی", "🔗 گزارش از فوروارد"],
            ["⚠️ گزارش NotoScam", "📜 تاریخچه گزارش"],
            ["🔧 مدیریت حساب", "📊 آمار من"],
            ["⚙️ تنظیمات", "📞 پشتیبانی"]
        ]
        
        await message.reply(
            "🎛️ **منوی اصلی**\n\n"
            "لطفا گزینه مورد نظر را انتخاب کنید:",
            reply_markup=keyboard
        )
    
    async def show_subscription_required(self, message: Message):
        """Show subscription required message"""
        user_id = message.from_user.id
        
        text = (
            "⚠️ **نیاز به اشتراک فعال**\n\n"
            "برای استفاده از امکانات ربات، باید اشتراک تهیه کنید.\n\n"
            f"🆔 آیدی شما: `{user_id}`\n\n"
            "📌 **مراحل خرید:**\n"
            "1️⃣ با ادمین تماس بگیرید\n"
            "2️⃣ آیدی خود را ارسال کنید\n"
            "3️⃣ پس از پرداخت، اشتراک فعال می‌شود\n\n"
            "👤 ادمین: @admin"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 تماس با ادمین", url="https://t.me/admin")],
            [InlineKeyboardButton("🔄 بررسی مجدد", callback_data="check_subscription")]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def show_user_stats(self, message: Message):
        """Show user statistics"""
        user_id = message.from_user.id
        
        # Get user reports
        reports = await self.db.get_user_reports(user_id, limit=100)
        
        # Calculate stats
        total_reports = len(reports)
        successful = sum(1 for r in reports if r.get('status') == 'completed')
        failed = sum(1 for r in reports if r.get('status') == 'failed')
        
        # Group by target type
        target_types = {}
        for report in reports:
            ttype = report.get('target_type', 'unknown')
            target_types[ttype] = target_types.get(ttype, 0) + 1
        
        text = (
            f"📊 **آمار گزارش‌های شما**\n\n"
            f"📈 **گزارش‌های کل:** {format_number(total_reports)}\n"
            f"✅ موفق: {format_number(successful)}\n"
            f"❌ ناموفق: {format_number(failed)}\n"
            f"📊 نرخ موفقیت: {((successful/total_reports)*100) if total_reports > 0 else 0:.1f}%\n\n"
            
            f"📁 **توزیع بر اساس نوع:**\n"
        )
        
        for ttype, count in target_types.items():
            persian_type = {
                'channel': 'کانال',
                'group': 'گروه',
                'user': 'کاربر',
                'post': 'پست'
            }.get(ttype, ttype)
            
            text += f"• {persian_type}: {count}\n"
        
        # Add daily average
        if total_reports > 0:
            first_report = reports[-1]
            created_at = first_report.get('created_at')
            if created_at:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                
                days_active = max(1, (datetime.now() - created_at).days)
                daily_avg = total_reports / days_active
                text += f"\n📅 میانگین روزانه: {daily_avg:.1f} گزارش"
        
        await message.reply(text)
    
    async def show_report_history(self, message: Message):
        """Show user's report history"""
        user_id = message.from_user.id
        reports = await self.db.get_user_reports(user_id, limit=20)
        
        if not reports:
            await message.reply("📜 شما هنوز گزارشی ثبت نکرده‌اید.")
            return
        
        text = "📜 **آخرین گزارش‌های شما**\n\n"
        
        for i, report in enumerate(reports[:10], 1):
            created_at = report.get('created_at')
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            date_str = created_at.strftime('%Y-%m-%d %H:%M')
            target = truncate_text(report.get('target', ''), 30)
            status = report.get('status', 'unknown')
            
            status_icon = {
                'completed': '✅',
                'failed': '❌',
                'pending': '⏳',
                'processing': '🔄'
            }.get(status, '❓')
            
            text += (
                f"{i}. {status_icon} `{target}`\n"
                f"   🕐 {date_str}\n"
                f"   📊 {report.get('successful_reports', 0)}/{report.get('accounts_used', 0)}\n"
            )
        
        if len(reports) > 10:
            text += f"\n... و {len(reports) - 10} گزارش دیگر"
        
        await message.reply(text)
    
    async def show_settings(self, message: Message):
        """Show user settings"""
        user_id = message.from_user.id
        user_data = await self.db.get_user(user_id)
        
        language = user_data.get('language_code', 'fa')
        
        text = (
            "⚙️ **تنظیمات کاربری**\n\n"
            f"🌐 زبان: { 'فارسی' if language == 'fa' else 'English' }\n"
            "🔔 اعلان‌ها: فعال\n\n"
            "⚡ **تنظیمات گزارش:**\n"
            "• تأخیر تصادفی: فعال\n"
            "• مشاهده قبل از گزارش: فعال\n"
            "• گزارش خودکار: غیرفعال\n\n"
            "⚠️ تنظیمات پیشرفته در حال توسعه است."
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_main")]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def handle_support(self, message: Message):
        """Handle support request"""
        text = (
            "📞 **پشتیبانی**\n\n"
            "برای ارتباط با تیم پشتیبانی می‌توانید از روش‌های زیر استفاده کنید:\n\n"
            "👤 **ادمین:** @admin\n"
            "👥 **گروه پشتیبانی:** @support_group\n"
            "📧 **ایمیل:** support@example.com\n\n"
            "⏰ **ساعات پاسخگویی:** ۹ صبح تا ۱۲ شب\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👤 ادمین", url="https://t.me/admin"),
                InlineKeyboardButton("👥 گروه", url="https://t.me/support_group")
            ],
            [InlineKeyboardButton("📋 منوی اصلی", callback_data="menu_main")]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def clear_user_state(self, user_id: int):
        """Clear user state"""
        if user_id in self.user_states:
            del self.user_states[user_id]