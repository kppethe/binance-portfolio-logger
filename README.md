# Binance Portfolio Logger

An automated system that retrieves cryptocurrency balances from Binance, calculates total portfolio value in USDT, and logs this data to Google Sheets daily. Designed for unattended operation on Proxmox servers with comprehensive error handling and monitoring.

## Features

- **Automated Portfolio Tracking**: Daily retrieval and logging of cryptocurrency portfolio values
- **Multi-Asset Support**: Handles 100+ cryptocurrencies with intelligent price conversion
- **Secure Credential Management**: Environment-based configuration with file permission validation
- **Robust Error Handling**: Exponential backoff, retry logic, and comprehensive logging
- **Proxmox Integration**: One-command installation script for Proxmox VE environments
- **Performance Optimized**: Completes execution within 30 seconds for typical portfolios
- **Comprehensive Monitoring**: Health checks, performance metrics, and security auditing

## Quick Start (Proxmox)

The fastest way to get started is using our automated Proxmox installation script:

```bash
# Download and run the Proxmox installation script
bash -c "$(wget -qLO - https://raw.githubusercontent.com/kppethe/binance-portfolio-logger/main/proxmox-install.sh)"
```

This will:
- Create a new Ubuntu 22.04 LXC container
- Install all dependencies and configure the application
- Set up systemd services for automated scheduling
- Configure security settings and firewall rules
- Provide step-by-step configuration guidance

## Manual Installation

For non-Proxmox environments:

1. **Install System Dependencies:**
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv git cron
   ```

2. **Clone and Setup:**
   ```bash
   git clone <repository-url>
   cd binance-portfolio-logger
   chmod +x setup.sh
   sudo ./setup.sh
   ```

3. **Configure Credentials:**
   ```bash
   sudo nano /opt/binance-portfolio-logger/.env
   # Add your Binance API keys and Google Sheets configuration
   ```

## Project Structure

```
├── src/                                # Application source code
│   ├── api/                           # External API integrations
│   │   ├── binance_client.py          # Binance API client with retry logic
│   │   ├── google_sheets_logger.py    # Google Sheets integration
│   │   └── portfolio_calculator.py    # Portfolio value calculation engine
│   ├── config/                        # Configuration management
│   │   └── configuration_manager.py   # Secure credential loading and validation
│   ├── models/                        # Data models and structures
│   │   └── data_models.py             # AssetBalance, PortfolioValue, etc.
│   ├── utils/                         # Utility modules
│   │   ├── error_handler.py           # Centralized error handling and logging
│   │   ├── health_monitor.py          # System health monitoring
│   │   └── security_validator.py      # Security validation and auditing
│   └── main_application.py            # Main application orchestrator
├── tests/                             # Comprehensive test suite
│   ├── test_*_integration.py          # Integration tests
│   ├── test_end_to_end_integration.py # End-to-end workflow tests
│   ├── test_performance.py            # Performance and timing tests
│   └── test_error_scenarios.py        # Error handling and recovery tests
├── docs/                              # Documentation
│   ├── api_documentation.md           # Complete API reference
│   └── troubleshooting_guide.md       # Comprehensive troubleshooting guide
├── examples/                          # Usage examples and demos
├── proxmox-install.sh                 # Automated Proxmox installation script
├── setup.sh                          # Manual installation script
├── validate_setup.py                 # System validation and health check
├── security_audit.py                 # Security configuration audit
├── health_check.py                   # Runtime health monitoring
├── requirements.txt                   # Python dependencies
├── .env.example                      # Environment variable template
├── DEPLOYMENT.md                     # Detailed deployment guide
└── README.md                         # This file
```

## Environment Variables

See `.env.example` for required environment variables including:
- Binance API credentials
- Google Sheets configuration
- Optional execution parameters

## Components Implemented

### Configuration Manager
- Secure loading of Binance API credentials from environment variables
- Google Sheets credential validation with file permission checks
- Execution configuration with validation and defaults
- Comprehensive error handling and validation

### Data Models
- `AssetBalance`: Cryptocurrency asset balance representation
- `PortfolioValue`: Portfolio value calculation results
- `BinanceCredentials`: Binance API credential structure
- `GoogleCredentials`: Google Sheets API configuration
- `ExecutionConfig`: Application execution parameters

### Security Features
- Environment variable-based credential storage
- File permission validation for service account files
- Input validation and sanitization
- No credential logging or exposure