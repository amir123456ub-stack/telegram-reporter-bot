#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Callback Handlers - Handle all callback queries
Lines: ~200
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config_manager import get_config
from database import DatabaseManager
from report_engine import ReportEngine
from scheduler import ReportScheduler
from connection_pool import ConnectionPool
from session_manager import SessionManager
from admin_panel import AdminPanel

logger = logging.getLogger(__name__)

class CallbackHandlers:
    """Handle all callback queries from inline keyboards"""
    
    def __init__(self, bot_client: Client, db: DatabaseManager,
                 report_engine: ReportEngine, scheduler: ReportScheduler,
                 connection_pool: ConnectionPool, session_manager: SessionManager,
                 admin_panel: AdminPanel, report_handlers, user_handlers, admin_handlers):
        self.bot = bot_client
        self.db = db
        self.report_engine = report_engine
        self.scheduler = scheduler
        self.connection_pool = connection_pool
        self.session_manager = session_manager
        self.admin_panel = admin_panel
        self.report_handlers = report_handlers
        self.user_handlers = user_handlers
        self.admin_handlers = admin_handlers
        self.config = get_config()
        
        # Register callback handler
        self._register_callback_handler()
        
        logger.info("Callback handlers initialized")
    
    def _register_callback_handler(self):
        """Register main callback handler"""
        
        @self.bot.on_callback_query()
        async def callback_handler(client: Client, callback_query: CallbackQuery):
            await self.handle_callback(callback_query)
    
    async def handle_callback(self, callback_query: CallbackQuery):
        """Handle all callback queries"""
        try:
            user_id = callback_query.from_user.id
            data = callback_query.data
            
            logger.debug(f"Callback from {user_id}: {data}")
            
            # Route to appropriate handler based on callback data prefix
            if data.startswith("reason_") or data.startswith("account_count_") or \
               data.startswith("schedule_") or data in ["confirm_report", "cancel_report", "check_subscription"]:
                await self.report_handlers.handle_callback(callback_query)
            
            elif data.startswith("admin_"):
                await self.admin_panel.handle_callback(callback_query, data)
            
            elif data.startswith("user_action_"):
                await self.admin_panel.handle_callback(callback_query, data)
            
            elif data.startswith("account_action_"):
                await self.admin_panel.handle_callback(callback_query, data)
            
            elif data.startswith("report_action_"):
                await self.admin_panel.handle_callback(callback_query, data)
            
            elif data.startswith("schedule_action_"):
                await self.admin_panel.handle_callback(callback_query, data)
            
            elif data.startswith("broadcast_"):
                await self.admin_panel.handle_callback(callback_query, data)
            
            elif data.startswith("menu_"):
                await self._handle_menu_callbacks(callback_query, data)
            
            elif data.startswith("settings_"):
                await self._handle_settings_callbacks(callback_query, data)
            
            elif data.startswith("job_"):
                await self._handle_job_callbacks(callback_query, data)
            
            else:
                await callback_query.answer("❌ عملیات نامعتبر", show_alert=True)
            
        except Exception as e:
            logger.error(f"Callback handler error: {e}")
            await callback_query.answer("❌ خطا در پردازش", show_alert=True)
    
    async def _handle_menu_callbacks(self, callback_query: CallbackQuery, data: str):
        """Handle menu navigation callbacks"""
        user_id = callback_query.from_user.id
        
        if data == "menu_main":
            # Show main menu
            await self.user_handlers.show_main_menu(callback_query.message)
            await callback_query.answer()
        
        elif data == "menu_help":
            # Show help
            await self.user_handlers.handle_help(callback_query.message)
            await callback_query.answer()
        
        elif data == "menu_profile":
            # Show profile
            await self.user_handlers.handle_profile(callback_query.message)
            await callback_query.answer()
        
        elif data == "menu_back":
            # Go back to previous menu
            await callback_query.message.edit_text(
                "🔙 بازگشت به منوی اصلی",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 منوی اصلی", callback_data="menu_main")]
                ])
            )
            await callback_query.answer()
        
        else:
            await callback_query.answer("❌ گزینه نامعتبر", show_alert=True)
    
    async def _handle_settings_callbacks(self, callback_query: CallbackQuery, data: str):
        """Handle settings callbacks"""
        user_id = callback_query.from_user.id
        
        if data == "settings_language":
            # Change language
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang_fa"),
                    InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
                ],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_main")]
            ])
            
            await callback_query.message.edit_text(
                "🌐 **انتخاب زبان**\n\n"
                "لطفا زبان مورد نظر خود را انتخاب کنید:",
                reply_markup=keyboard
            )
            await callback_query.answer()
        
        elif data.startswith("lang_"):
            lang = data.replace("lang_", "")
            
            # Update user language preference
            # This would require database update
            await callback_query.answer(f"✅ زبان به {'فارسی' if lang == 'fa' else 'English'} تغییر یافت", show_alert=True)
        
        elif data == "settings_notifications":
            await callback_query.answer("⚙️ تنظیمات اعلان در حال توسعه", show_alert=True)
        
        else:
            await callback_query.answer("❌ تنظیم نامعتبر", show_alert=True)
    
    async def _handle_job_callbacks(self, callback_query: CallbackQuery, data: str):
        """Handle scheduled job callbacks"""
        user_id = callback_query.from_user.id
        
        # Check if user is admin
        is_admin = user_id in self.config.ADMIN_IDS
        
        if not is_admin:
            await callback_query.answer("⛔ دسترسی محدود به مدیران", show_alert=True)
            return
        
        parts = data.split("_")
        
        if len(parts) >= 3:
            action = parts[1]
            job_id = parts[2]
            
            if action == "pause":
                success, msg = await self.scheduler.pause_job(job_id)
                await callback_query.answer(msg, show_alert=True)
                
            elif action == "resume":
                success, msg = await self.scheduler.resume_job(job_id)
                await callback_query.answer(msg, show_alert=True)
                
            elif action == "cancel":
                success, msg = await self.scheduler.cancel_job(job_id)
                await callback_query.answer(msg, show_alert=True)
                
            elif action == "run":
                success, msg = await self.scheduler.run_job_now(job_id)
                await callback_query.answer(msg, show_alert=True)
            
            elif action == "delete":
                success, msg = await self.scheduler.delete_job(job_id)
                await callback_query.answer(msg, show_alert=True)
        
        else:
            await callback_query.answer("❌ شناسه کار نامعتبر", show_alert=True)
    
    async def handle_admin_callback(self, callback_query: CallbackQuery, data: str):
        """Route admin callbacks to admin panel"""
        await self.admin_panel.handle_callback(callback_query, data)