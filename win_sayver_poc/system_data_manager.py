#!/usr/bin/env python3
"""
System Data Manager Module for Win Sayver POC.

This module handles persistent storage and retrieval of system specifications
using SQLite database for structured data storage with historical tracking.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils import WinSayverError


class SystemDataError(WinSayverError):
    """Raised when system data operations fail."""

    pass


class DatabaseError(SystemDataError):
    """Raised when database operations fail."""

    pass


class SystemDataManager:
    """
    Manages persistent storage and retrieval of system specifications.

    This class provides structured storage for system specifications with
    historical tracking, update detection, and efficient querying capabilities.
    """

    def __init__(self, app_name: str = "WinSayver"):
        """
        Initialize the SystemDataManager.

        Args:
            app_name: Application name for creating data directories
        """
        self.logger = logging.getLogger(__name__)
        self.app_name = app_name

        # Setup database path in user's AppData
        self.data_dir = Path.home() / "AppData" / "Local" / self.app_name
        self.db_path = self.data_dir / "system_specs.db"

        # Ensure directory exists
        self._setup_data_directory()

        # Initialize database
        self._init_database()

        self.logger.info(f"SystemDataManager initialized for {app_name}")

    def _setup_data_directory(self) -> None:
        """
        Create data storage directory.
        """
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Data directory ready: {self.data_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create data directory: {e}")
            raise SystemDataError(f"Cannot create data directory: {e}")

    def _init_database(self) -> None:
        """
        Initialize SQLite database with required tables.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                # Create system_specs table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS system_specs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        specs_version TEXT NOT NULL DEFAULT '1.0',
                        specs_data TEXT NOT NULL,
                        specs_hash TEXT NOT NULL,
                        collection_duration REAL,
                        collection_method TEXT DEFAULT 'auto',
                        is_current BOOLEAN DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Create system_components table for detailed component tracking
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS system_components (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        system_specs_id INTEGER NOT NULL,
                        component_type TEXT NOT NULL,
                        component_name TEXT NOT NULL,
                        component_data TEXT NOT NULL,
                        FOREIGN KEY (system_specs_id) REFERENCES system_specs (id)
                    )
                """
                )

                # Create indexes for better performance
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_system_specs_timestamp 
                    ON system_specs (timestamp DESC)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_system_specs_current 
                    ON system_specs (is_current, timestamp DESC)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_components_type 
                    ON system_components (component_type, system_specs_id)
                """
                )

                conn.commit()

            self.logger.debug("Database initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")

    def save_system_specs(
        self, specs_data: Dict[str, Any], collection_duration: Optional[float] = None, collection_method: str = "auto"
    ) -> bool:
        """
        Save system specifications to database.

        Args:
            specs_data: Complete system specification dictionary
            collection_duration: Time taken to collect specs (seconds)
            collection_method: Method used for collection ('auto', 'manual', 'forced')

        Returns:
            True if successful, False otherwise

        Raises:
            SystemDataError: If saving fails
        """
        try:
            if not specs_data or not isinstance(specs_data, dict):
                raise SystemDataError("System specs data must be a non-empty dictionary")

            # Generate specs hash for change detection
            specs_hash = self._generate_specs_hash(specs_data)

            # Check if specs have changed
            if not self._specs_have_changed(specs_hash):
                self.logger.debug("System specs unchanged, skipping save")
                return True

            # Prepare data for storage
            timestamp = datetime.now().isoformat()
            specs_json = json.dumps(specs_data, indent=2)

            # Start transaction
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Mark previous entries as not current
                cursor.execute("UPDATE system_specs SET is_current = 0")

                # Insert new specs record
                cursor.execute(
                    """
                    INSERT INTO system_specs 
                    (timestamp, specs_data, specs_hash, collection_duration, 
                     collection_method, is_current)
                    VALUES (?, ?, ?, ?, ?, 1)
                """,
                    (timestamp, specs_json, specs_hash, collection_duration, collection_method),
                )

                system_specs_id = cursor.lastrowid

                # Insert component details for better querying
                if system_specs_id is not None:
                    self._save_component_details(cursor, system_specs_id, specs_data)

                conn.commit()

            self.logger.info(f"System specs saved successfully (ID: {system_specs_id})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save system specs: {e}")
            if isinstance(e, SystemDataError):
                raise
            raise SystemDataError(f"System specs save failed: {e}")

    def load_latest_system_specs(self) -> Optional[Dict[str, Any]]:
        """
        Load the most recent system specifications.

        Returns:
            Dictionary containing system specs or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT specs_data, timestamp, collection_duration, collection_method
                    FROM system_specs 
                    WHERE is_current = 1 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """
                )

                row = cursor.fetchone()
                if not row:
                    self.logger.debug("No system specs found")
                    return None

                specs_json, timestamp, duration, method = row
                specs_data = json.loads(specs_json)

                # Add metadata
                specs_data["_metadata"] = {
                    "last_updated": timestamp,
                    "collection_duration": duration,
                    "collection_method": method,
                }

                self.logger.debug(f"Loaded system specs from {timestamp}")
                return specs_data

        except Exception as e:
            self.logger.error(f"Failed to load system specs: {e}")
            return None

    def get_specs_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get historical system specifications.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of dictionaries containing historical specs metadata
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT timestamp, specs_hash, collection_duration, 
                           collection_method, is_current
                    FROM system_specs 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """,
                    (limit,),
                )

                history = []
                for row in cursor.fetchall():
                    timestamp, specs_hash, duration, method, is_current = row
                    history.append(
                        {
                            "timestamp": timestamp,
                            "specs_hash": specs_hash,
                            "collection_duration": duration,
                            "collection_method": method,
                            "is_current": bool(is_current),
                        }
                    )

                self.logger.debug(f"Retrieved {len(history)} historical records")
                return history

        except Exception as e:
            self.logger.error(f"Failed to get specs history: {e}")
            return []

    def needs_update(self, threshold_days: int = 7) -> bool:
        """
        Check if system specs need updating based on age threshold.

        Args:
            threshold_days: Number of days after which specs should be updated

        Returns:
            True if update is needed, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT timestamp FROM system_specs 
                    WHERE is_current = 1 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """
                )

                row = cursor.fetchone()
                if not row:
                    self.logger.debug("No system specs found, update needed")
                    return True

                last_update = datetime.fromisoformat(row[0])
                age_days = (datetime.now() - last_update).days

                needs_update = age_days >= threshold_days
                self.logger.debug(f"System specs age: {age_days} days, needs update: {needs_update}")

                return needs_update

        except Exception as e:
            self.logger.error(f"Error checking update status: {e}")
            return True  # Default to needing update on error

    def get_component_history(self, component_type: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get history for a specific component type.

        Args:
            component_type: Type of component (e.g., 'cpu', 'memory', 'disk')
            limit: Maximum number of records to return

        Returns:
            List of component history records
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT ss.timestamp, sc.component_name, sc.component_data
                    FROM system_components sc
                    JOIN system_specs ss ON sc.system_specs_id = ss.id
                    WHERE sc.component_type = ?
                    ORDER BY ss.timestamp DESC
                    LIMIT ?
                """,
                    (component_type, limit),
                )

                history = []
                for row in cursor.fetchall():
                    timestamp, name, data = row
                    history.append({"timestamp": timestamp, "component_name": name, "component_data": json.loads(data)})

                return history

        except Exception as e:
            self.logger.error(f"Failed to get component history for {component_type}: {e}")
            return []

    def delete_old_specs(self, keep_days: int = 30) -> int:
        """
        Delete old system specifications to save space.

        Args:
            keep_days: Number of days of history to keep

        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            cutoff_iso = cutoff_date.isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get IDs to delete (preserve current specs)
                cursor.execute(
                    """
                    SELECT id FROM system_specs 
                    WHERE timestamp < ? AND is_current = 0
                """,
                    (cutoff_iso,),
                )

                ids_to_delete = [row[0] for row in cursor.fetchall()]

                if not ids_to_delete:
                    return 0

                # Delete component records first (foreign key constraint)
                placeholders = ",".join("?" * len(ids_to_delete))
                cursor.execute(
                    f"""
                    DELETE FROM system_components 
                    WHERE system_specs_id IN ({placeholders})
                """,
                    ids_to_delete,
                )

                # Delete specs records
                cursor.execute(
                    f"""
                    DELETE FROM system_specs 
                    WHERE id IN ({placeholders})
                """,
                    ids_to_delete,
                )

                deleted_count = len(ids_to_delete)
                conn.commit()

                self.logger.info(f"Deleted {deleted_count} old system specs records")
                return deleted_count

        except Exception as e:
            self.logger.error(f"Failed to delete old specs: {e}")
            return 0

    def _generate_specs_hash(self, specs_data: Dict[str, Any]) -> str:
        """
        Generate hash for specs data to detect changes.

        Args:
            specs_data: System specifications dictionary

        Returns:
            Hash string for the specs data
        """
        try:
            import hashlib

            # Remove metadata and timestamps for consistent hashing
            clean_data = {
                k: v
                for k, v in specs_data.items()
                if not k.startswith("_") and k not in ["timestamp", "collection_time"]
            }

            # Create stable JSON representation
            stable_json = json.dumps(clean_data, sort_keys=True, separators=(",", ":"))

            # Generate SHA-256 hash
            return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()[:16]

        except Exception as e:
            self.logger.warning(f"Failed to generate specs hash: {e}")
            return datetime.now().isoformat()  # Fallback to timestamp

    def _specs_have_changed(self, current_hash: str) -> bool:
        """
        Check if specs have changed since last save.

        Args:
            current_hash: Hash of current specs data

        Returns:
            True if specs have changed, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT specs_hash FROM system_specs 
                    WHERE is_current = 1 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """
                )

                row = cursor.fetchone()
                if not row:
                    return True  # No previous specs, so changed

                last_hash = row[0]
                return current_hash != last_hash

        except Exception as e:
            self.logger.error(f"Error checking specs changes: {e}")
            return True  # Default to changed on error

    def _save_component_details(self, cursor: sqlite3.Cursor, system_specs_id: int, specs_data: Dict[str, Any]) -> None:
        """
        Save individual component details for better querying.

        Args:
            cursor: Database cursor
            system_specs_id: ID of the system specs record
            specs_data: Complete system specification dictionary
        """
        try:
            # Map of component types to data paths
            component_mappings = {
                "cpu": ["hardware_specs", "processor"],
                "memory": ["hardware_specs", "memory"],
                "disk": ["hardware_specs", "storage"],
                "gpu": ["hardware_specs", "graphics"],
                "os": ["os_information"],
                "network": ["network_configuration"],
                "installed_software": ["installed_software"],
            }

            for component_type, data_path in component_mappings.items():
                component_data = specs_data

                # Navigate to the component data
                for key in data_path:
                    if isinstance(component_data, dict) and key in component_data:
                        component_data = component_data[key]
                    else:
                        component_data = None
                        break

                if component_data is not None:
                    # Extract component name
                    component_name = self._extract_component_name(component_type, component_data)

                    # Save component record
                    cursor.execute(
                        """
                        INSERT INTO system_components 
                        (system_specs_id, component_type, component_name, component_data)
                        VALUES (?, ?, ?, ?)
                    """,
                        (system_specs_id, component_type, component_name, json.dumps(component_data)),
                    )

        except Exception as e:
            self.logger.warning(f"Failed to save component details: {e}")
            # Don't raise exception as this is not critical

    def _extract_component_name(self, component_type: str, component_data: Any) -> str:
        """
        Extract a meaningful name for a component.

        Args:
            component_type: Type of component
            component_data: Component data

        Returns:
            Component name string
        """
        try:
            if isinstance(component_data, dict):
                # Try common name fields
                name_fields = ["name", "model", "description", "product_name", "caption"]
                for field in name_fields:
                    if field in component_data and component_data[field]:
                        return str(component_data[field])[:100]  # Limit length

                # For OS information
                if component_type == "os" and "os_name" in component_data:
                    version = component_data.get("os_version", "")
                    return f"{component_data['os_name']} {version}".strip()[:100]

            # Fallback to component type
            return component_type.capitalize()

        except Exception:
            return component_type.capitalize()

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics and information.

        Returns:
            Dictionary with database statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get total records
                cursor.execute("SELECT COUNT(*) FROM system_specs")
                total_specs = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM system_components")
                total_components = cursor.fetchone()[0]

                # Get current specs info
                cursor.execute(
                    """
                    SELECT timestamp, collection_method FROM system_specs 
                    WHERE is_current = 1 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """
                )
                current_info = cursor.fetchone()

                # Get database file size
                db_size_mb = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0

                return {
                    "database_path": str(self.db_path),
                    "database_size_mb": round(db_size_mb, 2),
                    "total_specs_records": total_specs,
                    "total_component_records": total_components,
                    "current_specs_timestamp": current_info[0] if current_info else None,
                    "current_specs_method": current_info[1] if current_info else None,
                    "last_updated": datetime.now().isoformat(),
                }

        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
            return {"error": str(e)}
