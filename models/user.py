#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User Model - User database schema and operations
Lines: ~200
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

class UserRole(Enum):
    """User role enumeration"""
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    BANNED = "banned"

@dataclass
class Subscription:
    """User subscription model"""
    user_id: int
    start_date: datetime
    end_date: datetime
    plan_type: str = "monthly"
    auto_renew: bool = False
    days_remaining: int = field(init=False)
    
    def __post_init__(self):
        self.days_remaining = max(0, (self.end_date - datetime.now()).days)
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is active"""
        return self.end_date > datetime.now() and self.days_remaining > 0
    
    @property
    def is_expired(self) -> bool:
        """Check if subscription is expired"""
        return self.end_date <= datetime.now()
    
    @property
    def days_left(self) -> int:
        """Get days left until expiry"""
        return self.days_remaining
    
    def extend(self, days: int) -> 'Subscription':
        """Extend subscription by days"""
        self.end_date += timedelta(days=days)
        self.days_remaining = max(0, (self.end_date - datetime.now()).days)
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "plan_type": self.plan_type,
            "auto_renew": self.auto_renew,
            "days_remaining": self.days_remaining,
            "is_active": self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Subscription':
        """Create from dictionary"""
        return cls(
            user_id=data["user_id"],
            start_date=datetime.fromisoformat(data["start_date"]) if isinstance(data["start_date"], str) else data["start_date"],
            end_date=datetime.fromisoformat(data["end_date"]) if isinstance(data["end_date"], str) else data["end_date"],
            plan_type=data.get("plan_type", "monthly"),
            auto_renew=data.get("auto_renew", False)
        )

@dataclass
class User:
    """User model"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole = UserRole.USER
    subscription: Optional[Subscription] = None
    
    # Statistics
    total_reports: int = 0
    successful_reports: int = 0
    failed_reports: int = 0
    reports_today: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    last_report: Optional[datetime] = None
    
    # Metadata
    language_code: str = "fa"
    is_bot: bool = False
    is_verified: bool = False
    is_restricted: bool = False
    
    def __post_init__(self):
        if isinstance(self.role, str):
            self.role = UserRole(self.role)
        
        if self.subscription and isinstance(self.subscription, dict):
            self.subscription = Subscription.from_dict(self.subscription)
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.username or str(self.user_id)
    
    @property
    def display_name(self) -> str:
        """Get display name"""
        if self.username:
            return f"@{self.username}"
        return self.full_name
    
    @property
    def is_admin(self) -> bool:
        """Check if user is admin"""
        return self.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]
    
    @property
    def is_super_admin(self) -> bool:
        """Check if user is super admin"""
        return self.role == UserRole.SUPER_ADMIN
    
    @property
    def is_banned(self) -> bool:
        """Check if user is banned"""
        return self.role == UserRole.BANNED
    
    @property
    def has_active_subscription(self) -> bool:
        """Check if user has active subscription"""
        return self.subscription and self.subscription.is_active
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_reports == 0:
            return 0.0
        return (self.successful_reports / self.total_reports) * 100
    
    def can_report(self) -> bool:
        """Check if user can report"""
        if self.is_banned:
            return False
        
        if not self.has_active_subscription and not self.is_admin:
            return False
        
        return True
    
    def increment_report(self, success: bool = True):
        """Increment report count"""
        self.total_reports += 1
        self.reports_today += 1
        self.last_report = datetime.now()
        
        if success:
            self.successful_reports += 1
        else:
            self.failed_reports += 1
    
    def update_activity(self):
        """Update last active timestamp"""
        self.last_active = datetime.now()
    
    def ban(self):
        """Ban user"""
        self.role = UserRole.BANNED
    
    def unban(self):
        """Unban user"""
        self.role = UserRole.USER
    
    def promote_to_admin(self):
        """Promote user to admin"""
        if self.role != UserRole.SUPER_ADMIN:
            self.role = UserRole.ADMIN
    
    def demote_from_admin(self):
        """Demote admin to user"""
        if self.role == UserRole.ADMIN:
            self.role = UserRole.USER
    
    def grant_subscription(self, days: int = 30):
        """Grant subscription to user"""
        now = datetime.now()
        end_date = now + timedelta(days=days)
        
        if self.subscription and self.subscription.is_active:
            # Extend existing subscription
            self.subscription.extend(days)
        else:
            # Create new subscription
            self.subscription = Subscription(
                user_id=self.user_id,
                start_date=now,
                end_date=end_date,
                plan_type="monthly"
            )
    
    def revoke_subscription(self):
        """Revoke user subscription"""
        self.subscription = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "role": self.role.value,
            "subscription": self.subscription.to_dict() if self.subscription else None,
            "total_reports": self.total_reports,
            "successful_reports": self.successful_reports,
            "failed_reports": self.failed_reports,
            "reports_today": self.reports_today,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "last_report": self.last_report.isoformat() if self.last_report else None,
            "language_code": self.language_code,
            "is_bot": self.is_bot,
            "is_verified": self.is_verified,
            "is_restricted": self.is_restricted
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create from dictionary"""
        user = cls(
            user_id=data["user_id"],
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            role=data.get("role", "user"),
            total_reports=data.get("total_reports", 0),
            successful_reports=data.get("successful_reports", 0),
            failed_reports=data.get("failed_reports", 0),
            reports_today=data.get("reports_today", 0),
            language_code=data.get("language_code", "fa"),
            is_bot=data.get("is_bot", False),
            is_verified=data.get("is_verified", False),
            is_restricted=data.get("is_restricted", False)
        )
        
        # Parse timestamps
        if data.get("created_at"):
            user.created_at = datetime.fromisoformat(data["created_at"].replace('Z', '+00:00'))
        
        if data.get("last_active"):
            user.last_active = datetime.fromisoformat(data["last_active"].replace('Z', '+00:00'))
        
        if data.get("last_report"):
            user.last_report = datetime.fromisoformat(data["last_report"].replace('Z', '+00:00'))
        
        # Parse subscription
        if data.get("subscription"):
            user.subscription = Subscription.from_dict(data["subscription"])
        
        return user
    
    @classmethod
    def from_telegram_user(cls, telegram_user) -> 'User':
        """Create from Telegram User object"""
        return cls(
            user_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=getattr(telegram_user, 'last_name', None),
            is_bot=telegram_user.is_bot,
            language_code=getattr(telegram_user, 'language_code', 'fa')
        )