"""
Error scenario tests for the Binance Portfolio Logger.

These tests validate error handling for network failures, API errors,
and other failure conditions to ensure robust operation.
"""

import pytest
import os
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
import requests
from binance.exceptions import BinanceAPIException, BinanceRequestException
import gspread.exceptions

from src.main_application import MainApplication
from src.api.binance_client import BinanceClient
from src.api.google_sheets_logger import GoogleSheetsLogger
from src.config.configuration_manager import ConfigurationManager


class TestNetworkFailureScenarios:
    """Test network failure handling and recovery."""

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for testing."""
        with patch.dict(os.environ, {
            'BINANCE_API_KEY': 'test_api_key',
            'BINANCE_API_SECRET': 'test_api_secret',
            'GOOGLE_SERVICE_ACCOUNT_PATH': '/tmp/test_service_account.json',
            'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id',
            'LOG_FILE_PATH': '/tmp/test_portfolio.log'
        }):
            yield

    @pytest.fixture
    def mock_service_account_file(self):
        """Create a temporary service account JSON file."""
        service_account_data = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest-private-key\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "test-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(service_account_data, f)
            temp_path = f.name
        
        with patch.dict(os.environ, {'GOOGLE_SERVICE_ACCOUNT_PATH': temp_path}):
            yield temp_path
        
        os.unlink(temp_path)

    @patch('src.api.binance_client.Client')
    def test_binance_connection_timeout(self, mock_binance_client, mock_env_vars):
        """Test handling of Binance API connection timeouts."""
        # Setup client to raise connection timeout
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.side_effect = requests.exceptions.Timeout("Connection timeout")

        # Test client behavior
        client = BinanceClient('test_key', 'test_secret')
        balances = client.get_account_balances()

        # Should return empty list on timeout
        assert balances == []

    @patch('src.api.binance_client.Client')
    def test_binance_connection_error(self, mock_binance_client, mock_env_vars):
        """Test handling of Binance API connection errors."""
        # Setup client to raise connection error
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.side_effect = requests.exceptions.ConnectionError("Connection failed")

        # Test client behavior
        client = BinanceClient('test_key', 'test_secret')
        balances = client.get_account_balances()

        # Should return empty list on connection error
        assert balances == []

    @patch('src.api.binance_client.Client')
    def test_binance_rate_limit_handling(self, mock_binance_client, mock_env_vars):
        """Test handling of Binance API rate limits."""
        # Setup client to raise rate limit error then succeed
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        
        rate_limit_error = BinanceAPIException(None, 429, "Rate limit exceeded")
        success_response = {'balances': [{'asset': 'BTC', 'free': '1.0', 'locked': '0.0'}]}
        
        mock_client_instance.get_account.side_effect = [rate_limit_error, success_response]

        # Test client behavior
        client = BinanceClient('test_key', 'test_secret')
        balances = client.get_account_balances()

        # Should retry and succeed
        assert len(balances) == 1
        assert balances[0].asset == 'BTC'

    @patch('src.api.binance_client.Client')
    def test_binance_authentication_failure(self, mock_binance_client, mock_env_vars):
        """Test handling of Binance API authentication failures."""
        # Setup client to raise authentication error
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.side_effect = BinanceAPIException(None, 401, "Invalid API key")

        # Test client behavior
        client = BinanceClient('test_key', 'test_secret')
        balances = client.get_account_balances()

        # Should return empty list on auth failure (no retry for auth errors)
        assert balances == []

    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_google_sheets_authentication_failure(self, mock_gspread, mock_service_account_file):
        """Test handling of Google Sheets authentication failures."""
        # Setup to raise authentication error
        mock_gspread.side_effect = gspread.exceptions.APIError("Authentication failed")

        # Test logger behavior
        logger = GoogleSheetsLogger(mock_service_account_file, 'test_id')
        
        from src.models.data_models import PortfolioValue
        from datetime import datetime
        
        portfolio_value = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=1000.0,
            asset_breakdown={},
            conversion_failures=[]
        )
        
        result = logger.append_portfolio_data(portfolio_value)
        
        # Should fail gracefully
        assert result is False

    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_google_sheets_quota_exceeded(self, mock_gspread, mock_service_account_file):
        """Test handling of Google Sheets API quota exceeded."""
        # Setup mock to raise quota exceeded error then succeed
        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet
        
        quota_error = gspread.exceptions.APIError("Quota exceeded")
        mock_worksheet.append_row.side_effect = [quota_error, quota_error, True]  # Fail twice, then succeed

        # Test logger behavior
        logger = GoogleSheetsLogger(mock_service_account_file, 'test_id')
        
        from src.models.data_models import PortfolioValue
        from datetime import datetime
        
        portfolio_value = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=1000.0,
            asset_breakdown={},
            conversion_failures=[]
        )
        
        result = logger.append_portfolio_data(portfolio_value)
        
        # Should succeed after retries
        assert result is True
        assert mock_worksheet.append_row.call_count == 3

    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_google_sheets_spreadsheet_not_found(self, mock_gspread, mock_service_account_file):
        """Test handling when Google Sheets spreadsheet is not found."""
        # Setup mock to raise spreadsheet not found error
        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_gc.open_by_key.side_effect = gspread.exceptions.SpreadsheetNotFound("Spreadsheet not found")

        # Test logger behavior
        logger = GoogleSheetsLogger(mock_service_account_file, 'test_id')
        
        from src.models.data_models import PortfolioValue
        from datetime import datetime
        
        portfolio_value = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=1000.0,
            asset_breakdown={},
            conversion_failures=[]
        )
        
        result = logger.append_portfolio_data(portfolio_value)
        
        # Should fail gracefully
        assert result is False

    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_google_sheets_worksheet_not_found(self, mock_gspread, mock_service_account_file):
        """Test handling when Google Sheets worksheet is not found."""
        # Setup mock to raise worksheet not found error, then create it
        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        
        # First call fails, second succeeds after worksheet creation
        mock_worksheet = Mock()
        mock_sheet.worksheet.side_effect = [
            gspread.exceptions.WorksheetNotFound("Worksheet not found"),
            mock_worksheet
        ]
        mock_sheet.add_worksheet.return_value = mock_worksheet

        # Test logger behavior
        logger = GoogleSheetsLogger(mock_service_account_file, 'test_id')
        
        from src.models.data_models import PortfolioValue
        from datetime import datetime
        
        portfolio_value = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=1000.0,
            asset_breakdown={},
            conversion_failures=[]
        )
        
        result = logger.append_portfolio_data(portfolio_value)
        
        # Should succeed after creating worksheet
        assert result is True
        mock_sheet.add_worksheet.assert_called_once()

    def test_invalid_configuration_missing_api_key(self):
        """Test handling of missing Binance API key."""
        with patch.dict(os.environ, {}, clear=True):
            config_manager = ConfigurationManager()
            
            with pytest.raises(ValueError, match="BINANCE_API_KEY"):
                config_manager.load_binance_credentials()

    def test_invalid_configuration_missing_service_account(self):
        """Test handling of missing Google service account file."""
        with patch.dict(os.environ, {'GOOGLE_SERVICE_ACCOUNT_PATH': '/nonexistent/file.json'}):
            config_manager = ConfigurationManager()
            
            with pytest.raises(FileNotFoundError):
                config_manager.load_google_credentials()

    def test_invalid_service_account_json(self):
        """Test handling of invalid service account JSON file."""
        # Create invalid JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name
        
        try:
            with patch.dict(os.environ, {'GOOGLE_SERVICE_ACCOUNT_PATH': temp_path}):
                config_manager = ConfigurationManager()
                
                with pytest.raises(json.JSONDecodeError):
                    config_manager.load_google_credentials()
        finally:
            os.unlink(temp_path)

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_partial_system_failure_recovery(self, mock_gspread, mock_binance_client,
                                           mock_env_vars, mock_service_account_file):
        """Test system behavior when some components fail but others succeed."""
        # Setup Binance to succeed
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = {
            'balances': [{'asset': 'BTC', 'free': '1.0', 'locked': '0.0'}]
        }
        mock_client_instance.get_all_tickers.return_value = [
            {'symbol': 'BTCUSDT', 'price': '45000.00'}
        ]

        # Setup Google Sheets to fail
        mock_gspread.side_effect = Exception("Google Sheets unavailable")

        # Execute main application
        app = MainApplication()
        result = app.run()

        # Should fail overall but handle partial success gracefully
        assert result is False

        # Verify Binance was called successfully
        mock_client_instance.get_account.assert_called_once()

    @patch('src.api.binance_client.Client')
    def test_malformed_api_response_handling(self, mock_binance_client, mock_env_vars):
        """Test handling of malformed API responses from Binance."""
        # Setup client to return malformed data
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        
        # Missing required fields
        mock_client_instance.get_account.return_value = {
            'balances': [
                {'asset': 'BTC'},  # Missing 'free' and 'locked'
                {'free': '1.0', 'locked': '0.0'},  # Missing 'asset'
                {'asset': 'ETH', 'free': '2.0', 'locked': '0.5'}  # Valid
            ]
        }

        # Test client behavior
        client = BinanceClient('test_key', 'test_secret')
        balances = client.get_account_balances()

        # Should only return valid balance entries
        assert len(balances) == 1
        assert balances[0].asset == 'ETH'

    @patch('src.api.binance_client.Client')
    def test_price_data_inconsistency(self, mock_binance_client, mock_env_vars):
        """Test handling when price data is missing for some assets."""
        # Setup client with balances but missing price data
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        
        mock_client_instance.get_account.return_value = {
            'balances': [
                {'asset': 'BTC', 'free': '1.0', 'locked': '0.0'},
                {'asset': 'UNKNOWN', 'free': '100.0', 'locked': '0.0'}  # No price available
            ]
        }
        
        mock_client_instance.get_all_tickers.return_value = [
            {'symbol': 'BTCUSDT', 'price': '45000.00'}
            # No UNKNOWNUSDT price
        ]

        # Test portfolio calculation
        from src.api.portfolio_calculator import PortfolioCalculator
        
        calculator = PortfolioCalculator(mock_client_instance)
        balances = [
            type('AssetBalance', (), {
                'asset': 'BTC', 'free': 1.0, 'locked': 0.0, 'total': 1.0
            })(),
            type('AssetBalance', (), {
                'asset': 'UNKNOWN', 'free': 100.0, 'locked': 0.0, 'total': 100.0
            })()
        ]
        
        portfolio_value = calculator.calculate_portfolio_value(balances)

        # Should handle missing price data gracefully
        assert portfolio_value.total_usdt == 45000.0  # Only BTC counted
        assert 'UNKNOWN' in portfolio_value.conversion_failures

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_memory_pressure_handling(self, mock_gspread, mock_binance_client,
                                    mock_env_vars, mock_service_account_file):
        """Test system behavior under memory pressure."""
        # Create extremely large dataset to simulate memory pressure
        large_balances = []
        for i in range(10000):  # Very large number of assets
            large_balances.append({
                'asset': f'COIN{i:05d}',
                'free': str(float(i + 1)),
                'locked': '0.0'
            })

        # Setup mocks
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = {'balances': large_balances}
        mock_client_instance.get_all_tickers.return_value = []  # No prices to force failures

        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet

        # Execute application
        app = MainApplication()
        result = app.run()

        # Should complete without crashing, even if some data is lost
        assert result in [True, False]  # Either succeeds or fails gracefully

    def test_disk_space_exhaustion_handling(self, mock_env_vars):
        """Test handling when disk space is exhausted for logging."""
        # Mock disk space error
        with patch('builtins.open', side_effect=OSError("No space left on device")):
            from src.utils.error_handler import ErrorHandler
            
            error_handler = ErrorHandler()
            
            # Should handle disk space error gracefully
            try:
                error_handler.log_execution_start()
                # Should not raise exception
                assert True
            except OSError:
                pytest.fail("ErrorHandler should handle disk space errors gracefully")

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_cascading_failure_recovery(self, mock_gspread, mock_binance_client,
                                      mock_env_vars, mock_service_account_file):
        """Test recovery from cascading failures across multiple components."""
        # Setup multiple failure points
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        
        # Binance fails multiple times then succeeds
        mock_client_instance.get_account.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            {'balances': [{'asset': 'BTC', 'free': '1.0', 'locked': '0.0'}]}
        ]
        mock_client_instance.get_all_tickers.return_value = [
            {'symbol': 'BTCUSDT', 'price': '45000.00'}
        ]

        # Google Sheets also fails then succeeds
        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet
        mock_worksheet.append_row.side_effect = [
            Exception("Sheets error"),
            True
        ]

        # Execute application
        app = MainApplication()
        result = app.run()

        # Should eventually succeed after retries
        assert result is True

        # Verify retry attempts were made
        assert mock_client_instance.get_account.call_count == 3
        assert mock_worksheet.append_row.call_count == 2