#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Security - Security utilities
Lines: ~200
"""

import os
import base64
import hashlib
import secrets
from typing import Optional, Tuple, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class SecurityManager:
    """Security utilities for encryption and hashing"""
    
    @staticmethod
    def generate_key(password: str = None, salt: bytes = None) -> Union[bytes, Tuple[bytes, bytes]]:
        """
        Generate encryption key
        
        Args:
            password: Password for key derivation
            salt: Salt for key derivation
            
        Returns:
            Encryption key or (key, salt) tuple
        """
        if password:
            if not salt:
                salt = os.urandom(16)
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            
            return key, salt
        else:
            # Generate random key
            return Fernet.generate_key()
    
    @staticmethod
    def encrypt_data(data: Union[str, bytes], key: bytes) -> bytes:
        """
        Encrypt data using Fernet
        
        Args:
            data: Data to encrypt
            key: Encryption key
            
        Returns:
            Encrypted data
        """
        if isinstance(data, str):
            data = data.encode()
        
        fernet = Fernet(key)
        return fernet.encrypt(data)
    
    @staticmethod
    def decrypt_data(encrypted_data: bytes, key: bytes) -> bytes:
        """
        Decrypt data using Fernet
        
        Args:
            encrypted_data: Data to decrypt
            key: Encryption key
            
        Returns:
            Decrypted data
        """
        fernet = Fernet(key)
        return fernet.decrypt(encrypted_data)
    
    @staticmethod
    def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
        """
        Hash password with salt
        
        Args:
            password: Password to hash
            salt: Salt for hashing
            
        Returns:
            Tuple of (password_hash, salt)
        """
        if not salt:
            salt = os.urandom(32)
        
        # Use PBKDF2 with SHA256
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000,
            dklen=64
        )
        
        return base64.b64encode(key).decode(), base64.b64encode(salt).decode()
    
    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Password to verify
            password_hash: Stored password hash
            salt: Stored salt
            
        Returns:
            True if password matches
        """
        hash_bytes = base64.b64decode(password_hash)
        salt_bytes = base64.b64decode(salt)
        
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt_bytes,
            100000,
            dklen=64
        )
        
        return secrets.compare_digest(base64.b64encode(key).decode(), password_hash)
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """
        Generate secure random token
        
        Args:
            length: Token length
            
        Returns:
            Random token
        """
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def encrypt_file(file_path: str, key: bytes, output_path: str = None) -> Optional[str]:
        """
        Encrypt file
        
        Args:
            file_path: Path to file
            key: Encryption key
            output_path: Output file path
            
        Returns:
            Output file path if successful
        """
        try:
            from pathlib import Path
            
            if not output_path:
                output_path = str(file_path) + '.encrypted'
            
            fernet = Fernet(key)
            
            with open(file_path, 'rb') as f:
                data = f.read()
            
            encrypted = fernet.encrypt(data)
            
            with open(output_path, 'wb') as f:
                f.write(encrypted)
            
            return output_path
            
        except Exception as e:
            return None
    
    @staticmethod
    def decrypt_file(file_path: str, key: bytes, output_path: str = None) -> Optional[str]:
        """
        Decrypt file
        
        Args:
            file_path: Path to encrypted file
            key: Decryption key
            output_path: Output file path
            
        Returns:
            Output file path if successful
        """
        try:
            if not output_path:
                output_path = file_path.replace('.encrypted', '.decrypted')
            
            fernet = Fernet(key)
            
            with open(file_path, 'rb') as f:
                encrypted = f.read()
            
            decrypted = fernet.decrypt(encrypted)
            
            with open(output_path, 'wb') as f:
                f.write(decrypted)
            
            return output_path
            
        except Exception as e:
            return None

# Global instance
_security_manager = None

def get_security_manager() -> SecurityManager:
    """Get singleton security manager"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager

# Convenience functions
def encrypt_data(data: Union[str, bytes], key: bytes) -> bytes:
    """Convenience function for data encryption"""
    return SecurityManager.encrypt_data(data, key)

def decrypt_data(encrypted_data: bytes, key: bytes) -> bytes:
    """Convenience function for data decryption"""
    return SecurityManager.decrypt_data(encrypted_data, key)

def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
    """Convenience function for password hashing"""
    return SecurityManager.hash_password(password, salt)

def generate_key(password: str = None, salt: bytes = None) -> Union[bytes, Tuple[bytes, bytes]]:
    """Convenience function for key generation"""
    return SecurityManager.generate_key(password, salt)

def generate_token(length: int = 32) -> str:
    """Convenience function for token generation"""
    return SecurityManager.generate_token(length)