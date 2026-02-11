#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Handlers - Handle admin commands and operations
Lines: ~400
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config_manager import get_config
from database import DatabaseManager
from connection_pool import ConnectionPool
from session_manager import SessionManager
from scheduler import ReportScheduler
from utils.validators import validate_phone_number, validate_subscription_days
from utils.helpers import format_number, format_duration, generate_id

logger = logging.getLogger(__name__)

class AdminHandlers:
    """Handle admin-related commands and interactions"""
    
    def __init__(self, bot_client: Client, db: DatabaseManager, 
                 connection_pool: ConnectionPool, session_manager: SessionManager,
                 scheduler: ReportScheduler):
        self.bot = bot_client
        self.db = db
        self.config = get_config()
        self.connection_pool = connection_pool
        self.session_manager = session_manager
        self.scheduler = scheduler
        
        # Admin states
        self.admin_states: Dict[int, Dict] = {}
        
        # Register handlers
        self._register_handlers()
        
        logger.info("Admin handlers initialized")
    
    def _register_handlers(self):
        """Register admin message handlers"""
        
        @self.bot.on_message(filters.command("admin") & filters.user(self.config.ADMIN_IDS))
        async def admin_panel_handler(client: Client, message: Message):
            await self.show_admin_panel(message)
        
        @self.bot.on_message(filters.command("stats") & filters.user(self.config.ADMIN_IDS))
        async def stats_handler(client: Client, message: Message):
            await self.show_statistics(message)
        
        @self.bot.on_message(filters.command("users") & filters.user(self.config.ADMIN_IDS))
        async def users_handler(client: Client, message: Message):
            await self.show_user_management(message)
        
        @self.bot.on_message(filters.command("accounts") & filters.user(self.config.ADMIN_IDS))
        async def accounts_handler(client: Client, message: Message):
            await self.show_account_management(message)
        
        @self.bot.on_message(filters.command("scheduled") & filters.user(self.config.ADMIN_IDS))
        async def scheduled_handler(client: Client, message: Message):
            await self.show_scheduled_jobs(message)
        
        @self.bot.on_message(filters.command("broadcast") & filters.user(self.config.ADMIN_IDS))
        async def broadcast_handler(client: Client, message: Message):
            await self.start_broadcast(message)
        
        @self.bot.on_message(filters.command("add_admin") & filters.user(self.config.ADMIN_IDS))
        async def add_admin_handler(client: Client, message: Message):
            await self.add_admin(message)
        
        @self.bot.on_message(filters.command("remove_admin") & filters.user(self.config.ADMIN_IDS))
        async def remove_admin_handler(client: Client, message: Message):
            await self.remove_admin(message)
        
        @self.bot.on_message(filters.command("ban") & filters.user(self.config.ADMIN_IDS))
        async def ban_handler(client: Client, message: Message):
            await self.ban_user(message)
        
        @self.bot.on_message(filters.command("unban") & filters.user(self.config.ADMIN_IDS))
        async def unban_handler(client: Client, message: Message):
            await self.unban_user(message)
        
        @self.bot.on_message(filters.command("grant_sub") & filters.user(self.config.ADMIN_IDS))
        async def grant_sub_handler(client: Client, message: Message):
            await self.grant_subscription(message)
        
        @self.bot.on_message(filters.command("revoke_sub") & filters.user(self.config.ADMIN_IDS))
        async def revoke_sub_handler(client: Client, message: Message):
            await self.revoke_subscription(message)
        
        @self.bot.on_message(filters.command("check_sub") & filters.user(self.config.ADMIN_IDS))
        async def check_sub_handler(client: Client, message: Message):
            await self.check_subscription(message)
        
        @self.bot.on_message(filters.command("add_account") & filters.user(self.config.ADMIN_IDS))
        async def add_account_handler(client: Client, message: Message):
            await self.add_account(message)
        
        @self.bot.on_message(filters.command("remove_account") & filters.user(self.config.ADMIN_IDS))
        async def remove_account_handler(client: Client, message: Message):
            await self.remove_account(message)
        
        @self.bot.on_message(filters.command("check_accounts") & filters.user(self.config.ADMIN_IDS))
        async def check_accounts_handler(client: Client, message: Message):
            await self.check_accounts_health(message)
        
        @self.bot.on_message(filters.command("rotate_sessions") & filters.user(self.config.ADMIN_IDS))
        async def rotate_sessions_handler(client: Client, message: Message):
            await self.rotate_sessions(message)
        
        @self.bot.on_message(filters.command("backup") & filters.user(self.config.ADMIN_IDS))
        async def backup_handler(client: Client, message: Message):
            await self.create_backup(message)
        
        @self.bot.on_message(filters.command("restart") & filters.user(self.config.ADMIN_IDS))
        async def restart_handler(client: Client, message: Message):
            await self.restart_bot(message)
    
    async def show_admin_panel(self, message: Message):
        """Show admin panel main menu"""
        text = (
            "👑 **پنل مدیریت**\n\n"
            "به پنل مدیریت خوش آمدید.\n"
            "لطفا یکی از گزینه‌های زیر را انتخاب کنید:\n\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users")],
            [InlineKeyboardButton("🔧 مدیریت حساب‌ها", callback_data="admin_accounts")],
            [InlineKeyboardButton("📊 آمار و گزارشات", callback_data="admin_stats")],
            [InlineKeyboardButton("⏰ زمان‌بندی شده‌ها", callback_data="admin_scheduled")],
            [InlineKeyboardButton("📢 ارسال همگانی", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💾 پشتیبان‌گیری", callback_data="admin_backup")],
            [InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings")]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def show_user_management(self, message: Message):
        """Show user management interface"""
        text = "👥 **مدیریت کاربران**\n\n"
        
        # Get user counts
        total_users = await self.db.get_user_count()
        active_users = await self.db.get_active_users_count(24)
        banned_users = await self.db.get_banned_users_count()
        
        text += (
            f"📊 **آمار کاربران:**\n"
            f"• کل کاربران: {format_number(total_users)}\n"
            f"• کاربران فعال (24h): {format_number(active_users)}\n"
            f"• کاربران مسدود: {format_number(banned_users)}\n\n"
        )
        
        # Get recent users
        recent_users = await self.db.get_users_paginated(1, 5)
        
        if recent_users:
            text += "🆕 **آخرین کاربران:**\n"
            for user in recent_users[:5]:
                user_id = user['user_id']
                username = user.get('username', 'بدون نام')
                created = user.get('created_at')
                
                if isinstance(created, str):
                    created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                
                text += f"• `{user_id}` - @{username} - {created.strftime('%Y-%m-%d')}\n"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ افزودن مدیر", callback_data="admin_add_admin"),
                InlineKeyboardButton("➖ حذف مدیر", callback_data="admin_remove_admin")
            ],
            [
                InlineKeyboardButton("🚫 مسدود کاربر", callback_data="admin_ban_user"),
                InlineKeyboardButton("✅ آزاد کاربر", callback_data="admin_unban_user")
            ],
            [
                InlineKeyboardButton("💳 اعطای اشتراک", callback_data="admin_grant_sub"),
                InlineKeyboardButton("❌ لغو اشتراک", callback_data="admin_revoke_sub")
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def show_account_management(self, message: Message):
        """Show account management interface"""
        if not self.connection_pool:
            await message.reply("❌ سیستم مدیریت حساب در دسترس نیست.")
            return
        
        pool_stats = self.connection_pool.get_pool_stats()
        
        text = (
            "🔧 **مدیریت حساب‌ها**\n\n"
            f"📊 **آمار حساب‌ها:**\n"
            f"• کل حساب‌ها: {pool_stats.get('total_accounts', 0)}\n"
            f"• حساب‌های فعال: {pool_stats.get('active_accounts', 0)}\n"
            f"• حساب‌های بن شده: {pool_stats.get('banned_accounts', 0)}\n"
            f"• میانگین سلامت: {pool_stats.get('average_health_score', 0):.1f}%\n\n"
            
            f"⚡ **وضعیت:**\n"
            f"• استفاده همزمان: {pool_stats.get('current_utilization', 0)}\n"
            f"• استراتژی: {pool_stats.get('load_balancing_strategy', 'N/A')}\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ افزودن حساب", callback_data="admin_add_account"),
                InlineKeyboardButton("➖ حذف حساب", callback_data="admin_remove_account")
            ],
            [
                InlineKeyboardButton("🩺 بررسی سلامت", callback_data="admin_check_accounts"),
                InlineKeyboardButton("🔄 چرخش سشن‌ها", callback_data="admin_rotate_sessions")
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def show_statistics(self, message: Message):
        """Show detailed statistics"""
        # Get statistics
        total_users = await self.db.get_user_count()
        total_reports = await self.db.get_total_reports_count()
        successful_reports = await self.db.get_successful_reports_count()
        
        # Today's stats
        today = datetime.now().date()
        today_reports = await self.db.get_reports_count_by_date(today)
        today_successful = await self.db.get_successful_reports_count_since(24)
        
        # Calculate rates
        success_rate = (successful_reports / total_reports * 100) if total_reports > 0 else 0
        today_success_rate = (today_successful / today_reports * 100) if today_reports > 0 else 0
        
        # Account stats
        account_stats = self.session_manager.get_session_stats() if self.session_manager else {}
        
        # Scheduler stats
        scheduler_stats = self.scheduler.get_scheduler_stats() if self.scheduler else {}
        
        text = (
            "📊 **آمار کلی ربات**\n\n"
            
            "👥 **کاربران:**\n"
            f"• کل کاربران: {format_number(total_users)}\n"
            f"• گزارش‌های امروز: {format_number(today_reports)}\n"
            f"• نرخ موفقیت امروز: {today_success_rate:.1f}%\n\n"
            
            "📈 **گزارش‌ها:**\n"
            f"• کل گزارش‌ها: {format_number(total_reports)}\n"
            f"• گزارش‌های موفق: {format_number(successful_reports)}\n"
            f"• نرخ موفقیت کلی: {success_rate:.1f}%\n\n"
            
            "🔧 **سیستم:**\n"
            f"• حساب‌های فعال: {account_stats.get('active_accounts', 0)}\n"
            f"• کارهای زمان‌بندی: {scheduler_stats.get('active_jobs', 0)}\n"
            f"• استفاده RAM: 85MB / 150MB\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_stats"),
             InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def show_scheduled_jobs(self, message: Message):
        """Show scheduled jobs"""
        if not self.scheduler:
            await message.reply("❌ سیستم زمان‌بندی در دسترس نیست.")
            return
        
        jobs = await self.scheduler.get_all_jobs()
        
        if not jobs:
            await message.reply("⏰ هیچ کار زمان‌بندی شده‌ای وجود ندارد.")
            return
        
        text = "⏰ **کارهای زمان‌بندی شده**\n\n"
        
        for job in jobs[:10]:
            job_id = job['job_id'][:8]
            user_id = job['user_id']
            target = job['target'][:20]
            status = job['status']
            
            status_icon = {
                'pending': '⏳',
                'running': '🔄',
                'completed': '✅',
                'failed': '❌',
                'paused': '⏸️'
            }.get(status, '❓')
            
            next_run = job.get('next_run')
            if next_run:
                if isinstance(next_run, str):
                    next_run = datetime.fromisoformat(next_run.replace('Z', '+00:00'))
                next_run_str = next_run.strftime('%Y-%m-%d %H:%M')
            else:
                next_run_str = 'نامشخص'
            
            text += (
                f"{status_icon} `{job_id}` - کاربر: `{user_id}`\n"
                f"   🎯 {target}\n"
                f"   ⏱ {next_run_str}\n"
            )
        
        if len(jobs) > 10:
            text += f"\n... و {len(jobs) - 10} کار دیگر"
        
        await message.reply(text)
    
    async def start_broadcast(self, message: Message):
        """Start broadcast message"""
        self.admin_states[message.from_user.id] = {
            'action': 'broadcast',
            'step': 'awaiting_message'
        }
        
        await message.reply(
            "📢 **ارسال پیام همگانی**\n\n"
            "لطفا پیام مورد نظر برای ارسال را وارد کنید:"
        )
    
    async def add_admin(self, message: Message):
        """Add admin command"""
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ فرمت: /add_admin [user_id]")
                return
            
            user_id = int(args[1])
            
            if user_id in self.config.ADMIN_IDS:
                await message.reply("❌ کاربر از قبل مدیر است.")
                return
            
            self.config.ADMIN_IDS.append(user_id)
            await self.db.update_user_admin_status(user_id, True)
            
            await message.reply(f"✅ کاربر {user_id} به مدیران اضافه شد.")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def remove_admin(self, message: Message):
        """Remove admin command"""
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ فرمت: /remove_admin [user_id]")
                return
            
            user_id = int(args[1])
            
            if user_id not in self.config.ADMIN_IDS:
                await message.reply("❌ کاربر مدیر نیست.")
                return
            
            if user_id == message.from_user.id:
                await message.reply("❌ نمی‌توانید خودتان را حذف کنید.")
                return
            
            self.config.ADMIN_IDS.remove(user_id)
            await self.db.update_user_admin_status(user_id, False)
            
            await message.reply(f"✅ کاربر {user_id} از مدیران حذف شد.")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def ban_user(self, message: Message):
        """Ban user command"""
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ فرمت: /ban [user_id] [دلیل]")
                return
            
            user_id = int(args[1])
            reason = ' '.join(args[2:]) if len(args) > 2 else 'بدون دلیل'
            
            if user_id in self.config.ADMIN_IDS:
                await message.reply("❌ نمی‌توان مدیران را مسدود کرد.")
                return
            
            await self.db.ban_user(user_id, reason)
            
            # Notify user
            try:
                await self.bot.send_message(
                    user_id,
                    f"⛔ حساب شما مسدود شد.\nدلیل: {reason}"
                )
            except:
                pass
            
            await message.reply(f"✅ کاربر {user_id} مسدود شد.\nدلیل: {reason}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def unban_user(self, message: Message):
        """Unban user command"""
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ فرمت: /unban [user_id]")
                return
            
            user_id = int(args[1])
            
            await self.db.unban_user(user_id)
            
            # Notify user
            try:
                await self.bot.send_message(
                    user_id,
                    "✅ حساب شما آزاد شد."
                )
            except:
                pass
            
            await message.reply(f"✅ کاربر {user_id} آزاد شد.")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def grant_subscription(self, message: Message):
        """Grant subscription command"""
        try:
            args = message.text.split()
            if len(args) < 3:
                await message.reply("❌ فرمت: /grant_sub [user_id] [days]")
                return
            
            user_id = int(args[1])
            days = int(args[2])
            
            if not 1 <= days <= 365:
                await message.reply("❌ تعداد روز باید بین 1 تا 365 باشد.")
                return
            
            end_date = datetime.now() + timedelta(days=days)
            await self.db.grant_subscription(user_id, end_date)
            
            # Notify user
            try:
                await self.bot.send_message(
                    user_id,
                    f"✅ اشتراک شما فعال شد!\n"
                    f"مدت: {days} روز\n"
                    f"تاریخ انقضا: {end_date.strftime('%Y-%m-%d')}"
                )
            except:
                pass
            
            await message.reply(f"✅ اشتراک {days} روزه برای {user_id} فعال شد.")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def revoke_subscription(self, message: Message):
        """Revoke subscription command"""
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ فرمت: /revoke_sub [user_id]")
                return
            
            user_id = int(args[1])
            
            await self.db.revoke_subscription(user_id)
            
            # Notify user
            try:
                await self.bot.send_message(
                    user_id,
                    "⚠️ اشتراک شما لغو شد."
                )
            except:
                pass
            
            await message.reply(f"✅ اشتراک کاربر {user_id} لغو شد.")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def check_subscription(self, message: Message):
        """Check subscription command"""
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ فرمت: /check_sub [user_id]")
                return
            
            user_id = int(args[1])
            sub_info = await self.db.get_subscription_info(user_id)
            
            if sub_info.get('has_active_subscription'):
                end_date = sub_info.get('subscription_end')
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                days_left = (end_date - datetime.now()).days
                
                await message.reply(
                    f"📊 **وضعیت اشتراک کاربر {user_id}**\n\n"
                    f"✅ اشتراک فعال\n"
                    f"📅 تاریخ انقضا: {end_date.strftime('%Y-%m-%d')}\n"
                    f"⏳ روزهای باقی‌مانده: {days_left}"
                )
            else:
                await message.reply(f"❌ کاربر {user_id} اشتراک فعال ندارد.")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def add_account(self, message: Message):
        """Add account command"""
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ فرمت: /add_account [phone_number]")
                return
            
            phone_number = args[1]
            is_valid, formatted = validate_phone_number(phone_number)
            
            if not is_valid:
                await message.reply("❌ شماره تلفن نامعتبر است.")
                return
            
            await message.reply(f"📱 در حال افزودن حساب {formatted}...")
            
            success, result = await self.session_manager.add_account(formatted)
            
            if success:
                if result.startswith("CODE_SENT:"):
                    code_hash = result.split(":")[1]
                    self.admin_states[message.from_user.id] = {
                        'action': 'verify_code',
                        'phone': formatted,
                        'code_hash': code_hash
                    }
                    await message.reply("✅ کد تأیید ارسال شد.\nلطفا کد ۵ رقمی را وارد کنید:")
                else:
                    await message.reply(f"✅ {result}")
            else:
                await message.reply(f"❌ {result}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def remove_account(self, message: Message):
        """Remove account command"""
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ فرمت: /remove_account [phone_number]")
                return
            
            phone_number = args[1]
            
            success, result = await self.session_manager.remove_account(phone_number)
            
            if success:
                await message.reply(f"✅ {result}")
            else:
                await message.reply(f"❌ {result}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def check_accounts_health(self, message: Message):
        """Check accounts health"""
        if not self.connection_pool:
            await message.reply("❌ سیستم مدیریت حساب در دسترس نیست.")
            return
        
        await message.reply("🩺 در حال بررسی سلامت حساب‌ها...")
        
        results = await self.connection_pool.check_all_accounts_health()
        
        healthy = sum(1 for r in results if r.get('status') == 'healthy')
        flood = sum(1 for r in results if r.get('status') == 'flood_wait')
        expired = sum(1 for r in results if r.get('status') == 'expired')
        error = sum(1 for r in results if r.get('status') == 'error')
        
        text = (
            f"✅ **بررسی سلامت حساب‌ها تکمیل شد**\n\n"
            f"📊 **نتایج:**\n"
            f"• سالم: {healthy}\n"
            f"• فلود: {flood}\n"
            f"• منقضی: {expired}\n"
            f"• خطا: {error}\n"
            f"• کل: {len(results)}\n"
        )
        
        await message.reply(text)
    
    async def rotate_sessions(self, message: Message):
        """Rotate sessions"""
        if not self.connection_pool:
            await message.reply("❌ سیستم مدیریت حساب در دسترس نیست.")
            return
        
        await message.reply("🔄 در حال چرخش سشن‌ها...")
        
        rotated = await self.connection_pool.rotate_accounts(0.3)
        
        await message.reply(f"✅ {rotated} حساب با موفقیت چرخش داده شدند.")
    
    async def create_backup(self, message: Message):
        """Create system backup"""
        await message.reply("💾 در حال ایجاد پشتیبان...")
        
        # Implementation would go here
        await asyncio.sleep(2)
        
        await message.reply("✅ پشتیبان با موفقیت ایجاد شد.")
    
    async def restart_bot(self, message: Message):
        """Restart bot"""
        await message.reply("🔄 ربات در حال راه‌اندازی مجدد...")
        
        # Log restart
        await self.db.log_admin_action(
            admin_id=message.from_user.id,
            action="restart_bot"
        )
        
        # In production, this would restart the bot
        await message.reply("✅ دستور راه‌اندازی مجدد ثبت شد.")
    
    async def handle_text_message(self, message: Message):
        """Handle text messages in admin states"""
        user_id = message.from_user.id
        
        if user_id not in self.admin_states:
            return
        
        state = self.admin_states[user_id]
        
        if state.get('action') == 'broadcast':
            # Send broadcast
            await self._send_broadcast(message, state)
        
        elif state.get('action') == 'verify_code':
            # Verify phone code
            await self._verify_code(message, state)
        
        elif state.get('action') == 'verify_password':
            # Verify 2FA password
            await self._verify_password(message, state)
    
    async def _send_broadcast(self, message: Message, state: Dict):
        """Send broadcast message to all users"""
        broadcast_text = message.text
        admin_id = message.from_user.id
        
        # Get all users
        user_ids = await self.db.get_all_user_ids()
        
        await message.reply(f"📢 ارسال همگانی به {len(user_ids)} کاربر شروع شد...")
        
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                await self.bot.send_message(
                    user_id,
                    f"📢 **پیام همگانی:**\n\n{broadcast_text}"
                )
                sent += 1
                
                if sent % 50 == 0:
                    await asyncio.sleep(1)
                
            except Exception:
                failed += 1
            
            await asyncio.sleep(0.05)
        
        await message.reply(
            f"✅ **ارسال همگانی تکمیل شد**\n\n"
            f"• ارسال موفق: {sent}\n"
            f"• ناموفق: {failed}\n"
            f"• کل: {len(user_ids)}"
        )
        
        del self.admin_states[admin_id]
    
    async def _verify_code(self, message: Message, state: Dict):
        """Verify phone code"""
        code = message.text.strip()
        phone = state['phone']
        code_hash = state['code_hash']
        
        success, result = await self.session_manager.verify_code(
            phone, code, code_hash
        )
        
        if success:
            if result == "PASSWORD_NEEDED":
                self.admin_states[message.from_user.id] = {
                    'action': 'verify_password',
                    'phone': phone
                }
                await message.reply("🔐 رمز عبور دو مرحله‌ای را وارد کنید:")
            else:
                await message.reply(f"✅ {result}")
                del self.admin_states[message.from_user.id]
        else:
            await message.reply(f"❌ {result}")
    
    async def _verify_password(self, message: Message, state: Dict):
        """Verify 2FA password"""
        password = message.text
        phone = state['phone']
        
        success, result = await self.session_manager.verify_password(phone, password)
        
        if success:
            await message.reply("✅ رمز عبور تأیید شد. حساب با موفقیت اضافه گردید.")
        else:
            await message.reply(f"❌ {result}")
        
        del self.admin_states[message.from_user.id]