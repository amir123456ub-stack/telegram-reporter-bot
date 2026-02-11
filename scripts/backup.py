#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backup Script - Database and session backup utilities
Lines: ~200
"""

import os
import sys
import shutil
import sqlite3
import asyncio
import logging
import json
import zipfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import get_config
from database import DatabaseManager
from utils.logger import setup_logger
from utils.security import SecurityManager, encrypt_file

logger = logging.getLogger(__name__)

class BackupManager:
    """Manage system backups"""
    
    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.security = SecurityManager()
        
        # Backup directories
        self.backup_dir = Path("backups")
        self.db_backup_dir = self.backup_dir / "database"
        self.session_backup_dir = self.backup_dir / "sessions"
        self.config_backup_dir = self.backup_dir / "config"
        
        # Create directories
        self.backup_dir.mkdir(exist_ok=True)
        self.db_backup_dir.mkdir(exist_ok=True)
        self.session_backup_dir.mkdir(exist_ok=True)
        self.config_backup_dir.mkdir(exist_ok=True)
    
    def backup_database(self, encrypt: bool = True) -> Optional[Path]:
        """
        Backup database file
        
        Args:
            encrypt: Encrypt backup file
            
        Returns:
            Path to backup file if successful
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            db_path = Path("bot_database.db")
            
            if not db_path.exists():
                logger.error("Database file not found")
                return None
            
            # Create backup filename
            backup_filename = f"db_backup_{timestamp}.db"
            backup_path = self.db_backup_dir / backup_filename
            
            # Copy database file
            shutil.copy2(db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            
            # Compress backup
            zip_filename = f"db_backup_{timestamp}.zip"
            zip_path = self.db_backup_dir / zip_filename
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(backup_path, backup_filename)
            
            # Remove uncompressed file
            backup_path.unlink()
            
            # Encrypt if requested
            if encrypt:
                key = self.security.generate_key(self.config.security.encryption_key)
                encrypted_path = encrypt_file(str(zip_path), key)
                
                if encrypted_path:
                    # Remove unencrypted zip
                    zip_path.unlink()
                    logger.info(f"Database backup encrypted: {encrypted_path}")
                    return Path(encrypted_path)
            
            logger.info(f"Database backup created: {zip_path}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return None
    
    def backup_sessions(self, encrypt: bool = True) -> Optional[Path]:
        """
        Backup all session files
        
        Args:
            encrypt: Encrypt backup file
            
        Returns:
            Path to backup file if successful
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sessions_dir = Path("sessions")
            
            if not sessions_dir.exists():
                logger.warning("Sessions directory not found")
                return None
            
            # Create backup filename
            backup_filename = f"sessions_backup_{timestamp}.zip"
            backup_path = self.session_backup_dir / backup_filename
            
            # Create zip archive
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for session_file in sessions_dir.glob("*"):
                    if session_file.is_file():
                        zipf.write(session_file, session_file.name)
            
            logger.info(f"Sessions backed up to {backup_path}")
            
            # Encrypt if requested
            if encrypt:
                key = self.security.generate_key(self.config.security.encryption_key)
                encrypted_path = encrypt_file(str(backup_path), key)
                
                if encrypted_path:
                    backup_path.unlink()
                    logger.info(f"Sessions backup encrypted: {encrypted_path}")
                    return Path(encrypted_path)
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to backup sessions: {e}")
            return None
    
    def backup_config(self) -> Optional[Path]:
        """
        Backup configuration files
        
        Returns:
            Path to backup file if successful
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"config_backup_{timestamp}.zip"
            backup_path = self.config_backup_dir / backup_filename
            
            # Files to backup
            files_to_backup = [
                ".env",
                "config.yaml",
                "config.json",
                "config.toml"
            ]
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in files_to_backup:
                    file_path = Path(file)
                    if file_path.exists():
                        zipf.write(file_path, file_path.name)
            
            logger.info(f"Configuration backed up to {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to backup config: {e}")
            return None
    
    def create_full_backup(self) -> Optional[Path]:
        """
        Create full system backup
        
        Returns:
            Path to backup file if successful
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"full_backup_{timestamp}.zip"
            backup_path = self.backup_dir / backup_filename
            
            # Create temp directory for backup files
            temp_dir = self.backup_dir / f"temp_{timestamp}"
            temp_dir.mkdir(exist_ok=True)
            
            # Backup database
            db_backup = self.backup_database(encrypt=False)
            if db_backup and db_backup.exists():
                shutil.copy2(db_backup, temp_dir / db_backup.name)
            
            # Backup sessions
            sessions_backup = self.backup_sessions(encrypt=False)
            if sessions_backup and sessions_backup.exists():
                shutil.copy2(sessions_backup, temp_dir / sessions_backup.name)
            
            # Backup config
            config_backup = self.backup_config()
            if config_backup and config_backup.exists():
                shutil.copy2(config_backup, temp_dir / config_backup.name)
            
            # Backup logs
            logs_dir = Path("logs")
            if logs_dir.exists():
                logs_backup = self._backup_logs(temp_dir)
            
            # Create backup info file
            info = {
                "timestamp": timestamp,
                "date": datetime.now().isoformat(),
                "version": self.config.to_dict().get("bot_version", "3.0.0"),
                "components": {
                    "database": bool(db_backup),
                    "sessions": bool(sessions_backup),
                    "config": bool(config_backup),
                    "logs": bool(logs_dir.exists())
                }
            }
            
            info_path = temp_dir / "backup_info.json"
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2, ensure_ascii=False)
            
            # Create final zip
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in temp_dir.glob("*"):
                    zipf.write(file, file.name)
            
            # Cleanup temp directory
            shutil.rmtree(temp_dir)
            
            logger.info(f"Full backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create full backup: {e}")
            return None
    
    def _backup_logs(self, temp_dir: Path) -> Optional[Path]:
        """
        Backup log files
        
        Args:
            temp_dir: Temporary directory to store backup
            
        Returns:
            Path to backup file if successful
        """
        try:
            logs_dir = Path("logs")
            log_files = list(logs_dir.glob("*.log"))
            
            if not log_files:
                return None
            
            backup_filename = "logs_backup.zip"
            backup_path = temp_dir / backup_filename
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for log_file in log_files:
                    if log_file.is_file():
                        zipf.write(log_file, log_file.name)
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to backup logs: {e}")
            return None
    
    def cleanup_old_backups(self, days: int = 30) -> int:
        """
        Delete backups older than specified days
        
        Args:
            days: Delete backups older than X days
            
        Returns:
            Number of deleted files
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0
            
            # Check all backup directories
            backup_dirs = [
                self.db_backup_dir,
                self.session_backup_dir,
                self.config_backup_dir,
                self.backup_dir
            ]
            
            for backup_dir in backup_dirs:
                if not backup_dir.exists():
                    continue
                
                for backup_file in backup_dir.glob("*"):
                    if backup_file.is_file():
                        # Get file modification time
                        mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                        
                        if mtime < cutoff_date:
                            backup_file.unlink()
                            deleted_count += 1
                            logger.debug(f"Deleted old backup: {backup_file}")
            
            logger.info(f"Cleaned up {deleted_count} old backup files")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
            return 0
    
    async def schedule_backup(self, interval_hours: int = 24):
        """
        Schedule automatic backups
        
        Args:
            interval_hours: Backup interval in hours
        """
        while True:
            try:
                logger.info("Running scheduled backup...")
                
                # Create backup
                backup_path = self.create_full_backup()
                
                if backup_path:
                    logger.info(f"Scheduled backup created: {backup_path}")
                    
                    # Cleanup old backups
                    self.cleanup_old_backups(30)
                
                # Wait for next backup
                await asyncio.sleep(interval_hours * 3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduled backup failed: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retry

def backup_database(encrypt: bool = True) -> Optional[str]:
    """Convenience function to backup database"""
    manager = BackupManager()
    result = manager.backup_database(encrypt)
    return str(result) if result else None

def backup_sessions(encrypt: bool = True) -> Optional[str]:
    """Convenience function to backup sessions"""
    manager = BackupManager()
    result = manager.backup_sessions(encrypt)
    return str(result) if result else None

def cleanup_old_backups(days: int = 30) -> int:
    """Convenience function to cleanup old backups"""
    manager = BackupManager()
    return manager.cleanup_old_backups(days)

def main():
    """Main entry point"""
    # Setup logging
    setup_logger("backup", log_level="INFO")
    
    logger.info("=" * 50)
    logger.info("Backup Script")
    logger.info("=" * 50)
    
    import argparse
    parser = argparse.ArgumentParser(description="Backup utilities")
    parser.add_argument("--type", choices=["db", "sessions", "config", "full", "cleanup"],
                       default="full", help="Backup type")
    parser.add_argument("--no-encrypt", action="store_true", help="Disable encryption")
    parser.add_argument("--days", type=int, default=30, help="Cleanup days")
    
    args = parser.parse_args()
    
    manager = BackupManager()
    
    if args.type == "db":
        result = manager.backup_database(encrypt=not args.no_encrypt)
        if result:
            logger.info(f"✅ Database backup created: {result}")
            return 0
    
    elif args.type == "sessions":
        result = manager.backup_sessions(encrypt=not args.no_encrypt)
        if result:
            logger.info(f"✅ Sessions backup created: {result}")
            return 0
    
    elif args.type == "config":
        result = manager.backup_config()
        if result:
            logger.info(f"✅ Config backup created: {result}")
            return 0
    
    elif args.type == "full":
        result = manager.create_full_backup()
        if result:
            logger.info(f"✅ Full backup created: {result}")
            return 0
    
    elif args.type == "cleanup":
        deleted = manager.cleanup_old_backups(args.days)
        logger.info(f"✅ Cleaned up {deleted} old backup files")
        return 0
    
    return 1

if __name__ == "__main__":
    sys.exit(main())