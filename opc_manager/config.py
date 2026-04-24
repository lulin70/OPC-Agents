#!/usr/bin/env python3
"""
Configuration management for OPC Manager
"""

import os
import toml
import threading
import time
from typing import Dict, Any, Callable


class ConfigManager:
    """Configuration manager for OPC-Agents system"""

    def __init__(self, config_path: str = "config.toml"):
        """Initialize the Config Manager"""
        self.config_path = config_path
        self.config = self._load_config()
        self.last_modified_time = (
            os.path.getmtime(self.config_path)
            if os.path.exists(self.config_path)
            else 0
        )
        self._watch_thread = None
        self._stop_watching = False
        self._callbacks = []
        self._lock = threading.RLock()

        # 启动配置文件监控
        self.start_watching()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from TOML file"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return toml.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}

    def reload_config(self) -> bool:
        """Reload configuration from file

        Returns:
            Whether the config was successfully reloaded
        """
        try:
            with self._lock:
                new_config = self._load_config()
                if new_config:
                    self.config = new_config
                    self.last_modified_time = (
                        os.path.getmtime(self.config_path)
                        if os.path.exists(self.config_path)
                        else 0
                    )
                    print(
                        f"[ConfigManager] Configuration reloaded from {self.config_path}"
                    )
                    # 触发回调
                    for callback in self._callbacks:
                        try:
                            callback()
                        except Exception as e:
                            print(f"[ConfigManager] Error in callback: {e}")
                    return True
        except Exception as e:
            print(f"[ConfigManager] Error reloading config: {e}")
        return False

    def start_watching(self) -> None:
        """Start watching the config file for changes"""
        if self._watch_thread is None or not self._watch_thread.is_alive():
            self._stop_watching = False
            self._watch_thread = threading.Thread(
                target=self._watch_config_file, daemon=True
            )
            self._watch_thread.start()
            print(f"[ConfigManager] Started watching config file: {self.config_path}")

    def stop_watching(self) -> None:
        """Stop watching the config file"""
        self._stop_watching = True
        if self._watch_thread:
            self._watch_thread.join(timeout=2)
            print(f"[ConfigManager] Stopped watching config file: {self.config_path}")

    def _watch_config_file(self) -> None:
        """Watch the config file for changes"""
        while not self._stop_watching:
            try:
                if os.path.exists(self.config_path):
                    current_modified_time = os.path.getmtime(self.config_path)
                    if current_modified_time > self.last_modified_time:
                        self.reload_config()
            except Exception as e:
                print(f"[ConfigManager] Error watching config file: {e}")
            time.sleep(5)  # 每5秒检查一次

    def register_callback(self, callback: Callable) -> None:
        """Register a callback to be called when config changes

        Args:
            callback: Callback function to call when config changes
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable) -> None:
        """Unregister a callback

        Args:
            callback: Callback function to unregister
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        """Get model configuration

        Args:
            model_name: Model name, default to None (use default model)

        Returns:
            Model configuration
        """
        with self._lock:
            if not model_name:
                model_name = self.config.get("models", {}).get("default", "glm")

            return self.config.get("models", {}).get(model_name, {})

    def get_available_models(self) -> list:
        """Get list of available models

        Returns:
            List of available model names
        """
        with self._lock:
            models = self.config.get("models", {})
            return [key for key in models if key != "default"]

    def get(self, section: str, key: str = None, default: Any = None) -> Any:
        """Get a configuration value

        Args:
            section: Configuration section
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        with self._lock:
            if section in self.config:
                if key:
                    return self.config[section].get(key, default)
                return self.config[section]
            return default

    def set(self, section: str, key: str, value: Any) -> bool:
        """Set a configuration value

        Args:
            section: Configuration section
            key: Configuration key
            value: Configuration value

        Returns:
            Whether the value was set successfully
        """
        try:
            with self._lock:
                if section not in self.config:
                    self.config[section] = {}
                self.config[section][key] = value
                # 保存到文件
                with open(self.config_path, "w", encoding="utf-8") as f:
                    toml.dump(self.config, f)
                self.last_modified_time = os.path.getmtime(self.config_path)
                # 触发回调
                for callback in self._callbacks:
                    try:
                        callback()
                    except Exception as e:
                        print(f"[ConfigManager] Error in callback: {e}")
                return True
        except Exception as e:
            print(f"[ConfigManager] Error setting config: {e}")
            return False
