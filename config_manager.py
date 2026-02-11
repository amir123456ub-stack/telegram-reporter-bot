#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Manager - Centralized settings management
Lines: ~850
"""

import os
import json
import yaml
import toml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = "sqlite:///bot_database.db"
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600
    echo: bool = False
    connect_args: Dict = field(default_factory=lambda: {"check_same_thread": False})
    
    def get_async_url(self) -> str:
        """Get async database URL"""
        if self.url.startswith("sqlite"):
            return self.url.replace("sqlite:///", "sqlite+aiosqlite:///")
        return self.url.replace("://", "+asyncpg://")

@dataclass
class TelegramConfig:
    """Telegram API configuration"""
    api_id: int = 0
    api_hash: str = ""
    bot_token: str = ""
    phone_number: str = ""
    session_path: str = "sessions"
    max_clients: int = 100
    flood_sleep_threshold: int = 60
    test_mode: bool = False
    
    def validate(self) -> bool:
        """Validate Telegram credentials"""
        if not self.api_id or self.api_id < 1000:
            logger.error("Invalid API ID")
            return False
        if not self.api_hash or len(self.api_hash) != 32:
            logger.error("Invalid API Hash")
            return False
        if not self.bot_token or ":" not in self.bot_token:
            logger.error("Invalid Bot Token")
            return False
        return True

@dataclass
class SecurityConfig:
    """Security configuration"""
    encryption_key: str = ""
    session_encryption: bool = True
    enable_2fa: bool = False
    max_login_attempts: int = 3
    session_timeout: int = 3600
    ip_whitelist: List[str] = field(default_factory=list)
    rate_limit_per_user: int = 10
    rate_limit_per_hour: int = 100
    
    def generate_encryption_key(self) -> str:
        """Generate encryption key if not set"""
        if not self.encryption_key:
            import secrets
            self.encryption_key = secrets.token_urlsafe(32)
            self._save_to_env()
        return self.encryption_key
    
    def _save_to_env(self):
        """Save encryption key to .env file"""
        env_path = Path(".env")
        if env_path.exists():
            content = env_path.read_text()
            if "ENCRYPTION_KEY" not in content:
                with open(env_path, "a") as f:
                    f.write(f"\nENCRYPTION_KEY={self.encryption_key}\n")
            else:
                # Update existing key
                lines = content.splitlines()
                new_lines = []
                for line in lines:
                    if line.startswith("ENCRYPTION_KEY="):
                        line = f"ENCRYPTION_KEY={self.encryption_key}"
                    new_lines.append(line)
                env_path.write_text("\n".join(new_lines))

@dataclass
class ReportingConfig:
    """Reporting configuration"""
    min_delay_between_actions: float = 1.2
    max_delay_between_actions: float = 4.7
    max_accounts_per_report: int = 50
    max_reports_per_account_per_hour: int = 5
    max_reports_per_account_per_day: int = 30
    cooldown_after_reports: int = 300
    enable_auto_join: bool = True
    enable_view_before_report: bool = True
    randomize_order: bool = True
    
    def get_random_delay(self) -> float:
        """Get random delay between actions"""
        import random
        return random.uniform(self.min_delay_between_actions, 
                            self.max_delay_between_actions)

@dataclass
class AntiDetectionConfig:
    """Anti-detection configuration"""
    enable_behavior_simulation: bool = True
    enable_device_spoofing: bool = True
    enable_proxy_rotation: bool = False
    enable_session_rotation: bool = True
    session_rotation_hours: int = 24
    max_concurrent_sessions: int = 5
    humanize_timing: bool = True
    add_random_errors: bool = True
    error_probability: float = 0.02
    
    # Device spoofing options
    device_models: List[str] = field(default_factory=lambda: [
        "iPhone 13 Pro", "iPhone 12", "Samsung Galaxy S22",
        "Xiaomi Redmi Note 11", "Google Pixel 6", "OnePlus 9"
    ])
    
    app_versions: List[str] = field(default_factory=lambda: [
        "9.0.0", "8.9.0", "8.8.0", "8.7.1", "8.6.0"
    ])
    
    system_versions: List[str] = field(default_factory=lambda: [
        "iOS 16.2", "iOS 15.7", "Android 13", "Android 12", "Android 11"
    ])

@dataclass
class TermuxConfig:
    """Termux-specific configuration"""
    optimize_memory: bool = True
    max_memory_mb: int = 150
    enable_background_service: bool = True
    low_power_mode: bool = False
    log_rotation_size_mb: int = 10
    max_log_files: int = 5
    auto_restart_on_crash: bool = True
    restart_delay_seconds: int = 30

@dataclass
class NotificationConfig:
    """Notification configuration"""
    enable_admin_notifications: bool = True
    enable_error_alerts: bool = True
    enable_daily_summary: bool = True
    daily_summary_time: str = "09:00"
    timezone: str = "Asia/Tehran"
    notification_chat_id: Optional[int] = None
    
    def get_summary_time(self) -> datetime.time:
        """Parse summary time"""
        from datetime import time
        try:
            hour, minute = map(int, self.daily_summary_time.split(":"))
            return time(hour, minute)
        except:
            return time(9, 0)  # Default 9 AM

class ConfigManager:
    """Main configuration manager"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = Path(config_file)
        self.env_file = Path(".env")
        
        # Load configurations
        self._load_env()
        self._load_config_file()
        
        # Initialize config objects
        self.db = DatabaseConfig()
        self.telegram = TelegramConfig()
        self.security = SecurityConfig()
        self.reporting = ReportingConfig()
        self.anti_detection = AntiDetectionConfig()
        self.termux = TermuxConfig()
        self.notification = NotificationConfig()
        
        # Apply loaded configs
        self._apply_env_configs()
        self._apply_file_configs()
        
        # Validate
        self._validate_configs()
        
        # Create necessary directories
        self._create_directories()
    
    def _load_env(self):
        """Load environment variables"""
        if self.env_file.exists():
            load_dotenv(dotenv_path=self.env_file)
        else:
            # Create default .env
            self._create_default_env()
    
    def _create_default_env(self):
        """Create default .env file"""
        default_env = """# Telegram API Credentials
API_ID=1234567
API_HASH=abcdef1234567890abcdef1234567890
BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789

# Admin Configuration
ADMIN_IDS=123456789,987654321

# Security
ENCRYPTION_KEY=your-32-char-encryption-key-change-this

# Database
DATABASE_URL=sqlite:///bot_database.db

# Reporting Limits
MAX_REPORTS_PER_HOUR=10
MAX_REPORTS_PER_DAY=100

# Delays (seconds)
MIN_DELAY=1.2
MAX_DELAY=4.7

# Logging
LOG_LEVEL=INFO
LOG_FILE=bot.log
"""
        self.env_file.write_text(default_env)
        logger.info(f"Created default .env file at {self.env_file}")
    
    def _load_config_file(self):
        """Load configuration from file"""
        self.file_config = {}
        
        if not self.config_file.exists():
            return
        
        try:
            if self.config_file.suffix == ".yaml":
                import yaml
                self.file_config = yaml.safe_load(self.config_file.read_text())
            elif self.config_file.suffix == ".json":
                self.file_config = json.loads(self.config_file.read_text())
            elif self.config_file.suffix == ".toml":
                import toml
                self.file_config = toml.load(self.config_file)
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
    
    def _apply_env_configs(self):
        """Apply environment variables to config objects"""
        # Telegram
        self.telegram.api_id = int(os.getenv("API_ID", 0))
        self.telegram.api_hash = os.getenv("API_HASH", "")
        self.telegram.bot_token = os.getenv("BOT_TOKEN", "")
        
        # Admin IDs
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        if admin_ids_str:
            self.ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(",")]
        else:
            self.ADMIN_IDS = []
        
        # Security
        self.security.encryption_key = os.getenv("ENCRYPTION_KEY", "")
        
        # Database
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            self.db.url = db_url
        
        # Reporting
        max_hour = os.getenv("MAX_REPORTS_PER_HOUR", "")
        if max_hour:
            self.security.rate_limit_per_user = int(max_hour)
        
        max_day = os.getenv("MAX_REPORTS_PER_DAY", "")
        if max_day:
            self.reporting.max_reports_per_account_per_day = int(max_day)
        
        # Delays
        min_delay = os.getenv("MIN_DELAY", "")
        if min_delay:
            self.reporting.min_delay_between_actions = float(min_delay)
        
        max_delay = os.getenv("MAX_DELAY", "")
        if max_delay:
            self.reporting.max_delay_between_actions = float(max_delay)
        
        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE = os.getenv("LOG_FILE", "bot.log")
    
    def _apply_file_configs(self):
        """Apply file configurations"""
        if not self.file_config:
            return
        
        # Apply to each config section
        config_mapping = {
            "database": self.db,
            "telegram": self.telegram,
            "security": self.security,
            "reporting": self.reporting,
            "anti_detection": self.anti_detection,
            "termux": self.termux,
            "notification": self.notification
        }
        
        for section, config_obj in config_mapping.items():
            if section in self.file_config:
                section_data = self.file_config[section]
                for key, value in section_data.items():
                    if hasattr(config_obj, key):
                        setattr(config_obj, key, value)
    
    def _validate_configs(self):
        """Validate all configurations"""
        # Validate Telegram credentials
        if not self.telegram.validate():
            logger.warning("Telegram credentials are invalid or missing")
        
        # Generate encryption key if needed
        if self.security.session_encryption and not self.security.encryption_key:
            self.security.generate_encryption_key()
            logger.info("Generated new encryption key")
        
        # Set default admin if none
        if not self.ADMIN_IDS:
            logger.warning("No admin IDs configured")
        
        # Validate reporting limits
        if self.reporting.max_accounts_per_report > 100:
            logger.warning("Max accounts per report should not exceed 100")
            self.reporting.max_accounts_per_report = 100
        
        # Validate delays
        if self.reporting.min_delay_between_actions < 0.5:
            logger.warning("Minimum delay too low, setting to 0.5")
            self.reporting.min_delay_between_actions = 0.5
        
        if self.reporting.max_delay_between_actions < self.reporting.min_delay_between_actions:
            self.reporting.max_delay_between_actions = self.reporting.min_delay_between_actions + 2.0
        
        logger.info("Configuration validation completed")
    
    def _create_directories(self):
        """Create necessary directories"""
        directories = [
            "sessions",
            "logs",
            "backups",
            "database",
            "config",
            "scripts"
        ]
        
        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
    
    def save_config(self, file_format: str = "yaml"):
        """Save current configuration to file"""
        config_dict = {
            "database": asdict(self.db),
            "telegram": asdict(self.telegram),
            "security": asdict(self.security),
            "reporting": asdict(self.reporting),
            "anti_detection": asdict(self.anti_detection),
            "termux": asdict(self.termux),
            "notification": asdict(self.notification)
        }
        
        try:
            if file_format == "yaml":
                import yaml
                with open(self.config_file, "w") as f:
                    yaml.dump(config_dict, f, default_flow_style=False)
            elif file_format == "json":
                with open(self.config_file.with_suffix(".json"), "w") as f:
                    json.dump(config_dict, f, indent=2)
            elif file_format == "toml":
                import toml
                with open(self.config_file.with_suffix(".toml"), "w") as f:
                    toml.dump(config_dict, f)
            
            logger.info(f"Configuration saved to {self.config_file}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def reload(self):
        """Reload configuration from files"""
        self._load_env()
        self._load_config_file()
        self._apply_env_configs()
        self._apply_file_configs()
        self._validate_configs()
        logger.info("Configuration reloaded")
    
    def get_telegram_client_config(self, session_name: str = "default") -> Dict:
        """Get configuration for Telegram client"""
        return {
            "api_id": self.telegram.api_id,
            "api_hash": self.telegram.api_hash,
            "session_name": str(Path(self.telegram.session_path) / session_name),
            "phone_number": self.telegram.phone_number,
            "app_version": self.anti_detection.app_versions[0],
            "device_model": self.anti_detection.device_models[0],
            "system_version": self.anti_detection.system_versions[0],
            "lang_code": "en",
            "system_lang_code": "en-US"
        }
    
    def to_dict(self) -> Dict:
        """Convert all configs to dictionary"""
        return {
            "database": asdict(self.db),
            "telegram": asdict(self.telegram),
            "security": asdict(self.security),
            "reporting": asdict(self.reporting),
            "anti_detection": asdict(self.anti_detection),
            "termux": asdict(self.termux),
            "notification": asdict(self.notification),
            "admin_ids": self.ADMIN_IDS,
            "log_level": self.LOG_LEVEL,
            "log_file": self.LOG_FILE
        }
    
    def print_summary(self):
        """Print configuration summary"""
        summary = f"""
╔══════════════════════════════════════════╗
║       Configuration Summary              ║
╠══════════════════════════════════════════╣
║ Telegram API: {'✓' if self.telegram.api_id else '✗'}
║ Bot Token: {'✓' if self.telegram.bot_token else '✗'}
║ Admin IDs: {len(self.ADMIN_IDS)}
║ Database: {self.db.url}
║ Security: {'✓' if self.security.encryption_key else '✗'}
║ Max Reports/Hour: {self.security.rate_limit_per_user}
║ Min Delay: {self.reporting.min_delay_between_actions}s
║ Max Delay: {self.reporting.max_delay_between_actions}s
║ Anti-Detection: {'✓' if self.anti_detection.enable_behavior_simulation else '✗'}
║ Termux Optimized: {'✓' if self.termux.optimize_memory else '✗'}
╚══════════════════════════════════════════╝
"""
        print(summary)

# Singleton instance
_config_instance = None

def get_config() -> ConfigManager:
    """Get singleton config instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance

if __name__ == "__main__":
    # Test configuration
    config = ConfigManager()
    config.print_summary()
    
    # Save sample config
    config.save_config("yaml")