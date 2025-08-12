"""
Configuration management for the SEC downloader.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """Configuration manager for the SEC downloader application."""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = "config/settings.yaml"
        
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_sec_config(self) -> Dict[str, Any]:
        return self._config.get('sec', {})
    
    def get_download_config(self) -> Dict[str, Any]:
        return self._config.get('download', {})
    
    def get_paths_config(self) -> Dict[str, Any]:
        return self._config.get('paths', {})
    
    def get_company_mappings(self) -> Dict[str, str]:
        companies = self._config.get('companies', {})
        return companies.get('mappings', {})
    
    def ensure_directories(self):
        paths = self.get_paths_config()
        for path_key, path_value in paths.items():
            if path_key in ['downloads', 'logs', 'temp']:
                Path(path_value).mkdir(parents=True, exist_ok=True)
