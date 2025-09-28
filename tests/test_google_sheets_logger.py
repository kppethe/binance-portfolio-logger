"""
Unit tests for Google Sheets logger with mocked API responses.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from pathlib import Path

from src.api.google_sheets_logger import GoogleSheetsLogger, GoogleSheetsError
from src.models.data_models import GoogleCredentials, PortfolioValue


class TestGoogleSheetsLogger:
    """Test cases for GoogleSheetsLogger class."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Create mock Google credentials for testing."""
        return GoogleCredentials(
            service_account_path="/path/to/service-account.json",
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Test Portfolio"
        )
    
    @pytest.fixture
    def sample_portfolio_value(self):
        """Create sample portfolio value for testing."""
        return PortfolioValue(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            total_usdt=1500.75,
            asset_breakdown={
                'BTC': 1000.50,
                'ETH': 400.25,
                'BNB': 100.00
            },
            conversion_failures=['UNKNOWN_COIN']
        )
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_initialization_success(self, mock_authorize, mock_creds_from_file, mock_exists, mock_credentials):
        """Test successful initialization of GoogleSheetsLogger."""
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_authorize.return_value = mock_client
        
        # Create logger
        logger = GoogleSheetsLogger(mock_credentials)
        
        # Verify initialization
        assert logger.credentials == mock_credentials
        assert logger.client == mock_client
        assert logger.max_retries == 3
        assert logger.base_delay == 1.0
        assert logger.max_delay == 30.0
        
        # Verify method calls
        mock_exists.assert_called_once()
        mock_creds_from_file.assert_called_once()
        mock_authorize.assert_called_once()
    
    @patch('src.api.google_sheets_logger.Path.exists')
    def test_initialization_missing_service_account(self, mock_exists, mock_credentials):
        """Test initialization failure when service account file is missing."""
        mock_exists.return_value = False
        
        with pytest.raises(GoogleSheetsError) as exc_info:
            GoogleSheetsLogger(mock_credentials)
        
        assert "Service account file not found" in str(exc_info.value)
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    def test_initialization_credential_error(self, mock_creds_from_file, mock_exists, mock_credentials):
        """Test initialization failure when credential loading fails."""
        mock_exists.return_value = True
        mock_creds_from_file.side_effect = Exception("Invalid credentials")
        
        with pytest.raises(GoogleSheetsError) as exc_info:
            GoogleSheetsLogger(mock_credentials)
        
        assert "Failed to initialize Google Sheets client" in str(exc_info.value)
    
    def test_get_delay_calculation(self, mock_credentials):
        """Test exponential backoff delay calculation."""
        with patch('src.api.google_sheets_logger.Path.exists', return_value=True), \
             patch('src.api.google_sheets_logger.Credentials.from_service_account_file'), \
             patch('src.api.google_sheets_logger.gspread.authorize'):
            
            logger = GoogleSheetsLogger(mock_credentials)
            
            # Test delay calculations
            assert logger._get_delay(0) == 1.0  # 1 * 2^0
            assert logger._get_delay(1) == 2.0  # 1 * 2^1
            assert logger._get_delay(2) == 4.0  # 1 * 2^2
            assert logger._get_delay(3) == 8.0  # 1 * 2^3
            assert logger._get_delay(10) == 30.0  # Capped at max_delay
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_validate_sheet_access_success(self, mock_authorize, mock_creds_from_file, mock_exists, mock_credentials):
        """Test successful sheet validation and access."""
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_spreadsheet = Mock()
        mock_worksheet = Mock()
        
        mock_authorize.return_value = mock_client
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        mock_worksheet.get_all_records.return_value = []
        
        # Create logger and validate
        logger = GoogleSheetsLogger(mock_credentials)
        result = logger.validate_sheet_access()
        
        # Verify results
        assert result is True
        assert logger.spreadsheet == mock_spreadsheet
        assert logger.worksheet == mock_worksheet
        
        # Verify method calls
        mock_client.open_by_key.assert_called_once_with("test_spreadsheet_id")
        mock_spreadsheet.worksheet.assert_called_once_with("Test Portfolio")
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_validate_sheet_access_create_worksheet(self, mock_authorize, mock_creds_from_file, mock_exists, mock_credentials):
        """Test sheet validation when worksheet needs to be created."""
        from gspread.exceptions import WorksheetNotFound
        
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_spreadsheet = Mock()
        mock_worksheet = Mock()
        
        mock_authorize.return_value = mock_client
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_spreadsheet.worksheet.side_effect = WorksheetNotFound("Worksheet not found")
        mock_spreadsheet.add_worksheet.return_value = mock_worksheet
        mock_worksheet.get_all_records.return_value = []
        
        # Create logger and validate
        logger = GoogleSheetsLogger(mock_credentials)
        result = logger.validate_sheet_access()
        
        # Verify results
        assert result is True
        assert logger.worksheet == mock_worksheet
        
        # Verify worksheet creation
        mock_spreadsheet.add_worksheet.assert_called_once_with(
            title="Test Portfolio",
            rows=1000,
            cols=10
        )
        mock_worksheet.append_row.assert_called_once_with(
            ['Timestamp', 'Total USDT Value', 'Asset Breakdown', 'Conversion Failures']
        )
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_validate_sheet_access_spreadsheet_not_found(self, mock_authorize, mock_creds_from_file, mock_exists, mock_credentials):
        """Test sheet validation failure when spreadsheet is not found."""
        from gspread.exceptions import SpreadsheetNotFound
        
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_authorize.return_value = mock_client
        mock_client.open_by_key.side_effect = SpreadsheetNotFound("Spreadsheet not found")
        
        # Create logger and test validation failure
        logger = GoogleSheetsLogger(mock_credentials)
        
        with pytest.raises(GoogleSheetsError) as exc_info:
            logger.validate_sheet_access()
        
        assert "Spreadsheet not found with ID" in str(exc_info.value)
    
    def test_format_portfolio_data(self, mock_credentials, sample_portfolio_value):
        """Test portfolio data formatting for Google Sheets."""
        with patch('src.api.google_sheets_logger.Path.exists', return_value=True), \
             patch('src.api.google_sheets_logger.Credentials.from_service_account_file'), \
             patch('src.api.google_sheets_logger.gspread.authorize'):
            
            logger = GoogleSheetsLogger(mock_credentials)
            formatted_data = logger._format_portfolio_data(sample_portfolio_value)
            
            # Verify formatted data
            assert len(formatted_data) == 4
            assert formatted_data[0] == "2024-01-15 10:30:00"  # Timestamp
            assert formatted_data[1] == "1500.75"  # Total USDT
            assert "BTC: $1000.50" in formatted_data[2]  # Asset breakdown
            assert "ETH: $400.25" in formatted_data[2]
            assert "BNB: $100.00" in formatted_data[2]
            assert formatted_data[3] == "UNKNOWN_COIN"  # Conversion failures
    
    def test_format_portfolio_data_empty_breakdown(self, mock_credentials):
        """Test portfolio data formatting with empty asset breakdown."""
        with patch('src.api.google_sheets_logger.Path.exists', return_value=True), \
             patch('src.api.google_sheets_logger.Credentials.from_service_account_file'), \
             patch('src.api.google_sheets_logger.gspread.authorize'):
            
            portfolio_value = PortfolioValue(
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                total_usdt=0.0,
                asset_breakdown={},
                conversion_failures=[]
            )
            
            logger = GoogleSheetsLogger(mock_credentials)
            formatted_data = logger._format_portfolio_data(portfolio_value)
            
            # Verify formatted data
            assert formatted_data[1] == "0.00"  # Total USDT
            assert formatted_data[2] == ""  # Empty asset breakdown
            assert formatted_data[3] == ""  # Empty conversion failures
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_append_portfolio_data_success(self, mock_authorize, mock_creds_from_file, mock_exists, 
                                         mock_credentials, sample_portfolio_value):
        """Test successful portfolio data append."""
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_worksheet = Mock()
        
        mock_authorize.return_value = mock_client
        
        # Create logger and set worksheet
        logger = GoogleSheetsLogger(mock_credentials)
        logger.worksheet = mock_worksheet
        
        # Test append
        result = logger.append_portfolio_data(sample_portfolio_value)
        
        # Verify results
        assert result is True
        mock_worksheet.append_row.assert_called_once()
        
        # Verify the data that was appended
        call_args = mock_worksheet.append_row.call_args[0][0]
        assert call_args[0] == "2024-01-15 10:30:00"
        assert call_args[1] == "1500.75"
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_append_portfolio_data_with_retry(self, mock_sleep, mock_authorize, mock_creds_from_file, 
                                            mock_exists, mock_credentials, sample_portfolio_value):
        """Test portfolio data append with retry logic."""
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_worksheet = Mock()
        
        mock_authorize.return_value = mock_client
        
        # Mock worksheet to fail twice then succeed
        # Use ConnectionError instead of APIError to avoid Response object complexity
        mock_worksheet.append_row.side_effect = [
            ConnectionError("Rate limit exceeded"),
            ConnectionError("Temporary error"),
            None  # Success on third attempt
        ]
        
        # Create logger and set worksheet
        logger = GoogleSheetsLogger(mock_credentials)
        logger.worksheet = mock_worksheet
        
        # Test append with retries
        result = logger.append_portfolio_data(sample_portfolio_value)
        
        # Verify results
        assert result is True
        assert mock_worksheet.append_row.call_count == 3
        assert mock_sleep.call_count == 2  # Two retries
        
        # Verify exponential backoff delays
        sleep_calls = mock_sleep.call_args_list
        assert sleep_calls[0][0][0] == 1.0  # First retry delay
        assert sleep_calls[1][0][0] == 2.0  # Second retry delay
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    @patch('time.sleep')
    def test_append_portfolio_data_max_retries_exceeded(self, mock_sleep, mock_authorize, mock_creds_from_file,
                                                      mock_exists, mock_credentials, sample_portfolio_value):
        """Test portfolio data append when max retries are exceeded."""
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_worksheet = Mock()
        
        mock_authorize.return_value = mock_client
        mock_worksheet.append_row.side_effect = ConnectionError("Persistent error")
        
        # Create logger and set worksheet
        logger = GoogleSheetsLogger(mock_credentials)
        logger.worksheet = mock_worksheet
        
        # Test append failure
        with pytest.raises(GoogleSheetsError) as exc_info:
            logger.append_portfolio_data(sample_portfolio_value)
        
        assert "failed after 3 attempts" in str(exc_info.value)
        assert mock_worksheet.append_row.call_count == 3
        assert mock_sleep.call_count == 2
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_append_portfolio_data_non_retryable_error(self, mock_authorize, mock_creds_from_file, mock_exists,
                                                     mock_credentials, sample_portfolio_value):
        """Test portfolio data append with non-retryable error."""
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_worksheet = Mock()
        
        mock_authorize.return_value = mock_client
        mock_worksheet.append_row.side_effect = ValueError("Invalid data format")
        
        # Create logger and set worksheet
        logger = GoogleSheetsLogger(mock_credentials)
        logger.worksheet = mock_worksheet
        
        # Test append failure
        with pytest.raises(GoogleSheetsError) as exc_info:
            logger.append_portfolio_data(sample_portfolio_value)
        
        assert "failed: Invalid data format" in str(exc_info.value)
        assert mock_worksheet.append_row.call_count == 1  # No retries for non-retryable errors
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_get_recent_entries(self, mock_authorize, mock_creds_from_file, mock_exists, mock_credentials):
        """Test getting recent entries from the sheet."""
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_worksheet = Mock()
        
        mock_authorize.return_value = mock_client
        
        # Mock worksheet data
        mock_records = [
            {'Timestamp': '2024-01-01 10:00:00', 'Total USDT Value': '1000.00'},
            {'Timestamp': '2024-01-02 10:00:00', 'Total USDT Value': '1100.00'},
            {'Timestamp': '2024-01-03 10:00:00', 'Total USDT Value': '1200.00'},
        ]
        mock_worksheet.get_all_records.return_value = mock_records
        
        # Create logger and set worksheet
        logger = GoogleSheetsLogger(mock_credentials)
        logger.worksheet = mock_worksheet
        
        # Test getting recent entries
        recent_entries = logger.get_recent_entries(limit=2)
        
        # Verify results
        assert len(recent_entries) == 2
        assert recent_entries[0]['Timestamp'] == '2024-01-02 10:00:00'
        assert recent_entries[1]['Timestamp'] == '2024-01-03 10:00:00'
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_test_connection_success(self, mock_authorize, mock_creds_from_file, mock_exists, mock_credentials):
        """Test successful connection test."""
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_spreadsheet = Mock()
        mock_worksheet = Mock()
        
        mock_authorize.return_value = mock_client
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        mock_worksheet.get_all_records.return_value = []
        
        mock_spreadsheet.title = "Test Spreadsheet"
        mock_worksheet.title = "Test Portfolio"
        mock_worksheet.row_count = 100
        mock_worksheet.col_count = 10
        
        # Create logger and test connection
        logger = GoogleSheetsLogger(mock_credentials)
        result = logger.test_connection()
        
        # Verify results
        assert result['status'] == 'success'
        assert result['spreadsheet_title'] == "Test Spreadsheet"
        assert result['worksheet_title'] == "Test Portfolio"
        assert result['row_count'] == 100
        assert result['col_count'] == 10
        assert 'last_updated' in result
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_test_connection_failure(self, mock_authorize, mock_creds_from_file, mock_exists, mock_credentials):
        """Test connection test failure."""
        # Setup mocks
        mock_exists.return_value = True
        mock_client = Mock()
        mock_authorize.return_value = mock_client
        mock_client.open_by_key.side_effect = Exception("Connection failed")
        
        # Create logger and test connection
        logger = GoogleSheetsLogger(mock_credentials)
        result = logger.test_connection()
        
        # Verify results
        assert result['status'] == 'error'
        assert 'Connection failed' in result['error']
        assert 'last_updated' in result


