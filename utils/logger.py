#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logger - Logging utilities
Lines: ~200
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import traceback
import json

# Logger instances cache
_loggers: Dict[str, logging.Logger] = {}

def setup_logger(
    name: str = "bot",
    log_level: str = "INFO",
    log_file: str = "bot.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    json_format: bool = False
) -> logging.Logger:
    """
    Setup logger with file and console handlers
    
    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file path
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        json_format: Use JSON format for logs
        
    Returns:
        Configured logger instance
    """
    
    # Check if logger already exists
    if name in _loggers:
        return _loggers[name]
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create formatters
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (with rotation)
    log_path = Path(log_file)
    log_path.parent.mkdir(exist_ok=True)
    
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Cache logger
    _loggers[name] = logger
    
    logger.info(f"Logger '{name}' initialized with level {log_level}")
    
    return logger

def get_logger(name: str = "bot") -> logging.Logger:
    """Get existing logger or create new one"""
    if name in _loggers:
        return _loggers[name]
    
    return setup_logger(name)

def log_error(logger: logging.Logger, error: Exception, context: Dict = None):
    """Log error with context"""
    error_details = {
        'type': type(error).__name__,
        'message': str(error),
        'traceback': traceback.format_exc()
    }
    
    if context:
        error_details['context'] = context
    
    logger.error(f"Error occurred: {json.dumps(error_details, ensure_ascii=False)}")

class JsonFormatter(logging.Formatter):
    """JSON log formatter"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'name': record.name,
            'level': record.levelname,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage()
        }
        
        if hasattr(record, 'exc_info') and record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
        
        if hasattr(record, 'extra'):
            log_data['extra'] = record.extra
        
        return json.dumps(log_data, ensure_ascii=False)

class AsyncLogger:
    """Async logger for coroutines"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    async def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)
    
    async def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
    
    async def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
    
    async def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)
    
    async def critical(self, msg: str, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)

def setup_termux_logger():
    """Setup logger optimized for Termux"""
    return setup_logger(
        name="termux_bot",
        log_file="logs/termux_bot.log",
        max_bytes=5 * 1024 * 1024,  # 5 MB
        backup_count=3
    )