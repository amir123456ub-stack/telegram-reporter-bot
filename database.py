#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Manager - Database operations and ORM
Lines: ~1200
"""

import asyncio
import logging
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
import aiosqlite

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database manager with async operations"""
    
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = Path(db_path)
        self.connection_pool = None
        self._init_database_sync()
    
    def _init_database_sync(self):
        """Initialize database synchronously (for table creation)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create tables
            self._create_tables(cursor)
            
            conn.commit()
            conn.close()
            
            logger.info(f"Database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _create_tables(self, cursor: sqlite3.Cursor):
        """Create all database tables"""
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_admin BOOLEAN DEFAULT FALSE,
                is_banned BOOLEAN DEFAULT FALSE,
                ban_reason TEXT,
                subscription_end TIMESTAMP,
                reports_today INTEGER DEFAULT 0,
                total_reports INTEGER DEFAULT 0,
                last_report_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                language_code TEXT DEFAULT 'fa'
            )
        """)
        
        # Create index on user_id
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_end)")
        
        # Accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                session_path TEXT,
                session_string TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                is_banned BOOLEAN DEFAULT FALSE,
                health_status TEXT DEFAULT 'unknown',
                last_used TIMESTAMP,
                total_reports INTEGER DEFAULT 0,
                successful_reports INTEGER DEFAULT 0,
                failed_reports INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                device_model TEXT,
                app_version TEXT,
                last_health_check TIMESTAMP,
                error_count INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_phone ON accounts(phone_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_active ON accounts(is_active)")
        
        # Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT NOT NULL,
                target TEXT NOT NULL,
                target_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                custom_text TEXT,
                accounts_used INTEGER DEFAULT 0,
                successful_reports INTEGER DEFAULT 0,
                failed_reports INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                scheduled BOOLEAN DEFAULT FALSE,
                schedule_interval TEXT,
                next_run TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)")
        
        # Report history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                target TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                response_time FLOAT,
                FOREIGN KEY (report_id) REFERENCES reports(id),
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_report ON report_history(report_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_account ON report_history(account_id)")
        
        # Scheduled jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                job_id TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                target TEXT NOT NULL,
                target_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                account_count INTEGER NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                timezone TEXT DEFAULT 'Asia/Tehran',
                max_executions INTEGER DEFAULT 0,
                current_execution INTEGER DEFAULT 0,
                last_executed TIMESTAMP,
                next_run TIMESTAMP,
                status TEXT DEFAULT 'pending',
                enabled BOOLEAN DEFAULT TRUE,
                total_success INTEGER DEFAULT 0,
                total_failed INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON scheduled_jobs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON scheduled_jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON scheduled_jobs(next_run)")
        
        # Subscription logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT NOT NULL,
                admin_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                days INTEGER,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Audit logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                target_user_id BIGINT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_admin ON audit_logs(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)")
        
        # System logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                module TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_created ON system_logs(created_at)")
        
        # User sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT NOT NULL,
                session_id TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")
        
        logger.info("Database tables created/verified")
    
    async def init_tables(self):
        """Initialize tables asynchronously"""
        # Tables are already created in __init__
        pass
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Get database connection"""
        try:
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            return conn
        except Exception as e:
            logger.error(f"Failed to get database connection: {e}")
            raise
    
    # ===== USER OPERATIONS =====
    
    async def register_user(self, user_id: int, username: str = None, 
                           first_name: str = None, last_name: str = None):
        """Register or update user"""
        try:
            async with await self.get_connection() as conn:
                # Check if user exists
                cursor = await conn.execute(
                    "SELECT id FROM users WHERE user_id = ?",
                    (user_id,)
                )
                existing = await cursor.fetchone()
                await cursor.close()
                
                if existing:
                    # Update existing user
                    await conn.execute("""
                        UPDATE users SET 
                        username = COALESCE(?, username),
                        first_name = COALESCE(?, first_name),
                        last_name = COALESCE(?, last_name),
                        last_active = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (username, first_name, last_name, user_id))
                else:
                    # Insert new user
                    await conn.execute("""
                        INSERT INTO users 
                        (user_id, username, first_name, last_name, created_at, last_active)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (user_id, username, first_name, last_name))
                
                await conn.commit()
                
                logger.info(f"User registered/updated: {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to register user {user_id}: {e}")
            return False
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM users WHERE user_id = ?
                """, (user_id,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
    
    async def update_user_last_active(self, user_id: int):
        """Update user's last active time"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET last_active = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update user last active {user_id}: {e}")
            return False
    
    async def check_subscription(self, user_id: int) -> bool:
        """Check if user has active subscription"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT subscription_end FROM users 
                    WHERE user_id = ? AND is_banned = FALSE
                """, (user_id,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                if not row:
                    return False
                
                sub_end = row["subscription_end"]
                if not sub_end:
                    return False
                
                # Parse datetime if it's string
                if isinstance(sub_end, str):
                    from datetime import datetime
                    sub_end = datetime.fromisoformat(sub_end.replace('Z', '+00:00'))
                
                # Check if subscription is still valid
                return sub_end > datetime.now()
                
        except Exception as e:
            logger.error(f"Failed to check subscription for {user_id}: {e}")
            return False
    
    async def grant_subscription(self, user_id: int, end_date: datetime):
        """Grant subscription to user"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET subscription_end = ?
                    WHERE user_id = ?
                """, (end_date, user_id))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to grant subscription to {user_id}: {e}")
            return False
    
    async def revoke_subscription(self, user_id: int):
        """Revoke user subscription"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET subscription_end = NULL
                    WHERE user_id = ?
                """, (user_id,))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to revoke subscription for {user_id}: {e}")
            return False
    
    async def get_subscription_info(self, user_id: int) -> Dict:
        """Get subscription information"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT subscription_end, is_banned FROM users 
                    WHERE user_id = ?
                """, (user_id,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                if not row:
                    return {}
                
                sub_end = row["subscription_end"]
                is_banned = row["is_banned"]
                
                result = {
                    "has_active_subscription": False,
                    "subscription_end": sub_end,
                    "is_banned": is_banned
                }
                
                if sub_end:
                    if isinstance(sub_end, str):
                        from datetime import datetime
                        sub_end = datetime.fromisoformat(sub_end.replace('Z', '+00:00'))
                    
                    result["has_active_subscription"] = (
                        not is_banned and sub_end > datetime.now()
                    )
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to get subscription info for {user_id}: {e}")
            return {}
    
    async def ban_user(self, user_id: int, reason: str = "بدون دلیل"):
        """Ban a user"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET is_banned = TRUE, ban_reason = ?
                    WHERE user_id = ?
                """, (reason, user_id))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to ban user {user_id}: {e}")
            return False
    
    async def unban_user(self, user_id: int):
        """Unban a user"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET is_banned = FALSE, ban_reason = NULL
                    WHERE user_id = ?
                """, (user_id,))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to unban user {user_id}: {e}")
            return False
    
    async def is_user_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT is_banned FROM users WHERE user_id = ?
                """, (user_id,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["is_banned"] if row else False
                
        except Exception as e:
            logger.error(f"Failed to check ban status for {user_id}: {e}")
            return True  # Assume banned on error
    
    async def update_user_admin_status(self, user_id: int, is_admin: bool):
        """Update user admin status"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET is_admin = ?
                    WHERE user_id = ?
                """, (is_admin, user_id))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update admin status for {user_id}: {e}")
            return False
    
    async def check_rate_limit(self, user_id: int, max_per_hour: int = 10) -> bool:
        """Check if user has exceeded rate limit"""
        try:
            async with await self.get_connection() as conn:
                # Get reports count in last hour
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM reports 
                    WHERE user_id = ? 
                    AND created_at > datetime('now', '-1 hour')
                """, (user_id,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                count = row["count"] if row else 0
                
                return count < max_per_hour
                
        except Exception as e:
            logger.error(f"Failed to check rate limit for {user_id}: {e}")
            return False
    
    # ===== REPORT OPERATIONS =====
    
    async def create_report(self, user_id: int, target: str, target_type: str, 
                           reason: str, account_count: int) -> int:
        """Create a new report"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    INSERT INTO reports 
                    (user_id, target, target_type, reason, accounts_used, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, target, target_type, reason, account_count))
                
                report_id = cursor.lastrowid
                await cursor.close()
                
                # Update user stats
                await conn.execute("""
                    UPDATE users SET 
                    total_reports = total_reports + 1,
                    reports_today = reports_today + 1,
                    last_report_time = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
                
                await conn.commit()
                
                logger.info(f"Report created: {report_id} for user {user_id}")
                return report_id
                
        except Exception as e:
            logger.error(f"Failed to create report: {e}")
            raise
    
    async def update_report_status(self, report_id: int, status: str, 
                                  successful: int = None, failed: int = None,
                                  error_message: str = None):
        """Update report status"""
        try:
            async with await self.get_connection() as conn:
                update_fields = []
                params = []
                
                update_fields.append("status = ?")
                params.append(status)
                
                if successful is not None:
                    update_fields.append("successful_reports = ?")
                    params.append(successful)
                
                if failed is not None:
                    update_fields.append("failed_reports = ?")
                    params.append(failed)
                
                if error_message:
                    update_fields.append("error_message = ?")
                    params.append(error_message)
                
                if status in ["completed", "failed", "cancelled"]:
                    update_fields.append("completed_at = CURRENT_TIMESTAMP")
                
                update_fields.append("accounts_used = COALESCE(?, accounts_used)")
                params.append((successful or 0) + (failed or 0))
                
                params.append(report_id)
                
                query = f"""
                    UPDATE reports SET 
                    {', '.join(update_fields)}
                    WHERE id = ?
                """
                
                await conn.execute(query, params)
                await conn.commit()
                
                logger.debug(f"Report {report_id} status updated to {status}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update report {report_id}: {e}")
            return False
    
    async def get_report(self, report_id: int) -> Optional[Dict]:
        """Get report by ID"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM reports WHERE id = ?
                """, (report_id,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get report {report_id}: {e}")
            return None
    
    async def add_report_history(self, report_id: int, account_id: str, 
                                target: str, reason: str, status: str,
                                error_message: str = None):
        """Add entry to report history"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO report_history 
                    (report_id, account_id, target, reason, status, error_message, executed_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (report_id, account_id, target, reason, status, error_message))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to add report history: {e}")
            return False
    
    async def get_user_reports(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get user's reports"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM reports 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (user_id, limit))
                
                rows = await cursor.fetchall()
                await cursor.close()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get reports for user {user_id}: {e}")
            return []
    
    async def get_reports_paginated(self, page: int, page_size: int = 10) -> List[Dict]:
        """Get paginated reports"""
        try:
            offset = (page - 1) * page_size
            
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM reports 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (page_size, offset))
                
                rows = await cursor.fetchall()
                await cursor.close()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get paginated reports: {e}")
            return []
    
    # ===== ACCOUNT OPERATIONS =====
    
    async def update_account_stats(self, phone_number: str, successful: int = 0):
        """Update account statistics"""
        try:
            async with await self.get_connection() as conn:
                if successful > 0:
                    await conn.execute("""
                        UPDATE accounts SET 
                        total_reports = total_reports + 1,
                        successful_reports = successful_reports + 1,
                        last_used = CURRENT_TIMESTAMP
                        WHERE phone_number = ?
                    """, (phone_number,))
                else:
                    await conn.execute("""
                        UPDATE accounts SET 
                        total_reports = total_reports + 1,
                        failed_reports = failed_reports + 1,
                        last_used = CURRENT_TIMESTAMP
                        WHERE phone_number = ?
                    """, (phone_number,))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update account stats for {phone_number}: {e}")
            return False
    
    async def update_account_health(self, phone_number: str, health_status: str):
        """Update account health status"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    UPDATE accounts SET 
                    health_status = ?,
                    last_health_check = CURRENT_TIMESTAMP
                    WHERE phone_number = ?
                """, (health_status, phone_number))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update account health for {phone_number}: {e}")
            return False
    
    async def ban_account(self, phone_number: str):
        """Ban an account"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    UPDATE accounts SET 
                    is_banned = TRUE,
                    is_active = FALSE
                    WHERE phone_number = ?
                """, (phone_number,))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to ban account {phone_number}: {e}")
            return False
    
    # ===== SCHEDULED JOBS OPERATIONS =====
    
    async def create_scheduled_job(self, job_data: Dict) -> bool:
        """Create a scheduled job"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO scheduled_jobs 
                    (job_id, user_id, target, target_type, reason, account_count,
                     schedule_type, schedule_value, timezone, max_executions,
                     current_execution, next_run, status, enabled,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    job_data["job_id"],
                    job_data["user_id"],
                    job_data["target"],
                    job_data["target_type"],
                    job_data["reason"],
                    job_data["account_count"],
                    job_data["schedule_type"],
                    job_data["schedule_value"],
                    job_data.get("timezone", "Asia/Tehran"),
                    job_data.get("max_executions", 0),
                    job_data.get("current_execution", 0),
                    job_data.get("next_run"),
                    job_data.get("status", "pending"),
                    job_data.get("enabled", True)
                ))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to create scheduled job: {e}")
            return False
    
    async def update_scheduled_job(self, job_data: Dict) -> bool:
        """Update scheduled job"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    UPDATE scheduled_jobs SET
                    user_id = ?, target = ?, target_type = ?, reason = ?,
                    account_count = ?, schedule_type = ?, schedule_value = ?,
                    timezone = ?, max_executions = ?, current_execution = ?,
                    last_executed = ?, next_run = ?, status = ?, enabled = ?,
                    total_success = ?, total_failed = ?, last_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ?
                """, (
                    job_data["user_id"],
                    job_data["target"],
                    job_data["target_type"],
                    job_data["reason"],
                    job_data["account_count"],
                    job_data["schedule_type"],
                    job_data["schedule_value"],
                    job_data.get("timezone", "Asia/Tehran"),
                    job_data.get("max_executions", 0),
                    job_data.get("current_execution", 0),
                    job_data.get("last_executed"),
                    job_data.get("next_run"),
                    job_data.get("status", "pending"),
                    job_data.get("enabled", True),
                    job_data.get("total_success", 0),
                    job_data.get("total_failed", 0),
                    job_data.get("last_error"),
                    job_data["job_id"]
                ))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update scheduled job {job_data.get('job_id')}: {e}")
            return False
    
    async def delete_scheduled_job(self, job_id: str) -> bool:
        """Delete scheduled job"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    DELETE FROM scheduled_jobs WHERE job_id = ?
                """, (job_id,))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete scheduled job {job_id}: {e}")
            return False
    
    async def get_scheduled_jobs(self) -> List[Dict]:
        """Get all scheduled jobs"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM scheduled_jobs ORDER BY next_run ASC
                """)
                
                rows = await cursor.fetchall()
                await cursor.close()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get scheduled jobs: {e}")
            return []
    
    async def cleanup_old_jobs(self, days: int = 30):
        """Clean up old completed/failed jobs"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    DELETE FROM scheduled_jobs 
                    WHERE status IN ('completed', 'failed', 'cancelled')
                    AND updated_at < datetime('now', ?)
                """, (f'-{days} days',))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return False
    
    # ===== STATISTICS OPERATIONS =====
    
    async def get_user_count(self) -> int:
        """Get total user count"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) as count FROM users")
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["count"] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get user count: {e}")
            return 0
    
    async def get_active_users_count(self, hours: int = 24) -> int:
        """Get count of active users in last N hours"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(DISTINCT user_id) as count 
                    FROM reports 
                    WHERE created_at > datetime('now', ?)
                """, (f'-{hours} hours',))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["count"] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get active users count: {e}")
            return 0
    
    async def get_banned_users_count(self) -> int:
        """Get count of banned users"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM users WHERE is_banned = TRUE
                """)
                
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["count"] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get banned users count: {e}")
            return 0
    
    async def get_total_reports_count(self) -> int:
        """Get total reports count"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) as count FROM reports")
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["count"] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get total reports count: {e}")
            return 0
    
    async def get_successful_reports_count(self) -> int:
        """Get count of successful reports"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM reports 
                    WHERE status = 'completed' AND successful_reports > 0
                """)
                
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["count"] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get successful reports count: {e}")
            return 0
    
    async def get_successful_reports_count_since(self, hours: int) -> int:
        """Get count of successful reports since N hours ago"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM reports 
                    WHERE status = 'completed' 
                    AND successful_reports > 0
                    AND created_at > datetime('now', ?)
                """, (f'-{hours} hours',))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["count"] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get successful reports count since {hours}h: {e}")
            return 0
    
    async def get_reports_count_by_date(self, date: datetime.date) -> int:
        """Get reports count for specific date"""
        try:
            date_str = date.strftime("%Y-%m-%d")
            
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM reports 
                    WHERE DATE(created_at) = ?
                """, (date_str,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["count"] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get reports count for {date}: {e}")
            return 0
    
    async def get_reports_count_since(self, hours: int) -> int:
        """Get reports count since N hours ago"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM reports 
                    WHERE created_at > datetime('now', ?)
                """, (f'-{hours} hours',))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["count"] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get reports count since {hours}h: {e}")
            return 0
    
    async def get_registrations_count(self, date: datetime.date) -> int:
        """Get registrations count for specific date"""
        try:
            date_str = date.strftime("%Y-%m-%d")
            
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM users 
                    WHERE DATE(created_at) = ?
                """, (date_str,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["count"] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get registrations count for {date}: {e}")
            return 0
    
    async def get_average_report_time(self) -> float:
        """Get average report completion time in seconds"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT AVG(
                        CAST(strftime('%s', completed_at) AS INTEGER) - 
                        CAST(strftime('%s', created_at) AS INTEGER)
                    ) as avg_time
                    FROM reports 
                    WHERE status = 'completed' 
                    AND completed_at IS NOT NULL
                """)
                
                row = await cursor.fetchone()
                await cursor.close()
                
                return row["avg_time"] if row and row["avg_time"] else 0.0
                
        except Exception as e:
            logger.error(f"Failed to get average report time: {e}")
            return 0.0
    
    async def get_users_paginated(self, page: int, page_size: int = 10) -> List[Dict]:
        """Get paginated users"""
        try:
            offset = (page - 1) * page_size
            
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM users 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (page_size, offset))
                
                rows = await cursor.fetchall()
                await cursor.close()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get paginated users: {e}")
            return []
    
    async def get_all_user_ids(self) -> List[int]:
        """Get all user IDs"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute("SELECT user_id FROM users")
                rows = await cursor.fetchall()
                await cursor.close()
                
                return [row["user_id"] for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get all user IDs: {e}")
            return []
    
    # ===== AUDIT LOGS =====
    
    async def log_admin_action(self, admin_id: int, action: str, 
                              target_user_id: int = None, details: str = ""):
        """Log admin action"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO audit_logs 
                    (admin_id, action, target_user_id, details, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (admin_id, action, target_user_id, details))
                
                await conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")
            return False
    
    async def get_audit_logs_paginated(self, page: int, page_size: int = 10) -> List[Dict]:
        """Get paginated audit logs"""
        try:
            offset = (page - 1) * page_size
            
            async with await self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM audit_logs 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (page_size, offset))
                
                rows = await cursor.fetchall()
                await cursor.close()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get audit logs: {e}")
            return []
    
    # ===== MAINTENANCE OPERATIONS =====
    
    async def cleanup_old_data(self, days: int = 30):
        """Clean up old data"""
        try:
            async with await self.get_connection() as conn:
                # Clean up old reports
                await conn.execute("""
                    DELETE FROM reports 
                    WHERE created_at < datetime('now', ?)
                    AND status IN ('completed', 'failed', 'cancelled')
                """, (f'-{days} days',))
                
                # Clean up old report history
                await conn.execute("""
                    DELETE FROM report_history 
                    WHERE executed_at < datetime('now', ?)
                """, (f'-{days} days',))
                
                # Clean up old system logs
                await conn.execute("""
                    DELETE FROM system_logs 
                    WHERE created_at < datetime('now', ?)
                """, (f'-{days} days',))
                
                # Clean up old audit logs
                await conn.execute("""
                    DELETE FROM audit_logs 
                    WHERE created_at < datetime('now', ?)
                """, (f'-{days} days',))
                
                # Clean up old user sessions
                await conn.execute("""
                    DELETE FROM user_sessions 
                    WHERE last_activity < datetime('now', ?)
                """, (f'-{days} days',))
                
                await conn.commit()
                
                logger.info(f"Cleaned up data older than {days} days")
                return True
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return False
    
    async def reset_daily_counts(self):
        """Reset daily counts (should be called daily)"""
        try:
            async with await self.get_connection() as conn:
                # Reset daily report counts for all users
                await conn.execute("""
                    UPDATE users SET reports_today = 0
                """)
                
                await conn.commit()
                logger.info("Daily counts reset")
                return True
                
        except Exception as e:
            logger.error(f"Failed to reset daily counts: {e}")
            return False
    
    async def backup_database(self, backup_path: str):
        """Create database backup"""
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return False
    
    async def get_database_size(self) -> int:
        """Get database size in bytes"""
        try:
            return self.db_path.stat().st_size if self.db_path.exists() else 0
        except Exception as e:
            logger.error(f"Failed to get database size: {e}")
            return 0
    
    async def optimize_database(self):
        """Optimize database (VACUUM)"""
        try:
            async with await self.get_connection() as conn:
                await conn.execute("VACUUM")
                await conn.commit()
                logger.info("Database optimized")
                return True
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")
            return False
    
    # ===== UTILITY METHODS =====
    
    async def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute raw query"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                await cursor.close()
                
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    async def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute update query and return affected rows"""
        try:
            async with await self.get_connection() as conn:
                cursor = await conn.execute(query, params)
                affected = cursor.rowcount
                await cursor.close()
                await conn.commit()
                
                return affected
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return 0
    
    async def close(self):
        """Close database connection"""
        # Connection is closed automatically with context manager
        pass

# Utility functions for database operations
def format_datetime(dt: datetime) -> str:
    """Format datetime for database"""
    return dt.isoformat()

def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime from database string"""
    from datetime import datetime
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

def calculate_daily_stats(rows: List[Dict]) -> Dict:
    """Calculate daily statistics from rows"""
    stats = {
        "total": len(rows),
        "successful": sum(1 for r in rows if r.get("status") == "completed"),
        "failed": sum(1 for r in rows if r.get("status") == "failed"),
        "pending": sum(1 for r in rows if r.get("status") == "pending"),
    }
    
    if stats["total"] > 0:
        stats["success_rate"] = (stats["successful"] / stats["total"]) * 100
    else:
        stats["success_rate"] = 0
    
    return stats

if __name__ == "__main__":
    # Test database manager
    import asyncio
    
    async def test():
        db = DatabaseManager("test.db")
        
        # Test user registration
        await db.register_user(123456789, "testuser", "Test", "User")
        
        # Test subscription
        end_date = datetime.now() + timedelta(days=30)
        await db.grant_subscription(123456789, end_date)
        
        # Check subscription
        has_sub = await db.check_subscription(123456789)
        print(f"User has subscription: {has_sub}")
        
        # Create report
        report_id = await db.create_report(
            user_id=123456789,
            target="@testchannel",
            target_type="channel",
            reason="spam",
            account_count=5
        )
        print(f"Created report: {report_id}")
        
        # Update report
        await db.update_report_status(report_id, "completed", successful=4, failed=1)
        
        # Get statistics
        user_count = await db.get_user_count()
        report_count = await db.get_total_reports_count()
        print(f"Users: {user_count}, Reports: {report_count}")
        
        # Cleanup
        import os
        if os.path.exists("test.db"):
            os.remove("test.db")
    
    asyncio.run(test())