#!/usr/bin/env python3
"""
Configuration management for OPC Manager
"""

import os
import toml
from typing import Dict, Any

class ConfigManager:
    """Configuration manager for OPC-Agents system"""
    
    def __init__(self, config_path: str = "config.toml"):
        """Initialize the Config Manager"""
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from TOML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return toml.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
    
    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        """Get model configuration
        
        Args:
            model_name: Model name, default to None (use default model)
            
        Returns:
            Model configuration
        """
        if not model_name:
            model_name = self.config.get('models', {}).get('default', 'glm')
        
        return self.config.get('models', {}).get(model_name, {})
    
    def get_available_models(self) -> list:
        """Get list of available models
        
        Returns:
            List of available model names
        """
        models = self.config.get('models', {})
        return [key for key in models if key != 'default']
