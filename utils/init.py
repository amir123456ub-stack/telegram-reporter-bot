#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilities Package - Common utility functions
"""

from .validators import validate_telegram_link, validate_phone_number, validate_username
from .helpers import (
    format_number, format_duration, format_datetime,
    extract_username, extract_message_id, generate_id,
    chunk_list, safe_get
)
from .logger import setup_logger, get_logger, log_error
from .security import encrypt_data, decrypt_data, hash_password, generate_key

__all__ = [
    # Validators
    'validate_telegram_link',
    'validate_phone_number',
    'validate_username',
    
    # Helpers
    'format_number',
    'format_duration',
    'format_datetime',
    'extract_username',
    'extract_message_id',
    'generate_id',
    'chunk_list',
    'safe_get',
    
    # Logger
    'setup_logger',
    'get_logger',
    'log_error',
    
    # Security
    'encrypt_data',
    'decrypt_data',
    'hash_password',
    'generate_key'
]

__version__ = '1.0.0'