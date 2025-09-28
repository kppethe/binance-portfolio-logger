"""
End-to-end integration tests for the Binance Portfolio Logger.

These tests validate the complete workflow using mock data and test credentials
to ensure all components work together correctly.
"""

import pytest
import os
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import time

from src.main_application import MainApplication
from src.config.configuration_manager import ConfigurationManager
from src.models.data_models import AssetBalance, PortfolioValue


class TestEndToEndIntegration:
    """End-to-end integration tests for complete workflow."""

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
        
        # Update environment variable to point to temp file
        with patch.dict(os.environ, {'GOOGLE_SERVICE_ACCOUNT_PATH': temp_path}):
            yield temp_path
        
        # Cleanup
        os.unlink(temp_path)

    @pytest.fixture
    def mock_binance_responses(self):
        """Mock Binance API responses."""
        account_info = {
            'balances': [
                {'asset': 'BTC', 'free': '1.5', 'locked': '0.0'},
                {'asset': 'ETH', 'free': '10.0', 'locked': '2.0'},
                {'asset': 'USDT', 'free': '1000.0', 'locked': '0.0'},
                {'asset': 'BNB', 'free': '0.0', 'locked': '0.0'}  # Should be filtered out
            ]
        }
        
        ticker_prices = [
            {'symbol': 'BTCUSDT', 'price': '45000.00'},
            {'symbol': 'ETHUSDT', 'price': '3000.00'},
            {'symbol': 'BNBUSDT', 'price': '400.00'}
        ]
        
        return {
            'account_info': account_info,
            'ticker_prices': ticker_prices
        }

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_complete_workflow_success(self, mock_gspread, mock_binance_client, 
                                     mock_env_vars, mock_service_account_file, 
                                     mock_binance_responses):
        """Test complete successful workflow execution."""
        # Setup Binance client mock
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = mock_binance_responses['account_info']
        mock_client_instance.get_all_tickers.return_value = mock_binance_responses['ticker_prices']

        # Setup Google Sheets mock
        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet

        # Execute main application
        app = MainApplication()
        result = app.run()

        # Verify success
        assert result is True

        # Verify Binance API calls
        mock_client_instance.get_account.assert_called_once()
        mock_client_instance.get_all_tickers.assert_called_once()

        # Verify Google Sheets calls
        mock_gc.open_by_key.assert_called_once()
        mock_worksheet.append_row.assert_called_once()

        # Verify logged data format
        logged_data = mock_worksheet.append_row.call_args[0][0]
        assert len(logged_data) >= 2  # At least timestamp and total value
        assert isinstance(logged_data[0], str)  # Timestamp
        assert isinstance(logged_data[1], (int, float))  # Total USDT value

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_workflow_with_binance_api_failure(self, mock_gspread, mock_binance_client,
                                             mock_env_vars, mock_service_account_file):
        """Test workflow behavior when Binance API fails."""
        # Setup Binance client to fail
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.side_effect = Exception("API Error")

        # Execute main application
        app = MainApplication()
        result = app.run()

        # Verify failure handling
        assert result is False

        # Verify no Google Sheets calls were made
        mock_gspread.assert_not_called()

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_workflow_with_google_sheets_failure(self, mock_gspread, mock_binance_client,
                                                mock_env_vars, mock_service_account_file,
                                                mock_binance_responses):
        """Test workflow behavior when Google Sheets API fails."""
        # Setup Binance client mock
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = mock_binance_responses['account_info']
        mock_client_instance.get_all_tickers.return_value = mock_binance_responses['ticker_prices']

        # Setup Google Sheets to fail
        mock_gspread.side_effect = Exception("Google Sheets API Error")

        # Execute main application
        app = MainApplication()
        result = app.run()

        # Verify failure handling
        assert result is False

        # Verify Binance API was still called
        mock_client_instance.get_account.assert_called_once()

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_workflow_with_partial_data(self, mock_gspread, mock_binance_client,
                                      mock_env_vars, mock_service_account_file):
        """Test workflow with assets that cannot be converted to USDT."""
        # Setup Binance client with unknown asset
        account_info = {
            'balances': [
                {'asset': 'BTC', 'free': '1.0', 'locked': '0.0'},
                {'asset': 'UNKNOWN', 'free': '100.0', 'locked': '0.0'}  # No price data
            ]
        }
        
        ticker_prices = [
            {'symbol': 'BTCUSDT', 'price': '45000.00'}
            # No UNKNOWNUSDT price
        ]

        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = account_info
        mock_client_instance.get_all_tickers.return_value = ticker_prices

        # Setup Google Sheets mock
        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet

        # Execute main application
        app = MainApplication()
        result = app.run()

        # Should still succeed with partial data
        assert result is True

        # Verify data was still logged
        mock_worksheet.append_row.assert_called_once()

    def test_configuration_validation_failure(self, mock_env_vars):
        """Test workflow fails gracefully with invalid configuration."""
        # Remove required environment variable
        with patch.dict(os.environ, {'BINANCE_API_KEY': ''}, clear=False):
            app = MainApplication()
            result = app.run()
            assert result is False

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_workflow_performance_within_constraints(self, mock_gspread, mock_binance_client,
                                                   mock_env_vars, mock_service_account_file,
                                                   mock_binance_responses):
        """Test that workflow completes within 30-second constraint."""
        # Setup mocks
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = mock_binance_responses['account_info']
        mock_client_instance.get_all_tickers.return_value = mock_binance_responses['ticker_prices']

        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet

        # Measure execution time
        start_time = time.time()
        app = MainApplication()
        result = app.run()
        execution_time = time.time() - start_time

        # Verify success and performance
        assert result is True
        assert execution_time < 30.0, f"Execution took {execution_time:.2f} seconds, exceeding 30s limit"

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_workflow_with_large_portfolio(self, mock_gspread, mock_binance_client,
                                         mock_env_vars, mock_service_account_file):
        """Test workflow performance with a large number of assets."""
        # Create large portfolio data
        large_balances = []
        large_prices = []
        
        for i in range(100):  # 100 different assets
            asset = f'COIN{i:03d}'
            large_balances.append({
                'asset': asset,
                'free': str(float(i + 1)),
                'locked': '0.0'
            })
            large_prices.append({
                'symbol': f'{asset}USDT',
                'price': str(float(i + 1) * 10)
            })

        account_info = {'balances': large_balances}

        # Setup mocks
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = account_info
        mock_client_instance.get_all_tickers.return_value = large_prices

        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet

        # Measure execution time
        start_time = time.time()
        app = MainApplication()
        result = app.run()
        execution_time = time.time() - start_time

        # Verify success and reasonable performance
        assert result is True
        assert execution_time < 30.0, f"Large portfolio execution took {execution_time:.2f} seconds"

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_retry_logic_integration(self, mock_gspread, mock_binance_client,
                                   mock_env_vars, mock_service_account_file,
                                   mock_binance_responses):
        """Test that retry logic works in integration scenario."""
        # Setup Binance client to fail twice then succeed
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.side_effect = [
            Exception("Temporary failure"),
            Exception("Another temporary failure"),
            mock_binance_responses['account_info']  # Success on third try
        ]
        mock_client_instance.get_all_tickers.return_value = mock_binance_responses['ticker_prices']

        # Setup Google Sheets mock
        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet

        # Execute main application
        app = MainApplication()
        result = app.run()

        # Should succeed after retries
        assert result is True

        # Verify retry attempts were made
        assert mock_client_instance.get_account.call_count == 3