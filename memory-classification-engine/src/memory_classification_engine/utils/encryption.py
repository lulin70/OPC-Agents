import os
import base64
from cryptography.fernet import Fernet
from typing import Optional, Any

class EncryptionManager:
    """Encryption manager for memory classification engine."""
    
    def __init__(self, key_path: str = None):
        """Initialize the encryption manager.
        
        Args:
            key_path: Path to store the encryption key.
        """
        self.key_path = key_path or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "encryption.key")
        self.key = self._load_or_generate_key()
        self.fernet = Fernet(self.key)
    
    def _load_or_generate_key(self) -> bytes:
        """Load or generate encryption key.
        
        Returns:
            Encryption key.
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
        
        # Load existing key if it exists
        if os.path.exists(self.key_path):
            with open(self.key_path, 'rb') as f:
                return f.read()
        
        # Generate new key if it doesn't exist
        key = Fernet.generate_key()
        with open(self.key_path, 'wb') as f:
            f.write(key)
        return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt data.
        
        Args:
            data: Data to encrypt.
            
        Returns:
            Encrypted data.
        """
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data.
        
        Args:
            encrypted_data: Encrypted data.
            
        Returns:
            Decrypted data.
        """
        return self.fernet.decrypt(encrypted_data.encode()).decode()
    
    def encrypt_dict(self, data: dict) -> dict:
        """Encrypt dictionary values.
        
        Args:
            data: Dictionary to encrypt.
            
        Returns:
            Encrypted dictionary.
        """
        encrypted_data = {}
        for key, value in data.items():
            if isinstance(value, str):
                encrypted_data[key] = self.encrypt(value)
            else:
                encrypted_data[key] = value
        return encrypted_data
    
    def decrypt_dict(self, encrypted_data: dict) -> dict:
        """Decrypt dictionary values.
        
        Args:
            encrypted_data: Encrypted dictionary.
            
        Returns:
            Decrypted dictionary.
        """
        decrypted_data = {}
        for key, value in encrypted_data.items():
            if isinstance(value, str) and value.startswith('gAAAAA'):  # Fernet ciphertext prefix
                decrypted_data[key] = self.decrypt(value)
            else:
                decrypted_data[key] = value
        return decrypted_data

# Create global encryption manager instance
encryption_manager = EncryptionManager()
