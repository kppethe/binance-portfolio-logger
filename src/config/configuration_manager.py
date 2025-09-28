"""
Configuration manager for handling environment variables and credential loading.
"""
import os
import stat
import logging
from pathlib import Path
from typing import Optional

from ..models.data_models import BinanceCredentials, GoogleCredentials, ExecutionConfig
from ..utils.security_validator import SecurityValidator, SecurityValidationError


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigurationManager:
    """Manages secure loading and validation of application configuration."""
    
    def __init__(self, enable_security_validation: bool = True):
        """
        Initialize the configuration manager.
        
        Args:
            enable_security_validation: Whether to enable comprehensive security validation
        """
        self._binance_credentials: Optional[BinanceCredentials] = None
        self._google_credentials: Optional[GoogleCredentials] = None
        self._execution_config: Optional[ExecutionConfig] = None
        self._security_validator = SecurityValidator() if enable_security_validation else None
        self.logger = logging.getLogger(__name__)
    
    def load_binance_credentials(self) -> BinanceCredentials:
        """
        Load Binance API credentials from environment variables.
        
        Returns:
            BinanceCredentials: The loaded credentials
            
        Raises:
            ConfigurationError: If credentials are missing or invalid
        """
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key:
            raise ConfigurationError("BINANCE_API_KEY environment variable is required")
        
        if not api_secret:
            raise ConfigurationError("BINANCE_API_SECRET environment variable is required")
        
        if len(api_key.strip()) == 0:
            raise ConfigurationError("BINANCE_API_KEY cannot be empty")
        
        if len(api_secret.strip()) == 0:
            raise ConfigurationError("BINANCE_API_SECRET cannot be empty")
        
        self._binance_credentials = BinanceCredentials(
            api_key=api_key.strip(),
            api_secret=api_secret.strip()
        )
        
        return self._binance_credentials
    
    def load_google_credentials(self) -> GoogleCredentials:
        """
        Load Google Sheets API credentials from environment variables.
        
        Returns:
            GoogleCredentials: The loaded credentials configuration
            
        Raises:
            ConfigurationError: If credentials are missing or invalid
        """
        service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH')
        spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
        sheet_name = os.getenv('GOOGLE_SHEET_NAME', 'Binance Portfolio')
        
        if not service_account_path:
            raise ConfigurationError("GOOGLE_SERVICE_ACCOUNT_PATH environment variable is required")
        
        if not spreadsheet_id:
            raise ConfigurationError("GOOGLE_SPREADSHEET_ID environment variable is required")
        
        # Validate service account file exists and has proper permissions
        service_account_file = Path(service_account_path)
        if not service_account_file.exists():
            raise ConfigurationError(f"Google service account file not found: {service_account_path}")
        
        if not service_account_file.is_file():
            raise ConfigurationError(f"Google service account path is not a file: {service_account_path}")
        
        # Check file permissions (should be 600 or more restrictive)
        # Note: On Windows, file permission checks work differently
        import platform
        if platform.system() != 'Windows':
            file_stat = service_account_file.stat()
            file_mode = stat.filemode(file_stat.st_mode)
            
            # Check if file is readable by others or group (security risk)
            if file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
                raise ConfigurationError(
                    f"Google service account file has insecure permissions: {file_mode}. "
                    "File should have 600 permissions (readable only by owner)."
                )
        
        self._google_credentials = GoogleCredentials(
            service_account_path=service_account_path,
            spreadsheet_id=spreadsheet_id.strip(),
            sheet_name=sheet_name.strip()
        )
        
        return self._google_credentials
    
    def get_execution_config(self) -> ExecutionConfig:
        """
        Get execution configuration with defaults and environment overrides.
        
        Returns:
            ExecutionConfig: The execution configuration
        """
        timeout_seconds = int(os.getenv('EXECUTION_TIMEOUT_SECONDS', '60'))
        max_retries = int(os.getenv('MAX_RETRIES', '3'))
        log_file_path = os.getenv('LOG_FILE_PATH', '/var/log/binance-portfolio.log')
        
        # Validate timeout is reasonable (allow smaller values for testing)
        if timeout_seconds < 1:
            raise ConfigurationError("EXECUTION_TIMEOUT_SECONDS must be at least 1 second")
        
        if timeout_seconds > 300:
            raise ConfigurationError("EXECUTION_TIMEOUT_SECONDS must be less than 300 seconds")
        
        # Validate max retries is reasonable
        if max_retries < 0:
            raise ConfigurationError("MAX_RETRIES must be non-negative")
        
        if max_retries > 10:
            raise ConfigurationError("MAX_RETRIES must be 10 or less")
        
        self._execution_config = ExecutionConfig(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            log_file_path=log_file_path
        )
        
        return self._execution_config
    
    def validate_configuration(self) -> bool:
        """
        Validate all configuration components with comprehensive security checks.
        
        Returns:
            bool: True if all configuration is valid
            
        Raises:
            ConfigurationError: If any configuration is invalid
        """
        try:
            # Load and validate all configuration components
            binance_creds = self.load_binance_credentials()
            google_creds = self.load_google_credentials()
            self.get_execution_config()
            
            # Run comprehensive security validation if enabled
            if self._security_validator:
                self.logger.info("Running comprehensive security validation...")
                
                # Validate environment variables
                try:
                    self._security_validator.validate_environment_variables()
                    self.logger.info("Environment variables validation passed")
                except SecurityValidationError as e:
                    raise ConfigurationError(f"Environment validation failed: {e}")
                
                # Validate credential formats
                try:
                    self._security_validator.validate_binance_credentials(binance_creds)
                    self._security_validator.validate_google_credentials(google_creds)
                    self.logger.info("Credential format validation passed")
                except SecurityValidationError as e:
                    raise ConfigurationError(f"Credential validation failed: {e}")
                
                # Validate API access (optional - can be disabled for faster startup)
                validate_api = os.getenv('VALIDATE_API_ON_STARTUP', 'true').lower() == 'true'
                if validate_api:
                    try:
                        self._security_validator.validate_binance_api_access(binance_creds)
                        self.logger.info("API access validation passed")
                    except SecurityValidationError as e:
                        raise ConfigurationError(f"API access validation failed: {e}")
                else:
                    self.logger.info("API access validation skipped (VALIDATE_API_ON_STARTUP=false)")
            
            self.logger.info("Configuration validation completed successfully")
            return True
            
        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ConfigurationError(f"Unexpected error during configuration validation: {str(e)}")
    
    def validate_startup_security(self) -> bool:
        """
        Run startup security validation with clear error messages.
        
        Returns:
            bool: True if startup security validation passes
            
        Raises:
            ConfigurationError: If security validation fails with detailed error message
        """
        if not self._security_validator:
            self.logger.warning("Security validation is disabled")
            return True
        
        try:
            self.logger.info("Running startup security validation...")
            
            # Run comprehensive security audit
            audit_results = self._security_validator.run_security_audit()
            
            if audit_results['overall_status'] == 'PASS':
                self.logger.info("Startup security validation passed")
                
                # Log any warnings
                for warning in audit_results['warnings']:
                    self.logger.warning(f"Security warning: {warning}")
                
                return True
            else:
                # Compile detailed error message
                error_messages = []
                error_messages.append("Startup security validation failed:")
                
                for check in audit_results['checks']:
                    if check['status'] == 'FAIL':
                        error_messages.append(f"  - {check['name']}: {check['message']}")
                
                if audit_results['errors']:
                    error_messages.append("Detailed errors:")
                    for error in audit_results['errors']:
                        error_messages.append(f"  - {error}")
                
                error_messages.append("\nTo fix these issues:")
                error_messages.append("  1. Check your environment variables (.env file)")
                error_messages.append("  2. Verify file permissions: chmod 600 <credential_files>")
                error_messages.append("  3. Validate your API credentials")
                error_messages.append("  4. Run 'python security_audit.py' for detailed analysis")
                
                raise ConfigurationError("\n".join(error_messages))
                
        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except Exception as e:
            raise ConfigurationError(f"Unexpected error during startup security validation: {e}")
    
    @property
    def binance_credentials(self) -> Optional[BinanceCredentials]:
        """Get cached Binance credentials."""
        return self._binance_credentials
    
    @property
    def google_credentials(self) -> Optional[GoogleCredentials]:
        """Get cached Google credentials."""
        return self._google_credentials
    
    @property
    def execution_config(self) -> Optional[ExecutionConfig]:
        """Get cached execution configuration."""
        return self._execution_config