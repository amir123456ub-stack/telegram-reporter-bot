#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session Manager - Handle Telegram session management
Lines: ~1500
"""

import asyncio
import logging
import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
import random
import hashlib
import base64
import pickle

# Cryptography
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Telegram
from pyrogram import Client
from pyrogram.errors import (
    SessionPasswordNeeded, PhoneCodeInvalid,
    PhoneCodeExpired, FloodWait, AuthKeyUnregistered
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from config_manager import get_config

logger = logging.getLogger(__name__)

class SessionEncryptor:
    """Handle session encryption/decryption"""
    
    def __init__(self, encryption_key: str):
        self.key = self._derive_key(encryption_key)
        self.fernet = Fernet(self.key)
    
    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from password"""
        salt = b'telegram_bot_salt_'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt_session(self, session_data: bytes) -> bytes:
        """Encrypt session data"""
        return self.fernet.encrypt(session_data)
    
    def decrypt_session(self, encrypted_data: bytes) -> bytes:
        """Decrypt session data"""
        return self.fernet.decrypt(encrypted_data)
    
    def encrypt_string(self, text: str) -> str:
        """Encrypt string to base64"""
        encrypted = self.fernet.encrypt(text.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_string(self, encrypted_text: str) -> str:
        """Decrypt base64 string"""
        encrypted_bytes = base64.b64decode(encrypted_text)
        return self.fernet.decrypt(encrypted_bytes).decode()

class SessionInfo:
    """Session information container"""
    
    def __init__(self, phone_number: str, session_path: str):
        self.phone_number = phone_number
        self.session_path = Path(session_path)
        self.session_string: Optional[str] = None
        self.device_model: str = ""
        self.app_version: str = ""
        self.created_at: datetime = datetime.now()
        self.last_used: Optional[datetime] = None
        self.is_active: bool = True
        self.is_banned: bool = False
        self.health_status: str = "unknown"
        self.total_reports: int = 0
        self.successful_reports: int = 0
        self.last_error: Optional[str] = None
        
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "phone_number": self.phone_number,
            "session_path": str(self.session_path),
            "session_string": self.session_string,
            "device_model": self.device_model,
            "app_version": self.app_version,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_active": self.is_active,
            "is_banned": self.is_banned,
            "health_status": self.health_status,
            "total_reports": self.total_reports,
            "successful_reports": self.successful_reports,
            "last_error": self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SessionInfo':
        """Create from dictionary"""
        session = cls(data["phone_number"], data["session_path"])
        session.session_string = data.get("session_string")
        session.device_model = data.get("device_model", "")
        session.app_version = data.get("app_version", "")
        
        if "created_at" in data and data["created_at"]:
            session.created_at = datetime.fromisoformat(data["created_at"])
        
        if "last_used" in data and data["last_used"]:
            session.last_used = datetime.fromisoformat(data["last_used"])
        
        session.is_active = data.get("is_active", True)
        session.is_banned = data.get("is_banned", False)
        session.health_status = data.get("health_status", "unknown")
        session.total_reports = data.get("total_reports", 0)
        session.successful_reports = data.get("successful_reports", 0)
        session.last_error = data.get("last_error")
        
        return session

class SessionManager:
    """Manage Telegram sessions"""
    
    def __init__(self, config):
        self.config = config
        self.encryptor = SessionEncryptor(config.security.encryption_key)
        self.sessions: Dict[str, SessionInfo] = {}
        self.active_clients: Dict[str, Client] = {}
        self.session_db_path = Path("sessions/sessions.db")
        self._init_database()
        self._load_sessions()
    
    def _init_database(self):
        """Initialize session database"""
        self.session_db_path.parent.mkdir(exist_ok=True)
        
        conn = sqlite3.connect(self.session_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                phone_number TEXT PRIMARY KEY,
                encrypted_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_health (
                phone_number TEXT PRIMARY KEY,
                health_status TEXT,
                last_check TIMESTAMP,
                error_count INTEGER DEFAULT 0,
                total_reports INTEGER DEFAULT 0,
                successful_reports INTEGER DEFAULT 0,
                FOREIGN KEY (phone_number) REFERENCES sessions(phone_number)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_sessions(self):
        """Load sessions from database"""
        try:
            conn = sqlite3.connect(self.session_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT phone_number, encrypted_data FROM sessions")
            rows = cursor.fetchall()
            
            for phone_number, encrypted_data in rows:
                try:
                    # Decrypt session data
                    decrypted = self.encryptor.decrypt_string(encrypted_data)
                    session_data = json.loads(decrypted)
                    
                    # Create SessionInfo object
                    session_info = SessionInfo.from_dict(session_data)
                    self.sessions[phone_number] = session_info
                    
                except Exception as e:
                    logger.error(f"Failed to load session {phone_number}: {e}")
            
            logger.info(f"Loaded {len(self.sessions)} sessions from database")
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
    
    def _save_session(self, session_info: SessionInfo):
        """Save session to database"""
        try:
            # Convert to dict and encrypt
            session_dict = session_info.to_dict()
            session_json = json.dumps(session_dict)
            encrypted = self.encryptor.encrypt_string(session_json)
            
            conn = sqlite3.connect(self.session_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO sessions 
                (phone_number, encrypted_data, last_updated)
                VALUES (?, ?, ?)
            """, (session_info.phone_number, encrypted, datetime.now()))
            
            conn.commit()
            conn.close()
            
            # Update in-memory cache
            self.sessions[session_info.phone_number] = session_info
            
        except Exception as e:
            logger.error(f"Failed to save session {session_info.phone_number}: {e}")
    
    async def add_account(self, phone_number: str, via_qr: bool = False) -> Tuple[bool, str]:
        """Add a new account to the system"""
        try:
            # Check if already exists
            if phone_number in self.sessions:
                return False, "این شماره قبلا اضافه شده است"
            
            # Generate session name
            session_name = f"session_{phone_number}_{int(datetime.now().timestamp())}"
            session_path = Path(self.config.telegram.session_path) / session_name
            
            # Create session info
            session_info = SessionInfo(phone_number, str(session_path))
            
            # Configure client parameters
            device_model = random.choice(self.config.anti_detection.device_models)
            app_version = random.choice(self.config.anti_detection.app_versions)
            system_version = random.choice(self.config.anti_detection.system_versions)
            
            # Create client
            client = Client(
                name=str(session_path),
                api_id=self.config.telegram.api_id,
                api_hash=self.config.telegram.api_hash,
                app_version=app_version,
                device_model=device_model,
                system_version=system_version,
                lang_code="en",
                system_lang_code="en-US",
                in_memory=False
            )
            
            await client.connect()
            
            if via_qr:
                # QR code login
                qr_code = await client.export_session_string()
                return True, f"QR_CODE:{qr_code}"
            else:
                # Phone code login
                sent_code = await client.send_code(phone_number)
                
                # Ask for code
                return True, f"CODE_SENT:{sent_code.phone_code_hash}"
            
        except FloodWait as e:
            wait_time = e.value
            return False, f"لطفا {wait_time} ثانیه صبر کنید و دوباره تلاش کنید"
        except Exception as e:
            logger.error(f"Failed to add account {phone_number}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def verify_code(self, phone_number: str, code: str, phone_code_hash: str = None) -> Tuple[bool, str]:
        """Verify phone code"""
        try:
            # Find session
            session_info = self.sessions.get(phone_number)
            if not session_info:
                return False, "جلسه‌ای یافت نشد"
            
            # Get client
            client = self.active_clients.get(phone_number)
            if not client:
                client = Client(
                    name=session_info.session_path,
                    api_id=self.config.telegram.api_id,
                    api_hash=self.config.telegram.api_hash,
                    in_memory=False
                )
                await client.connect()
            
            # Sign in
            try:
                signed_in = await client.sign_in(
                    phone_number=phone_number,
                    phone_code_hash=phone_code_hash,
                    phone_code=code
                )
            except SessionPasswordNeeded:
                return True, "PASSWORD_NEEDED"
            
            # Get session string
            session_string = await client.export_session_string()
            session_info.session_string = session_string
            session_info.device_model = client.device_model
            session_info.app_version = client.app_version
            session_info.is_active = True
            session_info.last_used = datetime.now()
            
            # Save session
            self._save_session(session_info)
            
            # Store client
            self.active_clients[phone_number] = client
            
            return True, "اکانت با موفقیت اضافه شد"
            
        except PhoneCodeInvalid:
            return False, "کد نامعتبر است"
        except PhoneCodeExpired:
            return False, "کد منقضی شده است"
        except Exception as e:
            logger.error(f"Code verification failed for {phone_number}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def verify_password(self, phone_number: str, password: str) -> Tuple[bool, str]:
        """Verify 2FA password"""
        try:
            client = self.active_clients.get(phone_number)
            if not client:
                return False, "کلاینت فعال یافت نشد"
            
            await client.check_password(password)
            
            # Get session string
            session_string = await client.export_session_string()
            
            # Update session info
            session_info = self.sessions[phone_number]
            session_info.session_string = session_string
            session_info.is_active = True
            session_info.last_used = datetime.now()
            
            # Save session
            self._save_session(session_info)
            
            return True, "رمز عبور تأیید شد"
            
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False, f"خطا: {str(e)}"
    
    async def remove_account(self, phone_number: str) -> Tuple[bool, str]:
        """Remove an account"""
        try:
            if phone_number not in self.sessions:
                return False, "اکانت یافت نشد"
            
            # Disconnect client if active
            if phone_number in self.active_clients:
                client = self.active_clients[phone_number]
                await client.disconnect()
                del self.active_clients[phone_number]
            
            # Remove from database
            conn = sqlite3.connect(self.session_db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM sessions WHERE phone_number = ?", (phone_number,))
            cursor.execute("DELETE FROM session_health WHERE phone_number = ?", (phone_number,))
            
            conn.commit()
            conn.close()
            
            # Remove session file
            session_info = self.sessions[phone_number]
            if Path(session_info.session_path).exists():
                Path(session_info.session_path).unlink()
            
            # Remove from memory
            del self.sessions[phone_number]
            
            return True, "اکانت با موفقیت حذف شد"
            
        except Exception as e:
            logger.error(f"Failed to remove account {phone_number}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def get_client(self, phone_number: str) -> Optional[Client]:
        """Get or create client for phone number"""
        try:
            # Check if already active
            if phone_number in self.active_clients:
                client = self.active_clients[phone_number]
                try:
                    # Test connection
                    await client.get_me()
                    return client
                except:
                    # Reconnect if needed
                    await client.disconnect()
                    del self.active_clients[phone_number]
            
            # Get session info
            session_info = self.sessions.get(phone_number)
            if not session_info or not session_info.session_string:
                return None
            
            # Create new client from session string
            client = Client(
                name=session_info.session_path,
                session_string=session_info.session_string,
                api_id=self.config.telegram.api_id,
                api_hash=self.config.telegram.api_hash,
                in_memory=True
            )
            
            await client.start()
            self.active_clients[phone_number] = client
            
            # Update last used
            session_info.last_used = datetime.now()
            self._save_session(session_info)
            
            return client
            
        except AuthKeyUnregistered:
            logger.warning(f"Session expired for {phone_number}")
            session_info = self.sessions.get(phone_number)
            if session_info:
                session_info.is_active = False
                session_info.health_status = "expired"
                self._save_session(session_info)
            return None
        except Exception as e:
            logger.error(f"Failed to get client for {phone_number}: {e}")
            return None
    
    async def get_available_accounts(self, count: int = 10) -> List[SessionInfo]:
        """Get available accounts for reporting"""
        try:
            available = []
            
            for phone_number, session_info in self.sessions.items():
                # Check if account is suitable
                if not session_info.is_active:
                    continue
                
                if session_info.is_banned:
                    continue
                
                # Check health status
                if session_info.health_status not in ["healthy", "good"]:
                    continue
                
                # Check if recently used (cooldown)
                if session_info.last_used:
                    time_since_last = datetime.now() - session_info.last_used
                    if time_since_last.total_seconds() < 300:  # 5 minutes cooldown
                        continue
                
                # Check daily limit
                if session_info.total_reports >= self.config.reporting.max_reports_per_account_per_day:
                    continue
                
                available.append(session_info)
                
                if len(available) >= count:
                    break
            
            # Sort by success rate and last used
            available.sort(
                key=lambda x: (
                    x.successful_reports / max(x.total_reports, 1),
                    -(x.last_used.timestamp() if x.last_used else 0)
                ),
                reverse=True
            )
            
            return available
            
        except Exception as e:
            logger.error(f"Failed to get available accounts: {e}")
            return []
    
    async def check_account_health(self, phone_number: str) -> Dict:
        """Check account health"""
        try:
            client = await self.get_client(phone_number)
            if not client:
                return {"status": "inactive", "message": "کلاینت فعال نیست"}
            
            # Test connection
            me = await client.get_me()
            
            # Update session info
            session_info = self.sessions[phone_number]
            session_info.health_status = "healthy"
            session_info.last_used = datetime.now()
            self._save_session(session_info)
            
            return {
                "status": "healthy",
                "username": me.username,
                "first_name": me.first_name,
                "phone_number": phone_number,
                "is_bot": me.is_bot
            }
            
        except FloodWait as e:
            return {"status": "flood_wait", "wait_time": e.value}
        except AuthKeyUnregistered:
            return {"status": "expired", "message": "سشن منقضی شده"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def check_all_accounts_health(self):
        """Check health of all accounts"""
        results = []
        
        for phone_number in list(self.sessions.keys()):
            try:
                health = await self.check_account_health(phone_number)
                results.append({
                    "phone_number": phone_number,
                    **health
                })
                
                # Delay between checks
                await asyncio.sleep(random.uniform(2, 5))
                
            except Exception as e:
                logger.error(f"Health check failed for {phone_number}: {e}")
        
        return results
    
    async def rotate_sessions(self):
        """Rotate sessions for anti-detection"""
        try:
            logger.info("Starting session rotation...")
            
            for phone_number, session_info in self.sessions.items():
                if not session_info.is_active:
                    continue
                
                # Check if rotation is needed
                if session_info.last_used:
                    hours_since_last = (datetime.now() - session_info.last_used).total_seconds() / 3600
                    if hours_since_last < self.config.anti_detection.session_rotation_hours:
                        continue
                
                # Recreate session with new parameters
                await self._recreate_session(session_info)
                
                # Delay between rotations
                await asyncio.sleep(random.uniform(5, 15))
            
            logger.info("Session rotation completed")
            
        except Exception as e:
            logger.error(f"Session rotation failed: {e}")
    
    async def _recreate_session(self, session_info: SessionInfo):
        """Recreate session with new parameters"""
        try:
            # Disconnect old client
            if session_info.phone_number in self.active_clients:
                client = self.active_clients[session_info.phone_number]
                await client.disconnect()
                del self.active_clients[session_info.phone_number]
            
            # Generate new device parameters
            new_device = random.choice(self.config.anti_detection.device_models)
            new_app_version = random.choice(self.config.anti_detection.app_versions)
            new_system = random.choice(self.config.anti_detection.system_versions)
            
            # Create new session string with new parameters
            # (In production, this would involve re-login or session migration)
            
            # For now, just update the parameters
            session_info.device_model = new_device
            session_info.app_version = new_app_version
            session_info.last_used = datetime.now()
            
            self._save_session(session_info)
            
            logger.info(f"Rotated session for {session_info.phone_number}")
            
        except Exception as e:
            logger.error(f"Failed to recreate session for {session_info.phone_number}: {e}")
    
    def get_session_stats(self) -> Dict:
        """Get session statistics"""
        total = len(self.sessions)
        active = sum(1 for s in self.sessions.values() if s.is_active)
        banned = sum(1 for s in self.sessions.values() if s.is_banned)
        
        total_reports = sum(s.total_reports for s in self.sessions.values())
        successful_reports = sum(s.successful_reports for s in self.sessions.values())
        
        success_rate = (successful_reports / total_reports * 100) if total_reports > 0 else 0
        
        return {
            "total_accounts": total,
            "active_accounts": active,
            "banned_accounts": banned,
            "total_reports": total_reports,
            "successful_reports": successful_reports,
            "success_rate": round(success_rate, 2),
            "average_reports_per_account": round(total_reports / max(total, 1), 2)
        }
    
    def export_sessions(self) -> str:
        """Export all sessions (encrypted)"""
        try:
            sessions_data = {}
            for phone_number, session_info in self.sessions.items():
                sessions_data[phone_number] = session_info.to_dict()
            
            sessions_json = json.dumps(sessions_data, indent=2)
            encrypted = self.encryptor.encrypt_string(sessions_json)
            
            return encrypted
            
        except Exception as e:
            logger.error(f"Failed to export sessions: {e}")
            return ""
    
    def import_sessions(self, encrypted_data: str) -> Tuple[bool, str]:
        """Import sessions from encrypted data"""
        try:
            # Decrypt data
            decrypted = self.encryptor.decrypt_string(encrypted_data)
            sessions_data = json.loads(decrypted)
            
            imported_count = 0
            
            for phone_number, data in sessions_data.items():
                # Create session info
                session_info = SessionInfo.from_dict(data)
                
                # Save to database
                self._save_session(session_info)
                imported_count += 1
            
            # Reload sessions
            self._load_sessions()
            
            return True, f"{imported_count} اکانت با موفقیت وارد شد"
            
        except Exception as e:
            logger.error(f"Failed to import sessions: {e}")
            return False, f"خطا در وارد کردن سشن‌ها: {str(e)}"

# Utility functions
def format_phone_number(phone: str) -> str:
    """Format phone number consistently"""
    phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not phone.startswith("98"):
        phone = "98" + phone.lstrip("0")
    return "+" + phone

def generate_session_name(phone_number: str) -> str:
    """Generate unique session name"""
    timestamp = int(datetime.now().timestamp())
    hash_input = f"{phone_number}_{timestamp}"
    hash_str = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return f"session_{hash_str}"

if __name__ == "__main__":
    # Test session manager
    import asyncio
    
    async def test():
        config = get_config()
        manager = SessionManager(config)
        
        print(f"Loaded {len(manager.sessions)} sessions")
        print(f"Stats: {manager.get_session_stats()}")
    
    asyncio.run(test())