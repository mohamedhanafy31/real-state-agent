"""
Utility Functions
Shared functions for configuration, logging, etc.
"""

import os
import logging
import yaml
import re
from pathlib import Path
from typing import Dict, Any, Optional

# Import the new logging system
try:
    from .logger import setup_run_logging, get_logger
    _NEW_LOGGING_AVAILABLE = True
except ImportError:
    _NEW_LOGGING_AVAILABLE = False


def setup_logging(level: str = "INFO", log_file: Optional[str] = None, use_run_logging: bool = True):
    """
    Setup logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file (deprecated, use run logging instead)
        use_run_logging: Whether to use the new run-based logging system
    """
    # Use new run-based logging if available and requested
    if _NEW_LOGGING_AVAILABLE and use_run_logging:
        # Get settings from environment or use defaults
        log_dir = os.getenv('LOG_DIR', 'logs')
        console_level = os.getenv('LOG_CONSOLE_LEVEL', level)
        file_level = os.getenv('LOG_FILE_LEVEL', 'DEBUG')
        use_json = os.getenv('LOG_JSON', 'false').lower() == 'true'
        
        setup_run_logging(
            log_dir=log_dir,
            level=level,
            console_level=console_level,
            file_level=file_level,
            use_json=use_json
        )
        return
    
    # Fallback to old simple logging
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def load_config(config_path: str = "config/settings.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        logging.warning(f"Config file not found: {config_path}. Using defaults.")
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config or {}
    except Exception as e:
        logging.error(f"Error loading config: {str(e)}")
        return {}


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Get a configuration value with nested key support.
    
    Args:
        config: Configuration dictionary
        key: Configuration key (supports nested keys with dots, e.g., "model.name")
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    keys = key.split('.')
    value = config
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    
    return value