class TestGoogleSheetsLoggerIntegration:
    """Integration tests for GoogleSheetsLogger."""
    
    @pytest.fixture
    def integration_credentials(self):
        """Create mock Google credentials for integration testing."""
        return GoogleCredentials(
            service_account_path="/path/to/service-account.json",
            spreadsheet_id="integration_test_spreadsheet_id",
            sheet_name="Integration Test Portfolio"
        )
    
    @patch('src.api.google_sheets_logger.Path.exists')
    @patch('src.api.google_sheets_logger.Credentials.from_service_account_file')
    @patch('src.api.google_sheets_logger.gspread.authorize')
    def test_full_workflow(self, mock_authorize, mock_creds_from_file, mock_exists, integration_credentials):
        """Test the complete workflow from initialization to data append."""
        # Setup mocks for full workflow
        mock_exists.return_value = True
        mock_client = Mock()
        mock_spreadsheet = Mock()
        mock_worksheet = Mock()
        
        mock_authorize.return_value = mock_client
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        mock_worksheet.get_all_records.return_value = []
        
        mock_spreadsheet.title = "Integration Test Spreadsheet"
        mock_worksheet.title = "Integration Test Portfolio"
        
        # Create portfolio data
        portfolio_value = PortfolioValue(
            timestamp=datetime(2024, 1, 15, 12, 0, 0),
            total_usdt=2500.00,
            asset_breakdown={'BTC': 2000.00, 'ETH': 500.00},
            conversion_failures=[]
        )
        
        # Execute full workflow
        logger = GoogleSheetsLogger(integration_credentials)
        
        # Validate sheet access
        validation_result = logger.validate_sheet_access()
        assert validation_result is True
        
        # Append portfolio data
        append_result = logger.append_portfolio_data(portfolio_value)
        assert append_result is True
        
        # Test connection
        connection_result = logger.test_connection()
        assert connection_result['status'] == 'success'
        
        # Verify all operations were called
        mock_client.open_by_key.assert_called()
        mock_spreadsheet.worksheet.assert_called()
        mock_worksheet.append_row.assert_called()
        mock_worksheet.get_all_records.assert_called()


if __name__ == '__main__':
    pytest.main([__file__])