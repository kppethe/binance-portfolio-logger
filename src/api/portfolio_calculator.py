"""
Portfolio calculation engine with multi-tier conversion strategy.
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from src.models.data_models import AssetBalance, PortfolioValue
from src.api.binance_client import BinanceClient


class PortfolioCalculator:
    """
    Portfolio calculator with multi-tier conversion strategy for USDT valuation.
    
    Implements a hierarchical approach to convert assets to USDT:
    1. Direct USDT pairs (primary)
    2. BTC pairs via BTC/USDT (secondary) 
    3. ETH pairs via ETH/USDT (tertiary)
    4. Assets without conversion paths are logged and assigned zero value
    """
    
    def __init__(self, binance_client: BinanceClient):
        """
        Initialize portfolio calculator with Binance client.
        
        Args:
            binance_client: Initialized BinanceClient instance
        """
        self.binance_client = binance_client
        self.logger = logging.getLogger(__name__)
        self._price_cache: Dict[str, float] = {}
        
    def calculate_portfolio_value(self, balances: List[AssetBalance]) -> PortfolioValue:
        """
        Calculate total portfolio value in USDT using multi-tier conversion strategy.
        
        Args:
            balances: List of AssetBalance objects
            
        Returns:
            PortfolioValue object with total USDT value and breakdown
        """
        self.logger.info(f"Starting portfolio calculation for {len(balances)} assets")
        
        # Clear price cache for fresh calculation
        self._price_cache.clear()
        
        # Fetch all prices once for efficiency
        try:
            all_prices = self.binance_client.get_all_prices()
            self._price_cache.update(all_prices)
            self.logger.info(f"Cached {len(all_prices)} price pairs")
        except Exception as e:
            self.logger.error(f"Failed to fetch all prices, will fetch individually: {e}")
        
        asset_breakdown = {}
        conversion_failures = []
        total_usdt = 0.0
        
        for balance in balances:
            asset = balance.asset
            amount = balance.total
            
            # Skip USDT as it's already in target currency
            if asset == 'USDT':
                usdt_value = amount
                self.logger.debug(f"{asset}: {amount} (direct USDT)")
            else:
                usdt_value = self.convert_asset_to_usdt(asset, amount)
                
                # Only treat as conversion failure if amount > 0 but conversion returned 0
                if usdt_value == 0.0 and amount > 0:
                    conversion_failures.append(asset)
                    self.logger.warning(f"Failed to convert {asset} to USDT, assigning zero value")
                else:
                    self.logger.debug(f"{asset}: {amount} -> {usdt_value:.2f} USDT")
            
            asset_breakdown[asset] = usdt_value
            total_usdt += usdt_value
        
        portfolio_value = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=total_usdt,
            asset_breakdown=asset_breakdown,
            conversion_failures=conversion_failures
        )
        
        self.logger.info(
            f"Portfolio calculation complete: {total_usdt:.2f} USDT total, "
            f"{len(conversion_failures)} conversion failures"
        )
        
        return portfolio_value
    
    def convert_asset_to_usdt(self, asset: str, amount: float) -> float:
        """
        Convert asset amount to USDT using multi-tier conversion strategy.
        
        Args:
            asset: Asset symbol (e.g., 'BTC', 'ETH')
            amount: Amount of asset to convert
            
        Returns:
            USDT value of the asset amount, 0.0 if conversion fails
        """
        if asset == 'USDT':
            return amount
        
        # Tier 1: Direct USDT pair conversion
        usdt_value = self._try_direct_usdt_conversion(asset, amount)
        if usdt_value is not None:
            return usdt_value
        
        # Tier 2: BTC pair conversion via BTC/USDT
        usdt_value = self._try_btc_pair_conversion(asset, amount)
        if usdt_value is not None:
            return usdt_value
        
        # Tier 3: ETH pair conversion via ETH/USDT
        usdt_value = self._try_eth_pair_conversion(asset, amount)
        if usdt_value is not None:
            return usdt_value
        
        # No conversion path found
        self.logger.warning(f"No conversion path found for {asset}")
        return 0.0
    
    def _try_direct_usdt_conversion(self, asset: str, amount: float) -> Optional[float]:
        """
        Try direct USDT pair conversion (primary method).
        
        Args:
            asset: Asset symbol
            amount: Amount to convert
            
        Returns:
            USDT value if successful, None if pair doesn't exist
        """
        symbol = f"{asset}USDT"
        price = self._get_cached_price(symbol)
        
        if price is not None:
            usdt_value = amount * price
            self.logger.debug(f"Direct conversion: {asset} -> USDT at {price:.8f}")
            return usdt_value
        
        return None
    
    def _try_btc_pair_conversion(self, asset: str, amount: float) -> Optional[float]:
        """
        Try BTC pair conversion via BTC/USDT (secondary method).
        
        Args:
            asset: Asset symbol
            amount: Amount to convert
            
        Returns:
            USDT value if successful, None if conversion fails
        """
        # Get asset price in BTC
        btc_symbol = f"{asset}BTC"
        asset_btc_price = self._get_cached_price(btc_symbol)
        
        if asset_btc_price is None:
            return None
        
        # Get BTC price in USDT
        btc_usdt_price = self._get_cached_price("BTCUSDT")
        
        if btc_usdt_price is None:
            self.logger.warning("BTC/USDT price not available for BTC pair conversion")
            return None
        
        # Convert: Asset -> BTC -> USDT
        btc_amount = amount * asset_btc_price
        usdt_value = btc_amount * btc_usdt_price
        
        self.logger.debug(
            f"BTC pair conversion: {asset} -> BTC at {asset_btc_price:.8f}, "
            f"BTC -> USDT at {btc_usdt_price:.2f}"
        )
        
        return usdt_value
    
    def _try_eth_pair_conversion(self, asset: str, amount: float) -> Optional[float]:
        """
        Try ETH pair conversion via ETH/USDT (tertiary method).
        
        Args:
            asset: Asset symbol
            amount: Amount to convert
            
        Returns:
            USDT value if successful, None if conversion fails
        """
        # Get asset price in ETH
        eth_symbol = f"{asset}ETH"
        asset_eth_price = self._get_cached_price(eth_symbol)
        
        if asset_eth_price is None:
            return None
        
        # Get ETH price in USDT
        eth_usdt_price = self._get_cached_price("ETHUSDT")
        
        if eth_usdt_price is None:
            self.logger.warning("ETH/USDT price not available for ETH pair conversion")
            return None
        
        # Convert: Asset -> ETH -> USDT
        eth_amount = amount * asset_eth_price
        usdt_value = eth_amount * eth_usdt_price
        
        self.logger.debug(
            f"ETH pair conversion: {asset} -> ETH at {asset_eth_price:.8f}, "
            f"ETH -> USDT at {eth_usdt_price:.2f}"
        )
        
        return usdt_value
    
    def _get_cached_price(self, symbol: str) -> Optional[float]:
        """
        Get price from cache or fetch individually if not cached.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            
        Returns:
            Price if available, None if not found
        """
        # Check cache first
        if symbol in self._price_cache:
            return self._price_cache[symbol]
        
        # Try to fetch individual price
        try:
            price = self.binance_client.get_price_for_asset(symbol)
            if price is not None:
                self._price_cache[symbol] = price
                return price
        except Exception as e:
            self.logger.debug(f"Failed to fetch price for {symbol}: {e}")
        
        return None
    
    def get_conversion_summary(self, portfolio_value: PortfolioValue) -> Dict[str, int]:
        """
        Generate summary of conversion methods used.
        
        Args:
            portfolio_value: PortfolioValue object from calculation
            
        Returns:
            Dictionary with counts of each conversion method used
        """
        summary = {
            'direct_usdt': 0,
            'btc_pair': 0,
            'eth_pair': 0,
            'failed': len(portfolio_value.conversion_failures)
        }
        
        # This is a simplified summary - in a real implementation,
        # we'd track which method was used for each asset during conversion
        for asset, value in portfolio_value.asset_breakdown.items():
            if asset == 'USDT':
                continue
            elif value > 0:
                # For now, assume direct USDT if successful
                # In practice, we'd track the actual method used
                summary['direct_usdt'] += 1
        
        return summary