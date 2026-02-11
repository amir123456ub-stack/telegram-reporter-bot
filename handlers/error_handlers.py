#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Error Handlers - Handle errors and exceptions
Lines: ~200
"""

import asyncio
import logging
import traceback
from typing import Optional, Dict, Any
from datetime import datetime

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery
from pyrogram.errors import (
    FloodWait, BadRequest, Unauthorized, Forbidden,
    ChatAdminRequired, UserNotParticipant, PeerIdInvalid,
    UsernameNotOccupied, ChannelPrivate, ChatWriteForbidden,
    MessageNotModified, MessageIdInvalid, QueryIdInvalid
)

from config_manager import get_config
from database import DatabaseManager
from utils.helpers import format_duration

logger = logging.getLogger(__name__)

class ErrorHandlers:
    """Handle errors and exceptions gracefully"""
    
    def __init__(self, bot_client: Client, db: DatabaseManager):
        self.bot = bot_client
        self.db = db
        self.config = get_config()
        
        # Register error handlers
        self._register_error_handlers()
        
        logger.info("Error handlers initialized")
    
    def _register_error_handlers(self):
        """Register error handlers for common exceptions"""
        
        @self.bot.on_error()
        async def global_error_handler(client: Client, error: Exception):
            await self.handle_global_error(error)
    
    async def handle_global_error(self, error: Exception):
        """Handle global uncaught exceptions"""
        error_type = type(error).__name__
        error_msg = str(error)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Unhandled error: {error_type} - {error_msg}")
        logger.debug(f"Traceback: {error_traceback}")
        
        # Log to database
        try:
            await self._log_error(error_type, error_msg, error_traceback)
        except:
            pass
        
        # Notify admins for critical errors
        if self._is_critical_error(error):
            await self._notify_admins(error_type, error_msg)
    
    async def handle_message_error(self, message: Message, error: Exception) -> Optional[str]:
        """Handle errors in message handlers"""
        user_id = message.from_user.id if message.from_user else None
        
        # Handle specific errors
        if isinstance(error, FloodWait):
            wait_time = error.value
            return (
                f"⚠️ **محدودیت موقت**\n\n"
                f"تلگرام درخواست شما را محدود کرد.\n"
                f"⏱ لطفا {format_duration(wait_time)} صبر کنید."
            )
        
        elif isinstance(error, Unauthorized):
            return "❌ دسترسی به حساب کاربری امکان‌پذیر نیست."
        
        elif isinstance(error, Forbidden):
            return "⛔ شما دسترسی لازم برای این عملیات را ندارید."
        
        elif isinstance(error, ChatAdminRequired):
            return "👑 این عملیات نیاز به دسترسی ادمین دارد."
        
        elif isinstance(error, UserNotParticipant):
            return "👤 کاربر عضو این گروه/کانال نیست."
        
        elif isinstance(error, PeerIdInvalid):
            return "❌ آیدی یا یوزرنیم نامعتبر است."
        
        elif isinstance(error, UsernameNotOccupied):
            return "❌ یوزرنیم یافت نشد."
        
        elif isinstance(error, ChannelPrivate):
            return "🔒 کانال خصوصی است و قابل دسترسی نیست."
        
        elif isinstance(error, ChatWriteForbidden):
            return "📝 امکان ارسال پیام در این گفتگو وجود ندارد."
        
        elif isinstance(error, MessageNotModified):
            return None  # Silently ignore
        
        elif isinstance(error, MessageIdInvalid):
            return "❌ شناسه پیام نامعتبر است."
        
        elif isinstance(error, BadRequest):
            return f"❌ درخواست نامعتبر: {str(error)}"
        
        # Generic error
        logger.error(f"Message error for user {user_id}: {error}")
        return "❌ خطایی در پردازش درخواست رخ داد."
    
    async def handle_callback_error(self, callback_query: CallbackQuery, error: Exception) -> Optional[str]:
        """Handle errors in callback handlers"""
        if isinstance(error, QueryIdInvalid):
            # Callback query expired, send new message
            await callback_query.message.reply(
                "⏰ این عملیات منقضی شده است.\n"
                "لطفا دوباره تلاش کنید."
            )
            return None
        
        elif isinstance(error, MessageNotModified):
            return None  # Silently ignore
        
        return await self.handle_message_error(callback_query.message, error)
    
    async def handle_report_error(self, report_id: int, account_id: str, error: Exception) -> Dict:
        """Handle errors during reporting"""
        error_data = {
            "report_id": report_id,
            "account_id": account_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        }
        
        if isinstance(error, FloodWait):
            error_data["flood_wait"] = error.value
            error_data["recoverable"] = True
        elif isinstance(error, (Unauthorized, AuthKeyUnregistered)):
            error_data["recoverable"] = False
            error_data["action"] = "remove_account"
        else:
            error_data["recoverable"] = True
        
        logger.warning(f"Report error: {error_data}")
        
        return error_data
    
    async def _log_error(self, error_type: str, error_msg: str, traceback_str: str):
        """Log error to database"""
        try:
            async with await self.db.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO system_logs (level, module, message, details, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    "ERROR",
                    "error_handler",
                    f"{error_type}: {error_msg}",
                    traceback_str[:1000]  # Truncate long tracebacks
                ))
                await conn.commit()
        except:
            pass
    
    async def _notify_admins(self, error_type: str, error_msg: str):
        """Notify admins about critical errors"""
        text = (
            "🚨 **خطای بحرانی**\n\n"
            f"📌 نوع: `{error_type}`\n"
            f"📝 پیام: {error_msg}\n"
            f"🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        for admin_id in self.config.ADMIN_IDS:
            try:
                await self.bot.send_message(admin_id, text)
            except:
                pass
    
    def _is_critical_error(self, error: Exception) -> bool:
        """Check if error is critical"""
        critical_errors = [
            "DatabaseError", "ConnectionError", "TimeoutError",
            "MemoryError", "SystemError"
        ]
        
        error_name = type(error).__name__
        return error_name in critical_errors

# handlers/__init__.py is already complete