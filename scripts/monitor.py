#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System Monitor - Health monitoring and alerting
Lines: ~200
"""

import os
import sys
import asyncio
import logging
import psutil
import platform
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import get_config
from database import DatabaseManager
from connection_pool import ConnectionPool
from session_manager import SessionManager
from utils.logger import setup_logger, get_logger
from utils.helpers import format_size, format_duration

logger = logging.getLogger(__name__)

class SystemMonitor:
    """System health monitor"""
    
    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.connection_pool = None
        self.session_manager = None
        
        # Alert thresholds
        self.thresholds = {
            "cpu_percent": 80,
            "memory_percent": 80,
            "disk_percent": 90,
            "database_size_mb": 500,
            "active_accounts": 10,
            "account_health_score": 50,
            "flood_wait_count": 5,
            "error_rate": 0.1  # 10%
        }
        
        # Alert history
        self.alert_history: List[Dict] = []
    
    def set_dependencies(self, connection_pool: ConnectionPool, session_manager: SessionManager):
        """Set required dependencies"""
        self.connection_pool = connection_pool
        self.session_manager = session_manager
    
    def check_system_resources(self) -> Dict:
        """
        Check system resource usage
        
        Returns:
            Dictionary with system metrics
        """
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used = memory.used
            memory_total = memory.total
            
            # Disk
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_used = disk.used
            disk_total = disk.total
            
            # Network
            network = psutil.net_io_counters()
            bytes_sent = network.bytes_sent
            bytes_recv = network.bytes_recv
            
            # System info
            system = {
                "platform": platform.system(),
                "release": platform.release(),
                "processor": platform.processor(),
                "hostname": platform.node(),
                "uptime": format_duration(time() - psutil.boot_time())
            }
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "status": "normal" if cpu_percent < self.thresholds["cpu_percent"] else "warning"
                },
                "memory": {
                    "percent": memory_percent,
                    "used": memory_used,
                    "total": memory_total,
                    "used_formatted": format_size(memory_used),
                    "total_formatted": format_size(memory_total),
                    "status": "normal" if memory_percent < self.thresholds["memory_percent"] else "warning"
                },
                "disk": {
                    "percent": disk_percent,
                    "used": disk_used,
                    "total": disk_total,
                    "used_formatted": format_size(disk_used),
                    "total_formatted": format_size(disk_total),
                    "status": "normal" if disk_percent < self.thresholds["disk_percent"] else "warning"
                },
                "network": {
                    "sent": bytes_sent,
                    "received": bytes_recv,
                    "sent_formatted": format_size(bytes_sent),
                    "received_formatted": format_size(bytes_recv)
                },
                "system": system,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to check system resources: {e}")
            return {"error": str(e)}
    
    async def check_database_health(self) -> Dict:
        """
        Check database health
        
        Returns:
            Dictionary with database metrics
        """
        try:
            db_path = Path("bot_database.db")
            
            if not db_path.exists():
                return {"error": "Database file not found"}
            
            # Database size
            size_bytes = db_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            
            # Get database stats
            total_users = await self.db.get_user_count()
            total_reports = await self.db.get_total_reports_count()
            active_jobs = await self.db.execute_query(
                "SELECT COUNT(*) as count FROM scheduled_jobs WHERE enabled = 1"
            )
            active_jobs_count = active_jobs[0]["count"] if active_jobs else 0
            
            # Check for corruption
            is_corrupted = False
            try:
                async with await self.db.get_connection() as conn:
                    await conn.execute("SELECT COUNT(*) FROM users")
            except:
                is_corrupted = True
            
            return {
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "size_formatted": format_size(size_bytes),
                "total_users": total_users,
                "total_reports": total_reports,
                "active_jobs": active_jobs_count,
                "is_corrupted": is_corrupted,
                "status": "warning" if size_mb > self.thresholds["database_size_mb"] else "normal",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to check database health: {e}")
            return {"error": str(e)}
    
    async def check_accounts_health(self) -> Dict:
        """
        Check accounts health
        
        Returns:
            Dictionary with account metrics
        """
        try:
            if not self.connection_pool:
                return {"error": "Connection pool not available"}
            
            # Get pool stats
            pool_stats = self.connection_pool.get_pool_stats()
            
            # Get account health distribution
            health_distribution = {}
            for account in self.connection_pool.accounts.values():
                health = account.health_status.value
                health_distribution[health] = health_distribution.get(health, 0) + 1
            
            # Calculate average health score
            total_accounts = pool_stats.get("total_accounts", 0)
            total_health = sum(acc.health_score for acc in self.connection_pool.accounts.values())
            avg_health = total_health / total_accounts if total_accounts > 0 else 0
            
            # Count flood wait accounts
            flood_wait_count = sum(
                1 for acc in self.connection_pool.accounts.values()
                if acc.status.value == "flood_wait"
            )
            
            return {
                "total_accounts": pool_stats.get("total_accounts", 0),
                "active_accounts": pool_stats.get("active_accounts", 0),
                "banned_accounts": pool_stats.get("banned_accounts", 0),
                "flood_wait_count": flood_wait_count,
                "average_health_score": round(avg_health, 2),
                "health_distribution": health_distribution,
                "status": "warning" if avg_health < self.thresholds["account_health_score"] else "normal",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to check accounts health: {e}")
            return {"error": str(e)}
    
    async def check_reporting_health(self) -> Dict:
        """
        Check reporting system health
        
        Returns:
            Dictionary with reporting metrics
        """
        try:
            # Get recent reports
            last_hour = datetime.now() - timedelta(hours=1)
            recent_reports = await self.db.get_reports_count_since(1)
            
            # Get successful reports
            successful_reports = await self.db.get_successful_reports_count_since(1)
            
            # Calculate error rate
            error_rate = 0
            if recent_reports > 0:
                error_rate = (recent_reports - successful_reports) / recent_reports
            
            # Get average response time
            avg_response_time = await self.db.get_average_report_time()
            
            return {
                "reports_last_hour": recent_reports,
                "successful_reports": successful_reports,
                "error_rate": round(error_rate * 100, 2),
                "average_response_time": round(avg_response_time, 2),
                "status": "warning" if error_rate > self.thresholds["error_rate"] else "normal",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to check reporting health: {e}")
            return {"error": str(e)}
    
    async def check_all(self) -> Dict:
        """
        Comprehensive system health check
        
        Returns:
            Dictionary with all health metrics
        """
        try:
            health_report = {
                "timestamp": datetime.now().isoformat(),
                "system": self.check_system_resources(),
                "database": await self.check_database_health(),
                "accounts": await self.check_accounts_health(),
                "reporting": await self.check_reporting_health(),
                "overall_status": "normal"
            }
            
            # Determine overall status
            statuses = []
            
            if "status" in health_report["system"]:
                statuses.append(health_report["system"]["status"])
            
            if "status" in health_report["database"]:
                statuses.append(health_report["database"]["status"])
            
            if "status" in health_report["accounts"]:
                statuses.append(health_report["accounts"]["status"])
            
            if "status" in health_report["reporting"]:
                statuses.append(health_report["reporting"]["status"])
            
            if "warning" in statuses:
                health_report["overall_status"] = "warning"
            elif "error" in statuses or any("error" in s for s in statuses):
                health_report["overall_status"] = "error"
            
            return health_report
            
        except Exception as e:
            logger.error(f"Failed to check all health: {e}")
            return {"error": str(e), "overall_status": "error"}
    
    async def send_alert(self, message: str, level: str = "warning"):
        """
        Send alert to admins
        
        Args:
            message: Alert message
            level: Alert level (info, warning, error, critical)
        """
        try:
            # Alert colors
            colors = {
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
                "critical": "🚨"
            }
            
            emoji = colors.get(level, "⚠️")
            
            alert_text = (
                f"{emoji} **هشدار سیستم**\n\n"
                f"📌 سطح: {level.upper()}\n"
                f"📝 پیام: {message}\n"
                f"🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Store in history
            self.alert_history.append({
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": message
            })
            
            # Keep only last 100 alerts
            if len(self.alert_history) > 100:
                self.alert_history = self.alert_history[-100:]
            
            # Send to admins (would use bot client in production)
            logger.warning(f"ALERT [{level.upper()}]: {message}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def generate_report(self) -> str:
        """
        Generate human-readable health report
        
        Returns:
            Formatted health report string
        """
        # This is a sync method that would run async checks
        # In production, this should be async
        return "Health report generation requires async context"

def check_system_health() -> Dict:
    """Convenience function to check system health"""
    import asyncio
    
    async def _check():
        monitor = SystemMonitor()
        return await monitor.check_all()
    
    return asyncio.run(_check())

def send_alert(message: str, level: str = "warning"):
    """Convenience function to send alert"""
    import asyncio
    
    async def _send():
        monitor = SystemMonitor()
        await monitor.send_alert(message, level)
    
    asyncio.run(_send())

async def main_async():
    """Async main entry point"""
    # Setup logging
    setup_logger("monitor", log_level="INFO")
    
    logger.info("=" * 50)
    logger.info("System Monitor")
    logger.info("=" * 50)
    
    monitor = SystemMonitor()
    health = await monitor.check_all()
    
    print(json.dumps(health, indent=2, ensure_ascii=False))
    
    return 0

def main():
    """Main entry point"""
    return asyncio.run(main_async())

if __name__ == "__main__":
    sys.exit(main())