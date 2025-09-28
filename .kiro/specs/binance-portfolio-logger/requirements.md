# Requirements Document

## Introduction

The Binance Portfolio Logger is an automated system that retrieves cryptocurrency balances from Binance, calculates total portfolio value in USDT, and logs this data to Google Sheets daily. The system will run unattended on a Proxmox server, providing historical tracking of portfolio performance with secure credential management and robust error handling.

## Requirements

### Requirement 1

**User Story:** As a cryptocurrency investor, I want to automatically fetch my Binance account balances daily, so that I can track my portfolio performance over time without manual intervention.

#### Acceptance Criteria

1. WHEN the system executes THEN it SHALL connect to Binance API using read-only API credentials
2. WHEN retrieving balances THEN the system SHALL fetch both free and locked amounts for all assets
3. WHEN an asset has zero balance THEN the system SHALL exclude it from calculations
4. IF API connection fails THEN the system SHALL retry up to 3 times with exponential backoff
5. WHEN API rate limits are approached THEN the system SHALL implement appropriate delays between requests

### Requirement 2

**User Story:** As a portfolio tracker, I want the system to calculate the total value of all my assets in USDT, so that I have a standardized measure of my portfolio worth.

#### Acceptance Criteria

1. WHEN calculating portfolio value THEN the system SHALL fetch current market prices for all held assets
2. WHEN an asset lacks a direct USDT pair THEN the system SHALL use alternative conversion paths (e.g., BTC or ETH pairs)
3. IF no conversion path exists for an asset THEN the system SHALL log the asset with zero USDT value and continue processing
4. WHEN fetching prices THEN the system SHALL use batch API calls to minimize rate limit impact
5. WHEN calculating total value THEN the system SHALL sum all individual asset values in USDT

### Requirement 3

**User Story:** As a data analyst, I want portfolio data automatically logged to Google Sheets with timestamps, so that I can analyze historical performance trends.

#### Acceptance Criteria

1. WHEN logging data THEN the system SHALL append a new row to the "Binance Portfolio" Google Sheet
2. WHEN creating a log entry THEN the system SHALL include timestamp in YYYY-MM-DD HH:MM:SS format
3. WHEN creating a log entry THEN the system SHALL include total portfolio value in USDT
4. WHEN logging fails THEN the system SHALL retry up to 3 times before reporting failure
5. IF Google Sheets API is unavailable THEN the system SHALL log locally and retry on next execution

### Requirement 4

**User Story:** As a system administrator, I want the portfolio logger to run automatically on a schedule, so that data collection happens consistently without manual intervention.

#### Acceptance Criteria

1. WHEN deployed THEN the system SHALL execute daily via cron job at a configurable time
2. WHEN scheduled execution begins THEN the system SHALL complete within 30 seconds for typical portfolio sizes
3. IF execution takes longer than 60 seconds THEN the system SHALL timeout and log an error
4. WHEN execution completes THEN the system SHALL log success/failure status locally
5. IF system resources are insufficient THEN the system SHALL log resource constraints and exit gracefully

### Requirement 5

**User Story:** As a security-conscious user, I want API credentials stored securely, so that my trading accounts remain protected from unauthorized access.

#### Acceptance Criteria

1. WHEN storing Binance API credentials THEN the system SHALL use environment variables or secure configuration files
2. WHEN storing Google Service Account credentials THEN the system SHALL use JSON key files with restricted file permissions
3. WHEN API keys are accessed THEN the system SHALL never log or display them in plain text
4. IF credential files are missing or invalid THEN the system SHALL fail gracefully with appropriate error messages
5. WHEN running THEN the system SHALL use read-only API permissions for Binance access

### Requirement 6

**User Story:** As a system operator, I want comprehensive error handling and logging, so that I can troubleshoot issues and ensure reliable operation.

#### Acceptance Criteria

1. WHEN errors occur THEN the system SHALL log detailed error information to /var/log/binance-portfolio.log
2. WHEN API calls fail THEN the system SHALL log the specific error code and message
3. WHEN network connectivity issues occur THEN the system SHALL implement retry logic with exponential backoff
4. IF critical errors prevent execution THEN the system SHALL send notification (optional) and exit with appropriate status code
5. WHEN successful execution completes THEN the system SHALL log confirmation with timestamp and portfolio value

### Requirement 7

**User Story:** As a deployment engineer, I want the system to run reliably on Proxmox infrastructure with automated installation, so that it integrates seamlessly with existing server management.

#### Acceptance Criteria

1. WHEN deployed THEN the system SHALL run on Python 3.9+ in Linux environment (Debian/Ubuntu)
2. WHEN installing dependencies THEN the system SHALL use pip for package management
3. WHEN running in Proxmox LXC container THEN the system SHALL operate within standard resource constraints (512MB RAM, 1 CPU, 8GB storage)
4. WHEN using the Proxmox installation script THEN the system SHALL create and configure a complete LXC container automatically
5. IF system dependencies are missing THEN the system SHALL provide clear installation instructions
6. WHEN system starts THEN the system SHALL validate all required dependencies and configurations
7. WHEN deployed via Proxmox script THEN the system SHALL include systemd service files for automated scheduling
8. WHEN installation completes THEN the system SHALL provide comprehensive post-installation configuration guidance