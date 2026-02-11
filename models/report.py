#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report Model - Report database schema and operations
Lines: ~200
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

class ReportType(Enum):
    """Report type enumeration"""
    CHANNEL = "channel"
    GROUP = "group"
    USER = "user"
    POST = "post"
    NOTOSCAM = "notoscam"
    AUTO_JOIN = "auto_join"
    VIEW_REPORT = "view_report"
    FORWARD = "forward"

class ReportStatus(Enum):
    """Report status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"

@dataclass
class ReportHistory:
    """Report history entry model"""
    report_id: int
    account_id: str
    target: str
    reason: str
    status: str
    error_message: Optional[str] = None
    response_time: float = 0.0
    executed_at: datetime = field(default_factory=datetime.now)
    
    @property
    def is_success(self) -> bool:
        """Check if report was successful"""
        return self.status == "success"
    
    @property
    def is_failure(self) -> bool:
        """Check if report failed"""
        return self.status == "failed"
    
    @property
    def execution_time_str(self) -> str:
        """Get formatted execution time"""
        if self.response_time < 1:
            return f"{self.response_time * 1000:.0f}ms"
        return f"{self.response_time:.1f}s"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "report_id": self.report_id,
            "account_id": self.account_id,
            "target": self.target,
            "reason": self.reason,
            "status": self.status,
            "error_message": self.error_message,
            "response_time": self.response_time,
            "executed_at": self.executed_at.isoformat(),
            "execution_time": self.execution_time_str
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReportHistory':
        """Create from dictionary"""
        history = cls(
            report_id=data["report_id"],
            account_id=data["account_id"],
            target=data["target"],
            reason=data["reason"],
            status=data["status"],
            error_message=data.get("error_message"),
            response_time=data.get("response_time", 0.0)
        )
        
        if data.get("executed_at"):
            history.executed_at = datetime.fromisoformat(data["executed_at"].replace('Z', '+00:00'))
        
        return history

@dataclass
class Report:
    """Report model"""
    id: Optional[int] = None
    user_id: int = 0
    target: str = ""
    target_type: ReportType = ReportType.CHANNEL
    reason: str = ""
    custom_text: Optional[str] = None
    
    # Statistics
    accounts_used: int = 0
    successful_reports: int = 0
    failed_reports: int = 0
    
    # Status
    status: ReportStatus = ReportStatus.PENDING
    error_message: Optional[str] = None
    
    # Scheduling
    scheduled: bool = False
    schedule_interval: Optional[str] = None
    next_run: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # History
    history: List[ReportHistory] = field(default_factory=list)
    
    def __post_init__(self):
        if isinstance(self.target_type, str):
            self.target_type = ReportType(self.target_type)
        
        if isinstance(self.status, str):
            self.status = ReportStatus(self.status)
        
        # Parse timestamps
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
        
        if self.completed_at and isinstance(self.completed_at, str):
            self.completed_at = datetime.fromisoformat(self.completed_at.replace('Z', '+00:00'))
        
        if self.next_run and isinstance(self.next_run, str):
            self.next_run = datetime.fromisoformat(self.next_run.replace('Z', '+00:00'))
    
    @property
    def total_accounts(self) -> int:
        """Get total accounts used"""
        return self.accounts_used
    
    @property
    def completion_percentage(self) -> float:
        """Get completion percentage"""
        if self.accounts_used == 0:
            return 0.0
        return (self.successful_reports + self.failed_reports) / self.accounts_used * 100
    
    @property
    def success_rate(self) -> float:
        """Get success rate"""
        if self.successful_reports + self.failed_reports == 0:
            return 0.0
        return (self.successful_reports / (self.successful_reports + self.failed_reports)) * 100
    
    @property
    def is_completed(self) -> bool:
        """Check if report is completed"""
        return self.status in [ReportStatus.COMPLETED, ReportStatus.FAILED, ReportStatus.CANCELLED]
    
    @property
    def is_processing(self) -> bool:
        """Check if report is processing"""
        return self.status == ReportStatus.PROCESSING
    
    @property
    def is_scheduled(self) -> bool:
        """Check if report is scheduled"""
        return self.scheduled
    
    @property
    def duration(self) -> Optional[float]:
        """Get report duration in seconds"""
        if self.completed_at and self.created_at:
            return (self.completed_at - self.created_at).total_seconds()
        return None
    
    @property
    def target_display(self) -> str:
        """Get formatted target for display"""
        if len(self.target) > 30:
            return self.target[:30] + "..."
        return self.target
    
    @property
    def type_display(self) -> str:
        """Get Persian display name for report type"""
        type_names = {
            ReportType.CHANNEL: "کانال",
            ReportType.GROUP: "گروه",
            ReportType.USER: "کاربر",
            ReportType.POST: "پست",
            ReportType.NOTOSCAM: "NotoScam",
            ReportType.AUTO_JOIN: "عضویت+گزارش",
            ReportType.VIEW_REPORT: "مشاهده+گزارش",
            ReportType.FORWARD: "فوروارد"
        }
        return type_names.get(self.target_type, str(self.target_type))
    
    @property
    def status_display(self) -> str:
        """Get Persian display name for status"""
        status_names = {
            ReportStatus.PENDING: "در انتظار",
            ReportStatus.PROCESSING: "در حال اجرا",
            ReportStatus.COMPLETED: "تکمیل شده",
            ReportStatus.FAILED: "ناموفق",
            ReportStatus.CANCELLED: "لغو شده",
            ReportStatus.PARTIAL: "ناتمام"
        }
        return status_names.get(self.status, str(self.status))
    
    def update_progress(self, successful: int = 0, failed: int = 0):
        """Update report progress"""
        self.successful_reports += successful
        self.failed_reports += failed
        
        if self.successful_reports + self.failed_reports >= self.accounts_used:
            if self.failed_reports == self.accounts_used:
                self.status = ReportStatus.FAILED
            elif self.successful_reports > 0:
                self.status = ReportStatus.COMPLETED
            else:
                self.status = ReportStatus.PARTIAL
            
            self.completed_at = datetime.now()
    
    def add_history(self, history: ReportHistory):
        """Add history entry"""
        self.history.append(history)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "target": self.target,
            "target_type": self.target_type.value,
            "target_display": self.target_display,
            "type_display": self.type_display,
            "reason": self.reason,
            "custom_text": self.custom_text,
            "accounts_used": self.accounts_used,
            "successful_reports": self.successful_reports,
            "failed_reports": self.failed_reports,
            "status": self.status.value,
            "status_display": self.status_display,
            "error_message": self.error_message,
            "scheduled": self.scheduled,
            "schedule_interval": self.schedule_interval,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "completion_percentage": self.completion_percentage,
            "success_rate": self.success_rate,
            "history": [h.to_dict() for h in self.history[-10:]]  # Last 10 entries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Report':
        """Create from dictionary"""
        report = cls(
            id=data.get("id"),
            user_id=data["user_id"],
            target=data["target"],
            target_type=data.get("target_type", "channel"),
            reason=data["reason"],
            custom_text=data.get("custom_text"),
            accounts_used=data.get("accounts_used", 0),
            successful_reports=data.get("successful_reports", 0),
            failed_reports=data.get("failed_reports", 0),
            status=data.get("status", "pending"),
            error_message=data.get("error_message"),
            scheduled=data.get("scheduled", False),
            schedule_interval=data.get("schedule_interval"),
            created_at=data.get("created_at", datetime.now()),
            completed_at=data.get("completed_at"),
            next_run=data.get("next_run")
        )
        
        # Parse history
        if data.get("history"):
            for h in data["history"]:
                report.history.append(ReportHistory.from_dict(h))
        
        return report