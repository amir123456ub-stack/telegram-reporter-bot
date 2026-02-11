#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helpers - Common helper functions
Lines: ~300
"""

import re
import random
import string
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from pathlib import Path
import secrets

def format_number(number: int) -> str:
    """Format number with commas"""
    return f"{number:,}"

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable"""
    if seconds < 60:
        return f"{seconds:.1f} ثانیه"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} دقیقه"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f} ساعت"
    else:
        days = seconds / 86400
        return f"{days:.1f} روز"

def format_datetime(dt: datetime, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime to string"""
    return dt.strftime(format)

def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse datetime from string"""
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None

def extract_username(text: str) -> Optional[str]:
    """Extract username from text"""
    # Pattern for @username
    pattern = r'@([a-zA-Z][a-zA-Z0-9_]{3,31}[a-zA-Z0-9])'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    
    # Pattern for t.me/username
    pattern = r't\.me/([a-zA-Z][a-zA-Z0-9_]{3,31}[a-zA-Z0-9])'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    
    return None

def extract_message_id(text: str) -> Optional[int]:
    """Extract message ID from text"""
    # Pattern for t.me/username/123
    pattern = r't\.me/[^/]+/(\d+)'
    match = re.search(pattern, text)
    if match:
        return int(match.group(1))
    
    # Pattern for t.me/c/123/456
    pattern = r't\.me/c/\d+/(\d+)'
    match = re.search(pattern, text)
    if match:
        return int(match.group(1))
    
    return None

def generate_id(prefix: str = "", length: int = 8) -> str:
    """Generate unique ID"""
    timestamp = int(datetime.now().timestamp())
    random_str = secrets.token_hex(4)
    unique_id = f"{timestamp:x}{random_str}"
    
    if prefix:
        return f"{prefix}_{unique_id[:length]}"
    return unique_id[:length]

def generate_random_string(length: int = 8) -> str:
    """Generate random string"""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def safe_get(data: Dict, *keys, default=None) -> Any:
    """Safely get nested dictionary value"""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        
        if current is None:
            return default
    
    return current

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def format_size(size_bytes: int) -> str:
    """Format file size to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    
    return f"{size_bytes:.1f} PB"

def calculate_hash(text: str, algorithm: str = "md5") -> str:
    """Calculate hash of text"""
    if algorithm == "md5":
        return hashlib.md5(text.encode()).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(text.encode()).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(text.encode()).hexdigest()
    else:
        return hashlib.md5(text.encode()).hexdigest()

def time_ago(dt: datetime) -> str:
    """Get human readable time ago"""
    now = datetime.now()
    diff = now - dt
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} سال پیش"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} ماه پیش"
    elif diff.days > 0:
        return f"{diff.days} روز پیش"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} ساعت پیش"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} دقیقه پیش"
    else:
        return "چند لحظه پیش"

def merge_dicts(dict1: Dict, dict2: Dict, overwrite: bool = True) -> Dict:
    """Merge two dictionaries"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key not in result or overwrite:
            result[key] = value
    
    return result

def sanitize_filename(filename: str) -> str:
    """Sanitize filename"""
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    return filename

def is_async_callable(obj) -> bool:
    """Check if object is async callable"""
    import asyncio
    import inspect
    
    return (
        asyncio.iscoroutinefunction(obj) or
        inspect.isawaitable(obj) or
        hasattr(obj, '__call__') and asyncio.iscoroutinefunction(obj.__call__)
    )

def to_boolean(value: Any) -> bool:
    """Convert value to boolean"""
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes', 'on', 'y']
    
    return bool(value)

def to_json(obj: Any, indent: int = None) -> str:
    """Convert object to JSON string"""
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Type {type(obj)} not serializable")
    
    return json.dumps(obj, default=json_serializer, indent=indent, ensure_ascii=False)

def from_json(json_str: str) -> Optional[Any]:
    """Parse JSON string to object"""
    try:
        return json.loads(json_str)
    except:
        return None

def retry_async(max_retries: int = 3, delay: float = 1.0):
    """Decorator for async retry"""
    import asyncio
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        wait = delay * (attempt + 1)
                        await asyncio.sleep(wait)
                    else:
                        raise last_exception
            
            raise last_exception
        
        return wrapper
    
    return decorator