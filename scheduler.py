#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report Scheduler - Task scheduling system
Lines: ~1000
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import pickle
from concurrent.futures import ThreadPoolExecutor
import croniter
import pytz

# Local imports
from config_manager import get_config
from database import DatabaseManager

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"

class ScheduleType(Enum):
    """Schedule type enumeration"""
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    DAILY = "daily"
    HOURLY = "hourly"

@dataclass
class ScheduledJob:
    """Scheduled job definition"""
    
    job_id: str
    user_id: int
    target: str
    target_type: str
    reason: str
    account_count: int
    
    # Scheduling
    schedule_type: ScheduleType
    schedule_value: str  # For interval: "5m", for cron: "0 9 * * *"
    timezone: str = "Asia/Tehran"
    
    # Execution control
    max_executions: int = 0  # 0 = unlimited
    current_execution: int = 0
    last_executed: Optional[datetime] = None
    next_run: Optional[datetime] = None
    
    # Status
    status: JobStatus = JobStatus.PENDING
    enabled: bool = True
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Results tracking
    total_success: int = 0
    total_failed: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict:
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
            "timezone": self.timezone,
            "max_executions": self.max_executions,
            "current_execution": self.current_execution,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "status": self.status.value,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "total_success": self.total_success,
            "total_failed": self.total_failed,
            "last_error": self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ScheduledJob':
        """Create from dictionary"""
        job = cls(
            job_id=data["job_id"],
            user_id=data["user_id"],
            target=data["target"],
            target_type=data["target_type"],
            reason=data["reason"],
            account_count=data["account_count"],
            schedule_type=ScheduleType(data["schedule_type"]),
            schedule_value=data["schedule_value"],
            timezone=data.get("timezone", "Asia/Tehran"),
            max_executions=data.get("max_executions", 0),
            current_execution=data.get("current_execution", 0),
            enabled=data.get("enabled", True),
            total_success=data.get("total_success", 0),
            total_failed=data.get("total_failed", 0),
            last_error=data.get("last_error")
        )
        
        # Parse datetime fields
        if data.get("last_executed"):
            job.last_executed = datetime.fromisoformat(data["last_executed"])
        
        if data.get("next_run"):
            job.next_run = datetime.fromisoformat(data["next_run"])
        
        if data.get("created_at"):
            job.created_at = datetime.fromisoformat(data["created_at"])
        
        if data.get("updated_at"):
            job.updated_at = datetime.fromisoformat(data["updated_at"])
        
        # Status
        if data.get("status"):
            job.status = JobStatus(data["status"])
        
        return job
    
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
                # Parse interval like "5m", "2h", "1d"
                interval = self._parse_interval(self.schedule_value)
                if not interval:
                    return None
                
                if self.last_executed:
                    next_run = self.last_executed + interval
                else:
                    next_run = now + interval
                
                return next_run
            
            elif self.schedule_type == ScheduleType.CRON:
                # Parse cron expression
                cron = croniter.croniter(self.schedule_value, now)
                return cron.get_next(datetime)
            
            elif self.schedule_type == ScheduleType.DAILY:
                # Daily at specific time (HH:MM)
                hour, minute = map(int, self.schedule_value.split(":"))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                return next_run
            
            elif self.schedule_type == ScheduleType.HOURLY:
                # Every X hours
                hours = int(self.schedule_value)
                if self.last_executed:
                    next_run = self.last_executed + timedelta(hours=hours)
                else:
                    next_run = now + timedelta(hours=hours)
                
                return next_run
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to calculate next run for job {self.job_id}: {e}")
            return None
    
    def _parse_interval(self, interval_str: str) -> Optional[timedelta]:
        """Parse interval string to timedelta"""
        try:
            if interval_str.endswith("m"):
                minutes = int(interval_str[:-1])
                return timedelta(minutes=minutes)
            elif interval_str.endswith("h"):
                hours = int(interval_str[:-1])
                return timedelta(hours=hours)
            elif interval_str.endswith("d"):
                days = int(interval_str[:-1])
                return timedelta(days=days)
            elif interval_str.endswith("w"):
                weeks = int(interval_str[:-1])
                return timedelta(weeks=weeks)
            else:
                # Assume minutes if no suffix
                minutes = int(interval_str)
                return timedelta(minutes=minutes)
        except:
            return None
    
    def should_run(self) -> bool:
        """Check if job should run now"""
        if not self.enabled:
            return False
        
        if self.status not in [JobStatus.PENDING, JobStatus.PAUSED]:
            return False
        
        if self.max_executions > 0 and self.current_execution >= self.max_executions:
            return False
        
        if not self.next_run:
            self.next_run = self.calculate_next_run()
        
        if not self.next_run:
            return False
        
        now = datetime.now(pytz.timezone(self.timezone))
        return now >= self.next_run

