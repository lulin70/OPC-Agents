import os
import yaml
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_path: str = None):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, use default path.
        """
        self.config_path = config_path or os.environ.get('MCE_CONFIG_PATH', './config/config.yaml')
        self.config = self.load_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.
        
        Args:
            key: The configuration key, using dot notation (e.g., "storage.data_path").
            default: The default value to return if the key is not found.
            
        Returns:
            The configuration value or the default.
        """
        # Check environment variable first
        env_key = key.upper().replace('.', '_')
        if f'MCE_{env_key}' in os.environ:
            return os.environ[f'MCE_{env_key}']
        
        # Then check config file
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file.
        
        Returns:
            The loaded configuration as a dictionary.
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config or {}
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.
        
        Args:
            key: The configuration key, using dot notation (e.g., "storage.data_path").
            default: The default value to return if the key is not found.
            
        Returns:
            The configuration value or the default.
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def reload(self):
        """Reload the configuration from file."""
        self.config = self.load_config()
    
    def get_rules(self, rules_path: str = None) -> Dict[str, Any]:
        """Load rules from file.
        
        Args:
            rules_path: Path to the rules file. If None, use path from config.
            
        Returns:
            The loaded rules as a dictionary.
        """
        rules_path = rules_path or self.get('rules.config_path', './config/rules.yaml')
        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules = yaml.safe_load(f)
            return rules or {}
        except Exception as e:
            print(f"Error loading rules: {e}")
            return {}
