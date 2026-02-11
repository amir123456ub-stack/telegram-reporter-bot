#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scripts Package - Maintenance and utility scripts
"""

from .init_db import initialize_database, create_tables, create_indexes
from .backup import backup_database, backup_sessions, cleanup_old_backups
from .monitor import SystemMonitor, check_system_health, send_alert

__all__ = [
    # Init DB
    'initialize_database',
    'create_tables',
    'create_indexes',
    
    # Backup
    'backup_database',
    'backup_sessions',
    'cleanup_old_backups',
    
    # Monitor
    'SystemMonitor',
    'check_system_health',
    'send_alert'
]

__version__ = '1.0.0'