#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Account Model - Account database schema and operations
Lines: ~200
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

class AccountStatus(Enum):
    """Account status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"
    FLOOD_WAIT = "flood_wait"
    EXPIRED = "expired"
    UNHEALTHY = "unhealthy"
    LIMITED = "limited"

class AccountHealth(Enum):
    """Account health enumeration"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class AccountStats:
    """Account statistics model"""
    total_reports: int = 0
    successful_reports: int = 0
    failed_reports: int = 0
    total_requests: int = 0
    flood_wait_count: int = 0
    error_count: int = 0
    
    # Timestamps
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_flood: Optional[datetime] = None
    
    # Performance
    average_response_time: float = 0.0
    total_response_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_reports == 0:
            return 0.0
        return (self.successful_reports / self.total_reports) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate"""
        if self.total_reports == 0:
            return 0.0
        return (self.failed_reports / self.total_reports) * 100
    
    @property
    def average_reports_per_day(self) -> float:
        """Calculate average reports per day"""
        if not self.last_success:
            return 0.0
        
        days_active = max(1, (datetime.now() - self.last_success).days)
        return self.total_reports / days_active
    
    def update_success(self, response_time: float = 0.0):
        """Update stats on success"""
        self.total_reports += 1
        self.successful_reports += 1
        self.total_requests += 1
        self.last_success = datetime.now()
        
        # Update response time
        if response_time > 0:
            self.total_response_time += response_time
            self.average_response_time = self.total_response_time / self.total_requests
    
    def update_failure(self, error_type: str = None):
        """Update stats on failure"""
        self.total_reports += 1
        self.failed_reports += 1
        self.total_requests += 1
        self.last_failure = datetime.now()
        
        if error_type == "flood_wait":
            self.flood_wait_count += 1
            self.last_flood = datetime.now()
        else:
            self.error_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_reports": self.total_reports,
            "successful_reports": self.successful_reports,
            "failed_reports": self.failed_reports,
            "total_requests": self.total_requests,
            "flood_wait_count": self.flood_wait_count,
            "error_count": self.error_count,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "last_flood": self.last_flood.isoformat() if self.last_flood else None,
            "success_rate": self.success_rate,
            "average_response_time": round(self.average_response_time, 3)
        }

@dataclass
class Account:
    """Account model"""
    phone_number: str
    session_path: Optional[str] = None
    session_string: Optional[str] = None
    
    # Status
    status: AccountStatus = AccountStatus.ACTIVE
    health: AccountHealth = AccountHealth.UNKNOWN
    
    # Device info
    device_model: Optional[str] = None
    app_version: Optional[str] = None
    system_version: Optional[str] = None
    lang_code: str = "en"
    
    # Statistics
    stats: AccountStats = field(default_factory=AccountStats)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    last_checked: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    
    # Metadata
    error_history: List[str] = field(default_factory=list)
    warning_flags: List[str] = field(default_factory=list)
    
    # Resource management
    concurrent_uses: int = 0
    max_concurrent: int = 1
    
    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = AccountStatus(self.status)
        
        if isinstance(self.health, str):
            self.health = AccountHealth(self.health)
        
        if isinstance(self.stats, dict):
            self.stats = AccountStats(**self.stats)
    
    @property
    def is_available(self) -> bool:
        """Check if account is available for use"""
        if self.status != AccountStatus.ACTIVE:
            return False
        
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
        
        if self.concurrent_uses >= self.max_concurrent:
            return False
        
        if self.health in [AccountHealth.POOR, AccountHealth.CRITICAL]:
            return False
        
        return True
    
    @property
    def is_banned(self) -> bool:
        """Check if account is banned"""
        return self.status == AccountStatus.BANNED
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return self.status == AccountStatus.EXPIRED
    
    @property
    def health_score(self) -> float:
        """Calculate health score (0-100)"""
        score = 100.0
        
        # Deduct for failures
        if self.stats.failure_rate > 50:
            score -= 40
        elif self.stats.failure_rate > 30:
            score -= 20
        elif self.stats.failure_rate > 10:
            score -= 10
        
        # Deduct for flood waits
        if self.stats.flood_wait_count > 10:
            score -= 30
        elif self.stats.flood_wait_count > 5:
            score -= 15
        elif self.stats.flood_wait_count > 0:
            score -= 5
        
        # Deduct for recent errors
        recent_errors = len([e for e in self.error_history[-10:] 
                           if "flood" in e.lower() or "ban" in e.lower()])
        score -= recent_errors * 5
        
        # Bonus for high success rate
        if self.stats.success_rate > 90:
            score += 20
        elif self.stats.success_rate > 80:
            score += 10
        elif self.stats.success_rate > 70:
            score += 5
        
        return max(0, min(100, score))
    
    @property
    def health_status(self) -> AccountHealth:
        """Get health status based on score"""
        score = self.health_score
        
        if score >= 90:
            return AccountHealth.EXCELLENT
        elif score >= 75:
            return AccountHealth.GOOD
        elif score >= 50:
            return AccountHealth.FAIR
        elif score >= 25:
            return AccountHealth.POOR
        else:
            return AccountHealth.CRITICAL
    
    def can_report(self, max_per_hour: int = 20) -> bool:
        """Check if account can report"""
        if not self.is_available:
            return False
        
        # Check hourly limit
        if self.last_used:
            hour_ago = datetime.now() - timedelta(hours=1)
            if self.last_used > hour_ago and self.stats.total_reports >= max_per_hour:
                return False
        
        return True
    
    def use(self):
        """Mark account as being used"""
        self.concurrent_uses += 1
        self.last_used = datetime.now()
    
    def release(self, success: bool = True, response_time: float = 0.0, error: str = None):
        """Release account after use"""
        self.concurrent_uses = max(0, self.concurrent_uses - 1)
        
        if success:
            self.stats.update_success(response_time)
        else:
            self.stats.update_failure(error)
            if error:
                self.add_error(error)
    
    def add_error(self, error_msg: str):
        """Add error to history"""
        self.error_history.append(f"{datetime.now().isoformat()}: {error_msg}")
        
        # Keep only last 20 errors
        if len(self.error_history) > 20:
            self.error_history = self.error_history[-20:]
        
        # Update status based on error
        if "banned" in error_msg.lower():
            self.status = AccountStatus.BANNED
        elif "flood" in error_msg.lower():
            self.status = AccountStatus.FLOOD_WAIT
        elif "expired" in error_msg.lower():
            self.status = AccountStatus.EXPIRED
        
        self.health = self.health_status
    
    def add_warning(self, warning: str):
        """Add warning flag"""
        if warning not in self.warning_flags:
            self.warning_flags.append(warning)
    
    def clear_warnings(self):
        """Clear all warnings"""
        self.warning_flags.clear()
    
    def apply_cooldown(self, seconds: int = 300):
        """Apply cooldown period"""
        self.cooldown_until = datetime.now() + timedelta(seconds=seconds)
    
    def reset(self):
        """Reset account state"""
        self.status = AccountStatus.ACTIVE
        self.cooldown_until = None
        self.error_history.clear()
        self.warning_flags.clear()
        self.health = AccountHealth.UNKNOWN
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "phone_number": self.phone_number,
            "session_path": self.session_path,
            "session_string": self.session_string,
            "status": self.status.value,
            "health": self.health_status.value,
            "health_score": self.health_score,
            "device_model": self.device_model,
            "app_version": self.app_version,
            "system_version": self.system_version,
            "lang_code": self.lang_code,
            "stats": self.stats.to_dict(),
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "concurrent_uses": self.concurrent_uses,
            "max_concurrent": self.max_concurrent,
            "error_count": len(self.error_history),
            "warning_count": len(self.warning_flags)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Account':
        """Create from dictionary"""
        account = cls(
            phone_number=data["phone_number"],
            session_path=data.get("session_path"),
            session_string=data.get("session_string"),
            status=data.get("status", "active"),
            device_model=data.get("device_model"),
            app_version=data.get("app_version"),
            system_version=data.get("system_version"),
            lang_code=data.get("lang_code", "en")
        )
        
        # Parse timestamps
        if data.get("created_at"):
            account.created_at = datetime.fromisoformat(data["created_at"].replace('Z', '+00:00'))
        
        if data.get("last_used"):
            account.last_used = datetime.fromisoformat(data["last_used"].replace('Z', '+00:00'))
        
        if data.get("last_checked"):
            account.last_checked = datetime.fromisoformat(data["last_checked"].replace('Z', '+00:00'))
        
        if data.get("cooldown_until"):
            account.cooldown_until = datetime.fromisoformat(data["cooldown_until"].replace('Z', '+00:00'))
        
        # Parse stats
        if data.get("stats"):
            account.stats = AccountStats(**data["stats"])
        
        return account