"""
Settings Service — runtime configuration management.

Reads and writes settings to config/settings.json.
Validates settings before applying changes.
"""

import os
import json
from typing import Dict, Any

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


# Default settings
DEFAULT_SETTINGS = {
    "simulation_speed": 1.0,
    "pso_iterations": 50,
    "pso_particles": 30,
    "model_selection": "rf_model.pkl",
    "logging_level": "INFO",
    "enable_notifications": True,
    "enable_animations": True,
}

# Validation rules: {key: (min, max)} for numeric settings
VALIDATION_RULES = {
    "simulation_speed": (0.1, 10.0),
    "pso_iterations": (10, 500),
    "pso_particles": (5, 200),
}


class SettingsManager:
    """
    Manages runtime application settings.

    Usage:
        manager = SettingsManager()
        settings = manager.get_all_settings()
        manager.update_settings({"pso_iterations": 100})
    """

    def __init__(self):
        """Initialize settings manager."""
        try:
            from config.config import config
            self.settings_file = config.SETTINGS_FILE
        except (ImportError, AttributeError):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.settings_file = os.path.join(base_dir, "config", "settings.json")

        self._settings = self._load_settings()
        logger.info("SettingsManager initialized")

    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all current settings.

        Returns
        -------
        dict
            All settings as key-value pairs.
        """
        return dict(self._settings)

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update multiple settings.

        Parameters
        ----------
        updates : dict
            Key-value pairs to update.

        Returns
        -------
        dict
            Updated settings.

        Raises
        ------
        ValueError
            If any setting value is invalid.
        """
        for key, value in updates.items():
            if not self.validate_setting(key, value):
                raise ValueError(f"Invalid value for setting '{key}': {value}")

        self._settings.update(updates)
        self._save_settings()

        logger.info(f"Settings updated: {list(updates.keys())}")
        return dict(self._settings)

    def validate_setting(self, key: str, value: Any) -> bool:
        """
        Validate a single setting value.

        Parameters
        ----------
        key : str
            Setting name.
        value : Any
            Setting value.

        Returns
        -------
        bool
            True if valid, False otherwise.
        """
        if key not in DEFAULT_SETTINGS:
            return False

        # Type check
        expected_type = type(DEFAULT_SETTINGS[key])
        if not isinstance(value, expected_type):
            # Allow int where float is expected
            if expected_type == float and isinstance(value, int):
                value = float(value)
            else:
                return False

        # Range check for numeric settings
        if key in VALIDATION_RULES:
            min_val, max_val = VALIDATION_RULES[key]
            if not (min_val <= value <= max_val):
                return False

        return True

    def reset_to_defaults(self) -> Dict[str, Any]:
        """
        Reset all settings to defaults.

        Returns
        -------
        dict
            Default settings.
        """
        self._settings = dict(DEFAULT_SETTINGS)
        self._save_settings()
        logger.info("Settings reset to defaults")
        return dict(self._settings)

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file, falling back to defaults."""
        settings = dict(DEFAULT_SETTINGS)

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    saved = json.load(f)
                # Merge saved settings with defaults (in case new settings were added)
                settings.update(saved)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load settings file: {e}")

        return settings

    def _save_settings(self):
        """Save current settings to file."""
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, "w") as f:
                json.dump(self._settings, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save settings: {e}")
