"""
Error handling and logging system for Binance Portfolio Logger.

This module provides comprehensive error handling, structured logging,
execution tracking, and performance metrics collection.
"""

import logging
import logging.handlers
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class ErrorCategory(Enum):
    """Categories of errors for structured handling."""
    CONFIGURATION = "configuration"
    API_ERROR = "api_error"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    DATA_PROCESSING = "data_processing"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class LogLevel(Enum):
    """Log levels for structured logging."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class ExecutionMetrics:
    """Tracks performance metrics during execution."""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    api_calls: Dict[str, int] = field(default_factory=dict)
    errors_encountered: List[str] = field(default_factory=list)
    portfolio_value: Optional[float] = None
    assets_processed: int = 0
    conversion_failures: int = 0
    
    @property
    def execution_duration(self) -> float:
        """Calculate execution duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def total_api_calls(self) -> int:
        """Get total number of API calls made."""
        return sum(self.api_calls.values())
    
    def add_api_call(self, service: str) -> None:
        """Record an API call for the specified service."""
        self.api_calls[service] = self.api_calls.get(service, 0) + 1
    
    def add_error(self, error_message: str) -> None:
        """Record an error encountered during execution."""
        self.errors_encountered.append(error_message)
    
    def finalize(self, portfolio_value: Optional[float] = None) -> None:
        """Finalize metrics collection."""
        self.end_time = time.time()
        if portfolio_value is not None:
            self.portfolio_value = portfolio_value


