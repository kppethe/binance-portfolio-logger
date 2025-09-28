"""
Unit tests for the ConfigurationManager class.
"""
import os
import tempfile
import stat
from pathlib import Path
from unittest.mock import patch
import pytest

from src.config.configuration_manager import ConfigurationManager, ConfigurationError
from src.models.data_models import BinanceCredentials, GoogleCredentials, ExecutionConfig
from src.utils.security_validator import SecurityValidationError


class TestConfigurationManager:
    """Test cases for ConfigurationManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_manager = ConfigurationManager(enable_security_validation=False)
    
    def test_load_binance_credentials_success(self):
        """Test successful loading of Binance credentials."""
        with patch.dict(os.environ, {
            'BINANCE_API_KEY': 'test_api_key',
            'BINANCE_API_SECRET': 'test_api_secret'
        }):
            credentials = self.config_manager.load_binance_credentials()
            
            assert isinstance(credentials, BinanceCredentials)
            assert credentials.api_key == 'test_api_key'
            assert credentials.api_secret == 'test_api_secret'
    
    def test_load_binance_credentials_missing_api_key(self):
        """Test error when BINANCE_API_KEY is missing."""
        with patch.dict(os.environ, {
            'BINANCE_API_SECRET': 'test_api_secret'
        }, clear=True):
            with pytest.raises(ConfigurationError, match="BINANCE_API_KEY environment variable is required"):
                self.config_manager.load_binance_credentials()
    
    def test_load_binance_credentials_missing_api_secret(self):
        """Test error when BINANCE_API_SECRET is missing."""
        with patch.dict(os.environ, {
            'BINANCE_API_KEY': 'test_api_key'
        }, clear=True):
            with pytest.raises(ConfigurationError, match="BINANCE_API_SECRET environment variable is required"):
                self.config_manager.load_binance_credentials()
    
    def test_load_binance_credentials_empty_api_key(self):
        """Test error when BINANCE_API_KEY is empty."""
        with patch.dict(os.environ, {
            'BINANCE_API_KEY': '   ',
            'BINANCE_API_SECRET': 'test_api_secret'
        }):
            with pytest.raises(ConfigurationError, match="BINANCE_API_KEY cannot be empty"):
                self.config_manager.load_binance_credentials()
    
    def test_load_binance_credentials_empty_api_secret(self):
        """Test error when BINANCE_API_SECRET is empty."""
        with patch.dict(os.environ, {
            'BINANCE_API_KEY': 'test_api_key',
            'BINANCE_API_SECRET': '   '
        }):
            with pytest.raises(ConfigurationError, match="BINANCE_API_SECRET cannot be empty"):
                self.config_manager.load_binance_credentials()
    
    def test_load_google_credentials_success(self):
        """Test successful loading of Google credentials."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            temp_file.write('{"type": "service_account"}')
            temp_file_path = temp_file.name
        
        try:
            # Set proper permissions (600)
            os.chmod(temp_file_path, stat.S_IRUSR | stat.S_IWUSR)
            
            with patch.dict(os.environ, {
                'GOOGLE_SERVICE_ACCOUNT_PATH': temp_file_path,
                'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id',
                'GOOGLE_SHEET_NAME': 'Test Sheet'
            }):
                credentials = self.config_manager.load_google_credentials()
                
                assert isinstance(credentials, GoogleCredentials)
                assert credentials.service_account_path == temp_file_path
                assert credentials.spreadsheet_id == 'test_spreadsheet_id'
                assert credentials.sheet_name == 'Test Sheet'
        finally:
            os.unlink(temp_file_path)
    
    def test_load_google_credentials_default_sheet_name(self):
        """Test Google credentials with default sheet name."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            temp_file.write('{"type": "service_account"}')
            temp_file_path = temp_file.name
        
        try:
            os.chmod(temp_file_path, stat.S_IRUSR | stat.S_IWUSR)
            
            with patch.dict(os.environ, {
                'GOOGLE_SERVICE_ACCOUNT_PATH': temp_file_path,
                'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id'
            }, clear=True):
                credentials = self.config_manager.load_google_credentials()
                
                assert credentials.sheet_name == 'Binance Portfolio'
        finally:
            os.unlink(temp_file_path)
    
    def test_load_google_credentials_missing_service_account_path(self):
        """Test error when GOOGLE_SERVICE_ACCOUNT_PATH is missing."""
        with patch.dict(os.environ, {
            'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id'
        }, clear=True):
            with pytest.raises(ConfigurationError, match="GOOGLE_SERVICE_ACCOUNT_PATH environment variable is required"):
                self.config_manager.load_google_credentials()
    
    def test_load_google_credentials_missing_spreadsheet_id(self):
        """Test error when GOOGLE_SPREADSHEET_ID is missing."""
        with patch.dict(os.environ, {
            'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service/account.json'
        }, clear=True):
            with pytest.raises(ConfigurationError, match="GOOGLE_SPREADSHEET_ID environment variable is required"):
                self.config_manager.load_google_credentials()
    
    def test_load_google_credentials_file_not_found(self):
        """Test error when service account file doesn't exist."""
        with patch.dict(os.environ, {
            'GOOGLE_SERVICE_ACCOUNT_PATH': '/nonexistent/path/service-account.json',
            'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id'
        }):
            with pytest.raises(ConfigurationError, match="Google service account file not found"):
                self.config_manager.load_google_credentials()
    
    @pytest.mark.skipif(os.name == 'nt', reason="File permission checks not supported on Windows")
    def test_load_google_credentials_insecure_permissions(self):
        """Test error when service account file has insecure permissions."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            temp_file.write('{"type": "service_account"}')
            temp_file_path = temp_file.name
        
        try:
            # Set insecure permissions (readable by group and others)
            os.chmod(temp_file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            
            with patch.dict(os.environ, {
                'GOOGLE_SERVICE_ACCOUNT_PATH': temp_file_path,
                'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id'
            }):
                with pytest.raises(ConfigurationError, match="Google service account file has insecure permissions"):
                    self.config_manager.load_google_credentials()
        finally:
            os.unlink(temp_file_path)
    
    def test_get_execution_config_defaults(self):
        """Test execution config with default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = self.config_manager.get_execution_config()
            
            assert isinstance(config, ExecutionConfig)
            assert config.timeout_seconds == 60
            assert config.max_retries == 3
            assert config.log_file_path == '/var/log/binance-portfolio.log'
    
    def test_get_execution_config_custom_values(self):
        """Test execution config with custom environment values."""
        with patch.dict(os.environ, {
            'EXECUTION_TIMEOUT_SECONDS': '120',
            'MAX_RETRIES': '5',
            'LOG_FILE_PATH': '/custom/log/path.log'
        }):
            config = self.config_manager.get_execution_config()
            
            assert config.timeout_seconds == 120
            assert config.max_retries == 5
            assert config.log_file_path == '/custom/log/path.log'
    
    def test_get_execution_config_timeout_too_low(self):
        """Test error when timeout is too low."""
        with patch.dict(os.environ, {
            'EXECUTION_TIMEOUT_SECONDS': '0'
        }):
            with pytest.raises(ConfigurationError, match="EXECUTION_TIMEOUT_SECONDS must be at least 1 second"):
                self.config_manager.get_execution_config()
    
    def test_get_execution_config_timeout_too_high(self):
        """Test error when timeout is too high."""
        with patch.dict(os.environ, {
            'EXECUTION_TIMEOUT_SECONDS': '400'
        }):
            with pytest.raises(ConfigurationError, match="EXECUTION_TIMEOUT_SECONDS must be less than 300 seconds"):
                self.config_manager.get_execution_config()
    
    def test_get_execution_config_negative_retries(self):
        """Test error when max retries is negative."""
        with patch.dict(os.environ, {
            'MAX_RETRIES': '-1'
        }):
            with pytest.raises(ConfigurationError, match="MAX_RETRIES must be non-negative"):
                self.config_manager.get_execution_config()
    
    def test_get_execution_config_too_many_retries(self):
        """Test error when max retries is too high."""
        with patch.dict(os.environ, {
            'MAX_RETRIES': '15'
        }):
            with pytest.raises(ConfigurationError, match="MAX_RETRIES must be 10 or less"):
                self.config_manager.get_execution_config()
    
    def test_validate_configuration_success(self):
        """Test successful validation of all configuration."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            temp_file.write('{"type": "service_account"}')
            temp_file_path = temp_file.name
        
        try:
            os.chmod(temp_file_path, stat.S_IRUSR | stat.S_IWUSR)
            
            with patch.dict(os.environ, {
                'BINANCE_API_KEY': 'test_api_key',
                'BINANCE_API_SECRET': 'test_api_secret',
                'GOOGLE_SERVICE_ACCOUNT_PATH': temp_file_path,
                'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id'
            }):
                result = self.config_manager.validate_configuration()
                
                assert result is True
                assert self.config_manager.binance_credentials is not None
                assert self.config_manager.google_credentials is not None
                assert self.config_manager.execution_config is not None
        finally:
            os.unlink(temp_file_path)
    
    def test_validate_configuration_failure(self):
        """Test validation failure when configuration is invalid."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError):
                self.config_manager.validate_configuration()
    
    def test_cached_properties(self):
        """Test that configuration properties are cached after loading."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            temp_file.write('{"type": "service_account"}')
            temp_file_path = temp_file.name
        
        try:
            os.chmod(temp_file_path, stat.S_IRUSR | stat.S_IWUSR)
            
            with patch.dict(os.environ, {
                'BINANCE_API_KEY': 'test_api_key',
                'BINANCE_API_SECRET': 'test_api_secret',
                'GOOGLE_SERVICE_ACCOUNT_PATH': temp_file_path,
                'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id'
            }):
                # Initially properties should be None
                assert self.config_manager.binance_credentials is None
                assert self.config_manager.google_credentials is None
                assert self.config_manager.execution_config is None
                
                # Load configuration
                self.config_manager.validate_configuration()
                
                # Properties should now be cached
                assert self.config_manager.binance_credentials is not None
                assert self.config_manager.google_credentials is not None
                assert self.config_manager.execution_config is not None
        finally:
            os.unlink(temp_file_path)
    
    @patch('src.utils.security_validator.SecurityValidator')
    def test_configuration_manager_with_security_validation_enabled(self, mock_security_validator_class):
        """Test ConfigurationManager initialization with security validation enabled."""
        mock_validator = mock_security_validator_class.return_value
        
        config_manager = ConfigurationManager(enable_security_validation=True)
        
        # Should create security validator
        mock_security_validator_class.assert_called_once()
        assert config_manager._security_validator is not None
    
    def test_configuration_manager_with_security_validation_disabled(self):
        """Test ConfigurationManager initialization with security validation disabled."""
        config_manager = ConfigurationManager(enable_security_validation=False)
        
        # Should not create security validator
        assert config_manager._security_validator is None
    
    @patch.dict(os.environ, {
        'BINANCE_API_KEY': 'valid_api_key_with_sufficient_length_123456789',
        'BINANCE_API_SECRET': 'valid_api_secret_with_sufficient_length_123456789',
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/tmp/service_account.json',
        'GOOGLE_SPREADSHEET_ID': 'valid_spreadsheet_id_with_sufficient_length_123456789'
    })
    @patch('src.utils.security_validator.SecurityValidator')
    def test_validate_configuration_with_security_validation(self, mock_security_validator_class):
        """Test configuration validation with security validation enabled."""
        # Mock security validator
        mock_validator = mock_security_validator_class.return_value
        mock_validator.validate_environment_variables.return_value = True
        mock_validator.validate_binance_credentials.return_value = True
        mock_validator.validate_google_credentials.return_value = True
        mock_validator.validate_binance_api_access.return_value = True
        
        # Mock file operations for Google credentials
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_file', return_value=True), \
             patch('platform.system', return_value='Windows'):
            
            config_manager = ConfigurationManager(enable_security_validation=True)
            result = config_manager.validate_configuration()
            
            assert result is True
            
            # Verify security validation methods were called
            mock_validator.validate_environment_variables.assert_called_once()
            mock_validator.validate_binance_credentials.assert_called_once()
            mock_validator.validate_google_credentials.assert_called_once()
            mock_validator.validate_binance_api_access.assert_called_once()
    
    @patch.dict(os.environ, {
        'BINANCE_API_KEY': 'valid_api_key_with_sufficient_length_123456789',
        'BINANCE_API_SECRET': 'valid_api_secret_with_sufficient_length_123456789',
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/tmp/service_account.json',
        'GOOGLE_SPREADSHEET_ID': 'valid_spreadsheet_id_with_sufficient_length_123456789',
        'VALIDATE_API_ON_STARTUP': 'false'
    })
    @patch('src.utils.security_validator.SecurityValidator')
    def test_validate_configuration_skip_api_validation(self, mock_security_validator_class):
        """Test configuration validation with API validation skipped."""
        # Mock security validator
        mock_validator = mock_security_validator_class.return_value
        mock_validator.validate_environment_variables.return_value = True
        mock_validator.validate_binance_credentials.return_value = True
        mock_validator.validate_google_credentials.return_value = True
        
        # Mock file operations for Google credentials
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_file', return_value=True), \
             patch('platform.system', return_value='Windows'):
            
            config_manager = ConfigurationManager(enable_security_validation=True)
            result = config_manager.validate_configuration()
            
            assert result is True
            
            # Verify API validation was NOT called
            mock_validator.validate_binance_api_access.assert_not_called()
    
    @patch('src.utils.security_validator.SecurityValidator')
    def test_validate_configuration_security_validation_failure(self, mock_security_validator_class):
        """Test configuration validation with security validation failure."""
        # Mock security validator with failure
        mock_validator = mock_security_validator_class.return_value
        mock_validator.validate_environment_variables.side_effect = SecurityValidationError("Test security error")
        
        config_manager = ConfigurationManager(enable_security_validation=True)
        
        with pytest.raises(ConfigurationError) as exc_info:
            config_manager.validate_configuration()
        
        assert "Environment validation failed" in str(exc_info.value)
        assert "Test security error" in str(exc_info.value)
    
    @patch('src.utils.security_validator.SecurityValidator')
    def test_validate_startup_security_success(self, mock_security_validator_class):
        """Test startup security validation with successful audit."""
        # Mock security validator with successful audit
        mock_validator = mock_security_validator_class.return_value
        mock_validator.run_security_audit.return_value = {
            'overall_status': 'PASS',
            'checks': [
                {'name': 'Test Check', 'status': 'PASS', 'message': 'Test passed'}
            ],
            'warnings': ['Test warning'],
            'errors': []
        }
        
        config_manager = ConfigurationManager(enable_security_validation=True)
        result = config_manager.validate_startup_security()
        
        assert result is True
        mock_validator.run_security_audit.assert_called_once()
    
    @patch('src.utils.security_validator.SecurityValidator')
    def test_validate_startup_security_failure(self, mock_security_validator_class):
        """Test startup security validation with failed audit."""
        # Mock security validator with failed audit
        mock_validator = mock_security_validator_class.return_value
        mock_validator.run_security_audit.return_value = {
            'overall_status': 'FAIL',
            'checks': [
                {'name': 'Test Check', 'status': 'FAIL', 'message': 'Test failed'}
            ],
            'warnings': [],
            'errors': ['Test error']
        }
        
        config_manager = ConfigurationManager(enable_security_validation=True)
        
        with pytest.raises(ConfigurationError) as exc_info:
            config_manager.validate_startup_security()
        
        assert "Startup security validation failed" in str(exc_info.value)
        assert "Test Check: Test failed" in str(exc_info.value)
        assert "Test error" in str(exc_info.value)
    
    def test_validate_startup_security_disabled(self):
        """Test startup security validation when security validation is disabled."""
        config_manager = ConfigurationManager(enable_security_validation=False)
        result = config_manager.validate_startup_security()
        
        assert result is True
    
    @patch('src.utils.security_validator.SecurityValidator')
    def test_validate_startup_security_unexpected_error(self, mock_security_validator_class):
        """Test startup security validation with unexpected error."""
        # Mock security validator with unexpected error
        mock_validator = mock_security_validator_class.return_value
        mock_validator.run_security_audit.side_effect = Exception("Unexpected error")
        
        config_manager = ConfigurationManager(enable_security_validation=True)
        
        with pytest.raises(ConfigurationError) as exc_info:
            config_manager.validate_startup_security()
        
        assert "Unexpected error during startup security validation" in str(exc_info.value)
        assert "Unexpected error" in str(exc_info.value)