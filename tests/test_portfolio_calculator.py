"""
Unit tests for PortfolioCalculator class.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from src.api.portfolio_calculator import PortfolioCalculator
from src.api.binance_client import BinanceClient
from src.models.data_models import AssetBalance, PortfolioValue, BinanceCredentials


class TestPortfolioCalculator:
    """Test cases for PortfolioCalculator class."""
    
    @pytest.fixture
    def mock_binance_client(self):
        """Create a mock BinanceClient for testing."""
        mock_client = Mock(spec=BinanceClient)
        return mock_client
    
    @pytest.fixture
    def portfolio_calculator(self, mock_binance_client):
        """Create PortfolioCalculator instance with mock client."""
        return PortfolioCalculator(mock_binance_client)
    
    @pytest.fixture
    def sample_balances(self):
        """Sample asset balances for testing."""
        return [
            AssetBalance(asset='BTC', free=1.0, locked=0.0, total=1.0),
            AssetBalance(asset='ETH', free=10.0, locked=0.0, total=10.0),
            AssetBalance(asset='USDT', free=1000.0, locked=0.0, total=1000.0),
            AssetBalance(asset='ADA', free=500.0, locked=0.0, total=500.0),
            AssetBalance(asset='DOT', free=100.0, locked=0.0, total=100.0),
        ]
    
    def test_init(self, mock_binance_client):
        """Test PortfolioCalculator initialization."""
        calculator = PortfolioCalculator(mock_binance_client)
        
        assert calculator.binance_client == mock_binance_client
        assert calculator._price_cache == {}
    
    def test_calculate_portfolio_value_success(self, portfolio_calculator, mock_binance_client, sample_balances):
        """Test successful portfolio value calculation."""
        # Mock price data
        mock_prices = {
            'BTCUSDT': 45000.0,
            'ETHUSDT': 3000.0,
            'ADAUSDT': 0.5,
            'DOTUSDT': 25.0,
        }
        mock_binance_client.get_all_prices.return_value = mock_prices
        
        result = portfolio_calculator.calculate_portfolio_value(sample_balances)
        
        # Verify result structure
        assert isinstance(result, PortfolioValue)
        assert isinstance(result.timestamp, datetime)
        assert result.total_usdt == 78750.0  # 45000 + 30000 + 1000 + 250 + 2500
        assert len(result.asset_breakdown) == 5
        assert result.conversion_failures == []
        
        # Verify individual asset calculations
        assert result.asset_breakdown['BTC'] == 45000.0
        assert result.asset_breakdown['ETH'] == 30000.0
        assert result.asset_breakdown['USDT'] == 1000.0
        assert result.asset_breakdown['ADA'] == 250.0
        assert result.asset_breakdown['DOT'] == 2500.0
    
    def test_calculate_portfolio_value_with_failures(self, portfolio_calculator, mock_binance_client, sample_balances):
        """Test portfolio calculation with some conversion failures."""
        # Mock partial price data (missing DOT)
        mock_prices = {
            'BTCUSDT': 45000.0,
            'ETHUSDT': 3000.0,
            'ADAUSDT': 0.5,
        }
        mock_binance_client.get_all_prices.return_value = mock_prices
        mock_binance_client.get_price_for_asset.return_value = None  # DOT lookup fails
        
        result = portfolio_calculator.calculate_portfolio_value(sample_balances)
        
        assert result.total_usdt == 76250.0  # Without DOT value
        assert 'DOT' in result.conversion_failures
        assert result.asset_breakdown['DOT'] == 0.0
    
    def test_calculate_portfolio_value_api_error_fallback(self, portfolio_calculator, mock_binance_client, sample_balances):
        """Test fallback to individual price fetching when batch fails."""
        # Mock get_all_prices to fail
        mock_binance_client.get_all_prices.side_effect = Exception("API Error")
        
        # Mock individual price fetches
        def mock_get_price(symbol):
            prices = {
                'BTCUSDT': 45000.0,
                'ETHUSDT': 3000.0,
                'ADAUSDT': 0.5,
                'DOTUSDT': 25.0,
            }
            return prices.get(symbol)
        
        mock_binance_client.get_price_for_asset.side_effect = mock_get_price
        
        result = portfolio_calculator.calculate_portfolio_value(sample_balances)
        
        assert result.total_usdt == 78750.0
        assert result.conversion_failures == []
    
    def test_convert_asset_to_usdt_direct_conversion(self, portfolio_calculator, mock_binance_client):
        """Test direct USDT pair conversion (primary method)."""
        mock_binance_client.get_all_prices.return_value = {'BTCUSDT': 45000.0}
        portfolio_calculator._price_cache = {'BTCUSDT': 45000.0}
        
        result = portfolio_calculator.convert_asset_to_usdt('BTC', 1.0)
        
        assert result == 45000.0
    
    def test_convert_asset_to_usdt_btc_pair_conversion(self, portfolio_calculator, mock_binance_client):
        """Test BTC pair conversion (secondary method)."""
        # Setup: ADA has no direct USDT pair, but has BTC pair
        portfolio_calculator._price_cache = {
            'ADABTC': 0.00001,  # ADA price in BTC
            'BTCUSDT': 45000.0,  # BTC price in USDT
        }
        # Mock that ADAUSDT doesn't exist
        mock_binance_client.get_price_for_asset.return_value = None
        
        result = portfolio_calculator.convert_asset_to_usdt('ADA', 1000.0)
        
        # 1000 ADA * 0.00001 BTC/ADA * 45000 USDT/BTC = 450 USDT
        assert result == 450.0
    
    def test_convert_asset_to_usdt_eth_pair_conversion(self, portfolio_calculator, mock_binance_client):
        """Test ETH pair conversion (tertiary method)."""
        # Setup: LINK has no USDT or BTC pair, but has ETH pair
        portfolio_calculator._price_cache = {
            'LINKETH': 0.01,     # LINK price in ETH
            'ETHUSDT': 3000.0,   # ETH price in USDT
        }
        # Mock that LINKUSDT and LINKBTC don't exist
        mock_binance_client.get_price_for_asset.return_value = None
        
        result = portfolio_calculator.convert_asset_to_usdt('LINK', 100.0)
        
        # 100 LINK * 0.01 ETH/LINK * 3000 USDT/ETH = 3000 USDT
        assert result == 3000.0
    
    def test_convert_asset_to_usdt_no_conversion_path(self, portfolio_calculator, mock_binance_client):
        """Test asset with no conversion path returns zero."""
        portfolio_calculator._price_cache = {}  # No prices available
        mock_binance_client.get_price_for_asset.return_value = None
        
        result = portfolio_calculator.convert_asset_to_usdt('UNKNOWN', 100.0)
        
        assert result == 0.0
    
    def test_convert_asset_to_usdt_usdt_direct(self, portfolio_calculator, mock_binance_client):
        """Test USDT conversion returns the same amount."""
        result = portfolio_calculator.convert_asset_to_usdt('USDT', 1000.0)
        
        assert result == 1000.0
    
    def test_try_direct_usdt_conversion_success(self, portfolio_calculator, mock_binance_client):
        """Test successful direct USDT conversion."""
        portfolio_calculator._price_cache = {'BTCUSDT': 45000.0}
        
        result = portfolio_calculator._try_direct_usdt_conversion('BTC', 1.0)
        
        assert result == 45000.0
    
    def test_try_direct_usdt_conversion_no_pair(self, portfolio_calculator, mock_binance_client):
        """Test direct USDT conversion when pair doesn't exist."""
        portfolio_calculator._price_cache = {}
        mock_binance_client.get_price_for_asset.return_value = None
        
        result = portfolio_calculator._try_direct_usdt_conversion('UNKNOWN', 1.0)
        
        assert result is None
    
    def test_try_btc_pair_conversion_success(self, portfolio_calculator, mock_binance_client):
        """Test successful BTC pair conversion."""
        portfolio_calculator._price_cache = {
            'ADABTC': 0.00001,
            'BTCUSDT': 45000.0,
        }
        
        result = portfolio_calculator._try_btc_pair_conversion('ADA', 1000.0)
        
        assert result == 450.0
    
    def test_try_btc_pair_conversion_no_asset_btc_pair(self, portfolio_calculator, mock_binance_client):
        """Test BTC pair conversion when asset/BTC pair doesn't exist."""
        portfolio_calculator._price_cache = {'BTCUSDT': 45000.0}
        mock_binance_client.get_price_for_asset.return_value = None
        
        result = portfolio_calculator._try_btc_pair_conversion('UNKNOWN', 1.0)
        
        assert result is None
    
    def test_try_btc_pair_conversion_no_btc_usdt(self, portfolio_calculator, mock_binance_client):
        """Test BTC pair conversion when BTC/USDT price unavailable."""
        portfolio_calculator._price_cache = {'ADABTC': 0.00001}
        mock_binance_client.get_price_for_asset.return_value = None
        
        result = portfolio_calculator._try_btc_pair_conversion('ADA', 1000.0)
        
        assert result is None
    
    def test_try_eth_pair_conversion_success(self, portfolio_calculator, mock_binance_client):
        """Test successful ETH pair conversion."""
        portfolio_calculator._price_cache = {
            'LINKETH': 0.01,
            'ETHUSDT': 3000.0,
        }
        
        result = portfolio_calculator._try_eth_pair_conversion('LINK', 100.0)
        
        assert result == 3000.0
    
    def test_try_eth_pair_conversion_no_asset_eth_pair(self, portfolio_calculator, mock_binance_client):
        """Test ETH pair conversion when asset/ETH pair doesn't exist."""
        portfolio_calculator._price_cache = {'ETHUSDT': 3000.0}
        mock_binance_client.get_price_for_asset.return_value = None
        
        result = portfolio_calculator._try_eth_pair_conversion('UNKNOWN', 1.0)
        
        assert result is None
    
    def test_try_eth_pair_conversion_no_eth_usdt(self, portfolio_calculator, mock_binance_client):
        """Test ETH pair conversion when ETH/USDT price unavailable."""
        portfolio_calculator._price_cache = {'LINKETH': 0.01}
        mock_binance_client.get_price_for_asset.return_value = None
        
        result = portfolio_calculator._try_eth_pair_conversion('LINK', 100.0)
        
        assert result is None
    
    def test_get_cached_price_from_cache(self, portfolio_calculator, mock_binance_client):
        """Test getting price from cache."""
        portfolio_calculator._price_cache = {'BTCUSDT': 45000.0}
        
        result = portfolio_calculator._get_cached_price('BTCUSDT')
        
        assert result == 45000.0
    
    def test_get_cached_price_fetch_individual(self, portfolio_calculator, mock_binance_client):
        """Test fetching individual price when not in cache."""
        portfolio_calculator._price_cache = {}
        mock_binance_client.get_price_for_asset.return_value = 45000.0
        
        result = portfolio_calculator._get_cached_price('BTCUSDT')
        
        assert result == 45000.0
        assert portfolio_calculator._price_cache['BTCUSDT'] == 45000.0
    
    def test_get_cached_price_not_found(self, portfolio_calculator, mock_binance_client):
        """Test getting price when not available."""
        portfolio_calculator._price_cache = {}
        mock_binance_client.get_price_for_asset.return_value = None
        
        result = portfolio_calculator._get_cached_price('UNKNOWN')
        
        assert result is None
    
    def test_get_cached_price_api_error(self, portfolio_calculator, mock_binance_client):
        """Test handling API error when fetching individual price."""
        portfolio_calculator._price_cache = {}
        mock_binance_client.get_price_for_asset.side_effect = Exception("API Error")
        
        result = portfolio_calculator._get_cached_price('BTCUSDT')
        
        assert result is None
    
    def test_get_conversion_summary(self, portfolio_calculator, mock_binance_client):
        """Test conversion summary generation."""
        portfolio_value = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=10000.0,
            asset_breakdown={'BTC': 5000.0, 'ETH': 3000.0, 'USDT': 2000.0},
            conversion_failures=['UNKNOWN1', 'UNKNOWN2']
        )
        
        summary = portfolio_calculator.get_conversion_summary(portfolio_value)
        
        assert summary['failed'] == 2
        assert summary['direct_usdt'] == 2  # BTC and ETH (simplified logic)
        assert 'btc_pair' in summary
        assert 'eth_pair' in summary
    
    def test_multi_tier_conversion_priority(self, portfolio_calculator, mock_binance_client):
        """Test that conversion methods are tried in correct priority order."""
        # Setup prices for all tiers
        portfolio_calculator._price_cache = {
            'TESTUSDT': 10.0,    # Direct USDT (should be used)
            'TESTBTC': 0.001,    # BTC pair (should be ignored)
            'TESTETH': 0.01,     # ETH pair (should be ignored)
            'BTCUSDT': 45000.0,
            'ETHUSDT': 3000.0,
        }
        
        result = portfolio_calculator.convert_asset_to_usdt('TEST', 100.0)
        
        # Should use direct USDT conversion (100 * 10.0 = 1000.0)
        # Not BTC pair (100 * 0.001 * 45000 = 4500.0)
        # Not ETH pair (100 * 0.01 * 3000 = 3000.0)
        assert result == 1000.0
    
    def test_conversion_fallback_chain(self, portfolio_calculator, mock_binance_client):
        """Test fallback from direct -> BTC -> ETH conversion."""
        # Setup: No direct USDT, no BTC pair, but ETH pair exists
        portfolio_calculator._price_cache = {
            'TESTETH': 0.01,
            'ETHUSDT': 3000.0,
        }
        mock_binance_client.get_price_for_asset.return_value = None  # No direct or BTC pairs
        
        result = portfolio_calculator.convert_asset_to_usdt('TEST', 100.0)
        
        # Should use ETH pair conversion: 100 * 0.01 * 3000 = 3000.0
        assert result == 3000.0
    
    def test_zero_balance_handling(self, portfolio_calculator, mock_binance_client):
        """Test handling of zero balance assets."""
        zero_balance = AssetBalance(asset='BTC', free=0.0, locked=0.0, total=0.0)
        mock_binance_client.get_all_prices.return_value = {'BTCUSDT': 45000.0}
        
        result = portfolio_calculator.calculate_portfolio_value([zero_balance])
        
        assert result.total_usdt == 0.0
        assert result.asset_breakdown['BTC'] == 0.0
        assert result.conversion_failures == []
    
    def test_large_portfolio_calculation(self, portfolio_calculator, mock_binance_client):
        """Test calculation with many assets."""
        # Create 50 different assets
        balances = []
        prices = {}
        
        for i in range(50):
            asset = f'TEST{i}'
            balances.append(AssetBalance(asset=asset, free=10.0, locked=0.0, total=10.0))
            prices[f'{asset}USDT'] = float(i + 1)  # Prices from 1.0 to 50.0
        
        mock_binance_client.get_all_prices.return_value = prices
        
        result = portfolio_calculator.calculate_portfolio_value(balances)
        
        # Expected total: sum of (10 * i) for i from 1 to 50 = 10 * (50 * 51 / 2) = 12750
        assert result.total_usdt == 12750.0
        assert len(result.asset_breakdown) == 50
        assert result.conversion_failures == []


if __name__ == '__main__':
    pytest.main([__file__])