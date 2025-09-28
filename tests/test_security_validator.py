"""
Unit tests for SecurityValidator class.
"""
import os
import json
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.utils.security_validator import SecurityValidator, SecurityValidationError
from src.models.data_models import BinanceCredentials, GoogleCredentials


class TestSecurityValidator(unittest.TestCase):
    """Test cases for SecurityValidator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()
        
        # Sample valid credentials
        self.valid_binance_creds = BinanceCredentials(
            api_key="valid_api_key_with_sufficient_length_12345",
            api_secret="valid_api_secret_with_sufficient_length_67890"
        )
        
        # Create temporary service account file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.service_account_path = os.path.join(self.temp_dir, "service_account.json")
        
        # Valid service account JSON
        self.valid_service_account = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest-key\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        
        with open(self.service_account_path, 'w') as f:
            json.dump(self.valid_service_account, f)
        
        self.valid_google_creds = GoogleCredentials(
            service_account_path=self.service_account_path,
            spreadsheet_id="valid_spreadsheet_id_with_sufficient_length",
            sheet_name="Test Sheet"
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('platform.system')
    @patch('src.utils.security_validator.Path.stat')
    def test_validate_file_permissions_unix_secure(self, mock_stat, mock_platform):
        """Test file permission validation on Unix with secure permissions."""
        mock_platform.return_value = 'Linux'
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content")
            temp_file_path = temp_file.name
        
        try:
            # Mock file stat to return secure permissions (0o600)
            mock_stat_result = Mock()
            mock_stat_result.st_mode = 0o100600  # Regular file with 600 permissions
            mock_stat.return_value = mock_stat_result
            
            # Should pass validation
            result = self.validator.validate_file_permissions(temp_file_path)
            self.assertTrue(result)
            
        finally:
            os.unlink(temp_file_path)
    
    @patch('platform.system')
    @patch('src.utils.security_validator.Path.stat')
    def test_validate_file_permissions_unix_insecure(self, mock_stat, mock_platform):
        """Test file permission validation on Unix with insecure permissions."""
        mock_platform.return_value = 'Linux'
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content")
            temp_file_path = temp_file.name
        
        try:
            # Mock file stat to return insecure permissions (0o644)
            mock_stat_result = Mock()
            mock_stat_result.st_mode = 0o100644  # Regular file with 644 permissions (readable by others)
            mock_stat.return_value = mock_stat_result
            
            # Should fail validation
            with self.assertRaises(SecurityValidationError) as context:
                self.validator.validate_file_permissions(temp_file_path)
            
            self.assertIn("insecure permissions", str(context.exception))
            
        finally:
            os.unlink(temp_file_path)
    
    @patch('platform.system')
    def test_validate_file_permissions_windows_skip(self, mock_platform):
        """Test file permission validation on Windows (should skip)."""
        mock_platform.return_value = 'Windows'
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content")
            temp_file_path = temp_file.name
        
        try:
            # Should pass validation (skipped on Windows)
            result = self.validator.validate_file_permissions(temp_file_path)
            self.assertTrue(result)
            
        finally:
            os.unlink(temp_file_path)
    
    def test_validate_file_permissions_nonexistent_file(self):
        """Test file permission validation with non-existent file."""
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_file_permissions("/nonexistent/file.txt")
        
        self.assertIn("File not found", str(context.exception))
    
    def test_validate_binance_credentials_valid(self):
        """Test Binance credentials validation with valid credentials."""
        result = self.validator.validate_binance_credentials(self.valid_binance_creds)
        self.assertTrue(result)
    
    def test_validate_binance_credentials_empty(self):
        """Test Binance credentials validation with empty credentials."""
        invalid_creds = BinanceCredentials(api_key="", api_secret="valid_secret_123456789")
        
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_binance_credentials(invalid_creds)
        
        self.assertIn("required", str(context.exception))
    
    def test_validate_binance_credentials_too_short(self):
        """Test Binance credentials validation with too short credentials."""
        invalid_creds = BinanceCredentials(api_key="short", api_secret="also_short")
        
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_binance_credentials(invalid_creds)
        
        self.assertIn("too short", str(context.exception))
    
    def test_validate_binance_credentials_placeholder(self):
        """Test Binance credentials validation with placeholder values."""
        invalid_creds = BinanceCredentials(
            api_key="your_api_key_here_with_sufficient_length",
            api_secret="valid_secret_with_sufficient_length_123456789"
        )
        
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_binance_credentials(invalid_creds)
        
        self.assertIn("placeholder", str(context.exception))
    
    @patch('platform.system')
    def test_validate_google_credentials_valid(self, mock_platform):
        """Test Google credentials validation with valid credentials."""
        mock_platform.return_value = 'Windows'  # Skip permission check
        
        result = self.validator.validate_google_credentials(self.valid_google_creds)
        self.assertTrue(result)
    
    def test_validate_google_credentials_invalid_json(self):
        """Test Google credentials validation with invalid JSON."""
        # Create invalid JSON file
        invalid_json_path = os.path.join(self.temp_dir, "invalid.json")
        with open(invalid_json_path, 'w') as f:
            f.write("invalid json content")
        
        invalid_creds = GoogleCredentials(
            service_account_path=invalid_json_path,
            spreadsheet_id="valid_spreadsheet_id_123456789",
            sheet_name="Test Sheet"
        )
        
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_google_credentials(invalid_creds)
        
        self.assertIn("Invalid JSON", str(context.exception))
    
    def test_validate_google_credentials_missing_fields(self):
        """Test Google credentials validation with missing required fields."""
        # Create service account JSON missing required fields
        incomplete_service_account = {
            "type": "service_account",
            "project_id": "test-project"
            # Missing other required fields
        }
        
        incomplete_json_path = os.path.join(self.temp_dir, "incomplete.json")
        with open(incomplete_json_path, 'w') as f:
            json.dump(incomplete_service_account, f)
        
        invalid_creds = GoogleCredentials(
            service_account_path=incomplete_json_path,
            spreadsheet_id="valid_spreadsheet_id_123456789",
            sheet_name="Test Sheet"
        )
        
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_google_credentials(invalid_creds)
        
        self.assertIn("missing required fields", str(context.exception))
    
    def test_validate_google_credentials_wrong_type(self):
        """Test Google credentials validation with wrong service account type."""
        # Create service account JSON with wrong type
        wrong_type_service_account = self.valid_service_account.copy()
        wrong_type_service_account["type"] = "user_account"
        
        wrong_type_json_path = os.path.join(self.temp_dir, "wrong_type.json")
        with open(wrong_type_json_path, 'w') as f:
            json.dump(wrong_type_service_account, f)
        
        invalid_creds = GoogleCredentials(
            service_account_path=wrong_type_json_path,
            spreadsheet_id="valid_spreadsheet_id_123456789",
            sheet_name="Test Sheet"
        )
        
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_google_credentials(invalid_creds)
        
        self.assertIn("Invalid service account type", str(context.exception))
    
    def test_validate_google_credentials_short_spreadsheet_id(self):
        """Test Google credentials validation with too short spreadsheet ID."""
        invalid_creds = GoogleCredentials(
            service_account_path=self.service_account_path,
            spreadsheet_id="short",
            sheet_name="Test Sheet"
        )
        
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_google_credentials(invalid_creds)
        
        self.assertIn("too short", str(context.exception))
    
    @patch('src.utils.security_validator.Client')
    def test_validate_binance_api_access_success(self, mock_client_class):
        """Test Binance API access validation with successful connection."""
        # Mock successful API client
        mock_client = Mock()
        mock_client.get_server_time.return_value = {"serverTime": 1234567890}
        mock_client.get_account.return_value = {"balances": []}
        mock_client.get_api_key_permission.return_value = {
            "enableSpotAndMarginTrading": False,
            "enableFutures": False,
            "enableWithdrawals": False
        }
        mock_client_class.return_value = mock_client
        
        result = self.validator.validate_binance_api_access(self.valid_binance_creds)
        self.assertTrue(result)
        
        # Verify API calls were made
        mock_client.get_server_time.assert_called()
        mock_client.get_account.assert_called()
    
    @patch('src.utils.security_validator.Client')
    def test_validate_binance_api_access_auth_failure(self, mock_client_class):
        """Test Binance API access validation with authentication failure."""
        from binance.exceptions import BinanceAPIException
        
        # Mock API client with authentication error
        mock_client = Mock()
        mock_client.get_server_time.return_value = {"serverTime": 1234567890}
        
        # Create a proper BinanceAPIException with a mock response
        mock_response = Mock()
        mock_response.text = '{"code": -2014, "msg": "API-key format invalid"}'
        api_exception = BinanceAPIException(mock_response, -2014, '{"code": -2014, "msg": "API-key format invalid"}')
        mock_client.get_account.side_effect = api_exception
        mock_client_class.return_value = mock_client
        
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_binance_api_access(self.valid_binance_creds)
        
        self.assertIn("authentication failed", str(context.exception))
    
    @patch('src.utils.security_validator.Client')
    def test_validate_binance_api_access_with_trading_permissions(self, mock_client_class):
        """Test Binance API access validation with trading permissions (should warn)."""
        # Mock API client with trading permissions enabled
        mock_client = Mock()
        mock_client.get_server_time.return_value = {"serverTime": 1234567890}
        mock_client.get_account.return_value = {"balances": []}
        mock_client.get_api_key_permission.return_value = {
            "enableSpotAndMarginTrading": True,  # Trading enabled - should warn
            "enableFutures": False,
            "enableWithdrawals": False
        }
        mock_client_class.return_value = mock_client
        
        # Should still pass but log warnings
        result = self.validator.validate_binance_api_access(self.valid_binance_creds)
        self.assertTrue(result)
    
    @patch.dict(os.environ, {
        'BINANCE_API_KEY': 'test_api_key_123456789',
        'BINANCE_API_SECRET': 'test_api_secret_123456789',
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service_account.json',
        'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id_123456789'
    })
    def test_validate_environment_variables_success(self):
        """Test environment variables validation with all required variables set."""
        result = self.validator.validate_environment_variables()
        self.assertTrue(result)
    
    @patch.dict(os.environ, {
        'BINANCE_API_KEY': 'test_api_key_123456789',
        # Missing BINANCE_API_SECRET
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service_account.json',
        'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id_123456789'
    }, clear=True)
    def test_validate_environment_variables_missing(self):
        """Test environment variables validation with missing variables."""
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_environment_variables()
        
        self.assertIn("Missing required environment variables", str(context.exception))
        self.assertIn("BINANCE_API_SECRET", str(context.exception))
    
    @patch.dict(os.environ, {
        'BINANCE_API_KEY': '',  # Empty value
        'BINANCE_API_SECRET': 'test_api_secret_123456789',
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service_account.json',
        'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id_123456789'
    })
    def test_validate_environment_variables_empty(self):
        """Test environment variables validation with empty variables."""
        with self.assertRaises(SecurityValidationError) as context:
            self.validator.validate_environment_variables()
        
        self.assertIn("Empty environment variables", str(context.exception))
        self.assertIn("BINANCE_API_KEY", str(context.exception))
    
    @patch('src.utils.security_validator.SecurityValidator.validate_environment_variables')
    @patch('src.utils.security_validator.SecurityValidator.validate_file_permissions')
    @patch('src.config.configuration_manager.ConfigurationManager')
    def test_run_security_audit_success(self, mock_config_manager_class, mock_validate_file_perms, mock_validate_env_vars):
        """Test comprehensive security audit with all checks passing."""
        # Mock successful validations
        mock_validate_env_vars.return_value = True
        mock_validate_file_perms.return_value = True
        
        # Mock configuration manager
        mock_config_manager = Mock()
        mock_config_manager.load_binance_credentials.return_value = self.valid_binance_creds
        mock_config_manager.load_google_credentials.return_value = self.valid_google_creds
        mock_config_manager_class.return_value = mock_config_manager
        
        # Mock environment variables
        with patch.dict(os.environ, {
            'GOOGLE_SERVICE_ACCOUNT_PATH': self.service_account_path
        }):
            # Mock API validation
            with patch.object(self.validator, 'validate_binance_api_access', return_value=True):
                audit_results = self.validator.run_security_audit()
        
        self.assertEqual(audit_results['overall_status'], 'PASS')
        self.assertTrue(len(audit_results['checks']) > 0)
        self.assertEqual(len(audit_results['errors']), 0)
    
    @patch('src.utils.security_validator.SecurityValidator.validate_environment_variables')
    def test_run_security_audit_failure(self, mock_validate_env_vars):
        """Test comprehensive security audit with failures."""
        # Mock failed environment validation
        mock_validate_env_vars.side_effect = SecurityValidationError("Missing environment variables")
        
        audit_results = self.validator.run_security_audit()
        
        self.assertEqual(audit_results['overall_status'], 'FAIL')
        self.assertTrue(len(audit_results['errors']) > 0)
        self.assertIn("Environment Variables", str(audit_results['errors']))


if __name__ == '__main__':
    unittest.main()