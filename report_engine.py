#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report Engine - Core reporting logic
Lines: ~2500
"""

import asyncio
import logging
import re
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from urllib.parse import urlparse, parse_qs
from enum import Enum
import hashlib
import json

# Telegram
from pyrogram import Client
from pyrogram.types import Chat, User, Message
from pyrogram.errors import (
    FloodWait, BadRequest, ChannelInvalid, ChannelPrivate,
    UsernameNotOccupied, UsernameInvalid, PeerIdInvalid,
    ChatAdminRequired, UserNotParticipant
)

# Local imports
from config_manager import get_config
from database import DatabaseManager

logger = logging.getLogger(__name__)

class ReportStatus(Enum):
    """Report status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ReportType(Enum):
    """Report type enumeration"""
    CHANNEL = "channel"
    GROUP = "group"
    USER = "user"
    POST = "post"
    NOTOSCAM = "notoscam"

class TargetInfo:
    """Target information container"""
    
    def __init__(self, target: str):
        self.original_target = target
        self.type: Optional[ReportType] = None
        self.chat_id: Optional[int] = None
        self.username: Optional[str] = None
        self.message_id: Optional[int] = None
        self.title: Optional[str] = None
        self.members_count: Optional[int] = None
        self.is_accessible: bool = False
        self.error: Optional[str] = None
        
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "original_target": self.original_target,
            "type": self.type.value if self.type else None,
            "chat_id": self.chat_id,
            "username": self.username,
            "message_id": self.message_id,
            "title": self.title,
            "members_count": self.members_count,
            "is_accessible": self.is_accessible,
            "error": self.error
        }

