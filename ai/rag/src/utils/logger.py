"""
Advanced Logging System
Provides detailed logging with separate log files for each run.
"""

import os
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json

# Suppress watchfiles logging globally
logging.getLogger('watchfiles').setLevel(logging.WARNING)
logging.getLogger('watchfiles.main').setLevel(logging.WARNING)
logging.getLogger('watchdog').setLevel(logging.WARNING)


class DetailedFormatter(logging.Formatter):
    """Custom formatter with detailed information."""
    
    # Detailed format with more information
    DETAILED_FORMAT = (
        '%(asctime)s | '
        '%(levelname)-8s | '
        '%(name)-30s | '
        '%(funcName)-20s | '
        '%(lineno)-4d | '
        '%(message)s'
    )
    
    # Simple format for console
    SIMPLE_FORMAT = '%(asctime)s - %(levelname)-8s - %(name)s - %(message)s'
    
    # JSON format for structured logging
    JSON_FORMAT = {
        'timestamp': '%(asctime)s',
        'level': '%(levelname)s',
        'logger': '%(name)s',
        'function': '%(funcName)s',
        'line': '%(lineno)d',
        'message': '%(message)s',
        'module': '%(module)s',
        'pathname': '%(pathname)s'
    }
    
    def __init__(self, format_type: str = "detailed", use_json: bool = False):
        """
        Initialize formatter.
        
        Args:
            format_type: "detailed" or "simple"
            use_json: Whether to use JSON format
        """
        if use_json:
            super().__init__(fmt=self._json_format)
        elif format_type == "detailed":
            super().__init__(fmt=self.DETAILED_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')
        else:
            super().__init__(fmt=self.SIMPLE_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')
        
        self.use_json = use_json
    
    def _json_format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'module': record.module,
            'pathname': record.pathname
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class RunLogger:
    """Manages logging for a single run with separate log files."""
    
    def __init__(
        self,
        run_name: Optional[str] = None,
        log_dir: str = "logs",
        level: str = "INFO",
        console_level: str = "INFO",
        file_level: str = "DEBUG",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        use_json: bool = False
    ):
        """
        Initialize run logger.
        
        Args:
            run_name: Name for this run (default: timestamp-based)
            log_dir: Directory to store log files
            level: Overall logging level
            console_level: Console logging level
            file_level: File logging level
            max_bytes: Maximum log file size before rotation
            backup_count: Number of backup files to keep
            use_json: Whether to use JSON format for logs
        """
        self.run_name = run_name or self._generate_run_name()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.use_json = use_json
        
        # Create separate log files for different components
        self.log_files = {
            'main': self.log_dir / f"{self.run_name}_main.log",
            'ingestion': self.log_dir / f"{self.run_name}_ingestion.log",
            'query': self.log_dir / f"{self.run_name}_query.log",
            'api': self.log_dir / f"{self.run_name}_api.log",
            'errors': self.log_dir / f"{self.run_name}_errors.log",
            'all': self.log_dir / f"{self.run_name}_all.log"
        }
        
        # Setup root logger
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        # Clear existing handlers
        self.root_logger.handlers.clear()
        
        # Setup console handler
        self._setup_console_handler(console_level)
        
        # Setup file handlers
        self._setup_file_handlers(file_level, max_bytes, backup_count)
        
        # Log initialization
        logger = logging.getLogger(__name__)
        logger.info(f"Logging system initialized for run: {self.run_name}")
        logger.info(f"Log directory: {self.log_dir.absolute()}")
        logger.info(f"Log files: {list(self.log_files.keys())}")
    
    def _generate_run_name(self) -> str:
        """Generate a unique run name based on timestamp."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _setup_console_handler(self, level: str):
        """Setup console handler with simple format."""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        console_formatter = DetailedFormatter(format_type="simple", use_json=False)
        console_handler.setFormatter(console_formatter)
        
        # Filter out watchfiles messages and WebSocket collaboration attempts
        def filter_watchfiles(record):
            msg = record.getMessage().lower()
            # Filter watchfiles/watchdog
            if (record.name.startswith('watchfiles') or 
                record.name.startswith('watchdog') or
                'watchfiles' in record.name.lower() or
                'changes detected' in msg):
                return False
            # Filter WebSocket collaboration attempts (from IDE extensions like VS Code/Cursor)
            if 'websocket' in msg and 'collaboration' in msg:
                return False
            if 'connection rejected' in msg and '403' in msg:
                return False
            if 'connection closed' in msg and 'collaboration' in msg:
                return False
            return True
        
        console_handler.addFilter(filter_watchfiles)
        self.root_logger.addHandler(console_handler)
    
    def _setup_file_handlers(self, level: str, max_bytes: int, backup_count: int):
        """Setup file handlers with rotation."""
        file_level = getattr(logging, level.upper(), logging.DEBUG)
        formatter = DetailedFormatter(format_type="detailed", use_json=self.use_json)
        
        # Filter to exclude watchfiles messages
        def filter_watchfiles(record):
            return not (record.name.startswith('watchfiles') or 
                       record.name.startswith('watchdog') or
                       'watchfiles' in record.name.lower() or
                       'changes detected' in record.getMessage().lower())
        
        # Main log file (all logs)
        all_handler = logging.handlers.RotatingFileHandler(
            self.log_files['all'],
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        all_handler.setLevel(file_level)
        all_handler.setFormatter(formatter)
        all_handler.addFilter(lambda record: record.levelno >= file_level and filter_watchfiles(record))
        self.root_logger.addHandler(all_handler)
        
        # Error log file (errors and critical only)
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_files['errors'],
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        error_handler.addFilter(lambda record: record.levelno >= logging.ERROR and filter_watchfiles(record))
        self.root_logger.addHandler(error_handler)
        
        # Component-specific handlers
        for component in ['main', 'ingestion', 'query', 'api']:
            handler = logging.handlers.RotatingFileHandler(
                self.log_files[component],
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            handler.setLevel(file_level)
            handler.setFormatter(formatter)
            # Filter by logger name and exclude watchfiles
            component_filter = self._create_component_filter(component)
            handler.addFilter(lambda record: component_filter(record) and filter_watchfiles(record))
            self.root_logger.addHandler(handler)
        
        # Suppress watchfiles logger at root level
        logging.getLogger('watchfiles').setLevel(logging.WARNING)
        logging.getLogger('watchfiles.main').setLevel(logging.WARNING)
        logging.getLogger('watchdog').setLevel(logging.WARNING)
    
    def _create_component_filter(self, component: str):
        """Create a filter for component-specific logging."""
        def component_filter(record: logging.LogRecord) -> bool:
            logger_name = record.name.lower()
            
            if component == 'main':
                return any(x in logger_name for x in ['__main__', 'main', 'rag_graph.main'])
            elif component == 'ingestion':
                return any(x in logger_name for x in ['ingestion', 'loader', 'cleaner', 'chunker', 'embed'])
            elif component == 'query':
                return any(x in logger_name for x in ['query', 'retrieval', 'retriever', 'generator', 'llm'])
            elif component == 'api':
                return any(x in logger_name for x in ['api', 'fastapi', 'uvicorn'])
            
            return False
        
        return component_filter
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance for a specific component."""
        return logging.getLogger(name)
    
    def log_run_info(self, info: Dict[str, Any]):
        """Log run information as a structured entry."""
        logger = logging.getLogger(__name__)
        logger.info("=" * 80)
        logger.info("RUN INFORMATION")
        logger.info("=" * 80)
        for key, value in info.items():
            logger.info(f"{key}: {value}")
        logger.info("=" * 80)
    
    def get_log_paths(self) -> Dict[str, Path]:
        """Get paths to all log files."""
        return self.log_files.copy()


# Global run logger instance
_run_logger: Optional[RunLogger] = None


def setup_run_logging(
    run_name: Optional[str] = None,
    log_dir: Optional[str] = None,
    level: Optional[str] = None,
    console_level: Optional[str] = None,
    file_level: Optional[str] = None,
    use_json: bool = False
) -> RunLogger:
    """
    Setup logging for a new run.
    
    Args:
        run_name: Name for this run (default: timestamp-based)
        log_dir: Directory to store log files (default: from env or "logs")
        level: Overall logging level (default: from env or "INFO")
        console_level: Console logging level (default: from env or "INFO")
        file_level: File logging level (default: from env or "DEBUG")
        use_json: Whether to use JSON format for logs
        
    Returns:
        RunLogger instance
    """
    global _run_logger
    
    # Get defaults from environment variables
    log_dir = log_dir or os.getenv('LOG_DIR', 'logs')
    level = level or os.getenv('LOG_LEVEL', 'INFO')
    console_level = console_level or os.getenv('LOG_CONSOLE_LEVEL', 'INFO')
    file_level = file_level or os.getenv('LOG_FILE_LEVEL', 'DEBUG')
    use_json = use_json or os.getenv('LOG_JSON', 'false').lower() == 'true'
    
    # Create new run logger
    _run_logger = RunLogger(
        run_name=run_name,
        log_dir=log_dir,
        level=level,
        console_level=console_level,
        file_level=file_level,
        use_json=use_json
    )
    
    return _run_logger


def get_run_logger() -> Optional[RunLogger]:
    """Get the current run logger instance."""
    return _run_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance, creating run logger if needed."""
    global _run_logger
    
    if _run_logger is None:
        # Auto-setup if not already done
        setup_run_logging()
    
    return logging.getLogger(name)

