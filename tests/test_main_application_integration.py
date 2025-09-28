"""
Integration tests for the main application orchestrator.

These tests verify the complete workflow execution and component integration.
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.main_application import MainApplication, ApplicationError, ExecutionTimeoutError
from src.models.data_models import AssetBalance, PortfolioValue, BinanceCredentials, GoogleCredentials


class TestMainApplicationIntegration(unittest.TestCase):
    """Integration tests for MainApplication class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test logs
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'test_portfolio.log')
        
        # Set up test environment variables
        self.test_env = {
            'BINANCE_API_KEY': 'test_api_key_12345',
            'BINANCE_API_SECRET': 'test_api_secret_67890',
            'GOOGLE_SERVICE_ACCOUNT_PATH': os.path.join(self.temp_dir, 'service_account.json'),
            'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id',
            'GOOGLE_SHEET_NAME': 'Test Portfolio',
            'LOG_FILE_PATH': self.log_file,
            'EXECUTION_TIMEOUT_SECONDS': '30',
            'MAX_RETRIES': '2'
        }
        
        # Create mock service account file
        service_account_content = '''
        {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\\ntest-private-key\\n-----END PRIVATE KEY-----\\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "test-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        '''
        
        with open(self.test_env['GOOGLE_SERVICE_ACCOUNT_PATH'], 'w') as f:
            f.write(service_account_content)
        
        # Set file permissions (simulate secure file)
        os.chmod(self.test_env['GOOGLE_SERVICE_ACCOUNT_PATH'], 0o600)
        
        # Apply test environment
        self.original_env = {}
        for key, value in self.test_env.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_mock_balances(self):
        """Create mock asset balances for testing."""
        return [
            AssetBalance(asset='BTC', free=0.5, locked=0.0, total=0.5),
            AssetBalance(asset='ETH', free=2.0, locked=0.5, total=2.5),
            AssetBalance(asset='USDT', free=1000.0, locked=0.0, total=1000.0),
            AssetBalance(asset='BNB', free=10.0, locked=0.0, total=10.0)
        ]
    
    def create_mock_portfolio_value(self):
        """Create mock portfolio value for testing."""
        return PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=25000.0,
            asset_breakdown={
                'BTC': 20000.0,
                'ETH': 3500.0,
                'USDT': 1000.0,
                'BNB': 500.0
            },
            conversion_failures=[]
        )
    
    @patch('src.main_application.BinanceClient')
    @patch('src.main_application.GoogleSheetsLogger')
    def test_successful_workflow_execution(self, mock_sheets_logger_class, mock_binance_client_class):
        """Test successful execution of the complete workflow."""
        # Setup mocks
        mock_binance_client = Mock()
        mock_binance_client.validate_connection.return_value = True
        mock_binance_client.get_account_balances.return_value = self.create_mock_balances()
        mock_binance_client_class.return_value = mock_binance_client
        
        mock_sheets_logger = Mock()
        mock_sheets_logger.validate_sheet_access.return_value = True
        mock_sheets_logger.append_portfolio_data.return_value = True
        mock_sheets_logger_class.return_value = mock_sheets_logger
        
        # Mock portfolio calculator
        with patch('src.main_application.PortfolioCalculator') as mock_calc_class:
            mock_calculator = Mock()
            mock_calculator.calculate_portfolio_value.return_value = self.create_mock_portfolio_value()
            mock_calc_class.return_value = mock_calculator
            
            # Execute application
            app = MainApplication()
            exit_code = app.run()
            
            # Verify successful execution
            self.assertEqual(exit_code, 0)
            
            # Verify component initialization
            self.assertIsNotNone(app.config_manager)
            self.assertIsNotNone(app.binance_client)
            self.assertIsNotNone(app.portfolio_calculator)
            self.assertIsNotNone(app.google_sheets_logger)
            self.assertIsNotNone(app.error_handler)
            
            # Verify workflow steps were called
            mock_binance_client.validate_connection.assert_called_once()
            mock_binance_client.get_account_balances.assert_called_once()
            mock_calculator.calculate_portfolio_value.assert_called_once()
            mock_sheets_logger.validate_sheet_access.assert_called_once()
            mock_sheets_logger.append_portfolio_data.assert_called_once()
    
    @patch('src.main_application.BinanceClient')
    @patch('src.main_application.GoogleSheetsLogger')
    def test_configuration_error_handling(self, mock_sheets_logger_class, mock_binance_client_class):
        """Test handling of configuration errors."""
        # Remove required environment variable
        del os.environ['BINANCE_API_KEY']
        
        app = MainApplication()
        exit_code = app.run()
        
        # Should fail with configuration error
        self.assertEqual(exit_code, 1)
    
    @patch('src.main_application.BinanceClient')
    @patch('src.main_application.GoogleSheetsLogger')
    def test_binance_connection_failure(self, mock_sheets_logger_class, mock_binance_client_class):
        """Test handling of Binance connection failures."""
        # Setup mock to fail connection validation
        mock_binance_client = Mock()
        mock_binance_client.validate_connection.return_value = False
        mock_binance_client_class.return_value = mock_binance_client
        
        app = MainApplication()
        exit_code = app.run()
        
        # Should fail with application error
        self.assertEqual(exit_code, 1)
    
    @patch('src.main_application.BinanceClient')
    @patch('src.main_application.GoogleSheetsLogger')
    def test_google_sheets_error_handling(self, mock_sheets_logger_class, mock_binance_client_class):
        """Test handling of Google Sheets errors."""
        # Setup Binance mock
        mock_binance_client = Mock()
        mock_binance_client.validate_connection.return_value = True
        mock_binance_client.get_account_balances.return_value = self.create_mock_balances()
        mock_binance_client_class.return_value = mock_binance_client
        
        # Setup Google Sheets mock to fail
        mock_sheets_logger = Mock()
        mock_sheets_logger.validate_sheet_access.side_effect = Exception("Sheets access failed")
        mock_sheets_logger_class.return_value = mock_sheets_logger
        
        app = MainApplication()
        exit_code = app.run()
        
        # Should fail with application error
        self.assertEqual(exit_code, 1)
    
    @patch('src.main_application.BinanceClient')
    @patch('src.main_application.GoogleSheetsLogger')
    def test_execution_timeout_handling(self, mock_sheets_logger_class, mock_binance_client_class):
        """Test execution timeout handling."""
        # Setup mocks
        mock_binance_client = Mock()
        mock_binance_client.validate_connection.return_value = True
        # Make get_account_balances hang to trigger timeout
        mock_binance_client.get_account_balances.side_effect = lambda: time.sleep(5)
        mock_binance_client_class.return_value = mock_binance_client
        
        mock_sheets_logger = Mock()
        mock_sheets_logger.validate_sheet_access.return_value = True
        mock_sheets_logger_class.return_value = mock_sheets_logger
        
        # Set very short timeout
        config_overrides = {'timeout': 1}
        app = MainApplication(config_overrides)
        exit_code = app.run()
        
        # Should fail with timeout error
        self.assertEqual(exit_code, 2)
    
    @patch('src.main_application.BinanceClient')
    @patch('src.main_application.GoogleSheetsLogger')
    def test_graceful_shutdown_handling(self, mock_sheets_logger_class, mock_binance_client_class):
        """Test graceful shutdown when signal is received."""
        # Setup mocks
        mock_binance_client = Mock()
        mock_binance_client.validate_connection.return_value = True
        mock_binance_client_class.return_value = mock_binance_client
        
        mock_sheets_logger = Mock()
        mock_sheets_logger.validate_sheet_access.return_value = True
        mock_sheets_logger_class.return_value = mock_sheets_logger
        
        app = MainApplication()
        
        # Initialize components
        app._initialize_components()
        
        # Request shutdown
        app.shutdown_requested = True
        
        # Try to execute workflow - should detect shutdown request
        with self.assertRaises(ApplicationError) as context:
            app._execute_workflow()
        
        self.assertIn("Shutdown requested", str(context.exception))
    
    @patch('src.main_application.BinanceClient')
    @patch('src.main_application.GoogleSheetsLogger')
    def test_empty_portfolio_handling(self, mock_sheets_logger_class, mock_binance_client_class):
        """Test handling of empty portfolio (no balances)."""
        # Setup mocks
        mock_binance_client = Mock()
        mock_binance_client.validate_connection.return_value = True
        mock_binance_client.get_account_balances.return_value = []  # Empty balances
        mock_binance_client_class.return_value = mock_binance_client
        
        mock_sheets_logger = Mock()
        mock_sheets_logger.validate_sheet_access.return_value = True
        mock_sheets_logger.append_portfolio_data.return_value = True
        mock_sheets_logger_class.return_value = mock_sheets_logger
        
        app = MainApplication()
        exit_code = app.run()
        
        # Should succeed even with empty portfolio
        self.assertEqual(exit_code, 0)
        
        # Verify empty portfolio was logged
        mock_sheets_logger.append_portfolio_data.assert_called_once()
        logged_portfolio = mock_sheets_logger.append_portfolio_data.call_args[0][0]
        self.assertEqual(logged_portfolio.total_usdt, 0.0)
        self.assertEqual(logged_portfolio.asset_breakdown, {})
    
    def test_config_overrides_application(self):
        """Test that configuration overrides are properly applied."""
        config_overrides = {
            'timeout': 120,
            'max_retries': 5,
            'log_file': '/tmp/custom.log'
        }
        
        app = MainApplication(config_overrides)
        app._apply_config_overrides()
        
        # Verify environment variables were set
        self.assertEqual(os.environ['EXECUTION_TIMEOUT_SECONDS'], '120')
        self.assertEqual(os.environ['MAX_RETRIES'], '5')
        self.assertEqual(os.environ['LOG_FILE_PATH'], '/tmp/custom.log')
    
    @patch('src.main_application.BinanceClient')
    @patch('src.main_application.GoogleSheetsLogger')
    def test_status_reporting(self, mock_sheets_logger_class, mock_binance_client_class):
        """Test application status reporting."""
        # Setup mocks
        mock_binance_client = Mock()
        mock_binance_client.validate_connection.return_value = True
        mock_binance_client_class.return_value = mock_binance_client
        
        mock_sheets_logger = Mock()
        mock_sheets_logger.validate_sheet_access.return_value = True
        mock_sheets_logger_class.return_value = mock_sheets_logger
        
        app = MainApplication()
        app._initialize_components()
        
        status = app.get_status()
        
        # Verify status structure
        self.assertIn('timestamp', status)
        self.assertIn('shutdown_requested', status)
        self.assertIn('components_initialized', status)
        self.assertIn('execution_timeout', status)
        
        # Verify component initialization status
        components = status['components_initialized']
        self.assertTrue(components['config_manager'])
        self.assertTrue(components['binance_client'])
        self.assertTrue(components['portfolio_calculator'])
        self.assertTrue(components['google_sheets_logger'])
        self.assertTrue(components['error_handler'])
    
    @patch('src.main_application.BinanceClient')
    @patch('src.main_application.GoogleSheetsLogger')
    def test_conversion_failures_handling(self, mock_sheets_logger_class, mock_binance_client_class):
        """Test handling of asset conversion failures."""
        # Setup mocks
        mock_binance_client = Mock()
        mock_binance_client.validate_connection.return_value = True
        mock_binance_client.get_account_balances.return_value = self.create_mock_balances()
        mock_binance_client_class.return_value = mock_binance_client
        
        mock_sheets_logger = Mock()
        mock_sheets_logger.validate_sheet_access.return_value = True
        mock_sheets_logger.append_portfolio_data.return_value = True
        mock_sheets_logger_class.return_value = mock_sheets_logger
        
        # Mock portfolio calculator with conversion failures
        with patch('src.main_application.PortfolioCalculator') as mock_calc_class:
            mock_calculator = Mock()
            portfolio_with_failures = self.create_mock_portfolio_value()
            portfolio_with_failures.conversion_failures = ['UNKNOWN_TOKEN', 'DELISTED_COIN']
            mock_calculator.calculate_portfolio_value.return_value = portfolio_with_failures
            mock_calc_class.return_value = mock_calculator
            
            app = MainApplication()
            exit_code = app.run()
            
            # Should still succeed despite conversion failures
            self.assertEqual(exit_code, 0)
            
            # Verify portfolio with failures was logged
            mock_sheets_logger.append_portfolio_data.assert_called_once()
            logged_portfolio = mock_sheets_logger.append_portfolio_data.call_args[0][0]
            self.assertEqual(len(logged_portfolio.conversion_failures), 2)


class TestMainApplicationCommandLine(unittest.TestCase):
    """Test command-line argument parsing and handling."""
    
    def test_argument_parser_creation(self):
        """Test that argument parser is created correctly."""
        from src.main_application import create_argument_parser
        
        parser = create_argument_parser()
        
        # Test parsing valid arguments
        args = parser.parse_args(['--timeout', '120', '--max-retries', '5'])
        self.assertEqual(args.timeout, 120)
        self.assertEqual(args.max_retries, 5)
    
    def test_dry_run_mode(self):
        """Test dry run mode functionality."""
        from src.main_application import create_argument_parser
        
        parser = create_argument_parser()
        args = parser.parse_args(['--dry-run'])
        self.assertTrue(args.dry_run)
    
    def test_version_argument(self):
        """Test version argument."""
        from src.main_application import create_argument_parser
        
        parser = create_argument_parser()
        
        # Version argument should cause SystemExit
        with self.assertRaises(SystemExit):
            parser.parse_args(['--version'])


if __name__ == '__main__':
    unittest.main()