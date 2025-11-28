"""
Utils Module
Shared utility functions.
"""

from .helpers import setup_logging, load_config, get_config_value

# Import new logging system
try:
    from .logger import setup_run_logging, get_run_logger, get_logger, RunLogger
    __all__ = [
        'setup_logging', 
        'load_config', 
        'get_config_value',
        'setup_run_logging',
        'get_run_logger',
        'get_logger',
        'RunLogger'
    ]
except ImportError:
    __all__ = ['setup_logging', 'load_config', 'get_config_value']

