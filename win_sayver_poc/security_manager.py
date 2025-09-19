#!/usr/bin/env python3
"""
Security Manager Module for Win Sayver POC.

This module handles secure storage and retrieval of sensitive data like API keys
using Fernet encryption from the cryptography library.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from utils import WinSayverError


class SecurityError(WinSayverError):
    """Raised when security operations fail."""

    pass


class EncryptionError(SecurityError):
    """Raised when encryption/decryption operations fail."""

    pass


class SecurityManager:
    """
    Manages secure storage and retrieval of sensitive data using Fernet encryption.

    This class provides secure storage for API keys and other sensitive configuration
    data using industry-standard encryption practices.
    """

    def __init__(self, app_name: str = "WinSayver"):
        """
        Initialize the SecurityManager.

        Args:
            app_name: Application name for creating data directories
        """
        self.logger = logging.getLogger(__name__)
        self.app_name = app_name

        # Setup secure storage directory in user's AppData
        self.config_dir = Path.home() / "AppData" / "Local" / self.app_name
        self.key_file = self.config_dir / ".security_key"
        self.encrypted_data_file = self.config_dir / ".encrypted_config"

        # Ensure directory exists with proper permissions
        self._setup_secure_directory()

        # Initialize encryption key
        self._encryption_key = None
        self._fernet = None

        self.logger.info(f"SecurityManager initialized for {app_name}")

    def _setup_secure_directory(self) -> None:
        """
        Create secure storage directory with appropriate permissions.
        """
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # Set directory permissions to be accessible only by the current user
            if os.name == "nt":  # Windows
                # On Windows, the AppData/Local folder is already user-restricted
                pass
            else:  # Unix-like systems (for future cross-platform support)
                os.chmod(self.config_dir, 0o700)

            self.logger.debug(f"Secure directory created: {self.config_dir}")

        except Exception as e:
            self.logger.error(f"Failed to create secure directory: {e}")
            raise SecurityError(f"Cannot create secure storage directory: {e}")

    def _generate_or_load_key(self) -> bytes:
        """
        Generate a new encryption key or load existing one.

        Returns:
            Encryption key as bytes

        Raises:
            SecurityError: If key generation or loading fails
        """
        try:
            if self.key_file.exists():
                # Load existing key
                with open(self.key_file, "rb") as f:
                    key = f.read()
                self.logger.debug("Loaded existing encryption key")
                return key
            else:
                # Generate new key
                key = Fernet.generate_key()

                # Save key securely
                with open(self.key_file, "wb") as f:
                    f.write(key)

                # Set file permissions (Windows handles this automatically for AppData)
                if os.name != "nt":
                    os.chmod(self.key_file, 0o600)

                self.logger.info("Generated new encryption key")
                return key

        except Exception as e:
            self.logger.error(f"Failed to handle encryption key: {e}")
            raise SecurityError(f"Encryption key error: {e}")

    def _get_fernet(self) -> Fernet:
        """
        Get or create Fernet encryption instance.

        Returns:
            Fernet encryption instance
        """
        if self._fernet is None:
            if self._encryption_key is None:
                self._encryption_key = self._generate_or_load_key()
            self._fernet = Fernet(self._encryption_key)
        return self._fernet

    def store_api_key(self, api_key: str, validate: bool = True) -> bool:
        """
        Store API key securely using encryption.

        Args:
            api_key: The API key to store
            validate: Whether to validate the API key format

        Returns:
            True if successful, False otherwise

        Raises:
            SecurityError: If storage fails
            EncryptionError: If encryption fails
        """
        try:
            if not api_key or not isinstance(api_key, str):
                raise SecurityError("API key must be a non-empty string")

            # Basic API key format validation
            if validate:
                if not self._validate_api_key_format(api_key):
                    raise SecurityError("API key format appears invalid")

            # Load existing encrypted data or create new
            encrypted_data = self._load_encrypted_data()

            # Encrypt and store the API key
            fernet = self._get_fernet()
            encrypted_api_key = fernet.encrypt(api_key.encode("utf-8"))

            # Store in encrypted data structure
            encrypted_data["api_key"] = encrypted_api_key.decode("utf-8")
            encrypted_data["api_key_set"] = True

            # Save encrypted data
            self._save_encrypted_data(encrypted_data)

            self.logger.info("API key stored securely")
            return True

        except Exception as e:
            self.logger.error(f"Failed to store API key: {e}")
            if isinstance(e, (SecurityError, EncryptionError)):
                raise
            raise EncryptionError(f"API key storage failed: {e}")

    def retrieve_api_key(self) -> Optional[str]:
        """
        Retrieve and decrypt the stored API key.

        Returns:
            Decrypted API key or None if not found

        Raises:
            EncryptionError: If decryption fails
        """
        try:
            encrypted_data = self._load_encrypted_data()

            if not encrypted_data.get("api_key_set", False):
                self.logger.debug("No API key stored")
                return None

            encrypted_api_key = encrypted_data.get("api_key")
            if not encrypted_api_key:
                self.logger.warning("API key marked as set but not found")
                return None

            # Decrypt the API key
            fernet = self._get_fernet()
            decrypted_key = fernet.decrypt(encrypted_api_key.encode("utf-8"))

            self.logger.debug("API key retrieved successfully")
            return decrypted_key.decode("utf-8")

        except Exception as e:
            self.logger.error(f"Failed to retrieve API key: {e}")
            raise EncryptionError(f"API key retrieval failed: {e}")

    def has_api_key(self) -> bool:
        """
        Check if an API key is stored.

        Returns:
            True if API key is stored, False otherwise
        """
        try:
            encrypted_data = self._load_encrypted_data()
            return encrypted_data.get("api_key_set", False)
        except Exception as e:
            self.logger.error(f"Error checking API key status: {e}")
            return False

    def remove_api_key(self) -> bool:
        """
        Remove the stored API key.

        Returns:
            True if successful, False otherwise
        """
        try:
            encrypted_data = self._load_encrypted_data()
            encrypted_data.pop("api_key", None)
            encrypted_data["api_key_set"] = False

            self._save_encrypted_data(encrypted_data)

            self.logger.info("API key removed")
            return True

        except Exception as e:
            self.logger.error(f"Failed to remove API key: {e}")
            return False

    def store_secure_data(self, key: str, value: str) -> bool:
        """
        Store arbitrary secure data using encryption.

        Args:
            key: Data key identifier
            value: Data value to encrypt and store

        Returns:
            True if successful, False otherwise
        """
        try:
            encrypted_data = self._load_encrypted_data()

            # Encrypt the value
            fernet = self._get_fernet()
            encrypted_value = fernet.encrypt(value.encode("utf-8"))

            # Store in encrypted data structure
            encrypted_data[f"secure_{key}"] = encrypted_value.decode("utf-8")

            self._save_encrypted_data(encrypted_data)

            self.logger.debug(f"Secure data stored for key: {key}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to store secure data for {key}: {e}")
            return False

    def retrieve_secure_data(self, key: str) -> Optional[str]:
        """
        Retrieve and decrypt stored secure data.

        Args:
            key: Data key identifier

        Returns:
            Decrypted value or None if not found
        """
        try:
            encrypted_data = self._load_encrypted_data()

            encrypted_value = encrypted_data.get(f"secure_{key}")
            if not encrypted_value:
                return None

            # Decrypt the value
            fernet = self._get_fernet()
            decrypted_value = fernet.decrypt(encrypted_value.encode("utf-8"))

            return decrypted_value.decode("utf-8")

        except Exception as e:
            self.logger.error(f"Failed to retrieve secure data for {key}: {e}")
            return None

    def _load_encrypted_data(self) -> Dict[str, Any]:
        """
        Load encrypted data structure from file.

        Returns:
            Dictionary containing encrypted data
        """
        try:
            if not self.encrypted_data_file.exists():
                return {}

            with open(self.encrypted_data_file, "r") as f:
                import json

                return json.load(f)

        except Exception as e:
            self.logger.warning(f"Failed to load encrypted data, creating new: {e}")
            return {}

    def _save_encrypted_data(self, data: Dict[str, Any]) -> None:
        """
        Save encrypted data structure to file.

        Args:
            data: Dictionary containing encrypted data
        """
        try:
            with open(self.encrypted_data_file, "w") as f:
                import json

                json.dump(data, f, indent=2)

            # Set file permissions
            if os.name != "nt":
                os.chmod(self.encrypted_data_file, 0o600)

        except Exception as e:
            self.logger.error(f"Failed to save encrypted data: {e}")
            raise SecurityError(f"Cannot save encrypted data: {e}")

    def _validate_api_key_format(self, api_key: str) -> bool:
        """
        Validate API key format (basic checks).

        Args:
            api_key: API key to validate

        Returns:
            True if format appears valid
        """
        try:
            # Basic format checks for Google API keys
            if len(api_key) < 10:
                return False

            # Check for obvious test/placeholder keys
            invalid_patterns = ["test", "example", "placeholder", "demo"]
            if any(pattern in api_key.lower() for pattern in invalid_patterns):
                return False

            # Google API keys typically contain alphanumeric characters and some symbols
            import re

            if not re.match(r"^[A-Za-z0-9_\-]+$", api_key):
                return False

            return True

        except Exception as e:
            self.logger.warning(f"API key validation error: {e}")
            return True  # Default to True if validation fails

    def get_security_status(self) -> Dict[str, Any]:
        """
        Get security manager status information.

        Returns:
            Dictionary with security status
        """
        try:
            return {
                "secure_directory": str(self.config_dir),
                "directory_exists": self.config_dir.exists(),
                "key_file_exists": self.key_file.exists(),
                "config_file_exists": self.encrypted_data_file.exists(),
                "has_api_key": self.has_api_key(),
                "encryption_ready": self._fernet is not None or self.key_file.exists(),
            }
        except Exception as e:
            self.logger.error(f"Error getting security status: {e}")
            return {"error": str(e)}
