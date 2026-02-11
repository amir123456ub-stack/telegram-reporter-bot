#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Initialization Script
Lines: ~200
"""

import os
import sys
import sqlite3
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import get_config
from database import DatabaseManager
from utils.logger import setup_logger

logger = logging.getLogger(__name__)

def initialize_database(db_path: str = "bot_database.db") -> bool:
    """
    Initialize the database with all tables and indexes
    
    Args:
        db_path: Path to database file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Initializing database at {db_path}")
        
        # Remove existing database if it exists
        if os.path.exists(db_path):
            backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(db_path, backup_path)
            logger.info(f"Existing database backed up to {backup_path}")
        
        # Create database manager
        db = DatabaseManager(db_path)
        
        # Test connection
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create all tables
        create_tables(cursor)
        
        # Create indexes
        create_indexes(cursor)
        
        # Insert default settings
        insert_default_settings(cursor)
        
        conn.commit()
        conn.close()
        
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def create_tables(cursor: sqlite3.Cursor):
    """Create all database tables"""
    
    logger.info("Creating tables...")
    
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
            successful_reports INTEGER DEFAULT 0,
            failed_reports INTEGER DEFAULT 0,
            last_report_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            language_code TEXT DEFAULT 'fa',
            is_bot BOOLEAN DEFAULT FALSE,
            is_verified BOOLEAN DEFAULT FALSE,
            is_restricted BOOLEAN DEFAULT FALSE
        )
    """)
    
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
            health_score INTEGER DEFAULT 100,
            last_used TIMESTAMP,
            total_reports INTEGER DEFAULT 0,
            successful_reports INTEGER DEFAULT 0,
            failed_reports INTEGER DEFAULT 0,
            total_requests INTEGER DEFAULT 0,
            flood_wait_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            device_model TEXT,
            app_version TEXT,
            system_version TEXT,
            lang_code TEXT DEFAULT 'en',
            last_health_check TIMESTAMP,
            cooldown_until TIMESTAMP,
            concurrent_uses INTEGER DEFAULT 0,
            max_concurrent INTEGER DEFAULT 1
        )
    """)
    
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
            error_message TEXT,
            scheduled BOOLEAN DEFAULT FALSE,
            schedule_interval TEXT,
            next_run TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            duration REAL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    # Report history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            account_id TEXT NOT NULL,
            target TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            response_time REAL DEFAULT 0,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES reports(id)
        )
    """)
    
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
    
    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            type TEXT DEFAULT 'string',
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    logger.info("All tables created successfully")

def create_indexes(cursor: sqlite3.Cursor):
    """Create all database indexes"""
    
    logger.info("Creating indexes...")
    
    # Users indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_end)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users(is_banned)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at)")
    
    # Accounts indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_phone ON accounts(phone_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_active ON accounts(is_active)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_health ON accounts(health_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_last_used ON accounts(last_used)")
    
    # Reports indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_target ON reports(target)")
    
    # Report history indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_report ON report_history(report_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_account ON report_history(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_executed ON report_history(executed_at)")
    
    # Scheduled jobs indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON scheduled_jobs(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON scheduled_jobs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON scheduled_jobs(next_run)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_enabled ON scheduled_jobs(enabled)")
    
    # Logs indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_admin ON audit_logs(admin_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_created ON system_logs(created_at)")
    
    # User sessions indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_activity ON user_sessions(last_activity)")
    
    logger.info("All indexes created successfully")

def insert_default_settings(cursor: sqlite3.Cursor):
    """Insert default settings"""
    
    logger.info("Inserting default settings...")
    
    default_settings = [
        ("bot_name", "Telegram Reporter Bot", "string", "Bot display name"),
        ("bot_version", "3.0.0", "string", "Bot version"),
        ("max_reports_per_hour", "10", "integer", "Maximum reports per user per hour"),
        ("max_reports_per_day", "50", "integer", "Maximum reports per user per day"),
        ("max_accounts_per_report", "50", "integer", "Maximum accounts per report"),
        ("min_delay", "1.2", "float", "Minimum delay between actions"),
        ("max_delay", "4.7", "float", "Maximum delay between actions"),
        ("enable_anti_detection", "true", "boolean", "Enable anti-detection system"),
        ("enable_auto_join", "true", "boolean", "Enable auto-join feature"),
        ("enable_view_report", "true", "boolean", "Enable view+report feature"),
        ("session_rotation_hours", "24", "integer", "Session rotation interval in hours"),
        ("db_cleanup_days", "30", "integer", "Delete data older than X days"),
        ("log_level", "INFO", "string", "Logging level"),
        ("maintenance_mode", "false", "boolean", "Enable maintenance mode"),
        ("admin_contact", "@admin", "string", "Admin contact username"),
        ("support_group", "@support", "string", "Support group username")
    ]
    
    for key, value, type_, description in default_settings:
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value, type, description)
            VALUES (?, ?, ?, ?)
        """, (key, value, type_, description))
    
    logger.info("Default settings inserted")

async def async_init():
    """Async initialization"""
    config = get_config()
    db = DatabaseManager()
    await db.init_tables()
    logger.info("Async database initialization completed")

def main():
    """Main entry point"""
    # Setup logging
    setup_logger("init_db", log_level="INFO")
    
    logger.info("=" * 50)
    logger.info("Database Initialization Script")
    logger.info("=" * 50)
    
    # Initialize database
    if initialize_database():
        logger.info("✅ Database initialized successfully")
        
        # Run async initialization
        asyncio.run(async_init())
        
        logger.info("✅ All initialization tasks completed")
        return 0
    else:
        logger.error("❌ Database initialization failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())