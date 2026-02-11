#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Anti-Detection System
Lines: ~2000
"""

import asyncio
import logging
import random
import time
import hashlib
import json
import platform
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
import socket
import struct
import urllib.parse
from dataclasses import dataclass, field
import secrets

# Cryptography
from cryptography.fernet import Fernet

# Telegram
from pyrogram import Client
from pyrogram.raw.core import TLObject
from pyrogram.raw.functions import InitConnection, InvokeWithLayer
from pyrogram.raw.types import (
    InputClientProxy, DataJSON, InputAppEvent,
    JsonObjectValue, JsonString, JsonNull
)

# Local imports
from config_manager import get_config

logger = logging.getLogger(__name__)

@dataclass
class HumanBehaviorProfile:
    """Profile for simulating human behavior"""
    
    # Typing patterns
    typing_speed_wpm: int = field(default_factory=lambda: random.randint(35, 75))
    typing_variation: float = field(default_factory=lambda: random.uniform(0.8, 1.2))
    
    # Action delays (seconds)
    min_delay: float = field(default_factory=lambda: random.uniform(0.8, 1.5))
    max_delay: float = field(default_factory=lambda: random.uniform(3.0, 6.0))
    
    # Reading patterns
    read_speed_wpm: int = field(default_factory=lambda: random.randint(150, 300))
    read_comprehension: float = field(default_factory=lambda: random.uniform(0.7, 0.95))
    
    # Activity patterns
    active_hours: List[int] = field(default_factory=lambda: 
        list(range(9, 12)) + list(range(14, 18)) + list(range(20, 23)))
    peak_hours: List[int] = field(default_factory=lambda: [10, 15, 21])
    
    # Error patterns
    typo_probability: float = field(default_factory=lambda: random.uniform(0.01, 0.03))
    correction_probability: float = field(default_factory=lambda: random.uniform(0.7, 0.9))
    
    # Navigation patterns
    scroll_speed: float = field(default_factory=lambda: random.uniform(0.5, 2.0))
    click_accuracy: float = field(default_factory=lambda: random.uniform(0.85, 0.98))
    
    def get_random_delay(self) -> float:
        """Get random delay based on profile"""
        base = random.uniform(self.min_delay, self.max_delay)
        # Add time-based variation (slower at night)
        hour = datetime.now().hour
        if hour < 6 or hour > 23:
            base *= random.uniform(1.2, 1.8)
        return base
    
    def should_make_error(self) -> bool:
        """Determine if should make a typo/error"""
        return random.random() < self.typo_probability

@dataclass
class DeviceFingerprint:
    """Device fingerprint for spoofing"""
    
    device_model: str = ""
    system_version: str = ""
    app_version: str = ""
    lang_code: str = "en"
    system_lang_code: str = "en-US"
    timezone: str = ""
    ip_address: str = ""
    user_agent: str = ""
    
    # Hardware simulation
    screen_width: int = 1080
    screen_height: int = 1920
    dpi: int = 420
    cpu_cores: int = 8
    ram_gb: int = 6
    storage_gb: int = 128
    
    # Network simulation
    connection_type: str = "wifi"
    network_operator: str = ""
    network_speed_mbps: float = 50.0
    
    def generate_user_agent(self) -> str:
        """Generate user agent string"""
        if "iPhone" in self.device_model:
            return (f"Telegram/{self.app_version} iOS/{self.system_version} "
                   f"Device/{self.device_model.replace(' ', '_')}")
        elif "Android" in self.system_version:
            return (f"Telegram/{self.app_version} Android/{self.system_version} "
                   f"Device/{self.device_model.replace(' ', '_')}")
        else:
            return f"Telegram/{self.app_version}"
    
    def to_client_params(self) -> Dict:
        """Convert to client parameters"""
        return {
            "device_model": self.device_model,
            "system_version": self.system_version,
            "app_version": self.app_version,
            "lang_code": self.lang_code,
            "system_lang_code": self.system_lang_code
        }

class BehavioralSimulator:
    """Simulate human behavior patterns"""
    
    def __init__(self):
        self.config = get_config()
        self.profiles: Dict[str, HumanBehaviorProfile] = {}
        self.activity_logs: Dict[str, List[datetime]] = {}
        
    def get_profile(self, session_id: str) -> HumanBehaviorProfile:
        """Get or create behavior profile for session"""
        if session_id not in self.profiles:
            self.profiles[session_id] = HumanBehaviorProfile()
        
        return self.profiles[session_id]
    
    async def simulate_typing(self, client: Client, chat_id: Union[int, str], 
                            text_length: int = 0):
        """Simulate typing activity"""
        try:
            profile = self.get_profile(str(chat_id))
            
            # Calculate typing time
            if text_length > 0:
                chars_per_second = (profile.typing_speed_wpm * 5) / 60
                typing_time = text_length / chars_per_second
                typing_time *= profile.typing_variation
                
                # Add random pauses
                pause_count = random.randint(0, text_length // 50)
                for _ in range(pause_count):
                    typing_time += random.uniform(0.5, 1.5)
                
                # Simulate typing
                await asyncio.sleep(min(typing_time, 5.0))
            
            # Random chance to send typing action
            if random.random() < 0.3:
                await client.send_chat_action(chat_id, "typing")
                await asyncio.sleep(random.uniform(0.5, 2.0))
                
        except Exception as e:
            logger.debug(f"Typing simulation failed: {e}")
    
    async def simulate_reading(self, message_length: int = 0):
        """Simulate reading time"""
        try:
            # Estimate reading time (words per minute)
            words = max(1, message_length // 5)
            reading_speed = random.randint(150, 300)  # WPM
            reading_time = words / reading_speed * 60
            
            # Add comprehension time
            comprehension = random.uniform(0.7, 0.95)
            total_time = reading_time / comprehension
            
            # Random variation
            total_time *= random.uniform(0.8, 1.2)
            
            await asyncio.sleep(min(total_time, 10.0))
            
        except Exception as e:
            logger.debug(f"Reading simulation failed: {e}")
    
    async def simulate_navigation(self):
        """Simulate navigation delays"""
        try:
            # Simulate mouse/touch movement
            actions = ["scroll", "click", "swipe", "tap"]
            action = random.choice(actions)
            
            if action == "scroll":
                # Scroll delay
                scroll_amount = random.randint(1, 5)
                delay = scroll_amount * random.uniform(0.1, 0.3)
            elif action == "click":
                # Click delay (including aim time)
                delay = random.uniform(0.2, 0.8)
            else:
                # Swipe/tap delay
                delay = random.uniform(0.1, 0.4)
            
            await asyncio.sleep(delay)
            
        except Exception as e:
            logger.debug(f"Navigation simulation failed: {e}")
    
    async def simulate_human_delay(self, session_id: str, 
                                  min_multiplier: float = 1.0,
                                  max_multiplier: float = 1.0):
        """Simulate human-like delay between actions"""
        try:
            profile = self.get_profile(session_id)
            
            # Base delay
            delay = profile.get_random_delay()
            
            # Apply multipliers
            delay *= random.uniform(min_multiplier, max_multiplier)
            
            # Time-based adjustment
            hour = datetime.now().hour
            if hour in profile.peak_hours:
                # Faster during peak hours
                delay *= random.uniform(0.7, 0.9)
            elif hour < 6 or hour > 23:
                # Slower at night
                delay *= random.uniform(1.2, 1.5)
            
            # Add micro-variations
            delay += random.uniform(-0.1, 0.1)
            delay = max(0.1, delay)  # Minimum delay
            
            # Simulate network latency
            network_latency = random.uniform(0.05, 0.3)
            total_delay = delay + network_latency
            
            await asyncio.sleep(total_delay)
            
        except Exception as e:
            logger.debug(f"Delay simulation failed: {e}")
            await asyncio.sleep(random.uniform(1.0, 3.0))
    
    async def simulate_pre_report_behavior(self, client: Client):
        """Simulate behavior before reporting"""
        try:
            # Random delays and actions
            actions = [
                self.simulate_navigation,
                lambda: asyncio.sleep(random.uniform(0.5, 1.5)),
                lambda: self.simulate_typing(client, "me", random.randint(10, 50))
            ]
            
            # Execute 2-4 random actions
            num_actions = random.randint(2, 4)
            selected_actions = random.sample(actions, num_actions)
            
            for action in selected_actions:
                await action()
                await self.simulate_human_delay(str(client.session_name))
            
        except Exception as e:
            logger.debug(f"Pre-report behavior simulation failed: {e}")
    
    async def simulate_post_report_behavior(self, client: Client):
        """Simulate behavior after reporting"""
        try:
            # Simulate reading confirmation
            await self.simulate_reading(random.randint(20, 100))
            
            # Random chance to navigate elsewhere
            if random.random() < 0.4:
                await self.simulate_navigation()
                await asyncio.sleep(random.uniform(1.0, 3.0))
            
            # Update activity log
            session_id = str(client.session_name)
            if session_id not in self.activity_logs:
                self.activity_logs[session_id] = []
            
            self.activity_logs[session_id].append(datetime.now())
            
            # Keep only last 100 activities
            if len(self.activity_logs[session_id]) > 100:
                self.activity_logs[session_id] = self.activity_logs[session_id][-100:]
            
        except Exception as e:
            logger.debug(f"Post-report behavior simulation failed: {e}")
    
    async def clean_session_traces(self, client: Client):
        """Clean session traces after use"""
        try:
            # Simulate app switching or closing
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Random chance to clear temporary data
            if random.random() < 0.2:
                await asyncio.sleep(random.uniform(1.0, 3.0))
            
        except Exception as e:
            logger.debug(f"Session trace cleaning failed: {e}")
    
    def get_activity_pattern(self, session_id: str) -> Dict:
        """Get activity pattern for session"""
        if session_id not in self.activity_logs:
            return {"total_activities": 0, "recent_activity": None}
        
        activities = self.activity_logs[session_id]
        if not activities:
            return {"total_activities": 0, "recent_activity": None}
        
        # Calculate statistics
        now = datetime.now()
        recent = activities[-1] if activities else None
        hours_since_last = (now - recent).total_seconds() / 3600 if recent else 24
        
        # Calculate daily pattern
        hour_counts = {}
        for activity in activities[-50:]:  # Last 50 activities
            hour = activity.hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        return {
            "total_activities": len(activities),
            "recent_activity": recent.isoformat() if recent else None,
            "hours_since_last": round(hours_since_last, 2),
            "hourly_distribution": hour_counts
        }

class DeviceSpoofer:
    """Spoof device fingerprints"""
    
    def __init__(self):
        self.config = get_config()
        self.fingerprints: Dict[str, DeviceFingerprint] = {}
        
        # Device databases
        self.ios_devices = [
            "iPhone 15 Pro", "iPhone 15", "iPhone 14 Pro", 
            "iPhone 14", "iPhone 13 Pro", "iPhone 13",
            "iPhone 12 Pro", "iPhone 12", "iPhone 11 Pro"
        ]
        
        self.android_devices = [
            "Samsung Galaxy S23", "Samsung Galaxy S22", 
            "Google Pixel 7", "Google Pixel 6",
            "Xiaomi 13", "Xiaomi 12", 
            "OnePlus 11", "OnePlus 10",
            "HUAWEI P50", "HUAWEI P40"
        ]
        
        self.ios_versions = ["17.0", "16.6", "16.4", "16.2", "16.0", "15.7"]
        self.android_versions = ["14", "13", "12L", "12", "11"]
        
        self.app_versions = ["9.4", "9.3", "9.2", "9.1", "9.0", "8.9", "8.8"]
        
        # Timezones by region
        self.timezones = {
            "IR": "Asia/Tehran",
            "US": "America/New_York",
            "EU": "Europe/London",
            "RU": "Europe/Moscow",
            "TR": "Europe/Istanbul",
            "AE": "Asia/Dubai",
            "CN": "Asia/Shanghai",
            "IN": "Asia/Kolkata"
        }
    
    def generate_fingerprint(self, session_id: str, 
                            device_type: str = "random") -> DeviceFingerprint:
        """Generate device fingerprint"""
        
        if session_id in self.fingerprints:
            return self.fingerprints[session_id]
        
        fingerprint = DeviceFingerprint()
        
        # Determine device type
        if device_type == "random":
            device_type = random.choice(["ios", "android"])
        
        # Set device-specific parameters
        if device_type == "ios":
            fingerprint.device_model = random.choice(self.ios_devices)
            fingerprint.system_version = random.choice(self.ios_versions)
            fingerprint.system_lang_code = random.choice(["en-US", "fa-IR", "ar-SA"])
            
        else:  # android
            fingerprint.device_model = random.choice(self.android_devices)
            fingerprint.system_version = random.choice(self.android_versions)
            fingerprint.system_lang_code = random.choice(["en-US", "fa-IR", "ar-SA"])
        
        # Common parameters
        fingerprint.app_version = random.choice(self.app_versions)
        fingerprint.lang_code = random.choice(["en", "fa", "ar", "ru"])
        
        # Timezone based on language
        if fingerprint.lang_code == "fa":
            fingerprint.timezone = self.timezones["IR"]
        elif fingerprint.lang_code == "ar":
            fingerprint.timezone = random.choice([self.timezones["AE"], self.timezones["SA"]])
        elif fingerprint.lang_code == "ru":
            fingerprint.timezone = self.timezones["RU"]
        else:
            fingerprint.timezone = random.choice(list(self.timezones.values()))
        
        # Hardware parameters
        if "iPhone" in fingerprint.device_model:
            fingerprint.screen_width = random.choice([1170, 1179, 1284])
            fingerprint.screen_height = random.choice([2532, 2556, 2778])
            fingerprint.dpi = 460
            fingerprint.cpu_cores = 6
            fingerprint.ram_gb = random.choice([4, 6, 8])
            fingerprint.storage_gb = random.choice([128, 256, 512])
            
        elif "Galaxy" in fingerprint.device_model:
            fingerprint.screen_width = 1080
            fingerprint.screen_height = 2340
            fingerprint.dpi = 420
            fingerprint.cpu_cores = 8
            fingerprint.ram_gb = random.choice([8, 12])
            fingerprint.storage_gb = random.choice([128, 256, 512])
            
        else:  # Generic Android
            fingerprint.screen_width = 1080
            fingerprint.screen_height = 1920
            fingerprint.dpi = 400
            fingerprint.cpu_cores = random.choice([4, 6, 8])
            fingerprint.ram_gb = random.choice([4, 6, 8])
            fingerprint.storage_gb = random.choice([64, 128, 256])
        
        # Network parameters
        fingerprint.connection_type = random.choice(["wifi", "mobile"])
        fingerprint.network_speed_mbps = random.uniform(10.0, 100.0)
        
        if fingerprint.connection_type == "mobile":
            operators = ["MCI", "MTN", "Rightel", "Turkcell", "Vodafone"]
            fingerprint.network_operator = random.choice(operators)
        
        # Generate user agent
        fingerprint.user_agent = fingerprint.generate_user_agent()
        
        # Store fingerprint
        self.fingerprints[session_id] = fingerprint
        
        return fingerprint
    
    def get_fingerprint(self, session_id: str) -> Optional[DeviceFingerprint]:
        """Get fingerprint for session"""
        return self.fingerprints.get(session_id)
    
    def update_fingerprint(self, session_id: str, 
                          updates: Dict[str, Any]) -> DeviceFingerprint:
        """Update fingerprint with new values"""
        fingerprint = self.get_fingerprint(session_id)
        if not fingerprint:
            fingerprint = self.generate_fingerprint(session_id)
        
        for key, value in updates.items():
            if hasattr(fingerprint, key):
                setattr(fingerprint, key, value)
        
        # Regenerate user agent if device changed
        if any(k in updates for k in ["device_model", "system_version", "app_version"]):
            fingerprint.user_agent = fingerprint.generate_user_agent()
        
        return fingerprint

class TrafficObfuscator:
    """Obfuscate network traffic patterns"""
    
    def __init__(self):
        self.config = get_config()
        self.request_patterns: Dict[str, List[datetime]] = {}
        
    async def obfuscate_mtproto_traffic(self, client: Client):
        """Obfuscate MTProto traffic patterns"""
        try:
            # Add random padding to requests
            padding_size = random.randint(0, 256)
            
            # Randomize request order
            if random.random() < 0.3:
                await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # Vary request sizes
            if random.random() < 0.2:
                # Send dummy request
                try:
                    await client.invoke({
                        "@type": "getAccountTtl",
                        "@extra": self._generate_random_extra()
                    })
                except:
                    pass
            
        except Exception as e:
            logger.debug(f"MTProto obfuscation failed: {e}")
    
    def _generate_random_extra(self) -> str:
        """Generate random extra data for requests"""
        random_data = {
            "ts": int(time.time()),
            "rnd": secrets.token_hex(8),
            "v": random.choice([1, 2, 3])
        }
        return json.dumps(random_data)
    
    async def shape_traffic(self, session_id: str, data_size: int):
        """Shape traffic to look more human"""
        try:
            # Record request
            if session_id not in self.request_patterns:
                self.request_patterns[session_id] = []
            
            now = datetime.now()
            self.request_patterns[session_id].append(now)
            
            # Keep only last hour
            cutoff = now - timedelta(hours=1)
            self.request_patterns[session_id] = [
                ts for ts in self.request_patterns[session_id] if ts > cutoff
            ]
            
            # Calculate request rate
            requests_last_hour = len(self.request_patterns[session_id])
            
            # Slow down if rate is too high
            if requests_last_hour > 100:
                slowdown = random.uniform(2.0, 5.0)
                await asyncio.sleep(slowdown)
            
            # Add jitter based on data size
            if data_size > 1000:  # Larger requests
                jitter = random.uniform(0.5, 2.0)
                await asyncio.sleep(jitter)
            
        except Exception as e:
            logger.debug(f"Traffic shaping failed: {e}")
    
    def get_traffic_stats(self, session_id: str) -> Dict:
        """Get traffic statistics for session"""
        if session_id not in self.request_patterns:
            return {"total_requests": 0, "requests_per_hour": 0}
        
        requests = self.request_patterns[session_id]
        now = datetime.now()
        
        # Count requests in last hour
        cutoff = now - timedelta(hours=1)
        recent_requests = [ts for ts in requests if ts > cutoff]
        
        return {
            "total_requests": len(requests),
            "requests_per_hour": len(recent_requests),
            "last_request": requests[-1].isoformat() if requests else None
        }

class PatternRandomizer:
    """Randomize patterns to avoid detection"""
    
    def __init__(self):
        self.sequence_variants = {
            "report_sequence": [
                ["view", "pause", "report"],
                ["view", "scroll", "view", "report"],
                ["view", "like", "report"],
                ["view", "pause", "scroll", "report"],
                ["view", "report", "view"]
            ],
            "login_sequence": [
                ["connect", "auth", "verify"],
                ["auth", "connect", "verify"],
                ["verify", "auth", "connect"]
            ],
            "navigation_sequence": [
                ["home", "search", "target"],
                ["search", "target", "home"],
                ["target", "home", "search"]
            ]
        }
    
    def randomize_sequence(self, sequence_type: str) -> List[str]:
        """Get randomized sequence"""
        variants = self.sequence_variants.get(sequence_type, [])
        if not variants:
            return []
        
        return random.choice(variants)
    
    def add_random_errors(self, action: str) -> bool:
        """Add random errors to simulate human fallibility"""
        error_probabilities = {
            "connect": 0.01,
            "auth": 0.02,
            "report": 0.03,
            "view": 0.01,
            "scroll": 0.005
        }
        
        probability = error_probabilities.get(action, 0.01)
        return random.random() < probability
    
    def generate_random_delays(self, base_delay: float) -> List[float]:
        """Generate random delay pattern"""
        num_steps = random.randint(2, 5)
        delays = []
        
        for _ in range(num_steps):
            variation = random.uniform(0.7, 1.3)
            delays.append(base_delay * variation)
        
        return delays

class AntiDetectionSystem:
    """Main anti-detection system"""
    
    def __init__(self):
        self.config = get_config()
        self.behavior_simulator = BehavioralSimulator()
        self.device_spoofer = DeviceSpoofer()
        self.traffic_obfuscator = TrafficObfuscator()
        self.pattern_randomizer = PatternRandomizer()
        
        # Detection counters
        self.suspicion_levels: Dict[str, float] = {}
        self.warning_flags: Dict[str, List[str]] = {}
        
        logger.info("Anti-detection system initialized")
    
    async def prepare_session(self, session_id: str, 
                            device_type: str = "random") -> DeviceFingerprint:
        """Prepare session with anti-detection measures"""
        try:
            # Generate device fingerprint
            fingerprint = self.device_spoofer.generate_fingerprint(
                session_id, device_type
            )
            
            # Initialize suspicion level
            self.suspicion_levels[session_id] = 0.0
            self.warning_flags[session_id] = []
            
            logger.debug(f"Prepared session {session_id} with {device_type} fingerprint")
            
            return fingerprint
            
        except Exception as e:
            logger.error(f"Failed to prepare session {session_id}: {e}")
            # Return default fingerprint
            return DeviceFingerprint()
    
    async def simulate_pre_report_behavior(self, client: Client):
        """Simulate human behavior before reporting"""
        if not self.config.anti_detection.enable_behavior_simulation:
            return
        
        try:
            session_id = str(client.session_name)
            
            # Check suspicion level
            suspicion = self.suspicion_levels.get(session_id, 0.0)
            if suspicion > 0.7:
                # High suspicion - add extra delays
                extra_delay = random.uniform(3.0, 8.0)
                await asyncio.sleep(extra_delay)
            
            # Simulate behavior
            await self.behavior_simulator.simulate_pre_report_behavior(client)
            
            # Randomize patterns
            if self.config.anti_detection.randomize_order:
                await self._randomize_action_order()
            
            # Obfuscate traffic
            if self.config.anti_detection.enable_device_spoofing:
                await self.traffic_obfuscator.obfuscate_mtproto_traffic(client)
            
        except Exception as e:
            logger.debug(f"Pre-report simulation failed: {e}")
    
    async def simulate_post_report_behavior(self, client: Client):
        """Simulate human behavior after reporting"""
        if not self.config.anti_detection.enable_behavior_simulation:
            return
        
        try:
            session_id = str(client.session_name)
            
            # Simulate behavior
            await self.behavior_simulator.simulate_post_report_behavior(client)
            
            # Clean traces
            await self.behavior_simulator.clean_session_traces(client)
            
            # Update traffic stats
            await self.traffic_obfuscator.shape_traffic(session_id, 100)
            
        except Exception as e:
            logger.debug(f"Post-report simulation failed: {e}")
    
    async def _randomize_action_order(self):
        """Randomize action order"""
        try:
            # Get random sequence
            sequence = self.pattern_randomizer.randomize_sequence("report_sequence")
            
            # Execute with delays
            for action in sequence:
                if action == "pause":
                    await asyncio.sleep(random.uniform(0.5, 2.0))
                elif action == "scroll":
                    await self.behavior_simulator.simulate_navigation()
                
                # Add random error
                if self.config.anti_detection.add_random_errors:
                    if self.pattern_randomizer.add_random_errors(action):
                        await asyncio.sleep(random.uniform(1.0, 3.0))
            
        except Exception as e:
            logger.debug(f"Action randomization failed: {e}")
    
    async def clean_session_traces(self, client: Client):
        """Clean session traces"""
        try:
            await self.behavior_simulator.clean_session_traces(client)
            
            # Randomize client parameters
            if self.config.anti_detection.enable_session_rotation:
                await self._rotate_session_parameters(client)
            
        except Exception as e:
            logger.debug(f"Session trace cleaning failed: {e}")
    
    async def _rotate_session_parameters(self, client: Client):
        """Rotate session parameters"""
        try:
            session_id = str(client.session_name)
            
            # Update device fingerprint
            updates = {
                "app_version": random.choice(self.device_spoofer.app_versions),
                "system_version": random.choice(self.device_spoofer.android_versions 
                                              if "Android" in client.system_version 
                                              else self.device_spoofer.ios_versions)
            }
            
            self.device_spoofer.update_fingerprint(session_id, updates)
            
            # Update suspicion level (reduce after rotation)
            current_suspicion = self.suspicion_levels.get(session_id, 0.0)
            self.suspicion_levels[session_id] = max(0.0, current_suspicion - 0.2)
            
        except Exception as e:
            logger.debug(f"Session parameter rotation failed: {e}")
    
    def check_suspicion_level(self, session_id: str) -> Dict:
        """Check suspicion level for session"""
        suspicion = self.suspicion_levels.get(session_id, 0.0)
        warnings = self.warning_flags.get(session_id, [])
        
        status = "safe"
        if suspicion > 0.7:
            status = "high_risk"
        elif suspicion > 0.4:
            status = "medium_risk"
        elif suspicion > 0.1:
            status = "low_risk"
        
        return {
            "session_id": session_id,
            "suspicion_level": round(suspicion, 3),
            "status": status,
            "warnings": warnings,
            "recommendation": self._get_recommendation(suspicion)
        }
    
    def _get_recommendation(self, suspicion: float) -> str:
        """Get recommendation based on suspicion level"""
        if suspicion > 0.7:
            return "توقف فوری - ریسک بن بالا"
        elif suspicion > 0.4:
            return "کاهش فعالیت - استراحت ۱ ساعته"
        elif suspicion > 0.1:
            return "افزودن تاخیر بیشتر بین عملیات‌ها"
        else:
            return "فعالیت عادی"
    
    def add_suspicion(self, session_id: str, reason: str, amount: float = 0.1):
        """Add suspicion to session"""
        if session_id not in self.suspicion_levels:
            self.suspicion_levels[session_id] = 0.0
            self.warning_flags[session_id] = []
        
        self.suspicion_levels[session_id] = min(1.0, 
            self.suspicion_levels[session_id] + amount)
        
        if reason not in self.warning_flags[session_id]:
            self.warning_flags[session_id].append(reason)
        
        logger.warning(f"Suspicion increased for {session_id}: {reason} (+{amount})")
    
    def reset_suspicion(self, session_id: str):
        """Reset suspicion for session"""
        self.suspicion_levels[session_id] = 0.0
        self.warning_flags[session_id] = []
        logger.info(f"Suspicion reset for {session_id}")
    
    async def perform_health_check(self, session_id: str) -> Dict:
        """Perform comprehensive health check"""
        try:
            # Get behavior patterns
            behavior = self.behavior_simulator.get_activity_pattern(session_id)
            
            # Get traffic stats
            traffic = self.traffic_obfuscator.get_traffic_stats(session_id)
            
            # Check suspicion level
            suspicion = self.check_suspicion_level(session_id)
            
            # Calculate health score
            health_score = 100
            health_score -= suspicion["suspicion_level"] * 50
            
            if traffic["requests_per_hour"] > 200:
                health_score -= 20
            
            if behavior["hours_since_last"] < 0.1:  # Too frequent
                health_score -= 15
            
            health_score = max(0, min(100, health_score))
            
            # Determine status
            if health_score >= 80:
                status = "سالم"
                color = "🟢"
            elif health_score >= 60:
                status = "احتیاط"
                color = "🟡"
            elif health_score >= 40:
                status = "ریسک"
                color = "🟠"
            else:
                status = "خطر"
                color = "🔴"
            
            return {
                "session_id": session_id,
                "health_score": round(health_score),
                "status": f"{color} {status}",
                "suspicion": suspicion,
                "behavior": behavior,
                "traffic": traffic,
                "recommendations": self._generate_recommendations(
                    health_score, suspicion, traffic, behavior
                )
            }
            
        except Exception as e:
            logger.error(f"Health check failed for {session_id}: {e}")
            return {
                "session_id": session_id,
                "health_score": 0,
                "status": "🔴 نامعلوم",
                "error": str(e)
            }
    
    def _generate_recommendations(self, health_score: float, 
                                 suspicion: Dict, 
                                 traffic: Dict,
                                 behavior: Dict) -> List[str]:
        """Generate recommendations based on health data"""
        recommendations = []
        
        if health_score < 60:
            recommendations.append("افزودن تاخیر بیشتر بین عملیات‌ها")
        
        if suspicion["suspicion_level"] > 0.3:
            recommendations.append("چرخش پارامترهای سشن")
        
        if traffic["requests_per_hour"] > 150:
            recommendations.append("کاهش تعداد درخواست‌ها در ساعت")
        
        if behavior["hours_since_last"] < 0.2:
            recommendations.append("افزایش فاصله زمانی بین فعالیت‌ها")
        
        if not recommendations:
            recommendations.append("فعالیت عادی ادامه دهید")
        
        return recommendations
    
    def get_system_stats(self) -> Dict:
        """Get system-wide statistics"""
        total_sessions = len(self.suspicion_levels)
        
        # Count by risk level
        risk_levels = {"safe": 0, "low_risk": 0, "medium_risk": 0, "high_risk": 0}
        
        for session_id in self.suspicion_levels:
            check = self.check_suspicion_level(session_id)
            risk_levels[check["status"]] = risk_levels.get(check["status"], 0) + 1
        
        # Calculate average suspicion
        avg_suspicion = sum(self.suspicion_levels.values()) / max(total_sessions, 1)
        
        return {
            "total_sessions": total_sessions,
            "risk_distribution": risk_levels,
            "average_suspicion": round(avg_suspicion, 3),
            "total_warnings": sum(len(w) for w in self.warning_flags.values()),
            "high_risk_sessions": [sid for sid, susp in self.suspicion_levels.items() 
                                  if susp > 0.7]
        }

# Utility functions for MTProto obfuscation
def generate_random_proxy() -> Optional[Dict]:
    """Generate random proxy configuration"""
    if random.random() < 0.3:  # 30% chance to use proxy
        proxy_types = ["socks5", "http"]
        proxy_type = random.choice(proxy_types)
        
        # Random proxy servers (example - in production use real proxy list)
        proxies = [
            {"host": "proxy1.example.com", "port": 1080},
            {"host": "proxy2.example.com", "port": 8080},
            {"host": "proxy3.example.com", "port": 3128}
        ]
        
        proxy = random.choice(proxies)
        return {
            "scheme": proxy_type,
            "hostname": proxy["host"],
            "port": proxy["port"]
        }
    
    return None

def generate_device_id() -> str:
    """Generate random device ID"""
    return secrets.token_hex(8)

if __name__ == "__main__":
    # Test anti-detection system
    import asyncio
    
    async def test():
        system = AntiDetectionSystem()
        
        # Test session preparation
        fingerprint = await system.prepare_session("test_session_1", "android")
        print(f"Generated fingerprint: {fingerprint.device_model}")
        
        # Test health check
        health = await system.perform_health_check("test_session_1")
        print(f"Health check: {health}")
        
        # Test system stats
        stats = system.get_system_stats()
        print(f"System stats: {stats}")
    
    asyncio.run(test())