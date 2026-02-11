#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduled Job Model - Scheduled job database schema and operations
Lines: ~200
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import pytz
import croniter

class ScheduleType(Enum):
    """Schedule type enumeration"""
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    DAILY = "daily"
    HOURLY = "hourly"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    SCHEDULED = "scheduled"

@dataclass
class ScheduledJob:
    """Scheduled job model"""
    job_id: str
    user_id: int
    target: str
    target_type: str
    reason: str
    account_count: int
    
    # Scheduling
    schedule_type: ScheduleType
    schedule_value: str
    timezone: str = "Asia/Tehran"
    
    # Execution control
    max_executions: int = 0  # 0 = unlimited
    current_execution: int = 0
    
    # Timestamps
    last_executed: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Status
    status: JobStatus = JobStatus.PENDING
    enabled: bool = True
    
    # Statistics
    total_success: int = 0
    total_failed: int = 0
    last_error: Optional[str] = None
    
    # History
    execution_history: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        if isinstance(self.schedule_type, str):
            self.schedule_type = ScheduleType(self.schedule_type)
        
        if isinstance(self.status, str):
            self.status = JobStatus(self.status)
        
        # Parse timestamps
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
        
        if isinstance(self.updated_at, str):
            self.updated_at = datetime.fromisoformat(self.updated_at.replace('Z', '+00:00'))
        
        if self.last_executed and isinstance(self.last_executed, str):
            self.last_executed = datetime.fromisoformat(self.last_executed.replace('Z', '+00:00'))
        
        if self.next_run and isinstance(self.next_run, str):
            self.next_run = datetime.fromisoformat(self.next_run.replace('Z', '+00:00'))
    
    @property
    def is_active(self) -> bool:
        """Check if job is active"""
        return self.enabled and self.status not in [
            JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED
        ]
    
    @property
    def is_running(self) -> bool:
        """Check if job is running"""
        return self.status == JobStatus.RUNNING
    
    @property
    def is_paused(self) -> bool:
        """Check if job is paused"""
        return self.status == JobStatus.PAUSED
    
    @property
    def is_completed(self) -> bool:
        """Check if job is completed"""
        return self.status == JobStatus.COMPLETED
    
    @property
    def remaining_executions(self) -> int:
        """Get remaining executions count"""
        if self.max_executions == 0:
            return -1  # Unlimited
        return max(0, self.max_executions - self.current_execution)
    
    @property
    def schedule_display(self) -> str:
        """Get Persian display name for schedule"""
        if self.schedule_type == ScheduleType.ONCE:
            if self.next_run:
                return f"یکبار در {self.next_run.strftime('%Y-%m-%d %H:%M')}"
            return "یکبار"
        
        elif self.schedule_type == ScheduleType.INTERVAL:
            if self.schedule_value.endswith('m'):
                return f"هر {self.schedule_value[:-1]} دقیقه"
            elif self.schedule_value.endswith('h'):
                return f"هر {self.schedule_value[:-1]} ساعت"
            elif self.schedule_value.endswith('d'):
                return f"هر {self.schedule_value[:-1]} روز"
            else:
                return f"هر {self.schedule_value} دقیقه"
        
        elif self.schedule_type == ScheduleType.DAILY:
            return f"روزانه ساعت {self.schedule_value}"
        
        elif self.schedule_type == ScheduleType.HOURLY:
            return f"ساعتی (هر {self.schedule_value} ساعت)"
        
        elif self.schedule_type == ScheduleType.WEEKLY:
            return f"هفتگی"
        
        elif self.schedule_type == ScheduleType.MONTHLY:
            return f"ماهانه"
        
        elif self.schedule_type == ScheduleType.CRON:
            return f"کرون: {self.schedule_value}"
        
        return str(self.schedule_value)
    
    @property
    def status_display(self) -> str:
        """Get Persian display name for status"""
        status_names = {
            JobStatus.PENDING: "در انتظار",
            JobStatus.RUNNING: "در حال اجرا",
            JobStatus.COMPLETED: "تکمیل شده",
            JobStatus.FAILED: "ناموفق",
            JobStatus.PAUSED: "متوقف شده",
            JobStatus.CANCELLED: "لغو شده",
            JobStatus.SCHEDULED: "زمان‌بندی شده"
        }
        return status_names.get(self.status, str(self.status))
    
    def calculate_next_run(self) -> Optional[datetime]:
        """Calculate next run time"""
        try:
            now = datetime.now(pytz.timezone(self.timezone))
            
            if self.schedule_type == ScheduleType.ONCE:
                # Parse datetime from schedule_value
                try:
                    next_run = datetime.fromisoformat(self.schedule_value)
                    if next_run > now:
                        return next_run.replace(tzinfo=pytz.timezone(self.timezone))
                    return None
                except:
                    return None
            
            elif self.schedule_type == ScheduleType.INTERVAL:
                interval = self._parse_interval(self.schedule_value)
                if not interval:
                    return None
                
                if self.last_executed:
                    next_run = self.last_executed + interval
                else:
                    next_run = now + interval
                
                return next_run
            
            elif self.schedule_type == ScheduleType.CRON:
                cron = croniter.croniter(self.schedule_value, now)
                return cron.get_next(datetime)
            
            elif self.schedule_type == ScheduleType.DAILY:
                hour, minute = map(int, self.schedule_value.split(":"))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                return next_run
            
            elif self.schedule_type == ScheduleType.HOURLY:
                hours = int(self.schedule_value)
                if self.last_executed:
                    next_run = self.last_executed + timedelta(hours=hours)
                else:
                    next_run = now + timedelta(hours=hours)
                
                return next_run
            
            elif self.schedule_type == ScheduleType.WEEKLY:
                # Every week on same day
                if self.last_executed:
                    next_run = self.last_executed + timedelta(weeks=1)
                else:
                    next_run = now + timedelta(weeks=1)
                
                return next_run
            
            elif self.schedule_type == ScheduleType.MONTHLY:
                # Every month on same day
                if self.last_executed:
                    # Add approximately a month
                    next_run = self.last_executed + timedelta(days=30)
                else:
                    next_run = now + timedelta(days=30)
                
                return next_run
            
            return None
            
        except Exception as e:
            return None
    
    def _parse_interval(self, interval_str: str) -> Optional[timedelta]:
        """Parse interval string to timedelta"""
        try:
            if interval_str.endswith('m'):
                minutes = int(interval_str[:-1])
                return timedelta(minutes=minutes)
            elif interval_str.endswith('h'):
                hours = int(interval_str[:-1])
                return timedelta(hours=hours)
            elif interval_str.endswith('d'):
                days = int(interval_str[:-1])
                return timedelta(days=days)
            elif interval_str.endswith('w'):
                weeks = int(interval_str[:-1])
                return timedelta(weeks=weeks)
            else:
                # Assume minutes
                minutes = int(interval_str)
                return timedelta(minutes=minutes)
        except:
            return None
    
    def should_run(self) -> bool:
        """Check if job should run now"""
        if not self.enabled:
            return False
        
        if self.status not in [JobStatus.PENDING, JobStatus.SCHEDULED]:
            return False
        
        if self.max_executions > 0 and self.current_execution >= self.max_executions:
            return False
        
        if not self.next_run:
            self.next_run = self.calculate_next_run()
        
        if not self.next_run:
            return False
        
        now = datetime.now(pytz.timezone(self.timezone))
        return now >= self.next_run
    
    def execute(self):
        """Mark job as running"""
        self.status = JobStatus.RUNNING
        self.updated_at = datetime.now()
    
    def complete(self, success: bool = True, error: str = None):
        """Mark job as completed"""
        self.current_execution += 1
        self.last_executed = datetime.now()
        self.updated_at = datetime.now()
        
        if success:
            self.status = JobStatus.COMPLETED
        else:
            self.status = JobStatus.FAILED
            self.last_error = error
        
        # Calculate next run
        self.next_run = self.calculate_next_run()
        
        # Check if should continue
        if self.max_executions > 0 and self.current_execution >= self.max_executions:
            self.enabled = False
            self.status = JobStatus.COMPLETED
        elif self.next_run:
            self.status = JobStatus.SCHEDULED
    
    def pause(self):
        """Pause job"""
        self.status = JobStatus.PAUSED
        self.enabled = False
        self.updated_at = datetime.now()
    
    def resume(self):
        """Resume job"""
        self.status = JobStatus.SCHEDULED
        self.enabled = True
        self.updated_at = datetime.now()
        self.next_run = self.calculate_next_run()
    
    def cancel(self):
        """Cancel job"""
        self.status = JobStatus.CANCELLED
        self.enabled = False
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "target": self.target,
            "target_type": self.target_type,
            "reason": self.reason,
            "account_count": self.account_count,
            "schedule_type": self.schedule_type.value,
            "schedule_value": self.schedule_value,
            "schedule_display": self.schedule_display,
            "timezone": self.timezone,
            "max_executions": self.max_executions,
            "current_execution": self.current_execution,
            "remaining_executions": self.remaining_executions,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "status_display": self.status_display,
            "enabled": self.enabled,
            "is_active": self.is_active,
            "is_running": self.is_running,
            "total_success": self.total_success,
            "total_failed": self.total_failed,
            "last_error": self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledJob':
        """Create from dictionary"""
        job = cls(
            job_id=data["job_id"],
            user_id=data["user_id"],
            target=data["target"],
            target_type=data["target_type"],
            reason=data["reason"],
            account_count=data["account_count"],
            schedule_type=data.get("schedule_type", "interval"),
            schedule_value=data["schedule_value"],
            timezone=data.get("timezone", "Asia/Tehran"),
            max_executions=data.get("max_executions", 0),
            current_execution=data.get("current_execution", 0),
            status=data.get("status", "pending"),
            enabled=data.get("enabled", True),
            total_success=data.get("total_success", 0),
            total_failed=data.get("total_failed", 0),
            last_error=data.get("last_error")
        )
        
        # Parse timestamps
        if data.get("last_executed"):
            job.last_executed = datetime.fromisoformat(data["last_executed"].replace('Z', '+00:00'))
        
        if data.get("next_run"):
            job.next_run = datetime.fromisoformat(data["next_run"].replace('Z', '+00:00'))
        
        if data.get("created_at"):
            job.created_at = datetime.fromisoformat(data["created_at"].replace('Z', '+00:00'))
        
        if data.get("updated_at"):
            job.updated_at = datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))
        
        return job