"""
Binance API client with error handling and retry logic.
"""
import time
import logging
from typing import List, Dict, Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from src.models.data_models import AssetBalance, BinanceCredentials


class BinanceClient:
    """
    Binance API client with authentication, error handling, and retry logic.
    
    Handles account balance retrieval, price fetching, and implements
    exponential backoff for rate limit management.
    """
    
    def __init__(self, credentials: BinanceCredentials):
        """
        Initialize Binance client with credentials.
        
        Args:
            credentials: BinanceCredentials object containing API key and secret
        """
        self.credentials = credentials
        self.client = None
        self.logger = logging.getLogger(__name__)
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the Binance client with authentication."""
        try:
            self.client = Client(
                api_key=self.credentials.api_key,
                api_secret=self.credentials.api_secret,
                testnet=False  # Set to True for testing
            )
            self.logger.info("Binance client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Binance client: {e}")
            raise
    
    def _exponential_backoff_retry(self, func, *args, max_retries: int = 3, **kwargs):
        """
        Execute function with exponential backoff retry logic.
        
        Args:
            func: Function to execute
            max_retries: Maximum number of retry attempts
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Function result on success
            
        Raises:
            Exception: Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (BinanceAPIException, BinanceRequestException) as e:
                last_exception = e
                
                # Don't retry on authentication errors
                if hasattr(e, 'code') and e.code in [-2014, -2015, -1021]:
                    self.logger.error(f"Authentication error, not retrying: {e}")
                    raise
                
                if attempt < max_retries:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    self.logger.warning(
                        f"API call failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(f"All retry attempts failed: {e}")
            except Exception as e:
                last_exception = e
                self.logger.error(f"Unexpected error in API call: {e}")
                break
        
        raise last_exception
    
    def get_account_balances(self) -> List[AssetBalance]:
        """
        Retrieve account balances from Binance, filtering out zero balances.
        
        Returns:
            List of AssetBalance objects with non-zero balances
            
        Raises:
            BinanceAPIException: On API errors
            BinanceRequestException: On request errors
        """
        def _get_balances():
            account_info = self.client.get_account()
            return account_info['balances']
        
        try:
            balances_data = self._exponential_backoff_retry(_get_balances)
            asset_balances = []
            
            for balance in balances_data:
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                # Filter out zero balances as per requirement 1.3
                if total > 0:
                    asset_balance = AssetBalance(
                        asset=balance['asset'],
                        free=free,
                        locked=locked,
                        total=total
                    )
                    asset_balances.append(asset_balance)
            
            self.logger.info(f"Retrieved {len(asset_balances)} non-zero asset balances")
            return asset_balances
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve account balances: {e}")
            raise
    
    def get_all_prices(self) -> Dict[str, float]:
        """
        Fetch all current market prices using batch API call for efficiency.
        
        Returns:
            Dictionary mapping symbol to price (e.g., {'BTCUSDT': 45000.0})
            
        Raises:
            BinanceAPIException: On API errors
            BinanceRequestException: On request errors
        """
        def _get_prices():
            return self.client.get_all_tickers()
        
        try:
            prices_data = self._exponential_backoff_retry(_get_prices)
            prices = {}
            
            for ticker in prices_data:
                symbol = ticker['symbol']
                price = float(ticker['price'])
                prices[symbol] = price
            
            self.logger.info(f"Retrieved prices for {len(prices)} trading pairs")
            return prices
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve all prices: {e}")
            raise
    
    def get_price_for_asset(self, symbol: str) -> Optional[float]:
        """
        Get current price for a specific trading pair.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            
        Returns:
            Current price as float, or None if not found
            
        Raises:
            BinanceAPIException: On API errors
            BinanceRequestException: On request errors
        """
        def _get_single_price():
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        
        try:
            price = self._exponential_backoff_retry(_get_single_price)
            self.logger.debug(f"Retrieved price for {symbol}: {price}")
            return price
            
        except BinanceAPIException as e:
            if e.code == -1121:  # Invalid symbol
                self.logger.warning(f"Invalid symbol {symbol}: {e}")
                return None
            raise
        except Exception as e:
            self.logger.error(f"Failed to retrieve price for {symbol}: {e}")
            raise
    
    def validate_connection(self) -> bool:
        """
        Validate API connection and credentials.
        
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            # Test connection with a simple API call
            self.client.get_server_time()
            self.logger.info("Binance API connection validated successfully")
            return True
        except Exception as e:
            self.logger.error(f"Binance API connection validation failed: {e}")
            return False
    
    def get_exchange_info(self) -> Dict:
        """
        Get exchange information including trading rules and symbol information.
        
        Returns:
            Exchange information dictionary
            
        Raises:
            BinanceAPIException: On API errors
            BinanceRequestException: On request errors
        """
        def _get_exchange_info():
            return self.client.get_exchange_info()
        
        try:
            exchange_info = self._exponential_backoff_retry(_get_exchange_info)
            self.logger.debug("Retrieved exchange information")
            return exchange_info
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve exchange information: {e}")
            raise