class ReportProgress:
    """Report progress tracker"""
    
    def __init__(self, report_id: int, total_accounts: int):
        self.report_id = report_id
        self.total_accounts = total_accounts
        self.completed_accounts = 0
        self.successful_reports = 0
        self.failed_reports = 0
        self.start_time = datetime.now()
        self.current_account = 0
        self.status = ReportStatus.PROCESSING
        self.errors: List[Dict] = []
        
    def update(self, successful: bool, error_msg: str = None):
        """Update progress"""
        self.completed_accounts += 1
        if successful:
            self.successful_reports += 1
        else:
            self.failed_reports += 1
            if error_msg:
                self.errors.append({
                    "account": self.completed_accounts,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Update current account
        self.current_account = self.completed_accounts
        
        # Check if completed
        if self.completed_accounts >= self.total_accounts:
            self.status = ReportStatus.COMPLETED
            
    def get_progress_percentage(self) -> float:
        """Get progress percentage"""
        if self.total_accounts == 0:
            return 0
        return (self.completed_accounts / self.total_accounts) * 100
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "report_id": self.report_id,
            "total_accounts": self.total_accounts,
            "completed_accounts": self.completed_accounts,
            "successful_reports": self.successful_reports,
            "failed_reports": self.failed_reports,
            "progress_percentage": self.get_progress_percentage(),
            "elapsed_time": self.get_elapsed_time(),
            "status": self.status.value,
            "current_account": self.current_account,
            "errors": self.errors
        }

class ReportEngine:
    """Core reporting engine"""
    
    # Telegram report reasons mapping
    REPORT_REASONS = {
        "خشونت": "violence",
        "سوء استفاده کودک": "child_abuse",
        "پورنوگرافی": "pornography",
        "مواد مخدر": "illegal_drugs",
        "اطلاعات شخصی": "personal_details",
        "اسپم": "spam",
        "کلاهبرداری": "scam",
        "اکانت جعلی": "fake_account",
        "کپی رایت": "copyright",
        "دیگر": "other"
    }
    
    # Reverse mapping for display
    REASON_DISPLAY = {v: k for k, v in REPORT_REASONS.items()}
    
    def __init__(self, connection_pool, anti_detection):
        self.config = get_config()
        self.connection_pool = connection_pool
        self.anti_detection = anti_detection
        self.db = DatabaseManager()
        
        # Progress tracking
        self.active_reports: Dict[int, ReportProgress] = {}
        self.report_queue = asyncio.Queue()
        
        # Start queue processor
        asyncio.create_task(self._process_report_queue())
        
        logger.info("Report engine initialized")
    
    async def start_report(self, user_id: int, target: str, target_type: str, 
                          reason: str, account_count: int) -> int:
        """Start a new report"""
        try:
            # Parse target
            target_info = await self._parse_target(target, target_type)
            
            if not target_info.is_accessible:
                raise ValueError(f"هدف قابل دسترسی نیست: {target_info.error}")
            
            # Create report in database
            report_id = await self.db.create_report(
                user_id=user_id,
                target=target,
                target_type=target_type,
                reason=reason,
                account_count=account_count
            )
            
            # Create progress tracker
            progress = ReportProgress(report_id, account_count)
            self.active_reports[report_id] = progress
            
            # Add to queue
            report_data = {
                "report_id": report_id,
                "user_id": user_id,
                "target_info": target_info,
                "reason": reason,
                "account_count": account_count
            }
            
            await self.report_queue.put(report_data)
            
            logger.info(f"Report {report_id} queued for processing")
            
            return report_id
            
        except Exception as e:
            logger.error(f"Failed to start report: {e}")
            raise
    
    async def _process_report_queue(self):
        """Process reports from queue"""
        while True:
            try:
                # Get report from queue
                report_data = await self.report_queue.get()
                
                # Process report
                await self._execute_report(report_data)
                
                # Mark as done
                self.report_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(5)
    
    async def _execute_report(self, report_data: Dict):
        """Execute a report"""
        report_id = report_data["report_id"]
        target_info = report_data["target_info"]
        reason = report_data["reason"]
        account_count = report_data["account_count"]
        
        progress = self.active_reports.get(report_id)
        if not progress:
            logger.error(f"No progress tracker for report {report_id}")
            return
        
        try:
            # Get available accounts
            accounts = await self.connection_pool.get_available_accounts(account_count)
            
            if not accounts:
                progress.status = ReportStatus.FAILED
                await self.db.update_report_status(report_id, "failed", "هیچ حسابی در دسترس نیست")
                return
            
            # Update progress with actual account count
            progress.total_accounts = len(accounts)
            
            # Process each account
            for i, account in enumerate(accounts, 1):
                try:
                    # Update current account
                    progress.current_account = i
                    
                    # Execute report with this account
                    success = await self._report_with_account(
                        account, target_info, reason, progress
                    )
                    
                    # Update progress
                    progress.update(success)
                    
                    # Update database
                    await self.db.add_report_history(
                        report_id=report_id,
                        account_id=account.phone_number,
                        target=target_info.original_target,
                        reason=reason,
                        status="success" if success else "failed"
                    )
                    
                    # Update account stats
                    await self.db.update_account_stats(
                        account.phone_number,
                        successful=1 if success else 0
                    )
                    
                    # Anti-detection delay
                    if i < len(accounts):
                        delay = self.config.reporting.get_random_delay()
                        await asyncio.sleep(delay)
                        
                except Exception as e:
                    logger.error(f"Account {account.phone_number} failed: {e}")
                    progress.update(False, str(e))
                    await self.db.add_report_history(
                        report_id=report_id,
                        account_id=account.phone_number,
                        target=target_info.original_target,
                        reason=reason,
                        status="failed",
                        error_message=str(e)
                    )
            
            # Finalize report
            progress.status = ReportStatus.COMPLETED
            
            await self.db.update_report_status(
                report_id,
                "completed",
                successful=progress.successful_reports,
                failed=progress.failed_reports
            )
            
            logger.info(f"Report {report_id} completed: "
                       f"{progress.successful_reports}/{progress.total_accounts} successful")
            
        except Exception as e:
            logger.error(f"Report {report_id} failed: {e}")
            progress.status = ReportStatus.FAILED
            await self.db.update_report_status(
                report_id,
                "failed",
                error_message=str(e)
            )
        finally:
            # Clean up after 1 hour
            await asyncio.sleep(3600)
            if report_id in self.active_reports:
                del self.active_reports[report_id]
    
    async def _report_with_account(self, account, target_info: TargetInfo, 
                                  reason: str, progress: ReportProgress) -> bool:
        """Report with a single account"""
        try:
            # Get client for account
            client = await self.connection_pool.get_client(account.phone_number)
            if not client:
                return False
            
            # Anti-detection: simulate human behavior
            await self.anti_detection.simulate_pre_report_behavior(client)
            
            # Map reason to Telegram reason
            telegram_reason = self.REPORT_REASONS.get(reason, "other")
            
            # Execute report based on target type
            if target_info.type == ReportType.CHANNEL:
                success = await self._report_channel(
                    client, target_info, telegram_reason
                )
            elif target_info.type == ReportType.GROUP:
                success = await self._report_group(
                    client, target_info, telegram_reason
                )
            elif target_info.type == ReportType.USER:
                success = await self._report_user(
                    client, target_info, telegram_reason
                )
            elif target_info.type == ReportType.POST:
                success = await self._report_post(
                    client, target_info, telegram_reason
                )
            else:
                return False
            
            # Anti-detection: simulate post-report behavior
            await self.anti_detection.simulate_post_report_behavior(client)
            
            return success
            
        except FloodWait as e:
            logger.warning(f"Flood wait for {account.phone_number}: {e.value}s")
            await asyncio.sleep(e.value)
            return False
        except Exception as e:
            logger.error(f"Report failed for {account.phone_number}: {e}")
            return False
    
    async def _report_channel(self, client: Client, target_info: TargetInfo, 
                             reason: str) -> bool:
        """Report a channel"""
        try:
            # Get chat object
            if target_info.username:
                chat = await client.get_chat(target_info.username)
            else:
                chat = await client.get_chat(target_info.chat_id)
            
            # Report the chat
            await client.report_chat(
                chat_id=chat.id,
                reason=reason
            )
            
            logger.info(f"Reported channel {chat.id} ({chat.title})")
            return True
            
        except BadRequest as e:
            logger.error(f"Bad request for channel report: {e}")
            return False
        except Exception as e:
            logger.error(f"Channel report failed: {e}")
            return False
    
    async def _report_group(self, client: Client, target_info: TargetInfo, 
                           reason: str) -> bool:
        """Report a group"""
        try:
            # Get chat object
            if target_info.username:
                chat = await client.get_chat(target_info.username)
            else:
                chat = await client.get_chat(target_info.chat_id)
            
            # For groups, we need to report messages
            # Get recent messages
            messages = []
            async for message in client.get_chat_history(chat.id, limit=3):
                messages.append(message)
            
            if not messages:
                # If no messages, report the chat itself
                await client.report_chat(
                    chat_id=chat.id,
                    reason=reason
                )
            else:
                # Report recent messages
                for message in messages:
                    try:
                        await client.report_chat(
                            chat_id=chat.id,
                            message_ids=message.id,
                            reason=reason
                        )
                        await asyncio.sleep(1)  # Small delay between message reports
                    except:
                        continue
            
            logger.info(f"Reported group {chat.id} ({chat.title})")
            return True
            
        except Exception as e:
            logger.error(f"Group report failed: {e}")
            return False
    
    async def _report_user(self, client: Client, target_info: TargetInfo, 
                          reason: str) -> bool:
        """Report a user"""
        try:
            # Get user object
            if target_info.username:
                user = await client.get_users(target_info.username)
            else:
                user = await client.get_users(target_info.chat_id)
            
            # Report user
            await client.report_user(
                user_id=user.id,
                reason=reason
            )
            
            logger.info(f"Reported user {user.id} ({user.username})")
            return True
            
        except Exception as e:
            logger.error(f"User report failed: {e}")
            return False
    
    async def _report_post(self, client: Client, target_info: TargetInfo, 
                          reason: str) -> bool:
        """Report a specific post"""
        try:
            # Extract channel and message ID
            if not target_info.chat_id or not target_info.message_id:
                return False
            
            # Report the message
            await client.report_chat(
                chat_id=target_info.chat_id,
                message_ids=target_info.message_id,
                reason=reason
            )
            
            logger.info(f"Reported post {target_info.message_id} in {target_info.chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Post report failed: {e}")
            return False
    
    async def _parse_target(self, target: str, target_type: str) -> TargetInfo:
        """Parse and validate target"""
        target_info = TargetInfo(target)
        
        try:
            # Clean target string
            target = target.strip()
            
            # Parse based on target type
            if target_type in ["channel", "group"]:
                await self._parse_chat_target(target, target_info, target_type)
            elif target_type == "user":
                await self._parse_user_target(target, target_info)
            elif target_type == "post":
                await self._parse_post_target(target, target_info)
            
            return target_info
            
        except Exception as e:
            target_info.error = str(e)
            target_info.is_accessible = False
            return target_info
    
    async def _parse_chat_target(self, target: str, target_info: TargetInfo, 
                                target_type: str):
        """Parse chat/channel/group target"""
        # Try to get a client for validation
        client = await self.connection_pool.get_any_client()
        if not client:
            raise ValueError("هیچ کلاینتی برای اعتبارسنجی در دسترس نیست")
        
        try:
            # Extract username or chat ID
            username = None
            chat_id = None
            
            # Handle different formats
            if target.startswith("https://t.me/"):
                parts = target.replace("https://t.me/", "").split("/")
                username = parts[0].lstrip("@")
            elif target.startswith("t.me/"):
                parts = target.replace("t.me/", "").split("/")
                username = parts[0].lstrip("@")
            elif target.startswith("@"):
                username = target.lstrip("@")
            elif target.isdigit() or (target.startswith("-") and target[1:].isdigit()):
                chat_id = int(target)
            else:
                username = target
            
            # Get chat info
            if username:
                chat = await client.get_chat(username)
            else:
                chat = await client.get_chat(chat_id)
            
            # Verify chat type
            if target_type == "channel" and chat.type != "channel":
                raise ValueError("این یک کانال نیست")
            elif target_type == "group" and chat.type not in ["group", "supergroup"]:
                raise ValueError("این یک گروه نیست")
            
            # Set target info
            target_info.type = ReportType.CHANNEL if target_type == "channel" else ReportType.GROUP
            target_info.chat_id = chat.id
            target_info.username = chat.username
            target_info.title = chat.title
            target_info.members_count = getattr(chat, 'members_count', None)
            target_info.is_accessible = True
            
            logger.info(f"Validated {target_type}: {chat.title} ({chat.id})")
            
        except (ChannelInvalid, ChannelPrivate, UsernameNotOccupied, UsernameInvalid) as e:
            raise ValueError("کانال/گروه یافت نشد یا خصوصی است")
        except Exception as e:
            raise ValueError(f"خطا در اعتبارسنجی: {str(e)}")
    
    async def _parse_user_target(self, target: str, target_info: TargetInfo):
        """Parse user target"""
        client = await self.connection_pool.get_any_client()
        if not client:
            raise ValueError("هیچ کلاینتی برای اعتبارسنجی در دسترس نیست")
        
        try:
            # Extract username or user ID
            username = None
            user_id = None
            
            if target.startswith("https://t.me/"):
                username = target.replace("https://t.me/", "").lstrip("@")
            elif target.startswith("t.me/"):
                username = target.replace("t.me/", "").lstrip("@")
            elif target.startswith("@"):
                username = target.lstrip("@")
            elif target.isdigit():
                user_id = int(target)
            else:
                username = target
            
            # Get user info
            if username:
                user = await client.get_users(username)
            else:
                user = await client.get_users(user_id)
            
            # Set target info
            target_info.type = ReportType.USER
            target_info.chat_id = user.id
            target_info.username = user.username
            target_info.title = f"{user.first_name} {user.last_name or ''}".strip()
            target_info.is_accessible = True
            
            logger.info(f"Validated user: {user.username or user.id}")
            
        except (UsernameNotOccupied, UsernameInvalid, PeerIdInvalid) as e:
            raise ValueError("کاربر یافت نشد")
        except Exception as e:
            raise ValueError(f"خطا در اعتبارسنجی کاربر: {str(e)}")
    
    async def _parse_post_target(self, target: str, target_info: TargetInfo):
        """Parse post/message target"""
        client = await self.connection_pool.get_any_client()
        if not client:
            raise ValueError("هیچ کلاینتی برای اعتبارسنجی در دسترس نیست")
        
        try:
            # Extract channel and message ID from URL
            # Format: https://t.me/channel/123 or https://t.me/c/chat_id/message_id
            if "t.me/c/" in target:
                # Private channel format
                parts = target.split("/")
                if len(parts) < 5:
                    raise ValueError("لینک پست نامعتبر است")
                
                chat_id = int(parts[-2])
                message_id = int(parts[-1])
                
                # Try to access the message
                try:
                    message = await client.get_messages(chat_id, message_id)
                    target_info.title = f"Post in private channel"
                except:
                    # Can't access private channel, but we can still report
                    pass
                
            else:
                # Public channel format
                match = re.search(r't\.me/([^/]+)/(\d+)', target)
                if not match:
                    raise ValueError("لینک پست نامعتبر است")
                
                username = match.group(1)
                message_id = int(match.group(2))
                
                # Get chat info
                chat = await client.get_chat(username)
                
                # Try to get message
                try:
                    message = await client.get_messages(chat.id, message_id)
                    target_info.title = f"Post: {message.text[:50] if message.text else 'No text'}"
                except:
                    target_info.title = f"Post in {chat.title}"
                
                chat_id = chat.id
            
            # Set target info
            target_info.type = ReportType.POST
            target_info.chat_id = chat_id
            target_info.message_id = message_id
            target_info.is_accessible = True
            
            logger.info(f"Validated post: {chat_id}/{message_id}")
            
        except Exception as e:
            raise ValueError(f"خطا در اعتبارسنجی پست: {str(e)}")
    
    async def get_report_status(self, report_id: int) -> Dict:
        """Get status of a report"""
        if report_id in self.active_reports:
            progress = self.active_reports[report_id]
            return progress.to_dict()
        
        # Check database for completed reports
        report = await self.db.get_report(report_id)
        if report:
            return {
                "report_id": report_id,
                "status": report["status"],
                "successful": report.get("successful_reports", 0),
                "failed": report.get("failed_reports", 0),
                "total": report.get("accounts_used", 0),
                "progress": 100 if report["status"] == "completed" else 0,
                "elapsed": 0
            }
        
        return {"error": "گزارش یافت نشد"}
    
    async def cancel_report(self, report_id: int) -> bool:
        """Cancel a running report"""
        if report_id in self.active_reports:
            progress = self.active_reports[report_id]
            progress.status = ReportStatus.CANCELLED
            
            # Update database
            await self.db.update_report_status(
                report_id,
                "cancelled",
                error_message="توسط کاربر لغو شد"
            )
            
            # Remove from active reports
            del self.active_reports[report_id]
            
            return True
        
        return False
    
    async def auto_join_report(self, target: str, reason: str, accounts_count: int) -> Dict:
        """Auto-join and report system"""
        try:
            # Parse target
            target_info = await self._parse_target(target, "channel")
            
            if not target_info.is_accessible:
                return {"success": False, "error": target_info.error}
            
            # Get accounts
            accounts = await self.connection_pool.get_available_accounts(accounts_count)
            
            if not accounts:
                return {"success": False, "error": "هیچ حسابی در دسترس نیست"}
            
            results = {
                "successful_joins": 0,
                "successful_reports": 0,
                "failed": 0,
                "details": []
            }
            
            # Process each account
            for account in accounts:
                try:
                    client = await self.connection_pool.get_client(account.phone_number)
                    if not client:
                        results["failed"] += 1
                        continue
                    
                    # Join the channel
                    try:
                        await client.join_chat(target_info.username or target_info.chat_id)
                        results["successful_joins"] += 1
                        
                        # Wait random time (10-30 seconds)
                        wait_time = random.uniform(10, 30)
                        await asyncio.sleep(wait_time)
                        
                        # View recent posts
                        await self._view_recent_posts(client, target_info.chat_id)
                        
                        # Report
                        telegram_reason = self.REPORT_REASONS.get(reason, "other")
                        success = await self._report_channel(client, target_info, telegram_reason)
                        
                        if success:
                            results["successful_reports"] += 1
                        
                        # Wait before leaving
                        await asyncio.sleep(random.uniform(5, 15))
                        
                        # Leave channel
                        try:
                            await client.leave_chat(target_info.chat_id)
                        except:
                            pass
                        
                        # Clean session traces
                        await self.anti_detection.clean_session_traces(client)
                        
                        results["details"].append({
                            "account": account.phone_number,
                            "joined": True,
                            "reported": success,
                            "left": True
                        })
                        
                    except (UserNotParticipant, ChatAdminRequired):
                        # Can't join, try direct report
                        success = await self._report_channel(client, target_info, 
                                                           self.REPORT_REASONS.get(reason, "other"))
                        if success:
                            results["successful_reports"] += 1
                        
                        results["details"].append({
                            "account": account.phone_number,
                            "joined": False,
                            "reported": success,
                            "left": False
                        })
                    
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "account": account.phone_number,
                        "error": str(e)
                    })
                
                # Delay between accounts
                await asyncio.sleep(random.uniform(3, 8))
            
            return {
                "success": True,
                "results": results,
                "total_accounts": len(accounts)
            }
            
        except Exception as e:
            logger.error(f"Auto-join report failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _view_recent_posts(self, client: Client, chat_id: int, count: int = 3):
        """View recent posts to simulate human behavior"""
        try:
            messages = []
            async for message in client.get_chat_history(chat_id, limit=count):
                messages.append(message)
            
            # Simulate viewing each message
            for message in messages:
                # Random view duration (3-8 seconds)
                view_time = random.uniform(3, 8)
                await asyncio.sleep(view_time)
                
                # Random chance to like
                if random.random() < 0.3:  # 30% chance
                    try:
                        await client.send_reaction(
                            chat_id=chat_id,
                            message_id=message.id,
                            emoji="👍"
                        )
                    except:
                        pass
                
                # Random delay between views
                await asyncio.sleep(random.uniform(1, 3))
                
        except Exception as e:
            logger.debug(f"View posts failed: {e}")
    
    async def view_and_report(self, target: str, accounts_count: int) -> Dict:
        """View posts before reporting"""
        try:
            # Parse target
            target_info = await self._parse_target(target, "channel")
            
            if not target_info.is_accessible:
                return {"success": False, "error": target_info.error}
            
            # Get accounts
            accounts = await self.connection_pool.get_available_accounts(accounts_count)
            
            if not accounts:
                return {"success": False, "error": "هیچ حسابی در دسترس نیست"}
            
            results = {
                "viewed": 0,
                "reported": 0,
                "failed": 0,
                "details": []
            }
            
            # Process each account
            for account in accounts:
                try:
                    client = await self.connection_pool.get_client(account.phone_number)
                    if not client:
                        results["failed"] += 1
                        continue
                    
                    # View posts
                    await self._view_recent_posts(client, target_info.chat_id, random.randint(3, 5))
                    results["viewed"] += 1
                    
                    # Report after viewing
                    success = await self._report_channel(
                        client, target_info, "spam"  # Default reason for this mode
                    )
                    
                    if success:
                        results["reported"] += 1
                    
                    results["details"].append({
                        "account": account.phone_number,
                        "viewed": True,
                        "reported": success
                    })
                    
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "account": account.phone_number,
                        "error": str(e)
                    })
                
                # Delay between accounts
                await asyncio.sleep(random.uniform(5, 10))
            
            return {
                "success": True,
                "results": results,
                "total_accounts": len(accounts)
            }
            
        except Exception as e:
            logger.error(f"View and report failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def report_to_notoscam(self, text: str, accounts_count: int) -> Dict:
        """Report to @notoscam channel"""
        try:
            notoscam_channel = "@notoscam"
            
            # Get accounts
            accounts = await self.connection_pool.get_available_accounts(accounts_count)
            
            if not accounts:
                return {"success": False, "error": "هیچ حسابی در دسترس نیست"}
            
            results = {
                "sent": 0,
                "failed": 0,
                "details": []
            }
            
            # Format message
            message = f"گزارش: {text}\n\nارسال شده توسط ربات گزارش‌گیری"
            
            # Send from each account
            for account in accounts:
                try:
                    client = await self.connection_pool.get_client(account.phone_number)
                    if not client:
                        results["failed"] += 1
                        continue
                    
                    # Send message
                    await client.send_message(
                        chat_id=notoscam_channel,
                        text=message
                    )
                    
                    results["sent"] += 1
                    results["details"].append({
                        "account": account.phone_number,
                        "status": "sent"
                    })
                    
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "account": account.phone_number,
                        "error": str(e)
                    })
                
                # Delay between accounts
                await asyncio.sleep(random.uniform(3, 7))
            
            return {
                "success": True,
                "results": results,
                "total_accounts": len(accounts)
            }
            
        except Exception as e:
            logger.error(f"Notoscam report failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_active_reports_count(self) -> int:
        """Get number of active reports"""
        return len(self.active_reports)
    
    async def cleanup_old_reports(self, days: int = 7):
        """Clean up old reports from memory"""
        current_time = datetime.now()
        to_remove = []
        
        for report_id, progress in self.active_reports.items():
            if progress.status in [ReportStatus.COMPLETED, ReportStatus.FAILED, ReportStatus.CANCELLED]:
                elapsed_hours = (current_time - progress.start_time).total_seconds() / 3600
                if elapsed_hours > 24:  # Remove after 24 hours
                    to_remove.append(report_id)
        
        for report_id in to_remove:
            del self.active_reports[report_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old reports from memory")

# Utility functions
def extract_forward_source(forwarded_message) -> Optional[Dict]:
    """Extract source information from forwarded message"""
    try:
        if not hasattr(forwarded_message, 'forward_from_chat') and not hasattr(forwarded_message, 'forward_from'):
            return None
        
        source = {}
        
        if forwarded_message.forward_from_chat:
            source['type'] = forwarded_message.forward_from_chat.type
            source['id'] = forwarded_message.forward_from_chat.id
            source['username'] = forwarded_message.forward_from_chat.username
            source['title'] = forwarded_message.forward_from_chat.title
            
            if hasattr(forwarded_message, 'forward_from_message_id'):
                source['message_id'] = forwarded_message.forward_from_message_id
        
        elif forwarded_message.forward_from:
            source['type'] = 'user'
            source['id'] = forwarded_message.forward_from.id
            source['username'] = forwarded_message.forward_from.username
            source['first_name'] = forwarded_message.forward_from.first_name
            source['last_name'] = forwarded_message.forward_from.last_name
        
        return source if source else None
        
    except Exception as e:
        logger.error(f"Failed to extract forward source: {e}")
        return None

if __name__ == "__main__":
    # Test report engine
    import asyncio
    
    async def test():
        from connection_pool import ConnectionPool
        from anti_detection import AntiDetectionSystem
        
        config = get_config()
        session_manager = None  # Mock
        connection_pool = ConnectionPool(config, session_manager)
        anti_detection = AntiDetectionSystem()
        
        engine = ReportEngine(connection_pool, anti_detection)
        
        print(f"Report engine initialized")
        print(f"Active reports: {engine.get_active_reports_count()}")
    
    asyncio.run(test())