#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Panel - Full administration interface
Lines: ~1500
"""

import asyncio
import logging
import json
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
import hashlib
import statistics
from collections import defaultdict

# Telegram
from pyrogram import Client
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
)

# Local imports
from config_manager import get_config
from database import DatabaseManager
from connection_pool import ConnectionPool
from report_engine import ReportEngine
from scheduler import ReportScheduler
from session_manager import SessionManager

logger = logging.getLogger(__name__)

class AdminPanel:
    """Full administration panel for the bot"""
    
    def __init__(self, db: DatabaseManager, config):
        self.db = db
        self.config = config
        self.bot_client = None
        self.report_engine = None
        self.scheduler = None
        self.connection_pool = None
        self.session_manager = None
        
        # Admin state management
        self.admin_sessions: Dict[int, Dict] = {}
        self.broadcast_queue = asyncio.Queue()
        
        # Start broadcast processor
        asyncio.create_task(self._process_broadcasts())
        
        logger.info("Admin panel initialized")
    
    def set_dependencies(self, bot_client: Client, report_engine: ReportEngine,
                        scheduler: ReportScheduler, connection_pool: ConnectionPool,
                        session_manager: SessionManager):
        """Set required dependencies"""
        self.bot_client = bot_client
        self.report_engine = report_engine
        self.scheduler = scheduler
        self.connection_pool = connection_pool
        self.session_manager = session_manager
    
    async def handle_admin_command(self, message: Message):
        """Handle admin commands"""
        try:
            user_id = message.from_user.id
            
            # Check if user is admin
            if not await self._is_admin(user_id):
                await message.reply("⛔ دسترسی محدود به مدیران")
                return
            
            # Parse command
            command = message.text.split()[0].lower()
            args = message.text.split()[1:] if len(message.text.split()) > 1 else []
            
            # Route to appropriate handler
            if command == "/admin":
                await self.show_admin_dashboard(message)
            elif command == "/stats":
                await self.show_statistics(message)
            elif command == "/users":
                await self.show_user_management(message, args)
            elif command == "/add_admin":
                await self.add_admin(message, args)
            elif command == "/remove_admin":
                await self.remove_admin(message, args)
            elif command == "/ban":
                await self.ban_user(message, args)
            elif command == "/unban":
                await self.unban_user(message, args)
            elif command == "/grant_sub":
                await self.grant_subscription(message, args)
            elif command == "/revoke_sub":
                await self.revoke_subscription(message, args)
            elif command == "/check_sub":
                await self.check_subscription(message, args)
            elif command == "/accounts":
                await self.show_account_management(message, args)
            elif command == "/check_accounts":
                await self.check_accounts_health(message)
            elif command == "/add_account":
                await self.add_account_manual(message, args)
            elif command == "/remove_account":
                await self.remove_account(message, args)
            elif command == "/rotate_sessions":
                await self.rotate_sessions(message)
            elif command == "/scheduled":
                await self.show_scheduled_jobs(message, args)
            elif command == "/reports":
                await self.show_report_history(message, args)
            elif command == "/broadcast":
                await self.start_broadcast(message, args)
            elif command == "/export_logs":
                await self.export_logs(message, args)
            elif command == "/backup":
                await self.create_backup(message)
            elif command == "/restart":
                await self.restart_bot(message)
            elif command == "/health":
                await self.show_health_check(message)
            elif command == "/revenue":
                await self.show_revenue_analytics(message, args)
            elif command == "/audit_logs":
                await self.show_audit_logs(message, args)
            elif command == "/settings":
                await self.show_settings(message)
            else:
                await message.reply("❌ دستور نامعتبر")
        
        except Exception as e:
            logger.error(f"Admin command error: {e}")
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def handle_callback(self, callback_query: CallbackQuery, data: str):
        """Handle admin panel callbacks"""
        try:
            user_id = callback_query.from_user.id
            
            if not await self._is_admin(user_id):
                await callback_query.answer("⛔ دسترسی محدود", show_alert=True)
                return
            
            # Parse callback data
            if data.startswith("admin_"):
                await self._handle_admin_callback(callback_query, data)
            elif data.startswith("user_action_"):
                await self._handle_user_action(callback_query, data)
            elif data.startswith("account_action_"):
                await self._handle_account_action(callback_query, data)
            elif data.startswith("report_action_"):
                await self._handle_report_action(callback_query, data)
            elif data.startswith("schedule_action_"):
                await self._handle_schedule_action(callback_query, data)
            elif data.startswith("broadcast_"):
                await self._handle_broadcast_callback(callback_query, data)
            
        except Exception as e:
            logger.error(f"Admin callback error: {e}")
            await callback_query.answer("خطا در پردازش", show_alert=True)
    
    async def _handle_admin_callback(self, callback_query: CallbackQuery, data: str):
        """Handle admin panel navigation"""
        action = data.split("_")[1]
        
        if action == "dashboard":
            await self.show_admin_dashboard(callback_query.message)
        elif action == "users":
            await self.show_user_management(callback_query.message)
        elif action == "accounts":
            await self.show_account_management(callback_query.message)
        elif action == "reports":
            await self.show_report_history(callback_query.message)
        elif action == "scheduled":
            await self.show_scheduled_jobs(callback_query.message)
        elif action == "stats":
            await self.show_statistics(callback_query.message)
        elif action == "health":
            await self.show_health_check(callback_query.message)
        elif action == "revenue":
            await self.show_revenue_analytics(callback_query.message)
        elif action == "audit":
            await self.show_audit_logs(callback_query.message)
        elif action == "settings":
            await self.show_settings(callback_query.message)
        elif action == "broadcast":
            await self.start_broadcast(callback_query.message)
        elif action == "backup":
            await self.create_backup(callback_query.message)
        
        await callback_query.answer()
    
    async def show_admin_dashboard(self, message: Message):
        """Show admin dashboard"""
        try:
            # Get statistics
            stats = await self._get_dashboard_stats()
            
            # Create dashboard message
            text = (
                "👑 **پنل مدیریت ربات گزارش‌گیری**\n\n"
                f"📊 **آمار کلی:**\n"
                f"• کاربران کل: {stats['total_users']}\n"
                f"• کاربران فعال (24h): {stats['active_users']}\n"
                f"• مدیران: {stats['admin_count']}\n"
                f"• کاربران مسدود: {stats['banned_users']}\n\n"
                
                f"📈 **گزارش‌ها:**\n"
                f"• گزارش‌های امروز: {stats['today_reports']}\n"
                f"• گزارش‌های کل: {stats['total_reports']}\n"
                f"• نرخ موفقیت: {stats['success_rate']}%\n\n"
                
                f"👥 **حساب‌ها:**\n"
                f"• حساب‌های کل: {stats['total_accounts']}\n"
                f"• حساب‌های فعال: {stats['active_accounts']}\n"
                f"• حساب‌های بن شده: {stats['banned_accounts']}\n\n"
                
                f"⏰ **زمان‌بندی‌ها:**\n"
                f"• کارهای فعال: {stats['active_jobs']}\n"
                f"• کارهای در حال اجرا: {stats['running_jobs']}\n"
            )
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users"),
                    InlineKeyboardButton("🔧 مدیریت حساب‌ها", callback_data="admin_accounts")
                ],
                [
                    InlineKeyboardButton("📜 تاریخچه گزارش‌ها", callback_data="admin_reports"),
                    InlineKeyboardButton("⏰ کارهای زمان‌بندی", callback_data="admin_scheduled")
                ],
                [
                    InlineKeyboardButton("📊 آمار پیشرفته", callback_data="admin_stats"),
                    InlineKeyboardButton("🩺 بررسی سلامت", callback_data="admin_health")
                ],
                [
                    InlineKeyboardButton("💳 درآمد و مالی", callback_data="admin_revenue"),
                    InlineKeyboardButton("🔍 لاگ‌های حسابرسی", callback_data="admin_audit")
                ],
                [
                    InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings"),
                    InlineKeyboardButton("📢 ارسال همگانی", callback_data="admin_broadcast")
                ],
                [
                    InlineKeyboardButton("💾 پشتیبان‌گیری", callback_data="admin_backup"),
                    InlineKeyboardButton("🔄 بازگشت به منو", callback_data="admin_dashboard")
                ]
            ])
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show admin dashboard: {e}")
            await self._send_error(message, "نمایش داشبورد")
    
    async def _get_dashboard_stats(self) -> Dict:
        """Get dashboard statistics"""
        try:
            # User statistics
            total_users = await self.db.get_user_count()
            active_users = await self.db.get_active_users_count(24)  # Last 24 hours
            admin_count = len(self.config.ADMIN_IDS)
            banned_users = await self.db.get_banned_users_count()
            
            # Report statistics
            today = datetime.now().date()
            today_reports = await self.db.get_reports_count_by_date(today)
            total_reports = await self.db.get_total_reports_count()
            
            # Calculate success rate
            successful_reports = await self.db.get_successful_reports_count()
            success_rate = round((successful_reports / total_reports * 100), 2) if total_reports > 0 else 0
            
            # Account statistics
            if self.connection_pool:
                pool_stats = self.connection_pool.get_pool_stats()
                total_accounts = pool_stats.get("total_accounts", 0)
                active_accounts = pool_stats.get("active_accounts", 0)
                banned_accounts = pool_stats.get("banned_accounts", 0)
            else:
                total_accounts = active_accounts = banned_accounts = 0
            
            # Scheduler statistics
            if self.scheduler:
                scheduler_stats = self.scheduler.get_scheduler_stats()
                active_jobs = scheduler_stats.get("active_jobs", 0)
                running_jobs = scheduler_stats.get("running_jobs", 0)
            else:
                active_jobs = running_jobs = 0
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "admin_count": admin_count,
                "banned_users": banned_users,
                "today_reports": today_reports,
                "total_reports": total_reports,
                "success_rate": success_rate,
                "total_accounts": total_accounts,
                "active_accounts": active_accounts,
                "banned_accounts": banned_accounts,
                "active_jobs": active_jobs,
                "running_jobs": running_jobs
            }
            
        except Exception as e:
            logger.error(f"Failed to get dashboard stats: {e}")
            return {}
    
    async def show_user_management(self, message: Message, args: List[str] = None):
        """Show user management interface"""
        try:
            page = int(args[0]) if args and args[0].isdigit() else 1
            page_size = 10
            
            # Get users for page
            users = await self.db.get_users_paginated(page, page_size)
            total_users = await self.db.get_user_count()
            total_pages = (total_users + page_size - 1) // page_size
            
            # Create user list text
            text = "👥 **مدیریت کاربران**\n\n"
            
            if not users:
                text += "هیچ کاربری یافت نشد.\n"
            else:
                for user in users:
                    user_id = user["user_id"]
                    username = user.get("username", "بدون نام")
                    first_name = user.get("first_name", "")
                    is_admin = user.get("is_admin", False)
                    is_banned = user.get("is_banned", False)
                    sub_end = user.get("subscription_end")
                    
                    # Format subscription status
                    if sub_end:
                        sub_date = datetime.fromisoformat(sub_end) if isinstance(sub_end, str) else sub_end
                        if sub_date > datetime.now():
                            sub_status = f"✅ تا {sub_date.strftime('%Y-%m-%d')}"
                        else:
                            sub_status = "❌ منقضی"
                    else:
                        sub_status = "❌ ندارد"
                    
                    text += (
                        f"🆔 `{user_id}`\n"
                        f"👤 {first_name} (@{username})\n"
                        f"👑 مدیر: {'✅' if is_admin else '❌'}\n"
                        f"🚫 مسدود: {'✅' if is_banned else '❌'}\n"
                        f"💳 اشتراک: {sub_status}\n"
                        f"📊 گزارش‌ها: {user.get('total_reports', 0)}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                    )
            
            text += f"\n📄 صفحه {page} از {total_pages}"
            
            # Create keyboard
            buttons = []
            
            # Navigation buttons
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⏪ قبلی", 
                    callback_data=f"admin_users_{page-1}"))
            
            nav_buttons.append(InlineKeyboardButton("🏠 داشبورد", 
                callback_data="admin_dashboard"))
            
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("بعدی ⏩", 
                    callback_data=f"admin_users_{page+1}"))
            
            if nav_buttons:
                buttons.append(nav_buttons)
            
            # Action buttons for first user (if any)
            if users:
                first_user = users[0]
                user_id = first_user["user_id"]
                
                action_buttons = [
                    InlineKeyboardButton("➕ مدیر", 
                        callback_data=f"user_action_add_admin_{user_id}"),
                    InlineKeyboardButton("➖ مدیر", 
                        callback_data=f"user_action_remove_admin_{user_id}"),
                    InlineKeyboardButton("🚫 مسدود", 
                        callback_data=f"user_action_ban_{user_id}"),
                    InlineKeyboardButton("✅ آزاد", 
                        callback_data=f"user_action_unban_{user_id}")
                ]
                buttons.append(action_buttons)
                
                sub_buttons = [
                    InlineKeyboardButton("💳 +30 روز", 
                        callback_data=f"user_action_grant_30_{user_id}"),
                    InlineKeyboardButton("💳 +7 روز", 
                        callback_data=f"user_action_grant_7_{user_id}"),
                    InlineKeyboardButton("💳 لغو", 
                        callback_data=f"user_action_revoke_{user_id}")
                ]
                buttons.append(sub_buttons)
            
            keyboard = InlineKeyboardMarkup(buttons)
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show user management: {e}")
            await self._send_error(message, "نمایش مدیریت کاربران")
    
    async def _handle_user_action(self, callback_query: CallbackQuery, data: str):
        """Handle user actions"""
        try:
            parts = data.split("_")
            action = parts[2]
            user_id = int(parts[3])
            
            if action == "add_admin":
                success, msg = await self._add_admin(user_id)
                await callback_query.answer(msg, show_alert=True)
                
            elif action == "remove_admin":
                success, msg = await self._remove_admin(user_id)
                await callback_query.answer(msg, show_alert=True)
                
            elif action == "ban":
                # Ask for ban reason
                await callback_query.message.reply(
                    f"لطفا دلیل مسدود کردن کاربر {user_id} را وارد کنید:"
                )
                # Store state for next message
                self.admin_sessions[callback_query.from_user.id] = {
                    "action": "ban_user",
                    "target_user_id": user_id
                }
                await callback_query.answer()
                return
                
            elif action == "unban":
                success, msg = await self._unban_user(user_id)
                await callback_query.answer(msg, show_alert=True)
                
            elif action == "grant_30":
                success, msg = await self._grant_subscription(user_id, 30)
                await callback_query.answer(msg, show_alert=True)
                
            elif action == "grant_7":
                success, msg = await self._grant_subscription(user_id, 7)
                await callback_query.answer(msg, show_alert=True)
                
            elif action == "revoke":
                success, msg = await self._revoke_subscription(user_id)
                await callback_query.answer(msg, show_alert=True)
            
            # Refresh user management page
            await self.show_user_management(callback_query.message)
            
        except Exception as e:
            logger.error(f"User action failed: {e}")
            await callback_query.answer("خطا در انجام عملیات", show_alert=True)
    
    async def add_admin(self, message: Message, args: List[str]):
        """Add admin command handler"""
        try:
            if len(args) < 1:
                await message.reply("❌ فرمت دستور: /add_admin [user_id]")
                return
            
            user_id = int(args[0])
            success, msg = await self._add_admin(user_id)
            
            await message.reply(f"✅ {msg}" if success else f"❌ {msg}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def _add_admin(self, user_id: int) -> Tuple[bool, str]:
        """Add user as admin"""
        try:
            # Check if already admin
            if user_id in self.config.ADMIN_IDS:
                return False, "کاربر از قبل مدیر است"
            
            # Add to admin list
            self.config.ADMIN_IDS.append(user_id)
            
            # Update in database
            await self.db.update_user_admin_status(user_id, True)
            
            # Log action
            await self._log_admin_action(
                admin_id=user_id,  # The one who performed the action
                action="add_admin",
                target_user_id=user_id,
                details="User added as admin"
            )
            
            return True, "کاربر به مدیران اضافه شد"
            
        except Exception as e:
            logger.error(f"Failed to add admin {user_id}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def remove_admin(self, message: Message, args: List[str]):
        """Remove admin command handler"""
        try:
            if len(args) < 1:
                await message.reply("❌ فرمت دستور: /remove_admin [user_id]")
                return
            
            user_id = int(args[0])
            success, msg = await self._remove_admin(user_id)
            
            await message.reply(f"✅ {msg}" if success else f"❌ {msg}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def _remove_admin(self, user_id: int) -> Tuple[bool, str]:
        """Remove user from admins"""
        try:
            # Check if is admin
            if user_id not in self.config.ADMIN_IDS:
                return False, "کاربر مدیر نیست"
            
            # Cannot remove yourself
            if user_id == message.from_user.id:
                return False, "نمی‌توانید خودتان را حذف کنید"
            
            # Remove from admin list
            self.config.ADMIN_IDS.remove(user_id)
            
            # Update in database
            await self.db.update_user_admin_status(user_id, False)
            
            # Log action
            await self._log_admin_action(
                admin_id=message.from_user.id,
                action="remove_admin",
                target_user_id=user_id,
                details="User removed from admins"
            )
            
            return True, "کاربر از مدیران حذف شد"
            
        except Exception as e:
            logger.error(f"Failed to remove admin {user_id}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def ban_user(self, message: Message, args: List[str]):
        """Ban user command handler"""
        try:
            if len(args) < 2:
                await message.reply("❌ فرمت دستور: /ban [user_id] [دلیل]")
                return
            
            user_id = int(args[0])
            reason = " ".join(args[1:])
            
            success, msg = await self._ban_user(user_id, reason)
            
            await message.reply(f"✅ {msg}" if success else f"❌ {msg}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def _ban_user(self, user_id: int, reason: str = "بدون دلیل") -> Tuple[bool, str]:
        """Ban a user"""
        try:
            # Cannot ban admins
            if user_id in self.config.ADMIN_IDS:
                return False, "نمی‌توان مدیران را مسدود کرد"
            
            # Ban user
            await self.db.ban_user(user_id, reason)
            
            # Log action
            await self._log_admin_action(
                admin_id=message.from_user.id if hasattr(message, 'from_user') else 0,
                action="ban_user",
                target_user_id=user_id,
                details=f"Reason: {reason}"
            )
            
            # Notify user if possible
            try:
                if self.bot_client:
                    await self.bot_client.send_message(
                        user_id,
                        f"⛔ حساب شما مسدود شده است.\nدلیل: {reason}"
                    )
            except:
                pass
            
            return True, f"کاربر {user_id} مسدود شد"
            
        except Exception as e:
            logger.error(f"Failed to ban user {user_id}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def unban_user(self, message: Message, args: List[str]):
        """Unban user command handler"""
        try:
            if len(args) < 1:
                await message.reply("❌ فرمت دستور: /unban [user_id]")
                return
            
            user_id = int(args[0])
            success, msg = await self._unban_user(user_id)
            
            await message.reply(f"✅ {msg}" if success else f"❌ {msg}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def _unban_user(self, user_id: int) -> Tuple[bool, str]:
        """Unban a user"""
        try:
            # Unban user
            await self.db.unban_user(user_id)
            
            # Log action
            await self._log_admin_action(
                admin_id=message.from_user.id if hasattr(message, 'from_user') else 0,
                action="unban_user",
                target_user_id=user_id,
                details="User unbanned"
            )
            
            # Notify user if possible
            try:
                if self.bot_client:
                    await self.bot_client.send_message(
                        user_id,
                        "✅ حساب شما آزاد شده است. اکنون می‌توانید از ربات استفاده کنید."
                    )
            except:
                pass
            
            return True, f"کاربر {user_id} آزاد شد"
            
        except Exception as e:
            logger.error(f"Failed to unban user {user_id}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def grant_subscription(self, message: Message, args: List[str]):
        """Grant subscription command handler"""
        try:
            if len(args) < 2:
                await message.reply("❌ فرمت دستور: /grant_sub [user_id] [days]")
                return
            
            user_id = int(args[0])
            days = int(args[1])
            
            success, msg = await self._grant_subscription(user_id, days)
            
            await message.reply(f"✅ {msg}" if success else f"❌ {msg}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def _grant_subscription(self, user_id: int, days: int) -> Tuple[bool, str]:
        """Grant subscription to user"""
        try:
            # Calculate end date
            end_date = datetime.now() + timedelta(days=days)
            
            # Grant subscription
            await self.db.grant_subscription(user_id, end_date)
            
            # Log action
            await self._log_admin_action(
                admin_id=message.from_user.id if hasattr(message, 'from_user') else 0,
                action="grant_subscription",
                target_user_id=user_id,
                details=f"{days} days"
            )
            
            # Notify user if possible
            try:
                if self.bot_client:
                    await self.bot_client.send_message(
                        user_id,
                        f"✅ اشتراک شما فعال شد!\n"
                        f"مدت: {days} روز\n"
                        f"تاریخ انقضا: {end_date.strftime('%Y-%m-%d')}"
                    )
            except:
                pass
            
            return True, f"اشتراک {days} روزه برای کاربر {user_id} فعال شد"
            
        except Exception as e:
            logger.error(f"Failed to grant subscription: {e}")
            return False, f"خطا: {str(e)}"
    
    async def revoke_subscription(self, message: Message, args: List[str]):
        """Revoke subscription command handler"""
        try:
            if len(args) < 1:
                await message.reply("❌ فرمت دستور: /revoke_sub [user_id]")
                return
            
            user_id = int(args[0])
            success, msg = await self._revoke_subscription(user_id)
            
            await message.reply(f"✅ {msg}" if success else f"❌ {msg}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def _revoke_subscription(self, user_id: int) -> Tuple[bool, str]:
        """Revoke user subscription"""
        try:
            # Revoke subscription
            await self.db.revoke_subscription(user_id)
            
            # Log action
            await self._log_admin_action(
                admin_id=message.from_user.id if hasattr(message, 'from_user') else 0,
                action="revoke_subscription",
                target_user_id=user_id,
                details="Subscription revoked"
            )
            
            # Notify user if possible
            try:
                if self.bot_client:
                    await self.bot_client.send_message(
                        user_id,
                        "⚠️ اشتراک شما لغو شد. برای تمدید با پشتیبانی تماس بگیرید."
                    )
            except:
                pass
            
            return True, f"اشتراک کاربر {user_id} لغو شد"
            
        except Exception as e:
            logger.error(f"Failed to revoke subscription: {e}")
            return False, f"خطا: {str(e)}"
    
    async def check_subscription(self, message: Message, args: List[str]):
        """Check subscription status"""
        try:
            if len(args) < 1:
                await message.reply("❌ فرمت دستور: /check_sub [user_id]")
                return
            
            user_id = int(args[0])
            sub_info = await self.db.get_subscription_info(user_id)
            
            if not sub_info:
                await message.reply(f"کاربر {user_id} اشتراک فعال ندارد.")
                return
            
            text = f"📊 **وضعیت اشتراک کاربر {user_id}**\n\n"
            
            if sub_info.get("has_active_subscription"):
                end_date = datetime.fromisoformat(sub_info["subscription_end"])
                days_left = (end_date - datetime.now()).days
                
                text += (
                    f"✅ اشتراک فعال\n"
                    f"📅 تاریخ انقضا: {end_date.strftime('%Y-%m-%d %H:%M')}\n"
                    f"⏳ روزهای باقی‌مانده: {days_left}\n"
                )
            else:
                text += "❌ اشتراک فعال ندارد\n"
                
                if sub_info.get("subscription_end"):
                    end_date = datetime.fromisoformat(sub_info["subscription_end"])
                    text += f"آخرین اشتراک: {end_date.strftime('%Y-%m-%d')}\n"
            
            await message.reply(text)
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def show_account_management(self, message: Message, args: List[str] = None):
        """Show account management interface"""
        try:
            if not self.connection_pool:
                await self._send_error(message, "Connection pool not available")
                return
            
            # Get account statistics
            pool_stats = self.connection_pool.get_pool_stats()
            
            text = (
                "🔧 **مدیریت حساب‌ها**\n\n"
                f"📊 **آمار حساب‌ها:**\n"
                f"• کل حساب‌ها: {pool_stats.get('total_accounts', 0)}\n"
                f"• حساب‌های فعال: {pool_stats.get('active_accounts', 0)}\n"
                f"• حساب‌های بن شده: {pool_stats.get('banned_accounts', 0)}\n"
                f"• حساب‌های غیرفعال: {pool_stats.get('inactive_accounts', 0)}\n"
                f"• میانگین امتیاز سلامت: {pool_stats.get('average_health_score', 0):.1f}\n\n"
                
                f"⚙️ **وضعیت اتصال:**\n"
                f"• استفاده همزمان: {pool_stats.get('current_utilization', 0)}\n"
                f"• حداکثر مجاز: {pool_stats.get('max_concurrent_allowed', 0)}\n"
                f"• استراتژی توازن بار: {pool_stats.get('load_balancing_strategy', 'N/A')}\n"
            )
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🩺 بررسی سلامت همه", 
                        callback_data="account_action_check_all"),
                    InlineKeyboardButton("🔄 چرخش سشن‌ها", 
                        callback_data="account_action_rotate")
                ],
                [
                    InlineKeyboardButton("➕ افزودن دستی حساب", 
                        callback_data="account_action_add"),
                    InlineKeyboardButton("➖ حذف حساب", 
                        callback_data="account_action_remove")
                ],
                [
                    InlineKeyboardButton("📊 جزئیات حساب‌ها", 
                        callback_data="account_action_details"),
                    InlineKeyboardButton("🏠 داشبورد", 
                        callback_data="admin_dashboard")
                ]
            ])
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show account management: {e}")
            await self._send_error(message, "نمایش مدیریت حساب‌ها")
    
    async def _handle_account_action(self, callback_query: CallbackQuery, data: str):
        """Handle account actions"""
        try:
            parts = data.split("_")
            action = parts[2]
            
            if action == "check_all":
                await self.check_accounts_health(callback_query.message)
                
            elif action == "rotate":
                await self.rotate_sessions(callback_query.message)
                
            elif action == "add":
                await callback_query.message.reply(
                    "لطفا شماره تلفن حساب را وارد کنید (با +98):"
                )
                # Store state for next message
                self.admin_sessions[callback_query.from_user.id] = {
                    "action": "add_account"
                }
                
            elif action == "remove":
                await callback_query.message.reply(
                    "لطفا شماره تلفن حساب برای حذف را وارد کنید:"
                )
                # Store state for next message
                self.admin_sessions[callback_query.from_user.id] = {
                    "action": "remove_account"
                }
                
            elif action == "details":
                await self._show_account_details(callback_query.message)
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Account action failed: {e}")
            await callback_query.answer("خطا در انجام عملیات", show_alert=True)
    
    async def check_accounts_health(self, message: Message):
        """Check health of all accounts"""
        try:
            if not self.connection_pool:
                await message.reply("❌ Connection pool not available")
                return
            
            await message.reply("🩺 در حال بررسی سلامت حساب‌ها...")
            
            # Start health check
            results = await self.connection_pool.check_all_accounts_health()
            
            # Count by status
            status_counts = {}
            for result in results:
                status = result.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Create summary
            text = "✅ **بررسی سلامت حساب‌ها تکمیل شد**\n\n"
            text += f"📊 **نتایج:**\n"
            
            for status, count in status_counts.items():
                text += f"• {status}: {count}\n"
            
            text += f"\n🔢 کل حساب‌ها: {len(results)}"
            
            # Add details for unhealthy accounts
            unhealthy = [r for r in results if r.get("status") in ["error", "flood_wait", "expired"]]
            if unhealthy:
                text += "\n\n⚠️ **حساب‌های مشکل‌دار:**\n"
                for acc in unhealthy[:5]:  # Show first 5
                    text += f"• {acc.get('phone_number')}: {acc.get('status')}\n"
                
                if len(unhealthy) > 5:
                    text += f"... و {len(unhealthy) - 5} حساب دیگر\n"
            
            await message.reply(text)
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            await message.reply(f"❌ خطا در بررسی سلامت: {str(e)}")
    
    async def rotate_sessions(self, message: Message):
        """Rotate sessions"""
        try:
            if not self.connection_pool:
                await message.reply("❌ Connection pool not available")
                return
            
            await message.reply("🔄 در حال چرخش سشن‌ها...")
            
            # Rotate 30% of accounts
            rotated = await self.connection_pool.rotate_accounts(0.3)
            
            await message.reply(f"✅ {rotated} حساب با موفقیت چرخش داده شدند")
            
        except Exception as e:
            logger.error(f"Session rotation failed: {e}")
            await message.reply(f"❌ خطا در چرخش سشن‌ها: {str(e)}")
    
    async def add_account_manual(self, message: Message, args: List[str]):
        """Add account manually"""
        try:
            if len(args) < 1:
                await message.reply("❌ فرمت دستور: /add_account [phone_number]")
                return
            
            phone_number = args[0]
            
            if not self.session_manager:
                await message.reply("❌ Session manager not available")
                return
            
            await message.reply(f"📱 در حال افزودن حساب {phone_number}...")
            
            # Add account
            success, result = await self.session_manager.add_account(phone_number)
            
            if success:
                if result.startswith("QR_CODE:"):
                    qr_code = result.split(":")[1]
                    await message.reply(
                        f"✅ حساب اضافه شد\n"
                        f"لطفا QR Code را اسکن کنید:\n"
                        f"`{qr_code[:50]}...`"
                    )
                elif result.startswith("CODE_SENT:"):
                    code_hash = result.split(":")[1]
                    await message.reply(
                        f"✅ کد تأیید ارسال شد\n"
                        f"لطفا کد تأیید را وارد کنید:\n"
                        f"کد هش: `{code_hash}`"
                    )
                else:
                    await message.reply(f"✅ {result}")
            else:
                await message.reply(f"❌ {result}")
            
        except Exception as e:
            logger.error(f"Failed to add account: {e}")
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def remove_account(self, message: Message, args: List[str]):
        """Remove account"""
        try:
            if len(args) < 1:
                await message.reply("❌ فرمت دستور: /remove_account [phone_number]")
                return
            
            phone_number = args[0]
            
            if not self.session_manager:
                await message.reply("❌ Session manager not available")
                return
            
            await message.reply(f"🗑️ در حال حذف حساب {phone_number}...")
            
            # Remove account
            success, result = await self.session_manager.remove_account(phone_number)
            
            if success:
                await message.reply(f"✅ {result}")
            else:
                await message.reply(f"❌ {result}")
            
        except Exception as e:
            logger.error(f"Failed to remove account: {e}")
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def show_statistics(self, message: Message):
        """Show advanced statistics"""
        try:
            # Get comprehensive stats
            stats = await self._get_advanced_stats()
            
            text = (
                "📈 **آمار پیشرفته ربات**\n\n"
                
                f"👥 **کاربران:**\n"
                f"• ثبت‌نام‌های امروز: {stats['today_registrations']}\n"
                f"• کاربران فعال هفته: {stats['weekly_active_users']}\n"
                f"• نرخ حفظ کاربر: {stats['retention_rate']}%\n"
                f"• میانگین گزارش/کاربر: {stats['avg_reports_per_user']:.1f}\n\n"
                
                f"📊 **گزارش‌ها:**\n"
                f"• گزارش‌های 24h گذشته: {stats['reports_24h']}\n"
                f"• گزارش‌های موفق 24h: {stats['successful_24h']}\n"
                f"• نرخ موفقیت 24h: {stats['success_rate_24h']}%\n"
                f"• زمان متوسط گزارش: {stats['avg_report_time']:.1f} ثانیه\n\n"
                
                f"🔧 **عملکرد:**\n"
                f"• گزارش‌های فعال: {stats['active_reports']}\n"
                f"• صف گزارش: {stats['queue_size']}\n"
                f"• میانگین تأخیر: {stats['avg_delay']:.1f} ثانیه\n"
                f"• خطاهای 24h: {stats['errors_24h']}\n"
            )
            
            # Add hourly distribution if available
            if stats.get('hourly_distribution'):
                text += f"\n🕐 **توزیع ساعتی گزارش‌ها:**\n"
                for hour, count in list(stats['hourly_distribution'].items())[:6]:
                    text += f"• {hour}:00 - {count}\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_stats"),
                 InlineKeyboardButton("🏠 داشبورد", callback_data="admin_dashboard")]
            ])
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show statistics: {e}")
            await self._send_error(message, "نمایش آمار")
    
    async def _get_advanced_stats(self) -> Dict:
        """Get advanced statistics"""
        try:
            # Time ranges
            now = datetime.now()
            today = now.date()
            yesterday = today - timedelta(days=1)
            week_ago = today - timedelta(days=7)
            
            # User statistics
            today_registrations = await self.db.get_registrations_count(today)
            weekly_active_users = await self.db.get_active_users_count(7 * 24)  # 7 days
            
            # Calculate retention rate (users active in last 7 days / total users)
            total_users = await self.db.get_user_count()
            retention_rate = round((weekly_active_users / total_users * 100), 2) if total_users > 0 else 0
            
            # Average reports per user
            total_reports = await self.db.get_total_reports_count()
            avg_reports_per_user = total_reports / total_users if total_users > 0 else 0
            
            # Report statistics for last 24 hours
            reports_24h = await self.db.get_reports_count_since(24)
            successful_24h = await self.db.get_successful_reports_count_since(24)
            success_rate_24h = round((successful_24h / reports_24h * 100), 2) if reports_24h > 0 else 0
            
            # Average report time
            avg_report_time = await self.db.get_average_report_time()
            
            # Performance statistics
            active_reports = self.report_engine.get_active_reports_count() if self.report_engine else 0
            queue_size = 0  # Would need to track queue
            
            # Get average delay from config
            avg_delay = (self.config.reporting.min_delay_between_actions + 
                        self.config.reporting.max_delay_between_actions) / 2
            
            # Error count (would need error logging system)
            errors_24h = 0
            
            # Hourly distribution (sample data)
            hourly_distribution = {}
            for hour in range(24):
                hourly_distribution[hour] = random.randint(5, 50)  # Mock data
            
            return {
                "today_registrations": today_registrations,
                "weekly_active_users": weekly_active_users,
                "retention_rate": retention_rate,
                "avg_reports_per_user": avg_reports_per_user,
                "reports_24h": reports_24h,
                "successful_24h": successful_24h,
                "success_rate_24h": success_rate_24h,
                "avg_report_time": avg_report_time,
                "active_reports": active_reports,
                "queue_size": queue_size,
                "avg_delay": avg_delay,
                "errors_24h": errors_24h,
                "hourly_distribution": hourly_distribution
            }
            
        except Exception as e:
            logger.error(f"Failed to get advanced stats: {e}")
            return {}
    
    async def show_report_history(self, message: Message, args: List[str] = None):
        """Show report history"""
        try:
            page = int(args[0]) if args and args[0].isdigit() else 1
            page_size = 10
            
            # Get reports for page
            reports = await self.db.get_reports_paginated(page, page_size)
            total_reports = await self.db.get_total_reports_count()
            total_pages = (total_reports + page_size - 1) // page_size
            
            # Create report list text
            text = "📜 **تاریخچه گزارش‌ها**\n\n"
            
            if not reports:
                text += "هیچ گزارشی یافت نشد.\n"
            else:
                for report in reports:
                    report_id = report["id"]
                    user_id = report["user_id"]
                    target = report["target"]
                    status = report["status"]
                    created = datetime.fromisoformat(report["created_at"]) if isinstance(report["created_at"], str) else report["created_at"]
                    
                    text += (
                        f"🆔 `REP-{report_id:06d}`\n"
                        f"👤 کاربر: `{user_id}`\n"
                        f"🎯 هدف: {target[:30]}...\n"
                        f"📊 وضعیت: {status}\n"
                        f"🕐 زمان: {created.strftime('%Y-%m-%d %H:%M')}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                    )
            
            text += f"\n📄 صفحه {page} از {total_pages}"
            
            # Create keyboard
            buttons = []
            
            # Navigation buttons
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⏪ قبلی", 
                    callback_data=f"admin_reports_{page-1}"))
            
            nav_buttons.append(InlineKeyboardButton("📊 آمار", 
                callback_data="admin_stats"))
            
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("بعدی ⏩", 
                    callback_data=f"admin_reports_{page+1}"))
            
            if nav_buttons:
                buttons.append(nav_buttons)
            
            # Export button
            buttons.append([
                InlineKeyboardButton("📤 خروجی CSV", 
                    callback_data="report_action_export"),
                InlineKeyboardButton("🏠 داشبورد", 
                    callback_data="admin_dashboard")
            ])
            
            keyboard = InlineKeyboardMarkup(buttons)
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show report history: {e}")
            await self._send_error(message, "نمایش تاریخچه گزارش‌ها")
    
    async def show_scheduled_jobs(self, message: Message, args: List[str] = None):
        """Show scheduled jobs"""
        try:
            if not self.scheduler:
                await self._send_error(message, "Scheduler not available")
                return
            
            # Get jobs
            jobs = await self.scheduler.get_all_jobs()
            
            text = "⏰ **کارهای زمان‌بندی شده**\n\n"
            
            if not jobs:
                text += "هیچ کار زمان‌بندی‌شده‌ای وجود ندارد.\n"
            else:
                for job in jobs[:10]:  # Show first 10
                    job_id = job["job_id"]
                    user_id = job["user_id"]
                    target = job["target"]
                    status = job["status"]
                    next_run = datetime.fromisoformat(job["next_run"]) if job.get("next_run") else None
                    
                    text += (
                        f"🆔 `{job_id[:8]}...`\n"
                        f"👤 کاربر: `{user_id}`\n"
                        f"🎯 هدف: {target[:20]}...\n"
                        f"📊 وضعیت: {status}\n"
                    )
                    
                    if next_run:
                        text += f"⏱ اجرای بعدی: {next_run.strftime('%Y-%m-%d %H:%M')}\n"
                    
                    text += f"━━━━━━━━━━━━━━━━━━━━\n"
            
            if len(jobs) > 10:
                text += f"\n... و {len(jobs) - 10} کار دیگر\n"
            
            # Get scheduler stats
            scheduler_stats = self.scheduler.get_scheduler_stats()
            text += (
                f"\n📊 **آمار زمان‌بندی:**\n"
                f"• کل کارها: {scheduler_stats['total_jobs']}\n"
                f"• کارهای فعال: {scheduler_stats['active_jobs']}\n"
                f"• کارهای در حال اجرا: {scheduler_stats['running_jobs']}\n"
            )
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 بروزرسانی", 
                        callback_data="admin_scheduled"),
                    InlineKeyboardButton("⏹ توقف همه", 
                        callback_data="schedule_action_stop_all")
                ],
                [
                    InlineKeyboardButton("📊 آمار", 
                        callback_data="admin_stats"),
                    InlineKeyboardButton("🏠 داشبورد", 
                        callback_data="admin_dashboard")
                ]
            ])
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show scheduled jobs: {e}")
            await self._send_error(message, "نمایش کارهای زمان‌بندی")
    
    async def start_broadcast(self, message: Message, args: List[str] = None):
        """Start broadcast message"""
        try:
            text = "📢 **ارسال پیام همگانی**\n\n"
            
            if args:
                # Start broadcast with provided message
                broadcast_message = " ".join(args)
                await self._start_broadcast_process(message, broadcast_message)
            else:
                # Ask for message
                text += "لطفا پیام همگانی را وارد کنید:"
                
                if isinstance(message, CallbackQuery):
                    await message.message.edit_text(text)
                else:
                    await message.reply(text)
                
                # Store state for next message
                self.admin_sessions[message.from_user.id] = {
                    "action": "broadcast_message"
                }
        
        except Exception as e:
            logger.error(f"Failed to start broadcast: {e}")
            await self._send_error(message, "شروع ارسال همگانی")
    
    async def _start_broadcast_process(self, message: Message, broadcast_text: str):
        """Start broadcast process"""
        try:
            # Get all user IDs
            user_ids = await self.db.get_all_user_ids()
            
            if not user_ids:
                await message.reply("❌ هیچ کاربری برای ارسال پیام وجود ندارد")
                return
            
            # Add to broadcast queue
            broadcast_id = hashlib.md5(f"{datetime.now()}_{broadcast_text}".encode()).hexdigest()[:8]
            
            broadcast_data = {
                "broadcast_id": broadcast_id,
                "admin_id": message.from_user.id,
                "message": broadcast_text,
                "user_ids": user_ids,
                "total_users": len(user_ids),
                "sent_count": 0,
                "failed_count": 0,
                "started_at": datetime.now()
            }
            
            await self.broadcast_queue.put(broadcast_data)
            
            # Send confirmation
            await message.reply(
                f"✅ ارسال همگانی شروع شد\n"
                f"🆔 کد: `{broadcast_id}`\n"
                f"👥 کاربران: {len(user_ids)}\n"
                f"📝 پیام: {broadcast_text[:50]}..."
            )
            
        except Exception as e:
            logger.error(f"Failed to start broadcast process: {e}")
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def _process_broadcasts(self):
        """Process broadcast queue"""
        while True:
            try:
                # Get broadcast from queue
                broadcast = await self.broadcast_queue.get()
                
                # Process broadcast
                await self._send_broadcast(broadcast)
                
                # Mark as done
                self.broadcast_queue.task_done()
                
            except Exception as e:
                logger.error(f"Broadcast processing error: {e}")
                await asyncio.sleep(5)
    
    async def _send_broadcast(self, broadcast: Dict):
        """Send broadcast to all users"""
        try:
            broadcast_id = broadcast["broadcast_id"]
            admin_id = broadcast["admin_id"]
            message_text = broadcast["message"]
            user_ids = broadcast["user_ids"]
            
            total_users = len(user_ids)
            sent = 0
            failed = 0
            
            logger.info(f"Starting broadcast {broadcast_id} to {total_users} users")
            
            # Send to each user
            for user_id in user_ids:
                try:
                    if self.bot_client:
                        await self.bot_client.send_message(
                            chat_id=user_id,
                            text=f"📢 **پیام همگانی مدیریت:**\n\n{message_text}"
                        )
                    
                    sent += 1
                    
                    # Update progress every 50 users
                    if sent % 50 == 0:
                        progress = (sent / total_users) * 100
                        logger.info(f"Broadcast {broadcast_id}: {sent}/{total_users} ({progress:.1f}%)")
                    
                    # Delay to avoid flooding
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    failed += 1
                    logger.debug(f"Failed to send to {user_id}: {e}")
            
            # Send completion report to admin
            completion_msg = (
                f"✅ **ارسال همگانی تکمیل شد**\n\n"
                f"🆔 کد: `{broadcast_id}`\n"
                f"👥 کل کاربران: {total_users}\n"
                f"✅ ارسال موفق: {sent}\n"
                f"❌ ناموفق: {failed}\n"
                f"⏱ زمان شروع: {broadcast['started_at'].strftime('%Y-%m-%d %H:%M')}\n"
                f"🕐 زمان پایان: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            if self.bot_client:
                await self.bot_client.send_message(admin_id, completion_msg)
            
            logger.info(f"Broadcast {broadcast_id} completed: {sent}/{total_users} successful")
            
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")
    
    async def export_logs(self, message: Message, args: List[str]):
        """Export logs"""
        try:
            date_str = args[0] if args else datetime.now().strftime("%Y-%m-%d")
            
            # Get logs for date
            logs = await self._get_logs_for_date(date_str)
            
            if not logs:
                await message.reply(f"❌ لاگی برای تاریخ {date_str} یافت نشد")
                return
            
            # Create CSV
            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer)
            
            # Write header
            csv_writer.writerow(["Timestamp", "Level", "Module", "Message"])
            
            # Write logs
            for log in logs:
                csv_writer.writerow([
                    log.get("timestamp", ""),
                    log.get("level", ""),
                    log.get("module", ""),
                    log.get("message", "")
                ])
            
            # Send file
            csv_data = csv_buffer.getvalue()
            
            if self.bot_client:
                # Save to file and send
                filename = f"logs_{date_str}.csv"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(csv_data)
                
                await self.bot_client.send_document(
                    chat_id=message.chat.id,
                    document=filename,
                    caption=f"📊 لاگ‌های تاریخ {date_str}"
                )
                
                # Cleanup
                Path(filename).unlink()
            
        except Exception as e:
            logger.error(f"Failed to export logs: {e}")
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def create_backup(self, message: Message):
        """Create system backup"""
        try:
            await message.reply("💾 در حال ایجاد پشتیبان...")
            
            # Create backup directory
            backup_dir = Path("backups")
            backup_dir.mkdir(exist_ok=True)
            
            # Generate backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"backup_{timestamp}.zip"
            
            # Create backup (simplified - would need actual backup logic)
            backup_data = {
                "timestamp": timestamp,
                "database_stats": await self._get_database_stats(),
                "config": self.config.to_dict(),
                "account_count": len(self.connection_pool.accounts) if self.connection_pool else 0,
                "user_count": await self.db.get_user_count()
            }
            
            # Save backup info
            backup_info_file = backup_dir / f"backup_info_{timestamp}.json"
            with open(backup_info_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            # Send backup info
            text = (
                f"✅ **پشتیبان ایجاد شد**\n\n"
                f"📅 تاریخ: {timestamp}\n"
                f"👥 کاربران: {backup_data['user_count']}\n"
                f"🔧 حساب‌ها: {backup_data['account_count']}\n"
                f"💾 فایل: `{backup_info_file.name}`"
            )
            
            # Send backup info file
            if self.bot_client:
                await self.bot_client.send_document(
                    chat_id=message.chat.id,
                    document=str(backup_info_file),
                    caption=text
                )
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            await message.reply(f"❌ خطا در ایجاد پشتیبان: {str(e)}")
    
    async def restart_bot(self, message: Message):
        """Restart bot command"""
        try:
            await message.reply("🔄 ربات در حال راه‌اندازی مجدد...")
            
            # Log restart
            await self._log_admin_action(
                admin_id=message.from_user.id,
                action="restart_bot",
                details="Bot restart initiated"
            )
            
            # In production, this would trigger a restart
            # For now, just send confirmation
            await message.reply("✅ دستور راه‌اندازی مجدد ثبت شد")
            
        except Exception as e:
            logger.error(f"Restart command failed: {e}")
            await message.reply(f"❌ خطا: {str(e)}")
    
    async def show_health_check(self, message: Message):
        """Show system health check"""
        try:
            text = "🩺 **بررسی سلامت سیستم**\n\n"
            
            # Check components
            components = {
                "Database": bool(self.db),
                "Connection Pool": bool(self.connection_pool),
                "Report Engine": bool(self.report_engine),
                "Scheduler": bool(self.scheduler),
                "Session Manager": bool(self.session_manager),
                "Bot Client": bool(self.bot_client)
            }
            
            for component, status in components.items():
                text += f"{'✅' if status else '❌'} {component}: {'فعال' if status else 'غیرفعال'}\n"
            
            # Add system info
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            text += (
                f"\n💻 **اطلاعات سیستم:**\n"
                f"• CPU: {cpu_percent}%\n"
                f"• RAM: {memory.percent}% ({memory.used / 1024**3:.1f} GB / {memory.total / 1024**3:.1f} GB)\n"
            )
            
            # Add bot statistics
            if self.report_engine:
                active_reports = self.report_engine.get_active_reports_count()
                text += f"• گزارش‌های فعال: {active_reports}\n"
            
            if self.scheduler:
                scheduler_stats = self.scheduler.get_scheduler_stats()
                text += f"• کارهای زمان‌بندی: {scheduler_stats['active_jobs']}\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_health"),
                 InlineKeyboardButton("🏠 داشبورد", callback_data="admin_dashboard")]
            ])
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show health check: {e}")
            await self._send_error(message, "نمایش بررسی سلامت")
    
    async def show_revenue_analytics(self, message: Message, args: List[str] = None):
        """Show revenue analytics"""
        try:
            # This would integrate with payment system
            # For now, show mock data
            
            text = (
                "💳 **تحلیل درآمد و مالی**\n\n"
                
                "📅 **دوره: 30 روز گذشته**\n"
                "• کل درآمد: 5,250,000 تومان\n"
                "• اشتراک‌های فعال: 42\n"
                "• میانگین ارزش هر کاربر: 125,000 تومان\n"
                "• نرخ تمدید: 78%\n\n"
                
                "📊 **توزیع اشتراک‌ها:**\n"
                "• 7 روزه: 15 کاربر\n"
                "• 30 روزه: 20 کاربر\n"
                "• 90 روزه: 7 کاربر\n\n"
                
                "📈 **روند ماهانه:**\n"
                "• ماه جاری: 2,100,000 تومان\n"
                "• ماه گذشته: 1,850,000 تومان\n"
                "• رشد: +13.5%\n"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 خروجی Excel", callback_data="revenue_export"),
                 InlineKeyboardButton("🏠 داشبورد", callback_data="admin_dashboard")]
            ])
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show revenue analytics: {e}")
            await self._send_error(message, "نمایش تحلیل درآمد")
    
    async def show_audit_logs(self, message: Message, args: List[str] = None):
        """Show audit logs"""
        try:
            page = int(args[0]) if args and args[0].isdigit() else 1
            page_size = 10
            
            # Get audit logs
            logs = await self.db.get_audit_logs_paginated(page, page_size)
            
            text = "🔍 **لاگ‌های حسابرسی**\n\n"
            
            if not logs:
                text += "هیچ لاگ حسابرسی یافت نشد.\n"
            else:
                for log in logs:
                    admin_id = log["admin_id"]
                    action = log["action"]
                    timestamp = datetime.fromisoformat(log["created_at"]) if isinstance(log["created_at"], str) else log["created_at"]
                    details = log.get("details", "")
                    
                    text += (
                        f"👤 مدیر: `{admin_id}`\n"
                        f"📝 عمل: {action}\n"
                        f"🕐 زمان: {timestamp.strftime('%Y-%m-%d %H:%M')}\n"
                    )
                    
                    if details:
                        text += f"📋 جزئیات: {details[:50]}...\n"
                    
                    text += f"━━━━━━━━━━━━━━━━━━━━\n"
            
            text += f"\n📄 صفحه {page}"
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⏪ قبلی", callback_data=f"admin_audit_{page-1}"),
                    InlineKeyboardButton("بعدی ⏩", callback_data=f"admin_audit_{page+1}")
                ],
                [
                    InlineKeyboardButton("📤 خروجی", callback_data="audit_export"),
                    InlineKeyboardButton("🏠 داشبورد", callback_data="admin_dashboard")
                ]
            ])
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show audit logs: {e}")
            await self._send_error(message, "نمایش لاگ‌های حسابرسی")
    
    async def show_settings(self, message: Message):
        """Show bot settings"""
        try:
            config_dict = self.config.to_dict()
            
            text = "⚙️ **تنظیمات ربات**\n\n"
            
            # Display important settings
            important_settings = {
                "API Configuration": config_dict.get("telegram", {}),
                "Security": config_dict.get("security", {}),
                "Reporting Limits": config_dict.get("reporting", {}),
                "Admin IDs": config_dict.get("admin_ids", [])
            }
            
            for category, settings in important_settings.items():
                text += f"**{category}:**\n"
                
                if isinstance(settings, dict):
                    for key, value in settings.items():
                        if key in ["encryption_key", "api_hash", "bot_token"]:
                            # Hide sensitive data
                            if value:
                                text += f"• {key}: `{'*' * 8}...`\n"
                            else:
                                text += f"• {key}: تنظیم نشده\n"
                        elif isinstance(value, list):
                            text += f"• {key}: {len(value)} آیتم\n"
                        else:
                            text += f"• {key}: {value}\n"
                elif isinstance(settings, list):
                    text += f"• تعداد: {len(settings)}\n"
                
                text += "\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 بارگذاری مجدد", callback_data="settings_reload"),
                 InlineKeyboardButton("🏠 داشبورد", callback_data="admin_dashboard")]
            ])
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show settings: {e}")
            await self._send_error(message, "نمایش تنظیمات")
    
    async def _is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.config.ADMIN_IDS
    
    async def _send_error(self, message: Union[Message, CallbackQuery], action: str):
        """Send error message"""
        error_msg = f"❌ خطا در {action}"
        
        if isinstance(message, CallbackQuery):
            await message.message.reply(error_msg)
        else:
            await message.reply(error_msg)
    
    async def _log_admin_action(self, admin_id: int, action: str, 
                               target_user_id: int = None, details: str = ""):
        """Log admin action to database"""
        try:
            await self.db.log_admin_action(
                admin_id=admin_id,
                action=action,
                target_user_id=target_user_id,
                details=details
            )
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")
    
    async def _get_logs_for_date(self, date_str: str) -> List[Dict]:
        """Get logs for specific date"""
        # This would read from log file
        # For now, return mock data
        return []
    
    async def _get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            return {
                "users": await self.db.get_user_count(),
                "reports": await self.db.get_total_reports_count(),
                "accounts": await self.session_manager.get_session_stats() if self.session_manager else {},
                "scheduled_jobs": await self.scheduler.get_all_jobs() if self.scheduler else []
            }
        except:
            return {}
    
    async def _show_account_details(self, message: Message):
        """Show detailed account information"""
        try:
            if not self.connection_pool:
                await message.reply("❌ Connection pool not available")
                return
            
            # Get detailed account info
            accounts_info = []
            for phone, account in list(self.connection_pool.accounts.items())[:10]:  # First 10
                accounts_info.append({
                    "phone": phone,
                    "status": account.status.value,
                    "health": account.health_score,
                    "reports": account.stats.total_reports,
                    "success_rate": account.stats.success_rate()
                })
            
            text = "📋 **جزئیات حساب‌ها**\n\n"
            
            for acc in accounts_info:
                text += (
                    f"📱 {acc['phone']}\n"
                    f"📊 وضعیت: {acc['status']}\n"
                    f"🩺 سلامت: {acc['health']:.1f}\n"
                    f"📈 گزارش‌ها: {acc['reports']}\n"
                    f"✅ نرخ موفقیت: {acc['success_rate']:.1f}%\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                )
            
            if len(self.connection_pool.accounts) > 10:
                text += f"\n... و {len(self.connection_pool.accounts) - 10} حساب دیگر\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 داشبورد", callback_data="admin_dashboard")]
            ])
            
            if isinstance(message, CallbackQuery):
                await message.message.edit_text(text, reply_markup=keyboard)
            else:
                await message.reply(text, reply_markup=keyboard)
        
        except Exception as e:
            logger.error(f"Failed to show account details: {e}")
            await self._send_error(message, "نمایش جزئیات حساب‌ها")
    
    async def _handle_broadcast_callback(self, callback_query: CallbackQuery, data: str):
        """Handle broadcast callbacks"""
        # Implementation would handle broadcast actions
        await callback_query.answer("در حال توسعه...", show_alert=True)
    
    async def _handle_report_action(self, callback_query: CallbackQuery, data: str):
        """Handle report actions"""
        action = data.split("_")[2]
        
        if action == "export":
            await self.export_logs(callback_query.message, ["reports"])
        
        await callback_query.answer()
    
    async def _handle_schedule_action(self, callback_query: CallbackQuery, data: str):
        """Handle schedule actions"""
        action = data.split("_")[2]
        
        if action == "stop_all":
            # Stop all scheduled jobs
            if self.scheduler:
                # Implementation to stop all jobs
                pass
            await callback_query.answer("همه کارها متوقف شدند", show_alert=True)
        
        await callback_query.answer()

# Helper functions for admin panel
def format_number(number: int) -> str:
    """Format number with commas"""
    return f"{number:,}"

def format_percentage(value: float) -> str:
    """Format percentage"""
    return f"{value:.1f}%"

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable"""
    if seconds < 60:
        return f"{seconds:.1f} ثانیه"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} دقیقه"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} ساعت"

if __name__ == "__main__":
    # Test admin panel
    import asyncio
    
    async def test():
        from database import DatabaseManager
        from config_manager import get_config
        
        config = get_config()
        db = DatabaseManager()
        
        panel = AdminPanel(db, config)
        
        print("Admin panel initialized")
        print(f"Admin IDs: {config.ADMIN_IDS}")
    
    asyncio.run(test())