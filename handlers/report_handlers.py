#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report Handlers - Handle reporting commands and workflows
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
from report_engine import ReportEngine, ReportType
from connection_pool import ConnectionPool
from utils.validators import (
    validate_telegram_link, validate_account_count,
    validate_report_reason
)
from utils.helpers import extract_username, extract_message_id, generate_id

logger = logging.getLogger(__name__)

class ReportHandlers:
    """Handle reporting commands and workflows"""
    
    # Report reasons in Persian
    REPORT_REASONS = [
        ("خشونت", "violence"),
        ("سوء استفاده کودک", "child_abuse"),
        ("پورنوگرافی", "pornography"),
        ("مواد مخدر", "illegal_drugs"),
        ("اطلاعات شخصی", "personal_info"),
        ("اسپم", "spam"),
        ("کلاهبرداری", "scam"),
        ("اکانت جعلی", "fake_account"),
        ("کپی رایت", "copyright"),
        ("دیگر", "other")
    ]
    
    def __init__(self, bot_client: Client, db: DatabaseManager,
                 report_engine: ReportEngine, connection_pool: ConnectionPool):
        self.bot = bot_client
        self.db = db
        self.report_engine = report_engine
        self.connection_pool = connection_pool
        self.config = get_config()
        
        # User states for reporting workflow
        self.report_states: Dict[int, Dict] = {}
        
        # Register handlers
        self._register_handlers()
        
        logger.info("Report handlers initialized")
    
    def _register_handlers(self):
        """Register report message handlers"""
        
        # Report type handlers
        @self.bot.on_message(filters.regex("^📢 گزارش کانال$"))
        async def channel_report_handler(client: Client, message: Message):
            await self.start_channel_report(message)
        
        @self.bot.on_message(filters.regex("^👥 گزارش گروه$"))
        async def group_report_handler(client: Client, message: Message):
            await self.start_group_report(message)
        
        @self.bot.on_message(filters.regex("^📝 گزارش پست$"))
        async def post_report_handler(client: Client, message: Message):
            await self.start_post_report(message)
        
        @self.bot.on_message(filters.regex("^👤 گزارش کاربر$"))
        async def user_report_handler(client: Client, message: Message):
            await self.start_user_report(message)
        
        @self.bot.on_message(filters.regex("^👁️ مشاهده \+ گزارش$"))
        async def view_report_handler(client: Client, message: Message):
            await self.start_view_report(message)
        
        @self.bot.on_message(filters.regex("^➕ عضویت\+گزارش$"))
        async def auto_join_report_handler(client: Client, message: Message):
            await self.start_auto_join_report(message)
        
        @self.bot.on_message(filters.regex("^⏰ گزارش زمان‌بندی$"))
        async def scheduled_report_handler(client: Client, message: Message):
            await self.start_scheduled_report(message)
        
        @self.bot.on_message(filters.regex("^🔗 گزارش از فوروارد$"))
        async def forward_report_handler(client: Client, message: Message):
            await self.start_forward_report(message)
        
        @self.bot.on_message(filters.regex("^⚠️ گزارش NotoScam$"))
        async def notoscam_report_handler(client: Client, message: Message):
            await self.start_notoscam_report(message)
        
        @self.bot.on_message(filters.forwarded)
        async def forwarded_message_handler(client: Client, message: Message):
            await self.handle_forwarded_message(message)
    
    async def start_channel_report(self, message: Message):
        """Start channel reporting workflow"""
        user_id = message.from_user.id
        
        # Check subscription
        if not await self.db.check_subscription(user_id):
            await self._send_subscription_required(message)
            return
        
        # Check rate limit
        if not await self.db.check_rate_limit(user_id, self.config.security.rate_limit_per_user):
            await message.reply(
                "⚠️ شما به محدودیت گزارش در ساعت رسیده‌اید.\n"
                "لطفا ۱ ساعت دیگر تلاش کنید."
            )
            return
        
        # Set state
        self.report_states[user_id] = {
            "report_type": "channel",
            "step": "awaiting_link"
        }
        
        await message.reply(
            "📢 **گزارش کانال**\n\n"
            "لطفا لینک کانال را ارسال کنید:\n\n"
            "مثال:\n"
            "• https://t.me/channel_name\n"
            "• @channel_name\n"
            "• t.me/channel_name"
        )
    
    async def start_group_report(self, message: Message):
        """Start group reporting workflow"""
        user_id = message.from_user.id
        
        if not await self.db.check_subscription(user_id):
            await self._send_subscription_required(message)
            return
        
        if not await self.db.check_rate_limit(user_id, self.config.security.rate_limit_per_user):
            await message.reply("⚠️ شما به محدودیت گزارش در ساعت رسیده‌اید.")
            return
        
        self.report_states[user_id] = {
            "report_type": "group",
            "step": "awaiting_link"
        }
        
        await message.reply(
            "👥 **گزارش گروه**\n\n"
            "لطفا لینک گروه را ارسال کنید:\n\n"
            "مثال:\n"
            "• https://t.me/group_name\n"
            "• @group_name\n"
            "• t.me/joinchat/abc123"
        )
    
    async def start_post_report(self, message: Message):
        """Start post reporting workflow"""
        user_id = message.from_user.id
        
        if not await self.db.check_subscription(user_id):
            await self._send_subscription_required(message)
            return
        
        if not await self.db.check_rate_limit(user_id, self.config.security.rate_limit_per_user):
            await message.reply("⚠️ شما به محدودیت گزارش در ساعت رسیده‌اید.")
            return
        
        self.report_states[user_id] = {
            "report_type": "post",
            "step": "awaiting_link"
        }
        
        await message.reply(
            "📝 **گزارش پست**\n\n"
            "لطفا لینک پست را ارسال کنید:\n\n"
            "مثال:\n"
            "• https://t.me/channel/1234\n"
            "• https://t.me/c/123456789/1234"
        )
    
    async def start_user_report(self, message: Message):
        """Start user reporting workflow"""
        user_id = message.from_user.id
        
        if not await self.db.check_subscription(user_id):
            await self._send_subscription_required(message)
            return
        
        if not await self.db.check_rate_limit(user_id, self.config.security.rate_limit_per_user):
            await message.reply("⚠️ شما به محدودیت گزارش در ساعت رسیده‌اید.")
            return
        
        self.report_states[user_id] = {
            "report_type": "user",
            "step": "awaiting_link"
        }
        
        await message.reply(
            "👤 **گزارش کاربر**\n\n"
            "لطفا آیدی یا یوزرنیم کاربر را ارسال کنید:\n\n"
            "مثال:\n"
            "• @username\n"
            "• 123456789"
        )
    
    async def start_view_report(self, message: Message):
        """Start view + report workflow"""
        user_id = message.from_user.id
        
        if not await self.db.check_subscription(user_id):
            await self._send_subscription_required(message)
            return
        
        self.report_states[user_id] = {
            "report_type": "view_report",
            "step": "awaiting_link"
        }
        
        await message.reply(
            "👁️ **مشاهده + گزارش**\n\n"
            "در این روش، حساب‌ها ابتدا چند پست آخر را مشاهده کرده\n"
            "سپس گزارش را ارسال می‌کنند.\n\n"
            "لطفا لینک کانال/گروه را ارسال کنید:"
        )
    
    async def start_auto_join_report(self, message: Message):
        """Start auto-join + report workflow"""
        user_id = message.from_user.id
        
        if not await self.db.check_subscription(user_id):
            await self._send_subscription_required(message)
            return
        
        self.report_states[user_id] = {
            "report_type": "auto_join",
            "step": "awaiting_link"
        }
        
        await message.reply(
            "➕ **عضویت + گزارش**\n\n"
            "در این روش، حساب‌ها ابتدا عضو کانال/گروه می‌شوند،\n"
            "سپس گزارش را ارسال کرده و خارج می‌شوند.\n\n"
            "لطفا لینک کانال/گروه را ارسال کنید:"
        )
    
    async def start_scheduled_report(self, message: Message):
        """Start scheduled report workflow"""
        user_id = message.from_user.id
        
        if not await self.db.check_subscription(user_id):
            await self._send_subscription_required(message)
            return
        
        self.report_states[user_id] = {
            "report_type": "scheduled",
            "step": "awaiting_link"
        }
        
        await message.reply(
            "⏰ **گزارش زمان‌بندی شده**\n\n"
            "لطفا لینک هدف را ارسال کنید:"
        )
    
    async def start_forward_report(self, message: Message):
        """Start report from forwarded message"""
        user_id = message.from_user.id
        
        if not await self.db.check_subscription(user_id):
            await self._send_subscription_required(message)
            return
        
        await message.reply(
            "🔗 **گزارش از فوروارد**\n\n"
            "لطفا پیام فوروارد شده را ارسال کنید."
        )
    
    async def start_notoscam_report(self, message: Message):
        """Start NotoScam report workflow"""
        user_id = message.from_user.id
        
        if not await self.db.check_subscription(user_id):
            await self._send_subscription_required(message)
            return
        
        self.report_states[user_id] = {
            "report_type": "notoscam",
            "step": "awaiting_text"
        }
        
        await message.reply(
            "⚠️ **گزارش به NotoScam**\n\n"
            "لطفا متن گزارش خود را وارد کنید:"
        )
    
    async def handle_forwarded_message(self, message: Message):
        """Handle forwarded message for reporting"""
        user_id = message.from_user.id
        
        if user_id not in self.report_states:
            return
        
        state = self.report_states[user_id]
        
        if state.get("report_type") == "forward_report" and state.get("step") == "awaiting_forward":
            # Extract source from forwarded message
            source = self._extract_forward_source(message)
            
            if not source:
                await message.reply("❌ اطلاعات فوروارد یافت نشد.")
                return
            
            # Auto-detect type and start appropriate workflow
            if source["type"] == "channel":
                self.report_states[user_id] = {
                    "report_type": "channel",
                    "target": source.get("username") or source.get("id"),
                    "step": "awaiting_reason"
                }
            elif source["type"] == "user":
                self.report_states[user_id] = {
                    "report_type": "user",
                    "target": source.get("username") or source.get("id"),
                    "step": "awaiting_reason"
                }
            elif source.get("message_id"):
                # Post from channel
                self.report_states[user_id] = {
                    "report_type": "post",
                    "target": f"t.me/{source.get('username')}/{source.get('message_id')}",
                    "step": "awaiting_reason"
                }
            
            await self._show_reason_selection(message)
    
    async def handle_text_message(self, message: Message):
        """Handle text messages in reporting workflow"""
        user_id = message.from_user.id
        
        if user_id not in self.report_states:
            return
        
        state = self.report_states[user_id]
        step = state.get("step")
        
        if step == "awaiting_link":
            await self._process_target_link(message, state)
        elif step == "awaiting_text":
            await self._process_custom_text(message, state)
        elif step == "awaiting_account_count":
            await self._process_account_count(message, state)
        elif step == "awaiting_schedule":
            await self._process_schedule(message, state)
    
    async def _process_target_link(self, message: Message, state: Dict):
        """Process target link input"""
        user_id = message.from_user.id
        link = message.text.strip()
        report_type = state.get("report_type")
        
        # Validate link based on report type
        expected_type = None
        if report_type in ["channel", "group", "user", "post"]:
            expected_type = report_type
        
        is_valid, extracted = validate_telegram_link(link, expected_type)
        
        if not is_valid:
            await message.reply(
                "❌ لینک نامعتبر است.\n"
                "لطفا یک لینک معتبر ارسال کنید."
            )
            return
        
        # Store target
        state["target"] = link
        state["step"] = "awaiting_reason"
        
        # Show reason selection
        await self._show_reason_selection(message)
    
    async def _show_reason_selection(self, message: Message):
        """Show report reason selection keyboard"""
        # Create keyboard with 2 columns
        keyboard = []
        row = []
        
        for i, (reason_text, reason_value) in enumerate(self.REPORT_REASONS, 1):
            row.append(InlineKeyboardButton(
                reason_text,
                callback_data=f"reason_{reason_value}"
            ))
            
            if i % 2 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("❌ انصراف", callback_data="cancel_report")
        ])
        
        await message.reply(
            "📝 **دلیل گزارش را انتخاب کنید:**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _process_custom_text(self, message: Message, state: Dict):
        """Process custom reason text"""
        user_id = message.from_user.id
        custom_text = message.text.strip()
        
        if len(custom_text) < 3:
            await message.reply("❌ متن باید حداقل ۳ حرف باشد.")
            return
        
        state["custom_reason"] = custom_text
        state["step"] = "awaiting_account_count"
        
        await self._show_account_selection(message)
    
    async def _process_account_count(self, message: Message, state: Dict):
        """Process account count input"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        # Get available accounts count
        available = await self.connection_pool.get_available_accounts_count()
        max_allowed = min(available, self.config.reporting.max_accounts_per_report)
        
        is_valid, count = validate_account_count(text, max_allowed)
        
        if not is_valid:
            await message.reply(
                f"❌ تعداد نامعتبر.\n"
                f"لطفا عددی بین ۱ تا {max_allowed} وارد کنید."
            )
            return
        
        state["account_count"] = count
        
        if state.get("report_type") == "scheduled":
            # Ask for schedule
            state["step"] = "awaiting_schedule"
            await self._show_schedule_options(message)
        else:
            # Show confirmation
            await self._show_report_confirmation(message, state)
    
    async def _process_schedule(self, message: Message, state: Dict):
        """Process schedule input"""
        text = message.text.strip()
        
        # Simple schedule parsing (for demo)
        # In production, use proper schedule selection interface
        if text.isdigit():
            # Schedule in hours
            hours = int(text)
            if 1 <= hours <= 168:
                state["schedule"] = f"{hours}h"
                state["step"] = "confirm"
                await self._show_report_confirmation(message, state)
            else:
                await message.reply("❌ تعداد ساعت باید بین ۱ تا ۱۶۸ باشد.")
        else:
            await message.reply("❌ لطفا تعداد ساعت را به عدد وارد کنید.")
    
    async def _show_account_selection(self, message: Message):
        """Show account count selection keyboard"""
        user_id = message.from_user.id
        available = await self.connection_pool.get_available_accounts_count()
        max_allowed = min(available, self.config.reporting.max_accounts_per_report)
        
        # Create keyboard with suggested counts
        keyboard = []
        row = []
        
        suggestions = [1, 3, 5, 10, 20, 50]
        suggestions = [s for s in suggestions if s <= max_allowed]
        
        for i, count in enumerate(suggestions, 1):
            row.append(InlineKeyboardButton(
                str(count),
                callback_data=f"account_count_{count}"
            ))
            
            if i % 3 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("✏️ تعداد دلخواه", callback_data="account_count_custom")
        ])
        keyboard.append([
            InlineKeyboardButton("❌ انصراف", callback_data="cancel_report")
        ])
        
        await message.reply(
            f"👥 **تعداد حساب‌ها**\n\n"
            f"حساب‌های فعال: {available}\n"
            f"حداکثر مجاز: {max_allowed}\n\n"
            f"لطفا تعداد حساب‌ها را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_schedule_options(self, message: Message):
        """Show schedule options for scheduled reports"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("۳۰ دقیقه", callback_data="schedule_30m"),
                InlineKeyboardButton("۱ ساعت", callback_data="schedule_1h"),
                InlineKeyboardButton("۲ ساعت", callback_data="schedule_2h")
            ],
            [
                InlineKeyboardButton("۶ ساعت", callback_data="schedule_6h"),
                InlineKeyboardButton("۱۲ ساعت", callback_data="schedule_12h"),
                InlineKeyboardButton("۲۴ ساعت", callback_data="schedule_24h")
            ],
            [
                InlineKeyboardButton("⏰ زمان دلخواه", callback_data="schedule_custom"),
                InlineKeyboardButton("❌ انصراف", callback_data="cancel_report")
            ]
        ])
        
        await message.reply(
            "⏰ **زمان‌بندی گزارش**\n\n"
            "لطفا فاصله زمانی بین گزارش‌ها را انتخاب کنید:",
            reply_markup=keyboard
        )
    
    async def _show_report_confirmation(self, message: Message, state: Dict):
        """Show report confirmation"""
        report_type = state.get("report_type")
        target = state.get("target")
        reason = state.get("reason", state.get("custom_reason", "نامشخص"))
        account_count = state.get("account_count", 1)
        
        # Persian names for report types
        type_names = {
            "channel": "کانال",
            "group": "گروه",
            "user": "کاربر",
            "post": "پست",
            "view_report": "مشاهده + گزارش",
            "auto_join": "عضویت + گزارش",
            "notoscam": "گزارش به NotoScam"
        }
        
        persian_type = type_names.get(report_type, report_type)
        
        text = (
            f"✅ **تأیید نهایی گزارش**\n\n"
            f"📁 نوع گزارش: {persian_type}\n"
            f"🎯 هدف: `{target}`\n"
            f"📝 دلیل: {reason}\n"
            f"👥 تعداد حساب: {account_count}\n\n"
            f"آیا می‌خواهید گزارش را شروع کنید؟"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ بله، شروع کن", callback_data="confirm_report"),
                InlineKeyboardButton("❌ خیر، انصراف", callback_data="cancel_report")
            ]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    async def handle_callback(self, callback_query: CallbackQuery):
        """Handle report-related callbacks"""
        user_id = callback_query.from_user.id
        data = callback_query.data
        
        if data.startswith("reason_"):
            await self._handle_reason_selection(callback_query, data)
        
        elif data.startswith("account_count_"):
            await self._handle_account_selection(callback_query, data)
        
        elif data.startswith("schedule_"):
            await self._handle_schedule_selection(callback_query, data)
        
        elif data == "confirm_report":
            await self._handle_report_confirmation(callback_query)
        
        elif data == "cancel_report":
            await self._handle_report_cancellation(callback_query)
        
        elif data == "check_subscription":
            await self._check_subscription_status(callback_query)
    
    async def _handle_reason_selection(self, callback_query: CallbackQuery, data: str):
        """Handle reason selection callback"""
        user_id = callback_query.from_user.id
        reason_value = data.replace("reason_", "")
        
        # Find Persian name for reason
        reason_text = next(
            (r[0] for r in self.REPORT_REASONS if r[1] == reason_value),
            "دیگر"
        )
        
        if user_id in self.report_states:
            self.report_states[user_id]["reason"] = reason_text
            
            if reason_value == "other":
                # Ask for custom reason
                self.report_states[user_id]["step"] = "awaiting_text"
                await callback_query.message.edit_text(
                    "📝 لطفا دلیل گزارش خود را وارد کنید:"
                )
            else:
                # Go to account selection
                self.report_states[user_id]["step"] = "awaiting_account_count"
                await self._show_account_selection(callback_query.message)
        
        await callback_query.answer()
    
    async def _handle_account_selection(self, callback_query: CallbackQuery, data: str):
        """Handle account count selection callback"""
        user_id = callback_query.from_user.id
        count_str = data.replace("account_count_", "")
        
        if count_str == "custom":
            self.report_states[user_id]["step"] = "awaiting_account_count"
            await callback_query.message.edit_text(
                "✏️ لطفا تعداد حساب‌ها را وارد کنید:"
            )
        else:
            count = int(count_str)
            
            if user_id in self.report_states:
                self.report_states[user_id]["account_count"] = count
                
                if self.report_states[user_id].get("report_type") == "scheduled":
                    self.report_states[user_id]["step"] = "awaiting_schedule"
                    await self._show_schedule_options(callback_query.message)
                else:
                    await self._show_report_confirmation(callback_query.message, 
                                                        self.report_states[user_id])
        
        await callback_query.answer()
    
    async def _handle_schedule_selection(self, callback_query: CallbackQuery, data: str):
        """Handle schedule selection callback"""
        user_id = callback_query.from_user.id
        schedule = data.replace("schedule_", "")
        
        if schedule == "custom":
            self.report_states[user_id]["step"] = "awaiting_schedule"
            await callback_query.message.edit_text(
                "⏰ لطفا تعداد ساعت را وارد کنید (۱-۱۶۸):"
            )
        else:
            if user_id in self.report_states:
                self.report_states[user_id]["schedule"] = schedule
                await self._show_report_confirmation(callback_query.message,
                                                    self.report_states[user_id])
        
        await callback_query.answer()
    
    async def _handle_report_confirmation(self, callback_query: CallbackQuery):
        """Handle report confirmation"""
        user_id = callback_query.from_user.id
        
        if user_id not in self.report_states:
            await callback_query.message.edit_text("❌ اطلاعات گزارش یافت نشد.")
            await callback_query.answer()
            return
        
        state = self.report_states[user_id]
        report_type = state.get("report_type")
        
        # Start progress message
        await callback_query.message.edit_text(
            "🚀 **شروع فرآیند گزارش‌گیری**\n\n"
            "در حال آماده‌سازی حساب‌ها..."
        )
        
        try:
            report_id = None
            
            if report_type in ["channel", "group", "user", "post"]:
                # Standard report
                report_id = await self.report_engine.start_report(
                    user_id=user_id,
                    target=state["target"],
                    target_type=report_type,
                    reason=state.get("reason", state.get("custom_reason", "other")),
                    account_count=state["account_count"]
                )
            
            elif report_type == "view_report":
                # View + report
                result = await self.report_engine.view_and_report(
                    target=state["target"],
                    accounts_count=state["account_count"]
                )
                
                await callback_query.message.edit_text(
                    self._format_special_report_result("view_report", result)
                )
            
            elif report_type == "auto_join":
                # Auto-join + report
                result = await self.report_engine.auto_join_report(
                    target=state["target"],
                    reason=state.get("reason", "other"),
                    accounts_count=state["account_count"]
                )
                
                await callback_query.message.edit_text(
                    self._format_special_report_result("auto_join", result)
                )
            
            elif report_type == "notoscam":
                # NotoScam report
                result = await self.report_engine.report_to_notoscam(
                    text=state.get("custom_reason", "گزارش"),
                    accounts_count=state["account_count"]
                )
                
                await callback_query.message.edit_text(
                    self._format_special_report_result("notoscam", result)
                )
            
            if report_id:
                # Start progress updates for standard report
                asyncio.create_task(
                    self._update_report_progress(callback_query.message, report_id, user_id)
                )
            
        except Exception as e:
            logger.error(f"Report failed: {e}")
            await callback_query.message.edit_text(f"❌ خطا: {str(e)}")
        
        # Clear state after successful start
        del self.report_states[user_id]
        await callback_query.answer()
    
    async def _handle_report_cancellation(self, callback_query: CallbackQuery):
        """Handle report cancellation"""
        user_id = callback_query.from_user.id
        
        if user_id in self.report_states:
            del self.report_states[user_id]
        
        await callback_query.message.edit_text("❌ گزارش لغو شد.")
        await callback_query.answer()
    
    async def _update_report_progress(self, message: Message, report_id: int, user_id: int):
        """Update report progress in real-time"""
        try:
            last_progress = 0
            
            while True:
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
                
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Progress update error: {e}")
    
    async def _check_subscription_status(self, callback_query: CallbackQuery):
        """Check subscription status"""
        user_id = callback_query.from_user.id
        has_sub = await self.db.check_subscription(user_id)
        
        if has_sub:
            await callback_query.message.edit_text(
                "✅ اشتراک شما فعال است.\n"
                "لطفا از منوی اصلی استفاده کنید."
            )
        else:
            await callback_query.message.edit_text(
                "❌ اشتراک شما فعال نیست.\n"
                "برای خرید با ادمین تماس بگیرید."
            )
        
        await callback_query.answer()
    
    async def _send_subscription_required(self, message: Message):
        """Send subscription required message"""
        user_id = message.from_user.id
        
        text = (
            "⚠️ **نیاز به اشتراک فعال**\n\n"
            f"🆔 آیدی شما: `{user_id}`\n\n"
            "برای خرید اشتراک با ادمین تماس بگیرید:\n"
            "👤 @admin"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 بررسی مجدد", callback_data="check_subscription")],
            [InlineKeyboardButton("📞 تماس با ادمین", url="https://t.me/admin")]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    def _extract_forward_source(self, message: Message) -> Optional[Dict]:
        """Extract source from forwarded message"""
        try:
            source = {}
            
            if message.forward_from_chat:
                chat = message.forward_from_chat
                source['type'] = chat.type
                source['id'] = chat.id
                source['username'] = chat.username
                source['title'] = chat.title
                
                if message.forward_from_message_id:
                    source['message_id'] = message.forward_from_message_id
            
            elif message.forward_from:
                user = message.forward_from
                source['type'] = 'user'
                source['id'] = user.id
                source['username'] = user.username
                source['first_name'] = user.first_name
                source['last_name'] = user.last_name
            
            return source if source else None
            
        except Exception as e:
            logger.error(f"Failed to extract forward source: {e}")
            return None
    
    def _format_special_report_result(self, report_type: str, result: Dict) -> str:
        """Format special report results"""
        if not result.get("success"):
            return f"❌ خطا: {result.get('error', 'نامشخص')}"
        
        results = result.get("results", {})
        
        if report_type == "view_report":
            return (
                f"✅ **گزارش مشاهده + گزارش تکمیل شد**\n\n"
                f"👁️ مشاهده: {results.get('viewed', 0)}\n"
                f"📝 گزارش: {results.get('reported', 0)}\n"
                f"❌ ناموفق: {results.get('failed', 0)}\n"
                f"📊 مجموع: {result.get('total_accounts', 0)}"
            )
        
        elif report_type == "auto_join":
            return (
                f"✅ **گزارش عضویت + گزارش تکمیل شد**\n\n"
                f"➕ عضویت: {results.get('successful_joins', 0)}\n"
                f"📝 گزارش: {results.get('successful_reports', 0)}\n"
                f"❌ ناموفق: {results.get('failed', 0)}\n"
                f"📊 مجموع: {result.get('total_accounts', 0)}"
            )
        
        elif report_type == "notoscam":
            return (
                f"✅ **گزارش به NotoScam ارسال شد**\n\n"
                f"📤 ارسال موفق: {results.get('sent', 0)}\n"
                f"❌ ناموفق: {results.get('failed', 0)}\n"
                f"📊 مجموع: {result.get('total_accounts', 0)}"
            )
        
        return "✅ گزارش با موفقیت انجام شد."

# handlers/callback_handlers.py and handlers/error_handlers.py remaining...