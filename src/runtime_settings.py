"""
Runtime Settings Manager
Handles persistent storage of UI-modified settings that need to survive container restarts.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger()


class RuntimeSettingsManager:
    """Manages runtime settings that can be modified via UI and persist across restarts."""
    
    def __init__(self, settings_file: str = "config/runtime_settings.json"):
        self.settings_file = Path(settings_file)
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._runtime_settings: Dict[str, Any] = {}
        self._load_settings()
    
    def _load_settings(self) -> None:
        """Load runtime settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    self._runtime_settings = json.load(f)
                logger.info(f"Loaded {len(self._runtime_settings)} runtime settings from {self.settings_file}")
            else:
                logger.info("No runtime settings file found, starting with empty settings")
                self._runtime_settings = {}
        except Exception as e:
            logger.error(f"Error loading runtime settings: {e}")
            self._runtime_settings = {}
    
    def _save_settings(self) -> bool:
        """Save runtime settings to file."""
        try:
            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write settings atomically
            temp_file = self.settings_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self._runtime_settings, f, indent=2)
            
            # Move temp file to actual file (atomic operation)
            temp_file.rename(self.settings_file)
            
            logger.info(f"Saved {len(self._runtime_settings)} runtime settings to {self.settings_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving runtime settings: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a runtime setting value."""
        return self._runtime_settings.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """Set a runtime setting value and save to disk."""
        try:
            old_value = self._runtime_settings.get(key)
            self._runtime_settings[key] = value
            
            if self._save_settings():
                logger.info(f"Updated runtime setting: {key} = {value} (was: {old_value})")
                return True
            else:
                # Rollback on save failure
                if old_value is not None:
                    self._runtime_settings[key] = old_value
                else:
                    self._runtime_settings.pop(key, None)
                return False
                
        except Exception as e:
            logger.error(f"Error setting runtime setting {key}: {e}")
            return False
    
    def update(self, settings_dict: Dict[str, Any]) -> bool:
        """Update multiple runtime settings at once."""
        try:
            old_settings = self._runtime_settings.copy()
            self._runtime_settings.update(settings_dict)
            
            if self._save_settings():
                logger.info(f"Updated {len(settings_dict)} runtime settings")
                return True
            else:
                # Rollback on save failure
                self._runtime_settings = old_settings
                return False
                
        except Exception as e:
            logger.error(f"Error updating runtime settings: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a runtime setting."""
        try:
            if key in self._runtime_settings:
                old_value = self._runtime_settings.pop(key)
                
                if self._save_settings():
                    logger.info(f"Deleted runtime setting: {key} (was: {old_value})")
                    return True
                else:
                    # Rollback on save failure
                    self._runtime_settings[key] = old_value
                    return False
            
            return True  # Key didn't exist, consider it successful
            
        except Exception as e:
            logger.error(f"Error deleting runtime setting {key}: {e}")
            return False
    
    def reset(self) -> bool:
        """Reset all runtime settings (clear the file)."""
        try:
            old_settings = self._runtime_settings.copy()
            self._runtime_settings = {}
            
            if self._save_settings():
                logger.info("Reset all runtime settings")
                return True
            else:
                # Rollback on save failure
                self._runtime_settings = old_settings
                return False
                
        except Exception as e:
            logger.error(f"Error resetting runtime settings: {e}")
            return False
    
    def get_all(self) -> Dict[str, Any]:
        """Get all runtime settings as a dictionary."""
        return self._runtime_settings.copy()
    
    def has_setting(self, key: str) -> bool:
        """Check if a runtime setting exists."""
        return key in self._runtime_settings
    
    def get_file_path(self) -> str:
        """Get the path to the runtime settings file."""
        return str(self.settings_file)


# Singleton instance
runtime_settings = RuntimeSettingsManager()