class ReportScheduler:
    """Main report scheduler"""
    
    def __init__(self, report_engine):
        self.config = get_config()
        self.report_engine = report_engine
        self.db = DatabaseManager()
        
        # Job storage
        self.jobs: Dict[str, ScheduledJob] = {}
        self.running_jobs: Set[str] = set()
        
        # Scheduler state
        self.is_running = False
        self.scheduler_task = None
        
        # Thread pool for concurrent execution
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        
        # Load existing jobs
        asyncio.create_task(self._load_jobs())
        
        logger.info("Report scheduler initialized")
    
    async def _load_jobs(self):
        """Load jobs from database"""
        try:
            jobs_data = await self.db.get_scheduled_jobs()
            
            for job_data in jobs_data:
                try:
                    job = ScheduledJob.from_dict(job_data)
                    self.jobs[job.job_id] = job
                    
                    # Recalculate next run
                    job.next_run = job.calculate_next_run()
                    
                except Exception as e:
                    logger.error(f"Failed to load job {job_data.get('job_id')}: {e}")
            
            logger.info(f"Loaded {len(self.jobs)} scheduled jobs")
            
        except Exception as e:
            logger.error(f"Failed to load jobs: {e}")
    
    async def start(self):
        """Start the scheduler"""
        if self.is_running:
            return
        
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info("Scheduler started")
    
    async def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Wait for running jobs to complete
        while self.running_jobs:
            await asyncio.sleep(1)
        
        logger.info("Scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                # Check for jobs to run
                await self._check_jobs()
                
                # Update job statuses
                await self._update_job_statuses()
                
                # Sleep before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)
    
    async def _check_jobs(self):
        """Check and execute jobs that are due"""
        now = datetime.now()
        
        for job_id, job in list(self.jobs.items()):
            try:
                if job.should_run() and job_id not in self.running_jobs:
                    # Execute job
                    asyncio.create_task(self._execute_job(job))
                    
            except Exception as e:
                logger.error(f"Failed to check job {job_id}: {e}")
    
    async def _execute_job(self, job: ScheduledJob):
        """Execute a scheduled job"""
        job_id = job.job_id
        
        try:
            # Mark as running
            self.running_jobs.add(job_id)
            job.status = JobStatus.RUNNING
            job.updated_at = datetime.now()
            
            # Save to database
            await self.db.update_scheduled_job(job.to_dict())
            
            logger.info(f"Executing job {job_id} for user {job.user_id}")
            
            # Execute report
            report_id = await self.report_engine.start_report(
                user_id=job.user_id,
                target=job.target,
                target_type=job.target_type,
                reason=job.reason,
                account_count=job.account_count
            )
            
            # Wait for report to complete (with timeout)
            timeout = 300  # 5 minutes
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                status = await self.report_engine.get_report_status(report_id)
                
                if status["status"] in ["completed", "failed"]:
                    # Update job statistics
                    job.current_execution += 1
                    job.last_executed = datetime.now()
                    
                    if status["status"] == "completed":
                        job.total_success += status.get("successful", 0)
                        job.total_failed += status.get("failed", 0)
                        job.status = JobStatus.COMPLETED
                    else:
                        job.total_failed += job.account_count
                        job.status = JobStatus.FAILED
                        job.last_error = status.get("error", "Unknown error")
                    
                    # Calculate next run
                    job.next_run = job.calculate_next_run()
                    
                    # Check if job should continue
                    if (job.max_executions > 0 and 
                        job.current_execution >= job.max_executions):
                        job.enabled = False
                        job.status = JobStatus.COMPLETED
                    
                    break
                
                await asyncio.sleep(5)
            
            else:
                # Timeout
                job.status = JobStatus.FAILED
                job.last_error = "Execution timeout"
                job.next_run = job.calculate_next_run()
            
            # Update job in database
            job.updated_at = datetime.now()
            await self.db.update_scheduled_job(job.to_dict())
            
            logger.info(f"Job {job_id} completed with status {job.status.value}")
            
        except Exception as e:
            logger.error(f"Failed to execute job {job_id}: {e}")
            
            job.status = JobStatus.FAILED
            job.last_error = str(e)
            job.updated_at = datetime.now()
            
            await self.db.update_scheduled_job(job.to_dict())
        
        finally:
            # Remove from running jobs
            self.running_jobs.discard(job_id)
    
    async def _update_job_statuses(self):
        """Update job statuses in memory"""
        try:
            for job_id, job in self.jobs.items():
                if job_id in self.running_jobs:
                    continue
                
                # Update next run if needed
                if not job.next_run and job.enabled:
                    job.next_run = job.calculate_next_run()
                
                # Check if job expired
                if (job.max_executions > 0 and 
                    job.current_execution >= job.max_executions):
                    job.enabled = False
                    if job.status == JobStatus.PENDING:
                        job.status = JobStatus.COMPLETED
        
        except Exception as e:
            logger.error(f"Failed to update job statuses: {e}")
    
    async def create_job(self, user_id: int, target: str, target_type: str,
                        reason: str, account_count: int,
                        schedule_type: str, schedule_value: str,
                        timezone: str = "Asia/Tehran",
                        max_executions: int = 0) -> Tuple[bool, str, str]:
        """Create a new scheduled job"""
        try:
            # Validate schedule
            if not self._validate_schedule(schedule_type, schedule_value):
                return False, "", "فرمت زمان‌بندی نامعتبر است"
            
            # Generate job ID
            job_id = self._generate_job_id(user_id, target, schedule_value)
            
            # Create job object
            job = ScheduledJob(
                job_id=job_id,
                user_id=user_id,
                target=target,
                target_type=target_type,
                reason=reason,
                account_count=account_count,
                schedule_type=ScheduleType(schedule_type),
                schedule_value=schedule_value,
                timezone=timezone,
                max_executions=max_executions
            )
            
            # Calculate first run
            job.next_run = job.calculate_next_run()
            if not job.next_run:
                return False, "", "زمان اجرای نامعتبر"
            
            # Save to database
            await self.db.create_scheduled_job(job.to_dict())
            
            # Add to memory
            self.jobs[job_id] = job
            
            logger.info(f"Created job {job_id} for user {user_id}")
            
            return True, job_id, "کار زمان‌بندی با موفقیت ایجاد شد"
            
        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            return False, "", f"خطا در ایجاد کار: {str(e)}"
    
    def _validate_schedule(self, schedule_type: str, schedule_value: str) -> bool:
        """Validate schedule parameters"""
        try:
            if schedule_type == ScheduleType.ONCE.value:
                # Should be ISO datetime
                datetime.fromisoformat(schedule_value)
                return True
            
            elif schedule_type == ScheduleType.INTERVAL.value:
                # Should be like "5m", "2h", "1d"
                return self._is_valid_interval(schedule_value)
            
            elif schedule_type == ScheduleType.CRON.value:
                # Should be valid cron expression
                croniter.croniter(schedule_value, datetime.now())
                return True
            
            elif schedule_type == ScheduleType.DAILY.value:
                # Should be "HH:MM"
                hour, minute = map(int, schedule_value.split(":"))
                return 0 <= hour <= 23 and 0 <= minute <= 59
            
            elif schedule_type == ScheduleType.HOURLY.value:
                # Should be integer
                hours = int(schedule_value)
                return 1 <= hours <= 24
            
            return False
            
        except:
            return False
    
    def _is_valid_interval(self, interval_str: str) -> bool:
        """Check if interval string is valid"""
        try:
            if interval_str.endswith("m"):
                minutes = int(interval_str[:-1])
                return 1 <= minutes <= 1440  # Max 24 hours
            elif interval_str.endswith("h"):
                hours = int(interval_str[:-1])
                return 1 <= hours <= 168  # Max 1 week
            elif interval_str.endswith("d"):
                days = int(interval_str[:-1])
                return 1 <= days <= 30  # Max 1 month
            elif interval_str.endswith("w"):
                weeks = int(interval_str[:-1])
                return 1 <= weeks <= 4  # Max 4 weeks
            else:
                # Assume minutes
                minutes = int(interval_str)
                return 1 <= minutes <= 1440
        except:
            return False
    
    def _generate_job_id(self, user_id: int, target: str, schedule: str) -> str:
        """Generate unique job ID"""
        input_str = f"{user_id}_{target}_{schedule}_{int(time.time())}"
        return hashlib.md5(input_str.encode()).hexdigest()[:12]
    
    async def pause_job(self, job_id: str) -> Tuple[bool, str]:
        """Pause a scheduled job"""
        try:
            job = self.jobs.get(job_id)
            if not job:
                return False, "کار یافت نشد"
            
            if job.status == JobStatus.RUNNING:
                return False, "کار در حال اجرا است، نمی‌توان متوقف کرد"
            
            job.enabled = False
            job.status = JobStatus.PAUSED
            job.updated_at = datetime.now()
            
            await self.db.update_scheduled_job(job.to_dict())
            
            return True, "کار با موفقیت متوقف شد"
            
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def resume_job(self, job_id: str) -> Tuple[bool, str]:
        """Resume a paused job"""
        try:
            job = self.jobs.get(job_id)
            if not job:
                return False, "کار یافت نشد"
            
            if job.status != JobStatus.PAUSED:
                return False, "کار متوقف نیست"
            
            job.enabled = True
            job.status = JobStatus.PENDING
            job.updated_at = datetime.now()
            
            # Recalculate next run
            job.next_run = job.calculate_next_run()
            
            await self.db.update_scheduled_job(job.to_dict())
            
            return True, "کار با موفقیت از سر گرفته شد"
            
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def cancel_job(self, job_id: str) -> Tuple[bool, str]:
        """Cancel a scheduled job"""
        try:
            job = self.jobs.get(job_id)
            if not job:
                return False, "کار یافت نشد"
            
            if job_id in self.running_jobs:
                return False, "کار در حال اجرا است"
            
            job.enabled = False
            job.status = JobStatus.CANCELLED
            job.updated_at = datetime.now()
            
            # Remove from jobs
            del self.jobs[job_id]
            
            # Update database
            await self.db.update_scheduled_job(job.to_dict())
            
            return True, "کار با موفقیت لغو شد"
            
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def delete_job(self, job_id: str) -> Tuple[bool, str]:
        """Delete a scheduled job"""
        try:
            job = self.jobs.get(job_id)
            if not job:
                return False, "کار یافت نشد"
            
            if job_id in self.running_jobs:
                return False, "کار در حال اجرا است"
            
            # Remove from memory
            del self.jobs[job_id]
            
            # Delete from database
            await self.db.delete_scheduled_job(job_id)
            
            return True, "کار با موفقیت حذف شد"
            
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False, f"خطا: {str(e)}"
    
    async def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job details"""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        return job.to_dict()
    
    async def get_user_jobs(self, user_id: int) -> List[Dict]:
        """Get all jobs for a user"""
        try:
            user_jobs = []
            
            for job in self.jobs.values():
                if job.user_id == user_id:
                    user_jobs.append(job.to_dict())
            
            return user_jobs
            
        except Exception as e:
            logger.error(f"Failed to get user jobs: {e}")
            return []
    
    async def get_all_jobs(self) -> List[Dict]:
        """Get all scheduled jobs"""
        return [job.to_dict() for job in self.jobs.values()]
    
    async def get_active_jobs_count(self) -> int:
        """Get count of active jobs"""
        return len([j for j in self.jobs.values() 
                   if j.enabled and j.status in [JobStatus.PENDING, JobStatus.PAUSED]])
    
    async def get_running_jobs_count(self) -> int:
        """Get count of running jobs"""
        return len(self.running_jobs)
    
    async def run_job_now(self, job_id: str) -> Tuple[bool, str]:
        """Run a job immediately"""
        try:
            job = self.jobs.get(job_id)
            if not job:
                return False, "کار یافت نشد"
            
            if job_id in self.running_jobs:
                return False, "کار در حال اجرا است"
            
            # Update next run to now
            job.next_run = datetime.now(pytz.timezone(job.timezone))
            
            # Trigger execution
            asyncio.create_task(self._execute_job(job))
            
            return True, "کار بلافاصله اجرا خواهد شد"
            
        except Exception as e:
            logger.error(f"Failed to run job {job_id} now: {e}")
            return False, f"خطا: {str(e)}"
    
    async def cleanup_old_jobs(self, days: int = 30):
        """Clean up old completed/failed jobs"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            jobs_to_remove = []
            
            for job_id, job in self.jobs.items():
                if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                    job.updated_at < cutoff_date):
                    jobs_to_remove.append(job_id)
            
            # Remove from memory
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
            
            # Remove from database
            await self.db.cleanup_old_jobs(days)
            
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
    
    def get_scheduler_stats(self) -> Dict:
        """Get scheduler statistics"""
        total_jobs = len(self.jobs)
        active_jobs = len([j for j in self.jobs.values() if j.enabled])
        running_jobs = len(self.running_jobs)
        
        # Count by status
        status_counts = {}
        for status in JobStatus:
            status_counts[status.value] = sum(
                1 for j in self.jobs.values() if j.status == status
            )
        
        # Count by schedule type
        schedule_counts = {}
        for schedule_type in ScheduleType:
            schedule_counts[schedule_type.value] = sum(
                1 for j in self.jobs.values() if j.schedule_type == schedule_type
            )
        
        return {
            "total_jobs": total_jobs,
            "active_jobs": active_jobs,
            "running_jobs": running_jobs,
            "status_distribution": status_counts,
            "schedule_distribution": schedule_counts,
            "is_running": self.is_running
        }

