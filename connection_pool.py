#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Connection Pool - Manage pool of Telegram clients
Lines: ~1500
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set, Deque
from collections import deque, defaultdict
from enum import Enum
import hashlib
import pickle
from dataclasses import dataclass, field

# Telegram
from pyrogram import Client
from pyrogram.errors import (
    FloodWait, AuthKeyUnregistered, SessionPasswordNeeded,
    PhoneCodeInvalid, PhoneCodeExpired
)

# Local imports
from config_manager import get_config
from session_manager import SessionInfo, SessionManager

logger = logging.getLogger(__name__)

class AccountStatus(Enum):
    """Account status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"
    FLOOD_WAIT = "flood_wait"
    EXPIRED = "expired"
    UNHEALTHY = "unhealthy"

@dataclass
class AccountStats:
    """Account statistics"""
    total_reports: int = 0
    successful_reports: int = 0
    failed_reports: int = 0
    total_requests: int = 0
    flood_wait_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    average_response_time: float = 0.0
    
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_reports == 0:
            return 0.0
        return (self.successful_reports / self.total_reports) * 100
    
    def update_success(self, response_time: float = 0.0):
        """Update stats on success"""
        self.total_reports += 1
        self.successful_reports += 1
        self.total_requests += 1
        self.last_success = datetime.now()
        
        # Update average response time
        if self.average_response_time == 0:
            self.average_response_time = response_time
        else:
            self.average_response_time = (
                self.average_response_time * 0.7 + response_time * 0.3
            )
    
    def update_failure(self, is_flood_wait: bool = False):
        """Update stats on failure"""
        self.total_reports += 1
        self.failed_reports += 1
        self.total_requests += 1
        self.last_failure = datetime.now()
        
        if is_flood_wait:
            self.flood_wait_count += 1

@dataclass
class PooledAccount:
    """Account in connection pool"""
    phone_number: str
    session_info: SessionInfo
    client: Optional[Client] = None
    status: AccountStatus = AccountStatus.ACTIVE
    stats: AccountStats = field(default_factory=AccountStats)
    
    # Connection management
    last_used: Optional[datetime] = None
    last_checked: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    
    # Resource tracking
    concurrent_uses: int = 0
    max_concurrent: int = 1
    
    # Health metrics
    health_score: float = 100.0
    suspicion_level: float = 0.0
    error_history: List[str] = field(default_factory=list)
    
    def is_available(self) -> bool:
        """Check if account is available for use"""
        if self.status != AccountStatus.ACTIVE:
            return False
        
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
        
        if self.concurrent_uses >= self.max_concurrent:
            return False
        
        # Check health score
        if self.health_score < 30.0:
            return False
        
        # Check suspicion level
        if self.suspicion_level > 0.7:
            return False
        
        # Check if recently used (cooldown)
        if self.last_used:
            time_since_last = datetime.now() - self.last_used
            if time_since_last.total_seconds() < 5:  # 5 second cooldown
                return False
        
        return True
    
    def can_report(self, max_reports_per_hour: int) -> bool:
        """Check if account can perform more reports"""
        # Check hourly limit
        if self.last_used:
            hour_ago = datetime.now() - timedelta(hours=1)
            recent_reports = 0
            
            # This would need tracking per hour in production
            # For now, using simple check
            if self.stats.total_reports > 0:
                # Estimate based on total reports and time
                hours_active = max(1, (datetime.now() - self.session_info.created_at).total_seconds() / 3600)
                avg_per_hour = self.stats.total_reports / hours_active
                if avg_per_hour > max_reports_per_hour * 0.8:
                    return False
        
        return True
    
    def update_health_score(self):
        """Update health score based on metrics"""
        score = 100.0
        
        # Deduct for failures
        failure_rate = self.stats.failed_reports / max(self.stats.total_reports, 1)
        score -= failure_rate * 40
        
        # Deduct for flood waits
        if self.stats.flood_wait_count > 0:
            score -= min(self.stats.flood_wait_count * 5, 30)
        
        # Deduct for suspicion
        score -= self.suspicion_level * 20
        
        # Deduct for recent errors
        if self.error_history:
            recent_errors = len([e for e in self.error_history[-10:] 
                               if "flood" in e.lower() or "ban" in e.lower()])
            score -= recent_errors * 10
        
        # Bonus for success rate
        success_rate = self.stats.success_rate()
        if success_rate > 80:
            score += 10
        elif success_rate > 90:
            score += 20
        
        self.health_score = max(0.0, min(100.0, score))
        
        # Update status based on health
        if self.health_score < 30:
            self.status = AccountStatus.UNHEALTHY
        elif self.health_score < 60:
            self.status = AccountStatus.INACTIVE
    
    def add_error(self, error_msg: str):
        """Add error to history"""
        self.error_history.append(f"{datetime.now().isoformat()}: {error_msg}")
        
        # Keep only last 20 errors
        if len(self.error_history) > 20:
            self.error_history = self.error_history[-20:]
        
        # Increase suspicion for certain errors
        if any(keyword in error_msg.lower() for keyword in 
               ["flood", "ban", "spam", "suspicious"]):
            self.suspicion_level = min(1.0, self.suspicion_level + 0.1)
        
        self.update_health_score()

class ConnectionPool:
    """Manage pool of Telegram connections"""
    
    def __init__(self, config, session_manager: SessionManager):
        self.config = config
        self.session_manager = session_manager
        
        # Pool storage
        self.accounts: Dict[str, PooledAccount] = {}
        self.account_queue: Deque[str] = deque()
        self.lock = asyncio.Lock()
        
        # Statistics
        self.pool_stats = {
            "total_accounts": 0,
            "active_accounts": 0,
            "banned_accounts": 0,
            "total_reports": 0,
            "successful_reports": 0,
            "pool_hit_rate": 0.0,
            "average_wait_time": 0.0
        }
        
        # Load balancing
        self.load_balancing = {
            "strategy": "round_robin",  # or "health_based", "success_rate"
            "last_selected": None,
            "selection_count": 0
        }
        
        # Start maintenance tasks
        self.maintenance_task = asyncio.create_task(self._maintenance_loop())
        
        logger.info("Connection pool initialized")
    
    async def initialize(self):
        """Initialize connection pool with all sessions"""
        try:
            async with self.lock:
                # Load all sessions
                for phone_number, session_info in self.session_manager.sessions.items():
                    await self._add_account_to_pool(phone_number, session_info)
                
                logger.info(f"Pool initialized with {len(self.accounts)} accounts")
                
        except Exception as e:
            logger.error(f"Failed to initialize pool: {e}")
    
    async def _add_account_to_pool(self, phone_number: str, session_info: SessionInfo):
        """Add account to pool"""
        account = PooledAccount(
            phone_number=phone_number,
            session_info=session_info
        )
        
        self.accounts[phone_number] = account
        self.account_queue.append(phone_number)
        
        # Update stats
        self.pool_stats["total_accounts"] += 1
        if account.status == AccountStatus.ACTIVE:
            self.pool_stats["active_accounts"] += 1
        elif account.status == AccountStatus.BANNED:
            self.pool_stats["banned_accounts"] += 1
    
    async def get_client(self, phone_number: str) -> Optional[Client]:
        """Get client for specific phone number"""
        try:
            account = self.accounts.get(phone_number)
            if not account or not account.is_available():
                return None
            
            # Check if client exists and is connected
            if account.client:
                try:
                    # Test connection
                    await account.client.get_me()
                    return account.client
                except (AuthKeyUnregistered, ConnectionError):
                    # Client needs reconnection
                    await self._reconnect_client(account)
            
            # Create new client
            client = await self.session_manager.get_client(phone_number)
            if client:
                account.client = client
                account.last_checked = datetime.now()
                return client
            
            # Mark as unavailable if can't get client
            account.status = AccountStatus.INACTIVE
            return None
            
        except Exception as e:
            logger.error(f"Failed to get client for {phone_number}: {e}")
            
            if account:
                account.add_error(f"get_client failed: {str(e)}")
                account.status = AccountStatus.UNHEALTHY
            
            return None
    
    async def get_available_accounts(self, count: int = 10) -> List[PooledAccount]:
        """Get available accounts for reporting"""
        try:
            available_accounts = []
            
            async with self.lock:
                # Try different selection strategies
                if self.load_balancing["strategy"] == "health_based":
                    accounts = await self._select_by_health(count)
                elif self.load_balancing["strategy"] == "success_rate":
                    accounts = await self._select_by_success_rate(count)
                else:  # round_robin
                    accounts = await self._select_round_robin(count)
                
                # Verify and prepare accounts
                for account in accounts:
                    if await self._prepare_account(account):
                        available_accounts.append(account)
                        
                        if len(available_accounts) >= count:
                            break
            
            self.load_balancing["selection_count"] += 1
            
            # Rotate strategy every 100 selections
            if self.load_balancing["selection_count"] % 100 == 0:
                await self._rotate_selection_strategy()
            
            return available_accounts
            
        except Exception as e:
            logger.error(f"Failed to get available accounts: {e}")
            return []
    
    async def _select_round_robin(self, count: int) -> List[PooledAccount]:
        """Select accounts using round-robin strategy"""
        selected = []
        
        for _ in range(min(count * 2, len(self.account_queue))):  # Try 2x needed
            if not self.account_queue:
                break
            
            phone_number = self.account_queue.popleft()
            self.account_queue.append(phone_number)
            
            account = self.accounts.get(phone_number)
            if account and account.is_available():
                selected.append(account)
                
                if len(selected) >= count:
                    break
        
        return selected
    
    async def _select_by_health(self, count: int) -> List[PooledAccount]:
        """Select accounts by health score"""
        # Get all available accounts
        all_accounts = [
            acc for acc in self.accounts.values() 
            if acc.is_available()
        ]
        
        # Sort by health score (descending)
        all_accounts.sort(key=lambda x: x.health_score, reverse=True)
        
        return all_accounts[:count]
    
    async def _select_by_success_rate(self, count: int) -> List[PooledAccount]:
        """Select accounts by success rate"""
        # Get all available accounts
        all_accounts = [
            acc for acc in self.accounts.values() 
            if acc.is_available() and acc.stats.total_reports > 0
        ]
        
        # Sort by success rate (descending)
        all_accounts.sort(key=lambda x: x.stats.success_rate(), reverse=True)
        
        return all_accounts[:count]
    
    async def _prepare_account(self, account: PooledAccount) -> bool:
        """Prepare account for use"""
        try:
            # Check limits
            if not account.can_report(self.config.reporting.max_reports_per_account_per_hour):
                return False
            
            # Get or create client
            if not account.client:
                client = await self.session_manager.get_client(account.phone_number)
                if not client:
                    account.status = AccountStatus.INACTIVE
                    return False
                account.client = client
            
            # Test connection
            try:
                start_time = time.time()
                await account.client.get_me()
                response_time = time.time() - start_time
                
                # Update stats
                account.stats.total_requests += 1
                account.last_checked = datetime.now()
                
                # If response too slow, mark for cooldown
                if response_time > 5.0:
                    account.cooldown_until = datetime.now() + timedelta(minutes=5)
                    return False
                
                return True
                
            except AuthKeyUnregistered:
                account.status = AccountStatus.EXPIRED
                return False
            except FloodWait as e:
                account.status = AccountStatus.FLOOD_WAIT
                account.cooldown_until = datetime.now() + timedelta(seconds=e.value)
                account.add_error(f"Flood wait: {e.value}s")
                return False
            except Exception as e:
                account.add_error(f"Connection test failed: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to prepare account {account.phone_number}: {e}")
            account.add_error(f"Preparation failed: {str(e)}")
            return False
    
    async def acquire_account(self) -> Optional[PooledAccount]:
        """Acquire an account for use"""
        try:
            accounts = await self.get_available_accounts(1)
            if not accounts:
                return None
            
            account = accounts[0]
            account.concurrent_uses += 1
            account.last_used = datetime.now()
            
            return account
            
        except Exception as e:
            logger.error(f"Failed to acquire account: {e}")
            return None
    
    def release_account(self, phone_number: str, 
                       success: bool = True, 
                       response_time: float = 0.0,
                       error: str = None):
        """Release an account after use"""
        try:
            account = self.accounts.get(phone_number)
            if not account:
                return
            
            account.concurrent_uses = max(0, account.concurrent_uses - 1)
            
            # Update statistics
            if success:
                account.stats.update_success(response_time)
                self.pool_stats["successful_reports"] += 1
                
                # Decrease suspicion on success
                account.suspicion_level = max(0.0, account.suspicion_level - 0.05)
            else:
                account.stats.update_failure("flood" in error.lower() if error else False)
                
                if error:
                    account.add_error(error)
            
            self.pool_stats["total_reports"] += 1
            
            # Apply cooldown based on usage
            if success:
                # Success cooldown (shorter)
                cooldown = random.uniform(
                    self.config.reporting.min_delay_between_actions,
                    self.config.reporting.max_delay_between_actions
                )
            else:
                # Failure cooldown (longer)
                cooldown = random.uniform(30, 120)  # 30-120 seconds
            
            account.cooldown_until = datetime.now() + timedelta(seconds=cooldown)
            
            # Update health score
            account.update_health_score()
            
        except Exception as e:
            logger.error(f"Failed to release account {phone_number}: {e}")
    
    async def get_any_client(self) -> Optional[Client]:
        """Get any available client (for validation purposes)"""
        try:
            accounts = await self.get_available_accounts(1)
            if not accounts:
                return None
            
            account = accounts[0]
            return account.client
            
        except Exception as e:
            logger.error(f"Failed to get any client: {e}")
            return None
    
    async def get_available_accounts_count(self) -> int:
        """Get count of available accounts"""
        try:
            count = 0
            for account in self.accounts.values():
                if account.is_available():
                    count += 1
            return count
        except Exception as e:
            logger.error(f"Failed to count available accounts: {e}")
            return 0
    
    async def check_account_health(self, phone_number: str) -> Dict:
        """Check health of specific account"""
        try:
            account = self.accounts.get(phone_number)
            if not account:
                return {"error": "Account not found"}
            
            # Test connection
            client = await self.get_client(phone_number)
            if not client:
                return {
                    "status": "inactive",
                    "health_score": account.health_score,
                    "error": "Cannot get client"
                }
            
            # Perform health check
            try:
                start_time = time.time()
                user = await client.get_me()
                response_time = time.time() - start_time
                
                health_data = {
                    "phone_number": phone_number,
                    "status": account.status.value,
                    "health_score": round(account.health_score, 2),
                    "suspicion_level": round(account.suspicion_level, 3),
                    "success_rate": round(account.stats.success_rate(), 2),
                    "total_reports": account.stats.total_reports,
                    "response_time": round(response_time, 3),
                    "username": user.username,
                    "first_name": user.first_name,
                    "is_bot": user.is_bot,
                    "last_used": account.last_used.isoformat() if account.last_used else None,
                    "concurrent_uses": account.concurrent_uses,
                    "cooldown_until": account.cooldown_until.isoformat() if account.cooldown_until else None
                }
                
                # Update account health based on response
                if response_time < 2.0:
                    account.health_score = min(100, account.health_score + 5)
                else:
                    account.health_score = max(0, account.health_score - 10)
                
                return health_data
                
            except FloodWait as e:
                account.status = AccountStatus.FLOOD_WAIT
                account.cooldown_until = datetime.now() + timedelta(seconds=e.value)
                return {
                    "status": "flood_wait",
                    "wait_time": e.value,
                    "health_score": account.health_score
                }
            except AuthKeyUnregistered:
                account.status = AccountStatus.EXPIRED
                return {"status": "expired", "health_score": 0}
            except Exception as e:
                account.add_error(f"Health check failed: {str(e)}")
                return {
                    "status": "error",
                    "error": str(e),
                    "health_score": account.health_score
                }
            
        except Exception as e:
            logger.error(f"Health check failed for {phone_number}: {e}")
            return {"error": str(e)}
    
    async def check_all_accounts_health(self) -> List[Dict]:
        """Check health of all accounts"""
        results = []
        
        for phone_number in list(self.accounts.keys()):
            try:
                health = await self.check_account_health(phone_number)
                health["phone_number"] = phone_number
                results.append(health)
                
                # Delay between checks to avoid flooding
                await asyncio.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"Failed to check health for {phone_number}: {e}")
                results.append({
                    "phone_number": phone_number,
                    "error": str(e)
                })
        
        return results
    
    async def rotate_accounts(self, percentage: float = 0.3):
        """Rotate a percentage of accounts"""
        try:
            logger.info(f"Starting account rotation ({percentage*100}%)")
            
            # Get active accounts
            active_accounts = [
                acc for acc in self.accounts.values() 
                if acc.status == AccountStatus.ACTIVE
            ]
            
            # Select accounts to rotate
            num_to_rotate = max(1, int(len(active_accounts) * percentage))
            accounts_to_rotate = random.sample(active_accounts, 
                                             min(num_to_rotate, len(active_accounts)))
            
            rotated = 0
            
            for account in accounts_to_rotate:
                try:
                    # Disconnect client
                    if account.client:
                        await account.client.disconnect()
                        account.client = None
                    
                    # Apply cooldown
                    account.cooldown_until = datetime.now() + timedelta(minutes=30)
                    
                    # Reset suspicion
                    account.suspicion_level = max(0.0, account.suspicion_level - 0.3)
                    
                    # Update health
                    account.health_score = min(100.0, account.health_score + 10.0)
                    
                    rotated += 1
                    
                    logger.debug(f"Rotated account {account.phone_number}")
                    
                except Exception as e:
                    logger.error(f"Failed to rotate account {account.phone_number}: {e}")
                
                # Delay between rotations
                await asyncio.sleep(random.uniform(2, 5))
            
            logger.info(f"Account rotation completed: {rotated} accounts rotated")
            return rotated
            
        except Exception as e:
            logger.error(f"Account rotation failed: {e}")
            return 0
    
    async def _reconnect_client(self, account: PooledAccount):
        """Reconnect client for account"""
        try:
            if account.client:
                try:
                    await account.client.disconnect()
                except:
                    pass
            
            # Get new client
            client = await self.session_manager.get_client(account.phone_number)
            if client:
                account.client = client
                account.last_checked = datetime.now()
                logger.info(f"Reconnected client for {account.phone_number}")
            else:
                account.status = AccountStatus.INACTIVE
                logger.warning(f"Failed to reconnect {account.phone_number}")
                
        except Exception as e:
            logger.error(f"Failed to reconnect client for {account.phone_number}: {e}")
            account.status = AccountStatus.INACTIVE
    
    async def _rotate_selection_strategy(self):
        """Rotate load balancing strategy"""
        strategies = ["round_robin", "health_based", "success_rate"]
        current = self.load_balancing["strategy"]
        
        # Move to next strategy
        current_index = strategies.index(current) if current in strategies else 0
        next_index = (current_index + 1) % len(strategies)
        
        self.load_balancing["strategy"] = strategies[next_index]
        logger.info(f"Load balancing strategy changed to: {self.load_balancing['strategy']}")
    
    async def _maintenance_loop(self):
        """Maintenance loop for pool management"""
        while True:
            try:
                # Run maintenance every 5 minutes
                await asyncio.sleep(300)
                
                await self._perform_maintenance()
                
            except Exception as e:
                logger.error(f"Maintenance loop error: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def _perform_maintenance(self):
        """Perform maintenance tasks"""
        try:
            logger.debug("Running connection pool maintenance")
            
            # 1. Clean up expired accounts
            await self._cleanup_expired_accounts()
            
            # 2. Update health scores
            for account in self.accounts.values():
                account.update_health_score()
            
            # 3. Reconnect inactive but healthy accounts
            await self._reconnect_inactive_accounts()
            
            # 4. Update pool statistics
            self._update_pool_stats()
            
            # 5. Log pool status
            self._log_pool_status()
            
        except Exception as e:
            logger.error(f"Maintenance failed: {e}")
    
    async def _cleanup_expired_accounts(self):
        """Clean up expired or banned accounts"""
        to_remove = []
        
        for phone_number, account in self.accounts.items():
            # Remove banned accounts older than 7 days
            if account.status == AccountStatus.BANNED:
                if account.last_checked:
                    days_since_check = (datetime.now() - account.last_checked).days
                    if days_since_check > 7:
                        to_remove.append(phone_number)
            
            # Remove expired accounts
            elif account.status == AccountStatus.EXPIRED:
                to_remove.append(phone_number)
        
        # Remove from pool
        for phone_number in to_remove:
            account = self.accounts.pop(phone_number, None)
            if account:
                # Remove from queue
                if phone_number in self.account_queue:
                    self.account_queue.remove(phone_number)
                
                # Update stats
                self.pool_stats["total_accounts"] -= 1
                if account.status == AccountStatus.BANNED:
                    self.pool_stats["banned_accounts"] -= 1
                
                logger.info(f"Removed {account.status.value} account: {phone_number}")
    
    async def _reconnect_inactive_accounts(self):
        """Attempt to reconnect inactive but healthy accounts"""
        for account in self.accounts.values():
            if (account.status == AccountStatus.INACTIVE and 
                account.health_score > 50 and
                account.suspicion_level < 0.5):
                
                try:
                    await self._reconnect_client(account)
                    await asyncio.sleep(1)  # Delay between reconnections
                except Exception as e:
                    logger.debug(f"Failed to reconnect {account.phone_number}: {e}")
    
    def _update_pool_stats(self):
        """Update pool statistics"""
        total = len(self.accounts)
        active = sum(1 for acc in self.accounts.values() 
                    if acc.status == AccountStatus.ACTIVE)
        
        self.pool_stats.update({
            "total_accounts": total,
            "active_accounts": active,
            "inactive_accounts": total - active,
            "average_health_score": sum(acc.health_score for acc in self.accounts.values()) / max(total, 1)
        })
    
    def _log_pool_status(self):
        """Log pool status"""
        if random.random() < 0.1:  # Log 10% of the time
            logger.info(
                f"Pool Status: {self.pool_stats['active_accounts']}/"
                f"{self.pool_stats['total_accounts']} active, "
                f"Avg health: {self.pool_stats['average_health_score']:.1f}"
            )
    
    def get_pool_stats(self) -> Dict:
        """Get pool statistics"""
        stats = self.pool_stats.copy()
        
        # Add detailed account status counts
        status_counts = {}
        for status in AccountStatus:
            status_counts[status.value] = sum(
                1 for acc in self.accounts.values() 
                if acc.status == status
            )
        
        stats["status_distribution"] = status_counts
        stats["load_balancing_strategy"] = self.load_balancing["strategy"]
        
        # Calculate pool utilization
        total_concurrent = sum(acc.concurrent_uses for acc in self.accounts.values())
        stats["current_utilization"] = total_concurrent
        stats["max_concurrent_allowed"] = sum(acc.max_concurrent for acc in self.accounts.values())
        
        return stats
    
    async def close_all(self):
        """Close all connections"""
        try:
            logger.info("Closing all connections in pool")
            
            for account in self.accounts.values():
                if account.client:
                    try:
                        await account.client.disconnect()
                    except:
                        pass
            
            # Cancel maintenance task
            if self.maintenance_task:
                self.maintenance_task.cancel()
                try:
                    await self.maintenance_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("All connections closed")
            
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

# Utility functions for connection management
def calculate_account_score(account: PooledAccount) -> float:
    """Calculate score for account selection"""
    score = account.health_score
    
    # Bonus for high success rate
    success_rate = account.stats.success_rate()
    if success_rate > 80:
        score += 20
    elif success_rate > 60:
        score += 10
    
    # Penalty for recent use
    if account.last_used:
        minutes_since_last = (datetime.now() - account.last_used).total_seconds() / 60
        if minutes_since_last < 5:
            score -= 30
        elif minutes_since_last < 15:
            score -= 10
    
    # Bonus for low suspicion
    score -= account.suspicion_level * 30
    
    return max(0, score)

def should_rotate_account(account: PooledAccount) -> bool:
    """Determine if account should be rotated"""
    # Rotate if suspicion is high
    if account.suspicion_level > 0.6:
        return True
    
    # Rotate if health is low
    if account.health_score < 40:
        return True
    
    # Rotate if used heavily recently
    if account.last_used:
        hours_since_last = (datetime.now() - account.last_used).total_seconds() / 3600
        if hours_since_last < 1 and account.stats.total_requests > 10:
            return True
    
    return False

if __name__ == "__main__":
    # Test connection pool
    import asyncio
    
    async def test():
        from config_manager import get_config
        from session_manager import SessionManager
        
        config = get_config()
        session_manager = SessionManager(config)
        
        pool = ConnectionPool(config, session_manager)
        
        print(f"Connection pool created")
        print(f"Pool stats: {pool.get_pool_stats()}")
        
        # Test account acquisition
        accounts = await pool.get_available_accounts(3)
        print(f"Available accounts: {len(accounts)}")
        
        await pool.close_all()
    
    asyncio.run(test())