"""
Unit tests for BinanceClient with mocked responses.
"""
import pytest
import time
import logging
from unittest.mock import Mock, patch, MagicMock
from binance.exceptions import BinanceAPIException, BinanceRequestException

from src.api.binance_client import BinanceClient
from src.models.data_models import BinanceCredentials, AssetBalance


def create_mock_binance_exception(code, message):
    """Helper function to create properly formatted BinanceAPIException."""
    mock_response = Mock()
    mock_response.text = f'{{"code": {code}, "msg": "{message}"}}'
    exception = BinanceAPIException(mock_response, code, mock_response.text)
    exception.code = code
    exception.message = message
    return exception


class TestBinanceClient:
    """Test suite for BinanceClient class."""
    
    @pytest.fixture
    def credentials(self):
        """Fixture providing test credentials."""
        return BinanceCredentials(
            api_key="test_api_key",
            api_secret="test_api_secret"
        )
    
    @pytest.fixture
    def mock_client(self, credentials, caplog):
        """Fixture providing BinanceClient with mocked Binance client."""
        with patch('src.api.binance_client.Client') as mock_binance_client:
            # Set up logging to capture log messages
            caplog.set_level(logging.INFO)
            client = BinanceClient(credentials)
            client.client = mock_binance_client.return_value
            return client
    
    def test_initialization_success(self, credentials):
        """Test successful client initialization."""
        with patch('src.api.binance_client.Client') as mock_binance_client:
            client = BinanceClient(credentials)
            
            mock_binance_client.assert_called_once_with(
                api_key="test_api_key",
                api_secret="test_api_secret",
                testnet=False
            )
            assert client.credentials == credentials
            assert client.client is not None
    
    def test_initialization_failure(self, credentials):
        """Test client initialization failure."""
        with patch('src.api.binance_client.Client', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                BinanceClient(credentials)
    
    def test_get_account_balances_success(self, mock_client):
        """Test successful account balance retrieval."""
        # Mock account info response
        mock_account_info = {
            'balances': [
                {'asset': 'BTC', 'free': '1.5', 'locked': '0.5'},
                {'asset': 'ETH', 'free': '10.0', 'locked': '0.0'},
                {'asset': 'USDT', 'free': '0.0', 'locked': '0.0'},  # Should be filtered out
                {'asset': 'BNB', 'free': '5.0', 'locked': '2.0'}
            ]
        }
        mock_client.client.get_account.return_value = mock_account_info
        
        balances = mock_client.get_account_balances()
        
        # Should return 3 balances (excluding USDT with zero balance)
        assert len(balances) == 3
        
        # Check BTC balance
        btc_balance = next(b for b in balances if b.asset == 'BTC')
        assert btc_balance.free == 1.5
        assert btc_balance.locked == 0.5
        assert btc_balance.total == 2.0
        
        # Check ETH balance
        eth_balance = next(b for b in balances if b.asset == 'ETH')
        assert eth_balance.free == 10.0
        assert eth_balance.locked == 0.0
        assert eth_balance.total == 10.0
        
        # Check BNB balance
        bnb_balance = next(b for b in balances if b.asset == 'BNB')
        assert bnb_balance.free == 5.0
        assert bnb_balance.locked == 2.0
        assert bnb_balance.total == 7.0
        
        # Verify USDT is not included (zero balance)
        usdt_balances = [b for b in balances if b.asset == 'USDT']
        assert len(usdt_balances) == 0
    
    def test_get_account_balances_api_error_with_retry(self, mock_client):
        """Test account balance retrieval with API error and successful retry."""
        # First call fails, second succeeds
        mock_client.client.get_account.side_effect = [
            create_mock_binance_exception(-1003, "Rate limit exceeded"),
            {
                'balances': [
                    {'asset': 'BTC', 'free': '1.0', 'locked': '0.0'}
                ]
            }
        ]
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            balances = mock_client.get_account_balances()
        
        assert len(balances) == 1
        assert balances[0].asset == 'BTC'
        assert mock_client.client.get_account.call_count == 2
    
    def test_get_account_balances_authentication_error_no_retry(self, mock_client):
        """Test that authentication errors are not retried."""
        mock_client.client.get_account.side_effect = create_mock_binance_exception(
            -2014, "API-key format invalid"
        )
        
        with pytest.raises(BinanceAPIException):
            mock_client.get_account_balances()
        
        # Should only be called once (no retry)
        assert mock_client.client.get_account.call_count == 1
    
    def test_get_account_balances_max_retries_exceeded(self, mock_client):
        """Test behavior when max retries are exceeded."""
        mock_client.client.get_account.side_effect = create_mock_binance_exception(
            -1003, "Rate limit exceeded"
        )
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(BinanceAPIException):
                mock_client.get_account_balances()
        
        # Should be called 4 times (initial + 3 retries)
        assert mock_client.client.get_account.call_count == 4
    
    def test_get_all_prices_success(self, mock_client):
        """Test successful price retrieval for all symbols."""
        mock_prices = [
            {'symbol': 'BTCUSDT', 'price': '45000.50'},
            {'symbol': 'ETHUSDT', 'price': '3000.25'},
            {'symbol': 'BNBUSDT', 'price': '400.75'}
        ]
        mock_client.client.get_all_tickers.return_value = mock_prices
        
        prices = mock_client.get_all_prices()
        
        assert len(prices) == 3
        assert prices['BTCUSDT'] == 45000.50
        assert prices['ETHUSDT'] == 3000.25
        assert prices['BNBUSDT'] == 400.75
    
    def test_get_all_prices_with_retry(self, mock_client):
        """Test price retrieval with retry on failure."""
        mock_client.client.get_all_tickers.side_effect = [
            BinanceRequestException("Network error"),
            [{'symbol': 'BTCUSDT', 'price': '45000.50'}]
        ]
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            prices = mock_client.get_all_prices()
        
        assert len(prices) == 1
        assert prices['BTCUSDT'] == 45000.50
        assert mock_client.client.get_all_tickers.call_count == 2
    
    def test_get_price_for_asset_success(self, mock_client):
        """Test successful single asset price retrieval."""
        mock_client.client.get_symbol_ticker.return_value = {
            'symbol': 'BTCUSDT',
            'price': '45000.50'
        }
        
        price = mock_client.get_price_for_asset('BTCUSDT')
        
        assert price == 45000.50
        mock_client.client.get_symbol_ticker.assert_called_once_with(symbol='BTCUSDT')
    
    def test_get_price_for_asset_invalid_symbol(self, mock_client):
        """Test price retrieval for invalid symbol."""
        mock_client.client.get_symbol_ticker.side_effect = create_mock_binance_exception(
            -1121, "Invalid symbol"
        )
        
        price = mock_client.get_price_for_asset('INVALIDUSDT')
        
        assert price is None
    
    def test_get_price_for_asset_other_api_error(self, mock_client):
        """Test price retrieval with non-symbol API error."""
        mock_client.client.get_symbol_ticker.side_effect = create_mock_binance_exception(
            -1003, "Rate limit exceeded"
        )
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(BinanceAPIException):
                mock_client.get_price_for_asset('BTCUSDT')
    
    def test_validate_connection_success(self, mock_client):
        """Test successful connection validation."""
        mock_client.client.get_server_time.return_value = {'serverTime': 1234567890}
        
        result = mock_client.validate_connection()
        
        assert result is True
        mock_client.client.get_server_time.assert_called_once()
    
    def test_validate_connection_failure(self, mock_client):
        """Test connection validation failure."""
        mock_client.client.get_server_time.side_effect = Exception("Connection failed")
        
        result = mock_client.validate_connection()
        
        assert result is False
    
    def test_get_exchange_info_success(self, mock_client):
        """Test successful exchange info retrieval."""
        mock_exchange_info = {
            'timezone': 'UTC',
            'serverTime': 1234567890,
            'symbols': []
        }
        mock_client.client.get_exchange_info.return_value = mock_exchange_info
        
        exchange_info = mock_client.get_exchange_info()
        
        assert exchange_info == mock_exchange_info
        mock_client.client.get_exchange_info.assert_called_once()
    
    def test_exponential_backoff_timing(self, mock_client):
        """Test that exponential backoff uses correct delays."""
        mock_client.client.get_account.side_effect = [
            create_mock_binance_exception(-1003, "Rate limit"),
            create_mock_binance_exception(-1003, "Rate limit"),
            create_mock_binance_exception(-1003, "Rate limit"),
            {'balances': []}
        ]
        
        with patch('time.sleep') as mock_sleep:
            mock_client.get_account_balances()
        
        # Should have 3 sleep calls with exponential backoff: 1s, 2s, 4s
        expected_delays = [1, 2, 4]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays
    
    def test_logging_on_success(self, mock_client, caplog):
        """Test that successful operations are logged."""
        mock_client.client.get_account.return_value = {
            'balances': [{'asset': 'BTC', 'free': '1.0', 'locked': '0.0'}]
        }
        
        mock_client.get_account_balances()
        
        assert "Retrieved 1 non-zero asset balances" in caplog.text
    
    def test_logging_on_retry(self, mock_client, caplog):
        """Test that retry attempts are logged."""
        mock_client.client.get_account.side_effect = [
            create_mock_binance_exception(-1003, "Rate limit"),
            {'balances': []}
        ]
        
        with patch('time.sleep'):
            mock_client.get_account_balances()
        
        assert "API call failed (attempt 1/4), retrying in 1s" in caplog.text
    
    def test_logging_on_failure(self, mock_client, caplog):
        """Test that failures are logged."""
        mock_client.client.get_account.side_effect = create_mock_binance_exception(
            -1003, "Rate limit"
        )
        
        with patch('time.sleep'):
            with pytest.raises(BinanceAPIException):
                mock_client.get_account_balances()
        
        assert "All retry attempts failed" in caplog.text