# Utility functions for scheduling
def format_schedule_display(schedule_type: str, schedule_value: str) -> str:
    """Format schedule for display"""
    if schedule_type == ScheduleType.ONCE.value:
        try:
            dt = datetime.fromisoformat(schedule_value)
            return f"یکبار در {dt.strftime('%Y-%m-%d %H:%M')}"
        except:
            return "یکبار"
    
    elif schedule_type == ScheduleType.INTERVAL.value:
        if schedule_value.endswith("m"):
            mins = int(schedule_value[:-1])
            return f"هر {mins} دقیقه"
        elif schedule_value.endswith("h"):
            hours = int(schedule_value[:-1])
            return f"هر {hours} ساعت"
        elif schedule_value.endswith("d"):
            days = int(schedule_value[:-1])
            return f"هر {days} روز"
        else:
            return f"هر {schedule_value} دقیقه"
    
    elif schedule_type == ScheduleType.CRON.value:
        return f"طبق کرون: {schedule_value}"
    
    elif schedule_type == ScheduleType.DAILY.value:
        return f"روزانه ساعت {schedule_value}"
    
    elif schedule_type == ScheduleType.HOURLY.value:
        hours = int(schedule_value)
        return f"ساعتی (هر {hours} ساعت)"
    
    return "نامشخص"

