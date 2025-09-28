"""
Data models for the Binance Portfolio Logger application.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List


@dataclass
class AssetBalance:
    """Represents a cryptocurrency asset balance."""
    asset: str
    free: float
    locked: float
    total: float


@dataclass
class PortfolioValue:
    """Represents the calculated portfolio value at a point in time."""
    timestamp: datetime
    total_usdt: float
    asset_breakdown: Dict[str, float]
    conversion_failures: List[str]


@dataclass
class BinanceCredentials:
    """Binance API credentials."""
    api_key: str
    api_secret: str


@dataclass
class GoogleCredentials:
    """Google Sheets API credentials configuration."""
    service_account_path: str
    spreadsheet_id: str
    sheet_name: str = "Binance Portfolio"


@dataclass
class ExecutionConfig:
    """Configuration for application execution parameters."""
    timeout_seconds: int = 60
    max_retries: int = 3
    log_file_path: str = "/var/log/binance-portfolio.log"