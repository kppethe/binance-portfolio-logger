"""
Performance tests for the Binance Portfolio Logger.

These tests validate that the application meets performance requirements,
particularly the 30-second execution constraint.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
import os
import tempfile
import json

from src.main_application import MainApplication
from src.api.binance_client import BinanceClient
from src.api.portfolio_calculator import PortfolioCalculator
from src.api.google_sheets_logger import GoogleSheetsLogger


class TestPerformanceRequirements:
    """Performance tests to validate execution time constraints."""

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

    def create_large_portfolio_data(self, num_assets=50):
        """Create mock data for a large portfolio."""
        balances = []
        prices = []
        
        for i in range(num_assets):
            asset = f'ASSET{i:03d}'
            balances.append({
                'asset': asset,
                'free': str(float(i + 1) * 0.1),
                'locked': str(float(i) * 0.05)
            })
            prices.append({
                'symbol': f'{asset}USDT',
                'price': str(float(i + 1) * 100)
            })
        
        return {
            'balances': balances,
            'prices': prices
        }

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_typical_portfolio_execution_time(self, mock_gspread, mock_binance_client,
                                            mock_env_vars, mock_service_account_file):
        """Test execution time with typical portfolio size (10-20 assets)."""
        # Create typical portfolio data
        portfolio_data = self.create_large_portfolio_data(15)
        
        # Setup mocks
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = {'balances': portfolio_data['balances']}
        mock_client_instance.get_all_tickers.return_value = portfolio_data['prices']

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

        # Verify performance requirements
        assert result is True
        assert execution_time < 30.0, f"Typical portfolio execution took {execution_time:.2f}s, exceeding 30s limit"
        assert execution_time < 10.0, f"Typical portfolio should complete in under 10s, took {execution_time:.2f}s"

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_large_portfolio_execution_time(self, mock_gspread, mock_binance_client,
                                          mock_env_vars, mock_service_account_file):
        """Test execution time with large portfolio (50+ assets)."""
        # Create large portfolio data
        portfolio_data = self.create_large_portfolio_data(75)
        
        # Setup mocks
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = {'balances': portfolio_data['balances']}
        mock_client_instance.get_all_tickers.return_value = portfolio_data['prices']

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

        # Verify performance requirements
        assert result is True
        assert execution_time < 30.0, f"Large portfolio execution took {execution_time:.2f}s, exceeding 30s limit"

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_execution_timeout_handling(self, mock_gspread, mock_binance_client,
                                      mock_env_vars, mock_service_account_file):
        """Test that execution respects timeout constraints."""
        # Setup mocks with artificial delays
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        
        def slow_get_account():
            time.sleep(35)  # Simulate slow API response
            return {'balances': []}
        
        mock_client_instance.get_account.side_effect = slow_get_account
        mock_client_instance.get_all_tickers.return_value = []

        # Execute with timeout
        start_time = time.time()
        app = MainApplication()
        
        # Use threading to enforce timeout
        result = [None]
        def run_with_timeout():
            result[0] = app.run()
        
        thread = threading.Thread(target=run_with_timeout)
        thread.daemon = True
        thread.start()
        thread.join(timeout=60)  # 60 second max wait
        
        execution_time = time.time() - start_time
        
        # Should timeout and fail gracefully
        assert execution_time < 65, "Execution should timeout within reasonable time"
        if thread.is_alive():
            # Thread is still running, which means timeout wasn't handled properly
            pytest.fail("Application did not respect timeout constraints")

    @patch('src.api.binance_client.Client')
    def test_binance_client_performance(self, mock_binance_client, mock_env_vars):
        """Test Binance client performance with large datasets."""
        # Create large dataset
        large_balances = []
        for i in range(100):
            large_balances.append({
                'asset': f'COIN{i:03d}',
                'free': str(float(i + 1)),
                'locked': '0.0'
            })

        large_prices = []
        for i in range(1000):  # Simulate many trading pairs
            large_prices.append({
                'symbol': f'PAIR{i:04d}',
                'price': str(float(i + 1) * 10)
            })

        # Setup mock
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = {'balances': large_balances}
        mock_client_instance.get_all_tickers.return_value = large_prices

        # Test client performance
        start_time = time.time()
        client = BinanceClient('test_key', 'test_secret')
        balances = client.get_account_balances()
        prices = client.get_all_prices()
        execution_time = time.time() - start_time

        # Verify performance
        assert len(balances) > 0
        assert len(prices) > 0
        assert execution_time < 5.0, f"Binance client operations took {execution_time:.2f}s, should be under 5s"

    def test_portfolio_calculator_performance(self):
        """Test portfolio calculator performance with large datasets."""
        from src.models.data_models import AssetBalance
        
        # Create large balance list
        balances = []
        for i in range(100):
            balances.append(AssetBalance(
                asset=f'COIN{i:03d}',
                free=float(i + 1),
                locked=float(i * 0.1),
                total=float(i + 1) + float(i * 0.1)
            ))

        # Mock price data
        price_data = {}
        for i in range(100):
            price_data[f'COIN{i:03d}USDT'] = float(i + 1) * 100

        # Mock Binance client
        mock_client = Mock()
        mock_client.get_all_prices.return_value = price_data

        # Test calculator performance
        start_time = time.time()
        calculator = PortfolioCalculator(mock_client)
        portfolio_value = calculator.calculate_portfolio_value(balances)
        execution_time = time.time() - start_time

        # Verify performance and results
        assert portfolio_value.total_usdt > 0
        assert execution_time < 2.0, f"Portfolio calculation took {execution_time:.2f}s, should be under 2s"

    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_google_sheets_logger_performance(self, mock_gspread, mock_service_account_file):
        """Test Google Sheets logger performance."""
        from src.models.data_models import PortfolioValue
        from datetime import datetime

        # Setup mock
        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet

        # Create test data
        portfolio_value = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=50000.0,
            asset_breakdown={'BTC': 45000.0, 'ETH': 5000.0},
            conversion_failures=[]
        )

        # Test logger performance
        start_time = time.time()
        logger = GoogleSheetsLogger(
            credentials_path=mock_service_account_file,
            spreadsheet_id='test_id'
        )
        result = logger.append_portfolio_data(portfolio_value)
        execution_time = time.time() - start_time

        # Verify performance
        assert result is True
        assert execution_time < 3.0, f"Google Sheets logging took {execution_time:.2f}s, should be under 3s"

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_memory_usage_efficiency(self, mock_gspread, mock_binance_client,
                                   mock_env_vars, mock_service_account_file):
        """Test that memory usage remains reasonable with large datasets."""
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create very large portfolio data
        portfolio_data = self.create_large_portfolio_data(200)
        
        # Setup mocks
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        mock_client_instance.get_account.return_value = {'balances': portfolio_data['balances']}
        mock_client_instance.get_all_tickers.return_value = portfolio_data['prices']

        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet

        # Execute application
        app = MainApplication()
        result = app.run()

        # Check memory usage after execution
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Verify reasonable memory usage
        assert result is True
        assert memory_increase < 100, f"Memory usage increased by {memory_increase:.1f}MB, should be under 100MB"

    def test_concurrent_execution_safety(self):
        """Test that the application handles concurrent execution attempts safely."""
        # This test would be relevant for production environments where
        # multiple cron jobs might accidentally overlap
        
        # For now, we'll test that the application can detect and handle
        # this scenario gracefully (implementation would depend on lock files)
        
        # This is a placeholder for future implementation
        assert True, "Concurrent execution safety test placeholder"

    @patch('src.api.binance_client.Client')
    @patch('src.api.google_sheets_logger.gspread.service_account')
    def test_network_latency_resilience(self, mock_gspread, mock_binance_client,
                                      mock_env_vars, mock_service_account_file):
        """Test performance with simulated network latency."""
        # Setup mocks with artificial delays to simulate network latency
        mock_client_instance = Mock()
        mock_binance_client.return_value = mock_client_instance
        
        def delayed_get_account():
            time.sleep(2)  # Simulate 2-second network delay
            return {'balances': [{'asset': 'BTC', 'free': '1.0', 'locked': '0.0'}]}
        
        def delayed_get_tickers():
            time.sleep(1)  # Simulate 1-second network delay
            return [{'symbol': 'BTCUSDT', 'price': '45000.00'}]
        
        mock_client_instance.get_account.side_effect = delayed_get_account
        mock_client_instance.get_all_tickers.side_effect = delayed_get_tickers

        # Setup Google Sheets with delay
        mock_gc = Mock()
        mock_gspread.return_value = mock_gc
        mock_sheet = Mock()
        mock_worksheet = Mock()
        mock_gc.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.return_value = mock_worksheet
        
        def delayed_append_row(data):
            time.sleep(1)  # Simulate 1-second Google Sheets delay
            return True
        
        mock_worksheet.append_row.side_effect = delayed_append_row

        # Execute with network delays
        start_time = time.time()
        app = MainApplication()
        result = app.run()
        execution_time = time.time() - start_time

        # Should still complete within reasonable time despite network delays
        assert result is True
        assert execution_time < 30.0, f"Execution with network delays took {execution_time:.2f}s"
        assert execution_time > 3.0, "Should reflect the simulated network delays"