class ErrorHandler:
    """
    Comprehensive error handling and logging system.
    
    Provides structured logging, execution tracking, log sanitization,
    and performance metrics collection for the portfolio logger.
    """
    
    # Sensitive patterns to sanitize from logs
    SENSITIVE_PATTERNS = [
        (re.compile(r'api[_-]?key["\s]*[:=]["\s]*"?([a-zA-Z0-9_-]{20,})"?', re.IGNORECASE), 'api_key="[REDACTED]"'),
        (re.compile(r'api[_-]?secret["\s]*[:=]["\s]*"?([a-zA-Z0-9_-]{20,})"?', re.IGNORECASE), 'api_secret="[REDACTED]"'),
        (re.compile(r'secret["\s]*[:=]["\s]*"?([a-zA-Z0-9_-]{20,})"?', re.IGNORECASE), 'secret="[REDACTED]"'),
        (re.compile(r'password["\s]*[:=]["\s]*"?([^\s"\']+)"?', re.IGNORECASE), 'password="[REDACTED]"'),
        (re.compile(r'token["\s]*[:=]["\s]*"?([a-zA-Z0-9._-]{20,})"?', re.IGNORECASE), 'token="[REDACTED]"'),
        (re.compile(r'"private_key":\s*"[^"]*"', re.IGNORECASE), '"private_key": "[REDACTED]"'),
        (re.compile(r'"client_secret":\s*"[^"]*"', re.IGNORECASE), '"client_secret": "[REDACTED]"'),
    ]
    
    def __init__(self, log_file_path: str = "/var/log/binance-portfolio/portfolio.log"):
        """
        Initialize the error handler with logging configuration.
        
        Args:
            log_file_path: Path to the main log file
        """
        self.log_file_path = log_file_path
        self.error_log_path = log_file_path.replace('.log', '_errors.log')
        self.metrics_log_path = log_file_path.replace('.log', '_metrics.log')
        
        self.logger = None
        self.error_logger = None
        self.metrics_logger = None
        self.execution_metrics = ExecutionMetrics()
        
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Set up structured logging with rotation and formatting."""
        # Ensure log directory exists
        log_dir = Path(self.log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Main application logger
        self.logger = logging.getLogger('binance_portfolio')
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        # Error logger
        self.error_logger = logging.getLogger('binance_portfolio_errors')
        self.error_logger.setLevel(logging.WARNING)
        self.error_logger.handlers.clear()
        
        # Metrics logger
        self.metrics_logger = logging.getLogger('binance_portfolio_metrics')
        self.metrics_logger.setLevel(logging.INFO)
        self.metrics_logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Main log handler with rotation
        main_handler = logging.handlers.RotatingFileHandler(
            self.log_file_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        main_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(main_handler)
        
        # Error log handler
        error_handler = logging.handlers.RotatingFileHandler(
            self.error_log_path,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setFormatter(detailed_formatter)
        self.error_logger.addHandler(error_handler)
        
        # Metrics log handler
        metrics_handler = logging.handlers.RotatingFileHandler(
            self.metrics_log_path,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        metrics_handler.setFormatter(simple_formatter)
        self.metrics_logger.addHandler(metrics_handler)
        
        # Console handler for development
        if os.getenv('BINANCE_LOGGER_DEBUG', '').lower() == 'true':
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(simple_formatter)
            console_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(console_handler)
    
    def _sanitize_message(self, message: str) -> str:
        """
        Sanitize log messages to remove sensitive information.
        
        Args:
            message: Original log message
            
        Returns:
            Sanitized log message with sensitive data redacted
        """
        sanitized = message
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized
    
    def _log_with_sanitization(self, logger: logging.Logger, level: LogLevel, 
                              message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a message with sanitization applied.
        
        Args:
            logger: Logger instance to use
            level: Log level
            message: Message to log
            extra: Additional context data
        """
        sanitized_message = self._sanitize_message(message)
        
        if extra:
            # Sanitize extra data as well
            sanitized_extra = {}
            for key, value in extra.items():
                if isinstance(value, str):
                    sanitized_extra[key] = self._sanitize_message(value)
                else:
                    sanitized_extra[key] = value
            extra = sanitized_extra
        
        logger.log(level.value, sanitized_message, extra=extra)
    
    def log_execution_start(self) -> None:
        """Log the start of a portfolio logging execution."""
        self.execution_metrics = ExecutionMetrics()
        
        start_message = f"Portfolio logging execution started at {datetime.now().isoformat()}"
        self._log_with_sanitization(self.logger, LogLevel.INFO, start_message)
        
        # Log system information
        system_info = {
            'python_version': os.sys.version.split()[0],
            'working_directory': os.getcwd(),
            'process_id': os.getpid()
        }
        
        self._log_with_sanitization(
            self.logger, 
            LogLevel.INFO, 
            f"System info: {system_info}"
        )
    
    def log_execution_success(self, portfolio_value: float, assets_processed: int = 0, 
                            conversion_failures: int = 0) -> None:
        """
        Log successful completion of portfolio logging execution.
        
        Args:
            portfolio_value: Total portfolio value in USDT
            assets_processed: Number of assets processed
            conversion_failures: Number of assets that failed conversion
        """
        self.execution_metrics.finalize(portfolio_value)
        self.execution_metrics.assets_processed = assets_processed
        self.execution_metrics.conversion_failures = conversion_failures
        
        success_message = (
            f"Portfolio logging completed successfully. "
            f"Portfolio value: ${portfolio_value:.2f} USDT, "
            f"Assets processed: {assets_processed}, "
            f"Conversion failures: {conversion_failures}, "
            f"Execution time: {self.execution_metrics.execution_duration:.2f}s"
        )
        
        self._log_with_sanitization(self.logger, LogLevel.INFO, success_message)
        self._log_performance_metrics()
    
    def log_execution_failure(self, error: Exception, error_category: ErrorCategory = ErrorCategory.UNKNOWN) -> None:
        """
        Log failed portfolio logging execution.
        
        Args:
            error: Exception that caused the failure
            error_category: Category of the error for structured handling
        """
        self.execution_metrics.finalize()
        self.execution_metrics.add_error(str(error))
        
        failure_message = (
            f"Portfolio logging execution failed after {self.execution_metrics.execution_duration:.2f}s. "
            f"Error category: {error_category.value}, "
            f"Error: {str(error)}"
        )
        
        self._log_with_sanitization(self.logger, LogLevel.ERROR, failure_message)
        self._log_with_sanitization(self.error_logger, LogLevel.ERROR, failure_message)
        
        # Log detailed error information
        import traceback
        error_details = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'error_category': error_category.value,
            'traceback': traceback.format_exc()
        }
        
        self._log_with_sanitization(
            self.error_logger, 
            LogLevel.ERROR, 
            f"Detailed error information: {error_details}"
        )
        
        self._log_performance_metrics()
    
    def handle_api_error(self, error: Exception, service: str, operation: str) -> bool:
        """
        Handle API-specific errors and determine if retry should occur.
        
        Args:
            error: API error that occurred
            service: Service name (e.g., 'binance', 'google_sheets')
            operation: Operation being performed
            
        Returns:
            True if operation should be retried, False otherwise
        """
        error_message = str(error).lower()
        
        # Categorize the error
        if any(keyword in error_message for keyword in ['rate limit', 'too many requests', '429']):
            category = ErrorCategory.API_ERROR
            should_retry = True
            log_level = LogLevel.WARNING
        elif any(keyword in error_message for keyword in ['unauthorized', 'forbidden', '401', '403']):
            category = ErrorCategory.AUTHENTICATION
            should_retry = False
            log_level = LogLevel.ERROR
        elif any(keyword in error_message for keyword in ['timeout', 'connection', 'network']):
            category = ErrorCategory.NETWORK
            should_retry = True
            log_level = LogLevel.WARNING
        else:
            category = ErrorCategory.API_ERROR
            should_retry = True
            log_level = LogLevel.WARNING
        
        # Log the error
        api_error_message = (
            f"API error in {service} during {operation}: {str(error)}. "
            f"Category: {category.value}, Retry recommended: {should_retry}"
        )
        
        self._log_with_sanitization(self.logger, log_level, api_error_message)
        self._log_with_sanitization(self.error_logger, log_level, api_error_message)
        
        # Record the error in metrics
        self.execution_metrics.add_error(f"{service}:{operation} - {str(error)}")
        
        return should_retry
    
    def log_api_call(self, service: str, operation: str, success: bool = True, 
                    response_time: Optional[float] = None) -> None:
        """
        Log API call for performance tracking.
        
        Args:
            service: Service name (e.g., 'binance', 'google_sheets')
            operation: Operation performed
            success: Whether the call was successful
            response_time: Response time in seconds
        """
        self.execution_metrics.add_api_call(service)
        
        status = "SUCCESS" if success else "FAILED"
        time_info = f" ({response_time:.3f}s)" if response_time else ""
        
        api_message = f"API call: {service}.{operation} - {status}{time_info}"
        self._log_with_sanitization(self.logger, LogLevel.DEBUG, api_message)
    
    def log_warning(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN) -> None:
        """
        Log a warning message with categorization.
        
        Args:
            message: Warning message
            category: Category of the warning
        """
        warning_message = f"[{category.value.upper()}] {message}"
        self._log_with_sanitization(self.logger, LogLevel.WARNING, warning_message)
    
    def log_info(self, message: str) -> None:
        """
        Log an informational message.
        
        Args:
            message: Information message
        """
        self._log_with_sanitization(self.logger, LogLevel.INFO, message)
    
    def log_debug(self, message: str) -> None:
        """
        Log a debug message.
        
        Args:
            message: Debug message
        """
        self._log_with_sanitization(self.logger, LogLevel.DEBUG, message)
    
    def _log_performance_metrics(self) -> None:
        """Log detailed performance metrics."""
        metrics_data = {
            'timestamp': datetime.now().isoformat(),
            'execution_duration_seconds': round(self.execution_metrics.execution_duration, 3),
            'total_api_calls': self.execution_metrics.total_api_calls,
            'api_calls_by_service': dict(self.execution_metrics.api_calls),
            'assets_processed': self.execution_metrics.assets_processed,
            'conversion_failures': self.execution_metrics.conversion_failures,
            'portfolio_value_usdt': self.execution_metrics.portfolio_value,
            'errors_count': len(self.execution_metrics.errors_encountered),
            'success': len(self.execution_metrics.errors_encountered) == 0
        }
        
        metrics_message = f"Performance metrics: {metrics_data}"
        self._log_with_sanitization(self.metrics_logger, LogLevel.INFO, metrics_message)
    
    def get_execution_metrics(self) -> ExecutionMetrics:
        """
        Get current execution metrics.
        
        Returns:
            Current execution metrics
        """
        return self.execution_metrics
    
    def create_log_rotation_config(self, config_path: str = "/etc/logrotate.d/binance-portfolio") -> str:
        """
        Create logrotate configuration for log rotation.
        
        Args:
            config_path: Path where to create the logrotate config
            
        Returns:
            Content of the logrotate configuration
        """
        log_dir = Path(self.log_file_path).parent
        
        config_content = f"""# Logrotate configuration for Binance Portfolio Logger
{log_dir}/*.log {{
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 binance-logger binance-logger
    postrotate
        # Send HUP signal to any running processes if needed
        /bin/kill -HUP `cat /var/run/binance-portfolio.pid 2> /dev/null` 2> /dev/null || true
    endscript
}}
"""
        
        try:
            with open(config_path, 'w') as f:
                f.write(config_content)
            self.log_info(f"Created logrotate configuration at {config_path}")
        except PermissionError:
            self.log_warning(
                f"Could not create logrotate config at {config_path}. "
                f"Manual creation required with sudo privileges.",
                ErrorCategory.SYSTEM
            )
        except Exception as e:
            self.log_warning(
                f"Failed to create logrotate config: {str(e)}",
                ErrorCategory.SYSTEM
            )
        
        return config_content