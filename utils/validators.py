#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validators - Input validation utilities
Lines: ~200
"""

import re
from typing import Tuple, Optional, Union
from urllib.parse import urlparse

def validate_telegram_link(link: str, expected_type: str = None) -> Tuple[bool, Optional[str]]:
    """
    Validate Telegram link
    
    Args:
        link: Telegram link to validate
        expected_type: Expected type (channel, group, user, post)
        
    Returns:
        Tuple of (is_valid, extracted_username_or_id)
    """
    if not link:
        return False, None
    
    # Clean the link
    link = link.strip()
    
    # Remove protocol
    clean_link = link.replace('https://', '').replace('http://', '')
    
    # Patterns for different types
    patterns = {
        'channel': [
            r'^t\.me/([a-zA-Z][a-zA-Z0-9_]{3,31}[a-zA-Z0-9])$',
            r'^@([a-zA-Z][a-zA-Z0-9_]{3,31}[a-zA-Z0-9])$'
        ],
        'group': [
            r'^t\.me/([a-zA-Z][a-zA-Z0-9_]{3,31}[a-zA-Z0-9])$',
            r'^@([a-zA-Z][a-zA-Z0-9_]{3,31}[a-zA-Z0-9])$',
            r'^t\.me/joinchat/([a-zA-Z0-9_-]{22})$',
            r'^\+([a-zA-Z0-9_-]{22})$'
        ],
        'user': [
            r'^t\.me/([a-zA-Z][a-zA-Z0-9_]{4,31}[a-zA-Z0-9])$',
            r'^@([a-zA-Z][a-zA-Z0-9_]{4,31}[a-zA-Z0-9])$',
            r'^\d{5,}$'  # User ID
        ],
        'post': [
            r'^t\.me/([a-zA-Z][a-zA-Z0-9_]{3,31}[a-zA-Z0-9])/(\d+)$',
            r'^t\.me/c/(\d+)/(\d+)$'  # Private channel
        ]
    }
    
    # Check all patterns if no type specified
    if not expected_type:
        for type_name, type_patterns in patterns.items():
            for pattern in type_patterns:
                match = re.match(pattern, clean_link)
                if match:
                    return True, (match.group(1) if match.lastindex == 1 else match.groups())
        return False, None
    
    # Check specific type
    if expected_type in patterns:
        for pattern in patterns[expected_type]:
            match = re.match(pattern, clean_link)
            if match:
                return True, (match.group(1) if match.lastindex == 1 else match.groups())
    
    return False, None

def validate_phone_number(phone: str) -> Tuple[bool, str]:
    """
    Validate phone number
    
    Args:
        phone: Phone number to validate
        
    Returns:
        Tuple of (is_valid, formatted_phone)
    """
    if not phone:
        return False, ""
    
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', phone)
    
    # Check length
    if len(cleaned) < 10 or len(cleaned) > 15:
        return False, cleaned
    
    # Format with country code
    if cleaned.startswith('0'):
        cleaned = '98' + cleaned[1:]
    elif not cleaned.startswith('98'):
        cleaned = '98' + cleaned
    
    # Final format with +
    formatted = '+' + cleaned
    
    return True, formatted

def validate_username(username: str) -> Tuple[bool, str]:
    """
    Validate Telegram username
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, cleaned_username)
    """
    if not username:
        return False, ""
    
    # Clean the username
    cleaned = username.strip().lower()
    
    # Remove @ if present
    if cleaned.startswith('@'):
        cleaned = cleaned[1:]
    
    # Remove t.me/ if present
    if cleaned.startswith('t.me/'):
        cleaned = cleaned[5:]
    
    # Check format
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]{3,31}[a-zA-Z0-9]$'
    
    if re.match(pattern, cleaned):
        return True, cleaned
    
    return False, cleaned

def validate_message_id(message_id: Union[int, str]) -> Tuple[bool, int]:
    """
    Validate Telegram message ID
    
    Args:
        message_id: Message ID to validate
        
    Returns:
        Tuple of (is_valid, message_id_int)
    """
    try:
        if isinstance(message_id, str):
            message_id = int(message_id)
        
        return message_id > 0, message_id
    except (ValueError, TypeError):
        return False, 0

def validate_chat_id(chat_id: Union[int, str]) -> Tuple[bool, int]:
    """
    Validate Telegram chat ID
    
    Args:
        chat_id: Chat ID to validate
        
    Returns:
        Tuple of (is_valid, chat_id_int)
    """
    try:
        if isinstance(chat_id, str):
            chat_id = int(chat_id)
        
        return True, chat_id
    except (ValueError, TypeError):
        return False, 0

def validate_report_reason(reason: str) -> bool:
    """
    Validate report reason
    
    Args:
        reason: Report reason to validate
        
    Returns:
        True if valid
    """
    valid_reasons = [
        'خشونت', 'سوء استفاده کودک', 'پورنوگرافی', 'مواد مخدر',
        'اطلاعات شخصی', 'اسپم', 'کلاهبرداری', 'اکانت جعلی',
        'کپی رایت', 'دیگر'
    ]
    
    return reason in valid_reasons

def validate_account_count(count: Union[int, str], max_allowed: int) -> Tuple[bool, int]:
    """
    Validate account count
    
    Args:
        count: Account count to validate
        max_allowed: Maximum allowed count
        
    Returns:
        Tuple of (is_valid, count_int)
    """
    try:
        if isinstance(count, str):
            count = int(count)
        
        if 1 <= count <= max_allowed:
            return True, count
        
        return False, 0
    except (ValueError, TypeError):
        return False, 0

def validate_subscription_days(days: Union[int, str]) -> Tuple[bool, int]:
    """
    Validate subscription days
    
    Args:
        days: Days to validate
        
    Returns:
        Tuple of (is_valid, days_int)
    """
    try:
        if isinstance(days, str):
            days = int(days)
        
        if 1 <= days <= 365:
            return True, days
        
        return False, 0
    except (ValueError, TypeError):
        return False, 0

def validate_json(json_str: str) -> Tuple[bool, Optional[dict]]:
    """
    Validate JSON string
    
    Args:
        json_str: JSON string to validate
        
    Returns:
        Tuple of (is_valid, parsed_json)
    """
    import json
    
    try:
        data = json.loads(json_str)
        return True, data
    except (json.JSONDecodeError, TypeError):
        return False, None

def validate_email(email: str) -> bool:
    """
    Validate email address
    
    Args:
        email: Email to validate
        
    Returns:
        True if valid
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

def validate_ip_address(ip: str) -> bool:
    """
    Validate IP address
    
    Args:
        ip: IP address to validate
        
    Returns:
        True if valid
    """
    import ipaddress
    
    try:
        ipaddress.ip_address(ip.strip())
        return True
    except ValueError:
        return False

def validate_url(url: str, allowed_schemes: list = None) -> bool:
    """
    Validate URL
    
    Args:
        url: URL to validate
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])
        
    Returns:
        True if valid
    """
    if not allowed_schemes:
        allowed_schemes = ['http', 'https']
    
    try:
        parsed = urlparse(url)
        return parsed.scheme in allowed_schemes and bool(parsed.netloc)
    except:
        return False