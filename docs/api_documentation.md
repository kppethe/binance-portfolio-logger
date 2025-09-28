# Binance Portfolio Logger - API Documentation

This document provides comprehensive API documentation for all classes and methods in the Binance Portfolio Logger system.

## Table of Contents

- [Configuration Management](#configuration-management)
- [Data Models](#data-models)
- [Binance API Client](#binance-api-client)
- [Portfolio Calculator](#portfolio-calculator)
- [Google Sheets Logger](#google-sheets-logger)
- [Error Handler](#error-handler)
- [Health Monitor](#health-monitor)
- [Security Validator](#security-validator)
- [Main Application](#main-application)

---

## Configuration Management

### ConfigurationManager

Handles secure loading and validation of all configuration data and credentials.

#### Class: `ConfigurationManager`

```python
class ConfigurationManager:
    """Manages application configuration and credential loading."""
```

#### Methods

##### `load_binance_credentials() -> BinanceCredentials`

Loads Binance API credentials from environment variables.

**Returns:**
- `BinanceCredentials`: Object containing API key and secret

**Raises:**
- `ValueError`: If required environment variables are missing
- `ValidationError`: If credentials fail validation

**Environment Variables Required:**
- `BINANCE_API_KEY`: Binance API key
- `BINANCE_API_SECRET`: Binance API secret

**Example:**
```python
config_manager = ConfigurationManager()
binance_creds = config_manager.load_binance_credentials()
```

##### `load_google_credentials() -> GoogleCredentials`

Loads Google Sheets API credentials from service account file.

**Returns:**
- `GoogleCredentials`: Object containing service account path and spreadsheet configuration

**Raises:**
- `FileNotFoundError`: If service account file doesn't exist
- `PermissionError`: If file permissions are incorrect
- `json.JSONDecodeError`: If service account file is invalid JSON

**Environment Variables Required:**
- `GOOGLE_SERVICE_ACCOUNT_PATH`: Path to service account JSON file
- `GOOGLE_SPREADSHEET_ID`: Google Sheets spreadsheet ID

**Example:**
```python
config_manager = ConfigurationManager()
google_creds = config_manager.load_google_credentials()
```

##### `get_execution_config() -> ExecutionConfig`

Retrieves execution configuration with defaults.

**Returns:**
- `ExecutionConfig`: Object containing execution parameters

**Environment Variables (Optional):**
- `EXECUTION_TIMEOUT`: Timeout in seconds (default: 60)
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `LOG_FILE_PATH`: Log file path (default: /var/log/binance-portfolio.log)

**Example:**
```python
config_manager = ConfigurationManager()
exec_config = config_manager.get_execution_config()
```

##### `validate_configuration() -> bool`

Validates all configuration and credentials.

**Returns:**
- `bool`: True if all configuration is valid

**Raises:**
- `ConfigurationError`: If any configuration is invalid

**Example:**
```python
config_manager = ConfigurationManager()
is_valid = config_manager.validate_configuration()
```

---

## Data Models

### AssetBalance

Represents a cryptocurrency asset balance.

#### Class: `AssetBalance`

```python
@dataclass
class AssetBalance:
    """Represents a cryptocurrency asset balance."""
    asset: str          # Asset symbol (e.g., 'BTC', 'ETH')
    free: float         # Available balance
    locked: float       # Locked balance (in orders, staking, etc.)
    total: float        # Total balance (free + locked)
```

**Example:**
```python
balance = AssetBalance(
    asset='BTC',
    free=1.5,
    locked=0.2,
    total=1.7
)
```

### PortfolioValue

Represents calculated portfolio value and metadata.

#### Class: `PortfolioValue`

```python
@dataclass
class PortfolioValue:
    """Represents calculated portfolio value."""
    timestamp: datetime                    # Calculation timestamp
    total_usdt: float                     # Total portfolio value in USDT
    asset_breakdown: Dict[str, float]     # Per-asset USDT values
    conversion_failures: List[str]        # Assets that couldn't be converted
```

**Example:**
```python
portfolio = PortfolioValue(
    timestamp=datetime.now(),
    total_usdt=50000.0,
    asset_breakdown={'BTC': 45000.0, 'ETH': 5000.0},
    conversion_failures=['UNKNOWN_COIN']
)
```

### BinanceCredentials

Contains Binance API credentials.

#### Class: `BinanceCredentials`

```python
@dataclass
class BinanceCredentials:
    """Binance API credentials."""
    api_key: str        # Binance API key
    api_secret: str     # Binance API secret
```

### GoogleCredentials

Contains Google Sheets API configuration.

#### Class: `GoogleCredentials`

```python
@dataclass
class GoogleCredentials:
    """Google Sheets API credentials and configuration."""
    service_account_path: str              # Path to service account JSON
    spreadsheet_id: str                    # Google Sheets spreadsheet ID
    sheet_name: str = "Binance Portfolio"  # Worksheet name
```

### ExecutionConfig

Contains application execution configuration.

#### Class: `ExecutionConfig`

```python
@dataclass
class ExecutionConfig:
    """Application execution configuration."""
    timeout_seconds: int = 60                                    # Execution timeout
    max_retries: int = 3                                        # Maximum retry attempts
    log_file_path: str = "/var/log/binance-portfolio.log"       # Log file path
```

---

## Binance API Client

### BinanceClient

Handles all interactions with the Binance API.

#### Class: `BinanceClient`

```python
class BinanceClient:
    """Client for interacting with Binance API."""
    
    def __init__(self, api_key: str, api_secret: str):
        """Initialize Binance client with credentials."""
```

#### Methods

##### `get_account_balances() -> List[AssetBalance]`

Retrieves account balances from Binance API.

**Returns:**
- `List[AssetBalance]`: List of non-zero asset balances

**Raises:**
- `BinanceAPIException`: For API-specific errors
- `ConnectionError`: For network connectivity issues
- `TimeoutError`: For request timeouts

**Features:**
- Automatically filters out zero balances
- Implements exponential backoff retry logic
- Handles rate limiting automatically

**Example:**
```python
client = BinanceClient(api_key, api_secret)
balances = client.get_account_balances()
for balance in balances:
    print(f"{balance.asset}: {balance.total}")
```

##### `get_all_prices() -> Dict[str, float]`

Retrieves current market prices for all trading pairs.

**Returns:**
- `Dict[str, float]`: Mapping of trading pair symbols to prices

**Raises:**
- `BinanceAPIException`: For API-specific errors
- `ConnectionError`: For network connectivity issues

**Example:**
```python
client = BinanceClient(api_key, api_secret)
prices = client.get_all_prices()
btc_price = prices.get('BTCUSDT', 0.0)
```

##### `get_price_for_asset(symbol: str) -> float`

Retrieves price for a specific trading pair.

**Parameters:**
- `symbol` (str): Trading pair symbol (e.g., 'BTCUSDT')

**Returns:**
- `float`: Current price, or 0.0 if not found

**Example:**
```python
client = BinanceClient(api_key, api_secret)
btc_price = client.get_price_for_asset('BTCUSDT')
```

##### `validate_credentials() -> bool`

Validates API credentials by making a test request.

**Returns:**
- `bool`: True if credentials are valid

**Example:**
```python
client = BinanceClient(api_key, api_secret)
is_valid = client.validate_credentials()
```

---

## Portfolio Calculator

### PortfolioCalculator

Converts asset balances to USDT values using current market prices.

#### Class: `PortfolioCalculator`

```python
class PortfolioCalculator:
    """Calculates portfolio value in USDT."""
    
    def __init__(self, binance_client: BinanceClient):
        """Initialize with Binance client for price data."""
```

#### Methods

##### `calculate_portfolio_value(balances: List[AssetBalance]) -> PortfolioValue`

Calculates total portfolio value in USDT.

**Parameters:**
- `balances` (List[AssetBalance]): List of asset balances to convert

**Returns:**
- `PortfolioValue`: Complete portfolio valuation with breakdown

**Conversion Strategy:**
1. Direct USDT pairs (e.g., BTC/USDT)
2. BTC pairs converted via BTC/USDT (e.g., ETH/BTC → BTC/USDT)
3. ETH pairs converted via ETH/USDT
4. Assets without conversion paths are logged as failures

**Example:**
```python
calculator = PortfolioCalculator(binance_client)
portfolio_value = calculator.calculate_portfolio_value(balances)
print(f"Total value: ${portfolio_value.total_usdt:.2f}")
```

##### `convert_asset_to_usdt(asset: str, amount: float) -> float`

Converts a specific asset amount to USDT value.

**Parameters:**
- `asset` (str): Asset symbol (e.g., 'BTC')
- `amount` (float): Amount of asset to convert

**Returns:**
- `float`: USDT value, or 0.0 if conversion not possible

**Example:**
```python
calculator = PortfolioCalculator(binance_client)
btc_value = calculator.convert_asset_to_usdt('BTC', 1.5)
```

##### `get_conversion_rate(from_asset: str, to_asset: str = 'USDT') -> float`

Gets conversion rate between two assets.

**Parameters:**
- `from_asset` (str): Source asset symbol
- `to_asset` (str): Target asset symbol (default: 'USDT')

**Returns:**
- `float`: Conversion rate, or 0.0 if not available

**Example:**
```python
calculator = PortfolioCalculator(binance_client)
btc_to_usdt_rate = calculator.get_conversion_rate('BTC', 'USDT')
```

---

## Google Sheets Logger

### GoogleSheetsLogger

Manages data persistence to Google Sheets with retry logic.

#### Class: `GoogleSheetsLogger`

```python
class GoogleSheetsLogger:
    """Logs portfolio data to Google Sheets."""
    
    def __init__(self, credentials_path: str, spreadsheet_id: str, sheet_name: str = "Binance Portfolio"):
        """Initialize with Google Sheets credentials and configuration."""
```

#### Methods

##### `append_portfolio_data(portfolio_value: PortfolioValue) -> bool`

Appends portfolio data to Google Sheets.

**Parameters:**
- `portfolio_value` (PortfolioValue): Portfolio data to log

**Returns:**
- `bool`: True if successful, False otherwise

**Data Format:**
- Column A: Timestamp (YYYY-MM-DD HH:MM:SS)
- Column B: Total USDT Value
- Column C+: Optional asset breakdown

**Retry Logic:**
- Up to 3 retry attempts
- Exponential backoff between retries
- Handles quota limits and temporary failures

**Example:**
```python
logger = GoogleSheetsLogger(creds_path, spreadsheet_id)
success = logger.append_portfolio_data(portfolio_value)
```

##### `validate_sheet_access() -> bool`

Validates access to the Google Sheets spreadsheet.

**Returns:**
- `bool`: True if sheet is accessible

**Example:**
```python
logger = GoogleSheetsLogger(creds_path, spreadsheet_id)
has_access = logger.validate_sheet_access()
```

##### `create_sheet_if_not_exists() -> bool`

Creates the target worksheet if it doesn't exist.

**Returns:**
- `bool`: True if sheet exists or was created successfully

**Example:**
```python
logger = GoogleSheetsLogger(creds_path, spreadsheet_id)
sheet_ready = logger.create_sheet_if_not_exists()
```

##### `get_last_logged_value() -> Optional[PortfolioValue]`

Retrieves the most recently logged portfolio value.

**Returns:**
- `Optional[PortfolioValue]`: Last logged value, or None if sheet is empty

**Example:**
```python
logger = GoogleSheetsLogger(creds_path, spreadsheet_id)
last_value = logger.get_last_logged_value()
```

---

## Error Handler

### ErrorHandler

Provides centralized logging, error handling, and monitoring capabilities.

#### Class: `ErrorHandler`

```python
class ErrorHandler:
    """Centralized error handling and logging."""
    
    def __init__(self, log_file_path: str = "/var/log/binance-portfolio.log"):
        """Initialize error handler with log file configuration."""
```

#### Methods

##### `setup_logging(log_file: str = None) -> None`

Sets up logging configuration.

**Parameters:**
- `log_file` (str, optional): Custom log file path

**Features:**
- Structured logging with timestamps
- Separate error and info log files
- Log rotation configuration
- Sanitization of sensitive data

**Example:**
```python
error_handler = ErrorHandler()
error_handler.setup_logging("/custom/log/path.log")
```

##### `log_execution_start() -> None`

Logs the start of an execution cycle.

**Example:**
```python
error_handler = ErrorHandler()
error_handler.log_execution_start()
```

##### `log_execution_success(portfolio_value: float) -> None`

Logs successful execution completion.

**Parameters:**
- `portfolio_value` (float): Total portfolio value calculated

**Example:**
```python
error_handler = ErrorHandler()
error_handler.log_execution_success(50000.0)
```

##### `log_execution_failure(error: Exception) -> None`

Logs execution failure with error details.

**Parameters:**
- `error` (Exception): Exception that caused the failure

**Example:**
```python
error_handler = ErrorHandler()
try:
    # Some operation
    pass
except Exception as e:
    error_handler.log_execution_failure(e)
```

##### `handle_api_error(error: Exception) -> bool`

Handles API errors and determines if retry should occur.

**Parameters:**
- `error` (Exception): API error to handle

**Returns:**
- `bool`: True if operation should be retried

**Example:**
```python
error_handler = ErrorHandler()
should_retry = error_handler.handle_api_error(api_exception)
```

##### `sanitize_log_data(data: str) -> str`

Sanitizes log data to prevent credential exposure.

**Parameters:**
- `data` (str): Raw log data

**Returns:**
- `str`: Sanitized log data with credentials masked

**Example:**
```python
error_handler = ErrorHandler()
safe_data = error_handler.sanitize_log_data(raw_log_message)
```

---

## Health Monitor

### HealthMonitor

Monitors system health and performance metrics.

#### Class: `HealthMonitor`

```python
class HealthMonitor:
    """Monitors system health and performance."""
    
    def __init__(self):
        """Initialize health monitor."""
```

#### Methods

##### `check_system_health() -> Dict[str, Any]`

Performs comprehensive system health check.

**Returns:**
- `Dict[str, Any]`: Health status report

**Checks Include:**
- API connectivity
- Disk space
- Memory usage
- Log file accessibility
- Configuration validity

**Example:**
```python
health_monitor = HealthMonitor()
health_status = health_monitor.check_system_health()
```

##### `check_api_connectivity() -> bool`

Tests connectivity to external APIs.

**Returns:**
- `bool`: True if all APIs are accessible

**Example:**
```python
health_monitor = HealthMonitor()
apis_ok = health_monitor.check_api_connectivity()
```

##### `get_performance_metrics() -> Dict[str, float]`

Retrieves current performance metrics.

**Returns:**
- `Dict[str, float]`: Performance metrics

**Metrics Include:**
- Memory usage
- CPU usage
- Disk usage
- Network latency

**Example:**
```python
health_monitor = HealthMonitor()
metrics = health_monitor.get_performance_metrics()
```

##### `validate_portfolio_value(current_value: float, historical_values: List[float]) -> bool`

Validates portfolio value against historical data.

**Parameters:**
- `current_value` (float): Current portfolio value
- `historical_values` (List[float]): Recent historical values

**Returns:**
- `bool`: True if value is within expected range

**Example:**
```python
health_monitor = HealthMonitor()
is_valid = health_monitor.validate_portfolio_value(50000.0, [48000.0, 49000.0, 51000.0])
```

---

## Security Validator

### SecurityValidator

Validates security configurations and credentials.

#### Class: `SecurityValidator`

```python
class SecurityValidator:
    """Validates security configurations."""
    
    def __init__(self):
        """Initialize security validator."""
```

#### Methods

##### `validate_file_permissions(file_path: str, expected_permissions: str = "600") -> bool`

Validates file permissions for security.

**Parameters:**
- `file_path` (str): Path to file to check
- `expected_permissions` (str): Expected permission string (default: "600")

**Returns:**
- `bool`: True if permissions are correct

**Example:**
```python
validator = SecurityValidator()
is_secure = validator.validate_file_permissions("/path/to/credentials.json")
```

##### `validate_api_credentials(api_key: str, api_secret: str) -> bool`

Validates API credentials by testing access.

**Parameters:**
- `api_key` (str): Binance API key
- `api_secret` (str): Binance API secret

**Returns:**
- `bool`: True if credentials are valid and have appropriate permissions

**Example:**
```python
validator = SecurityValidator()
creds_valid = validator.validate_api_credentials(api_key, api_secret)
```

##### `check_environment_security() -> List[str]`

Checks environment for security issues.

**Returns:**
- `List[str]`: List of security warnings/issues found

**Example:**
```python
validator = SecurityValidator()
security_issues = validator.check_environment_security()
```

##### `audit_system_security() -> Dict[str, Any]`

Performs comprehensive security audit.

**Returns:**
- `Dict[str, Any]`: Security audit report

**Example:**
```python
validator = SecurityValidator()
audit_report = validator.audit_system_security()
```

---

## Main Application

### MainApplication

Orchestrates the complete portfolio logging workflow.

#### Class: `MainApplication`

```python
class MainApplication:
    """Main application orchestrator."""
    
    def __init__(self):
        """Initialize main application with all components."""
```

#### Methods

##### `run() -> bool`

Executes the complete portfolio logging workflow.

**Returns:**
- `bool`: True if execution completed successfully

**Workflow:**
1. Load and validate configuration
2. Initialize all components
3. Retrieve account balances from Binance
4. Calculate portfolio value in USDT
5. Log data to Google Sheets
6. Handle errors and cleanup

**Example:**
```python
app = MainApplication()
success = app.run()
```

##### `validate_setup() -> bool`

Validates that all components are properly configured.

**Returns:**
- `bool`: True if setup is valid

**Example:**
```python
app = MainApplication()
setup_ok = app.validate_setup()
```

##### `get_status() -> Dict[str, Any]`

Gets current application status and health.

**Returns:**
- `Dict[str, Any]`: Status report

**Example:**
```python
app = MainApplication()
status = app.get_status()
```

##### `cleanup() -> None`

Performs cleanup operations.

**Example:**
```python
app = MainApplication()
app.cleanup()
```

---

## Error Handling

### Exception Classes

#### `ConfigurationError`

Raised when configuration is invalid or missing.

```python
class ConfigurationError(Exception):
    """Configuration-related errors."""
    pass
```

#### `APIError`

Raised for API-related errors.

```python
class APIError(Exception):
    """API-related errors."""
    pass
```

#### `ValidationError`

Raised for data validation errors.

```python
class ValidationError(Exception):
    """Data validation errors."""
    pass
```

---

## Usage Examples

### Basic Usage

```python
from src.main_application import MainApplication

# Simple execution
app = MainApplication()
success = app.run()

if success:
    print("Portfolio logged successfully")
else:
    print("Execution failed - check logs")
```

### Advanced Usage with Custom Configuration

```python
import os
from src.config.configuration_manager import ConfigurationManager
from src.main_application import MainApplication

# Set custom configuration
os.environ['EXECUTION_TIMEOUT'] = '45'
os.environ['MAX_RETRIES'] = '5'

# Validate configuration before running
config_manager = ConfigurationManager()
if config_manager.validate_configuration():
    app = MainApplication()
    success = app.run()
else:
    print("Configuration validation failed")
```

### Health Monitoring

```python
from src.utils.health_monitor import HealthMonitor

# Check system health before execution
health_monitor = HealthMonitor()
health_status = health_monitor.check_system_health()

if health_status['overall_status'] == 'healthy':
    app = MainApplication()
    success = app.run()
else:
    print(f"System health issues: {health_status['issues']}")
```

### Error Handling

```python
from src.main_application import MainApplication
from src.utils.error_handler import ErrorHandler

error_handler = ErrorHandler()
error_handler.setup_logging()

try:
    app = MainApplication()
    success = app.run()
    
    if success:
        error_handler.log_execution_success(app.get_last_portfolio_value())
    else:
        error_handler.log_execution_failure(Exception("Execution failed"))
        
except Exception as e:
    error_handler.log_execution_failure(e)
    error_handler.handle_api_error(e)
```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BINANCE_API_KEY` | Yes | - | Binance API key |
| `BINANCE_API_SECRET` | Yes | - | Binance API secret |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Yes | - | Path to Google service account JSON |
| `GOOGLE_SPREADSHEET_ID` | Yes | - | Google Sheets spreadsheet ID |
| `GOOGLE_SHEET_NAME` | No | "Binance Portfolio" | Worksheet name |
| `EXECUTION_TIMEOUT` | No | 60 | Execution timeout in seconds |
| `MAX_RETRIES` | No | 3 | Maximum retry attempts |
| `LOG_FILE_PATH` | No | "/var/log/binance-portfolio.log" | Log file path |

### File Permissions

| File/Directory | Permissions | Owner | Description |
|----------------|-------------|-------|-------------|
| Application directory | 750 | binance-logger:binance-logger | Main application directory |
| Credentials directory | 700 | binance-logger:binance-logger | Credentials storage |
| .env file | 600 | binance-logger:binance-logger | Environment variables |
| Service account JSON | 600 | binance-logger:binance-logger | Google credentials |
| Log directory | 755 | binance-logger:binance-logger | Log file storage |

---

## Performance Considerations

### Execution Time

- Target execution time: < 30 seconds for typical portfolios
- Maximum timeout: 60 seconds
- Large portfolios (100+ assets): May take up to 45 seconds

### Memory Usage

- Typical usage: < 50MB RAM
- Large portfolios: < 100MB RAM
- Memory is released after each execution

### API Rate Limits

- Binance API: Respects rate limits with exponential backoff
- Google Sheets API: Limited to 100 requests per 100 seconds
- Batch operations used where possible to minimize API calls

### Network Requirements

- Outbound HTTPS access to:
  - `api.binance.com` (port 443)
  - `sheets.googleapis.com` (port 443)
- Recommended: Stable internet connection with < 2 second latency

---

## Security Best Practices

### Credential Management

1. Use environment variables for API keys
2. Set restrictive file permissions (600) on credential files
3. Never log or display credentials in plain text
4. Use read-only API permissions where possible
5. Regularly rotate API keys

### System Security

1. Run application as non-privileged user
2. Restrict network access to required APIs only
3. Keep system and dependencies updated
4. Monitor logs for suspicious activity
5. Use IP whitelisting for API access when possible

### Data Protection

1. Log files contain no sensitive information
2. Portfolio values are logged but not detailed holdings
3. Error messages are sanitized to prevent information leakage
4. Temporary files are cleaned up after execution

---

## Troubleshooting

### Common Issues

1. **API Authentication Failures**
   - Verify API keys are correct
   - Check API key permissions (should be read-only)
   - Ensure IP whitelisting includes server IP

2. **Google Sheets Access Issues**
   - Verify service account has access to spreadsheet
   - Check Google Sheets API is enabled
   - Validate service account JSON file format

3. **Permission Errors**
   - Check file permissions on credentials
   - Verify application user has access to log directory
   - Ensure service account file is readable

4. **Network Connectivity**
   - Test connectivity to `api.binance.com`
   - Test connectivity to `sheets.googleapis.com`
   - Check firewall rules for outbound HTTPS

### Debug Mode

Enable debug logging by setting environment variable:
```bash
export LOG_LEVEL=DEBUG
```

This provides detailed logging of all operations and API calls.