def calculate_next_runs(job: ScheduledJob, count: int = 5) -> List[datetime]:
    """Calculate next N run times"""
    runs = []
    
    if not job.enabled or job.max_executions == 0:
        return runs
    
    next_run = job.next_run or job.calculate_next_run()
    if not next_run:
        return runs
    
    current = next_run
    runs.append(current)
    
    for _ in range(count - 1):
        # Calculate next run based on schedule type
        if job.schedule_type == ScheduleType.INTERVAL:
            interval = job._parse_interval(job.schedule_value)
            if interval:
                current = current + interval
                runs.append(current)
        elif job.schedule_type == ScheduleType.CRON:
            cron = croniter.croniter(job.schedule_value, current)
            current = cron.get_next(datetime)
            runs.append(current)
        elif job.schedule_type == ScheduleType.DAILY:
            current = current + timedelta(days=1)
            runs.append(current)
        elif job.schedule_type == ScheduleType.HOURLY:
            hours = int(job.schedule_value)
            current = current + timedelta(hours=hours)
            runs.append(current)
        else:
            break
    
    return runs

if __name__ == "__main__":
    # Test scheduler
    import asyncio
    
    async def test():
        from report_engine import ReportEngine
        from connection_pool import ConnectionPool
        from anti_detection import AntiDetectionSystem
        
        config = get_config()
        session_manager = None  # Mock
        connection_pool = ConnectionPool(config, session_manager)
        anti_detection = AntiDetectionSystem()
        report_engine = ReportEngine(connection_pool, anti_detection)
        
        scheduler = ReportScheduler(report_engine)
        
        print(f"Scheduler created")
        print(f"Stats: {scheduler.get_scheduler_stats()}")
        
        await scheduler.start()
        await asyncio.sleep(2)
        await scheduler.stop()
    
    asyncio.run(test())