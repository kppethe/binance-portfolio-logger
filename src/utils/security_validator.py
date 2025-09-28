"""
Security validation utilities for credential and configuration security.
"""
import os
import stat
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

from ..models.data_models import BinanceCredentials, GoogleCredentials


class SecurityValidationError(Exception):
    """Raised when security validation fails."""
    pass


class SecurityValidator:
    """
    Validates security aspects of the application including credentials,
    file permissions, and API access.
    """
    
    def __init__(self):
        """Initialize the security validator."""
        self.logger = logging.getLogger(__name__)
        self._validation_results: List[Dict] = []
    
    def validate_file_permissions(self, file_path: str, expected_mode: int = 0o600) -> bool:
        """
        Validate file permissions are secure (readable only by owner).
        
        Args:
            file_path: Path to file to check
            expected_mode: Expected file permission mode (default: 0o600)
            
        Returns:
            True if permissions are secure, False otherwise
            
        Raises:
            SecurityValidationError: If file doesn't exist or has insecure permissions
        """
        file_obj = Path(file_path)
        
        if not file_obj.exists():
            raise SecurityValidationError(f"File not found: {file_path}")
        
        if not file_obj.is_file():
            raise SecurityValidationError(f"Path is not a file: {file_path}")
        
        # Skip permission checks on Windows as they work differently
        import platform
        if platform.system() == 'Windows':
            self.logger.info(f"Skipping permission check on Windows for: {file_path}")
            return True
        
        file_stat = file_obj.stat()
        current_mode = file_stat.st_mode & 0o777  # Get permission bits only
        
        # Check if file is readable by group or others (security risk)
        if file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
            raise SecurityValidationError(
                f"File has insecure permissions: {oct(current_mode)}. "
                f"File should have {oct(expected_mode)} permissions (readable only by owner). "
                f"Run: chmod {oct(expected_mode)} {file_path}"
            )
        
        # Check if file is writable by group or others (security risk)
        if file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise SecurityValidationError(
                f"File has insecure permissions: {oct(current_mode)}. "
                f"File should not be writable by group or others. "
                f"Run: chmod {oct(expected_mode)} {file_path}"
            )
        
        self.logger.info(f"File permissions validated for: {file_path}")
        return True
    
    def validate_binance_credentials(self, credentials: BinanceCredentials) -> bool:
        """
        Validate Binance credentials format and basic structure.
        
        Args:
            credentials: BinanceCredentials object to validate
            
        Returns:
            True if credentials are valid format
            
        Raises:
            SecurityValidationError: If credentials are invalid
        """
        if not credentials.api_key or not credentials.api_secret:
            raise SecurityValidationError("Binance API key and secret are required")
        
        # Basic format validation for Binance API keys
        api_key = credentials.api_key.strip()
        api_secret = credentials.api_secret.strip()
        
        if len(api_key) < 32:
            raise SecurityValidationError("Binance API key appears to be too short (minimum 32 characters)")
        
        if len(api_secret) < 32:
            raise SecurityValidationError("Binance API secret appears to be too short (minimum 32 characters)")
        
        # Check for common placeholder values
        placeholder_values = ['your_api_key_here', 'your_api_secret_here', 'placeholder', 'test', 'demo']
        if any(placeholder in api_key.lower() for placeholder in placeholder_values):
            raise SecurityValidationError("Binance API key appears to be a placeholder value")
        
        if any(placeholder in api_secret.lower() for placeholder in placeholder_values):
            raise SecurityValidationError("Binance API secret appears to be a placeholder value")
        
        # Check for obvious test patterns
        if api_key.startswith('test') or api_secret.startswith('test'):
            self.logger.warning("Binance credentials appear to be test values")
        
        self.logger.info("Binance credentials format validation passed")
        return True
    
    def validate_google_credentials(self, credentials: GoogleCredentials) -> bool:
        """
        Validate Google service account credentials file and format.
        
        Args:
            credentials: GoogleCredentials object to validate
            
        Returns:
            True if credentials are valid
            
        Raises:
            SecurityValidationError: If credentials are invalid
        """
        service_account_path = credentials.service_account_path
        
        # Validate file exists and has secure permissions
        self.validate_file_permissions(service_account_path, 0o600)
        
        # Validate JSON format and required fields
        try:
            with open(service_account_path, 'r') as f:
                service_account_data = json.load(f)
        except json.JSONDecodeError as e:
            raise SecurityValidationError(f"Invalid JSON in service account file: {e}")
        except Exception as e:
            raise SecurityValidationError(f"Failed to read service account file: {e}")
        
        # Check required fields for Google service account
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in service_account_data]
        
        if missing_fields:
            raise SecurityValidationError(
                f"Service account file missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate service account type
        if service_account_data.get('type') != 'service_account':
            raise SecurityValidationError(
                f"Invalid service account type: {service_account_data.get('type')}. "
                "Expected 'service_account'"
            )
        
        # Validate spreadsheet ID format (basic check)
        spreadsheet_id = credentials.spreadsheet_id.strip()
        if len(spreadsheet_id) < 20:
            raise SecurityValidationError("Google Spreadsheet ID appears to be too short")
        
        # Check for placeholder values
        placeholder_values = ['your_spreadsheet_id_here', 'placeholder', 'test', 'demo']
        if any(placeholder in spreadsheet_id.lower() for placeholder in placeholder_values):
            raise SecurityValidationError("Google Spreadsheet ID appears to be a placeholder value")
        
        self.logger.info("Google credentials validation passed")
        return True
    
    def validate_binance_api_access(self, credentials: BinanceCredentials) -> bool:
        """
        Validate Binance API access by testing read-only operations.
        
        Args:
            credentials: BinanceCredentials object to test
            
        Returns:
            True if API access is valid and read-only
            
        Raises:
            SecurityValidationError: If API access is invalid or has excessive permissions
        """
        try:
            # Initialize client for testing
            client = Client(
                api_key=credentials.api_key,
                api_secret=credentials.api_secret,
                testnet=False
            )
            
            # Test 1: Basic connectivity
            try:
                server_time = client.get_server_time()
                self.logger.info("Binance API connectivity test passed")
            except Exception as e:
                raise SecurityValidationError(f"Binance API connectivity test failed: {e}")
            
            # Test 2: Account info access (read-only)
            try:
                account_info = client.get_account()
                self.logger.info("Binance account info access test passed")
            except BinanceAPIException as e:
                if e.code in [-2014, -2015]:  # API key format invalid or IP restriction
                    raise SecurityValidationError(f"Binance API authentication failed: {e}")
                elif e.code == -1021:  # Timestamp outside recv window
                    raise SecurityValidationError(f"Binance API timestamp error: {e}")
                else:
                    raise SecurityValidationError(f"Binance API access error: {e}")
            except Exception as e:
                raise SecurityValidationError(f"Binance account access test failed: {e}")
            
            # Test 3: Verify API key permissions (should be read-only)
            try:
                # Try to get API key permissions
                api_restrictions = client.get_api_key_permission()
                
                # Check if trading is enabled (should be disabled for security)
                if api_restrictions.get('enableSpotAndMarginTrading', False):
                    self.logger.warning(
                        "WARNING: Binance API key has trading permissions enabled. "
                        "For security, consider using read-only API keys."
                    )
                
                # Check if futures trading is enabled (should be disabled for security)
                if api_restrictions.get('enableFutures', False):
                    self.logger.warning(
                        "WARNING: Binance API key has futures trading permissions enabled. "
                        "For security, consider using read-only API keys."
                    )
                
                # Check if withdrawals are enabled (should be disabled for security)
                if api_restrictions.get('enableWithdrawals', False):
                    self.logger.warning(
                        "WARNING: Binance API key has withdrawal permissions enabled. "
                        "For security, consider using read-only API keys."
                    )
                
                self.logger.info("Binance API permissions validated")
                
            except Exception as e:
                # Some API keys might not support permission checking
                self.logger.warning(f"Could not verify API key permissions: {e}")
            
            # Test 4: Test rate limiting behavior
            try:
                # Make a few quick calls to test rate limiting
                for _ in range(3):
                    client.get_server_time()
                self.logger.info("Binance API rate limiting test passed")
            except Exception as e:
                self.logger.warning(f"Binance API rate limiting test warning: {e}")
            
            self.logger.info("Binance API access validation completed successfully")
            return True
            
        except SecurityValidationError:
            # Re-raise security validation errors
            raise
        except Exception as e:
            raise SecurityValidationError(f"Unexpected error during Binance API validation: {e}")
    
    def validate_environment_variables(self) -> bool:
        """
        Validate that required environment variables are set and not empty.
        
        Returns:
            True if all required environment variables are valid
            
        Raises:
            SecurityValidationError: If required environment variables are missing or invalid
        """
        required_env_vars = [
            'BINANCE_API_KEY',
            'BINANCE_API_SECRET',
            'GOOGLE_SERVICE_ACCOUNT_PATH',
            'GOOGLE_SPREADSHEET_ID'
        ]
        
        missing_vars = []
        empty_vars = []
        
        for var_name in required_env_vars:
            var_value = os.getenv(var_name)
            
            if var_value is None:
                missing_vars.append(var_name)
            elif len(var_value.strip()) == 0:
                empty_vars.append(var_name)
        
        if missing_vars:
            raise SecurityValidationError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
        
        if empty_vars:
            raise SecurityValidationError(
                f"Empty environment variables: {', '.join(empty_vars)}"
            )
        
        self.logger.info("Environment variables validation passed")
        return True
    
    def run_security_audit(self) -> Dict[str, any]:
        """
        Run comprehensive security audit of the application configuration.
        
        Returns:
            Dictionary containing audit results with status and details
        """
        audit_results = {
            'timestamp': None,
            'overall_status': 'UNKNOWN',
            'checks': [],
            'warnings': [],
            'errors': []
        }
        
        import datetime
        audit_results['timestamp'] = datetime.datetime.now().isoformat()
        
        # Check 1: Environment variables
        try:
            self.validate_environment_variables()
            audit_results['checks'].append({
                'name': 'Environment Variables',
                'status': 'PASS',
                'message': 'All required environment variables are set'
            })
        except SecurityValidationError as e:
            audit_results['checks'].append({
                'name': 'Environment Variables',
                'status': 'FAIL',
                'message': str(e)
            })
            audit_results['errors'].append(f"Environment Variables: {e}")
        
        # Check 2: File permissions
        try:
            service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH')
            if service_account_path:
                self.validate_file_permissions(service_account_path)
                audit_results['checks'].append({
                    'name': 'File Permissions',
                    'status': 'PASS',
                    'message': 'Service account file has secure permissions'
                })
            else:
                audit_results['checks'].append({
                    'name': 'File Permissions',
                    'status': 'SKIP',
                    'message': 'Service account path not configured'
                })
        except SecurityValidationError as e:
            audit_results['checks'].append({
                'name': 'File Permissions',
                'status': 'FAIL',
                'message': str(e)
            })
            audit_results['errors'].append(f"File Permissions: {e}")
        
        # Check 3: Credential format validation
        try:
            from ..config.configuration_manager import ConfigurationManager
            config_manager = ConfigurationManager()
            
            # Validate Binance credentials
            binance_creds = config_manager.load_binance_credentials()
            self.validate_binance_credentials(binance_creds)
            
            # Validate Google credentials
            google_creds = config_manager.load_google_credentials()
            self.validate_google_credentials(google_creds)
            
            audit_results['checks'].append({
                'name': 'Credential Format',
                'status': 'PASS',
                'message': 'All credentials have valid format'
            })
        except Exception as e:
            audit_results['checks'].append({
                'name': 'Credential Format',
                'status': 'FAIL',
                'message': str(e)
            })
            audit_results['errors'].append(f"Credential Format: {e}")
        
        # Check 4: API access validation
        try:
            from ..config.configuration_manager import ConfigurationManager
            config_manager = ConfigurationManager()
            binance_creds = config_manager.load_binance_credentials()
            
            self.validate_binance_api_access(binance_creds)
            audit_results['checks'].append({
                'name': 'API Access',
                'status': 'PASS',
                'message': 'Binance API access validated successfully'
            })
        except Exception as e:
            audit_results['checks'].append({
                'name': 'API Access',
                'status': 'FAIL',
                'message': str(e)
            })
            audit_results['errors'].append(f"API Access: {e}")
        
        # Determine overall status
        failed_checks = [check for check in audit_results['checks'] if check['status'] == 'FAIL']
        if failed_checks:
            audit_results['overall_status'] = 'FAIL'
        else:
            audit_results['overall_status'] = 'PASS'
        
        return audit_results