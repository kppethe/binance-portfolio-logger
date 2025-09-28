"""
Google Sheets logger for portfolio data with retry logic and error handling.
"""
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

try:
    import gspread
    from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
    from google.oauth2.service_account import Credentials
except ImportError as e:
    raise ImportError(
        "Google Sheets dependencies not installed. "
        "Please install with: pip install gspread google-auth"
    ) from e

from ..models.data_models import PortfolioValue, GoogleCredentials


class GoogleSheetsError(Exception):
    """Base exception for Google Sheets operations."""
    pass


class GoogleSheetsLogger:
    """
    Manages data persistence to Google Sheets with retry logic and error handling.
    
    This class handles authentication, sheet validation, data formatting,
    and implements exponential backoff retry logic for failed operations.
    """
    
    def __init__(self, credentials: GoogleCredentials):
        """
        Initialize the Google Sheets logger.
        
        Args:
            credentials: Google Sheets API credentials configuration
            
        Raises:
            GoogleSheetsError: If initialization fails
        """
        self.credentials = credentials
        self.client: Optional[gspread.Client] = None
        self.spreadsheet: Optional[gspread.Spreadsheet] = None
        self.worksheet: Optional[gspread.Worksheet] = None
        self.logger = logging.getLogger(__name__)
        
        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay in seconds
        self.max_delay = 30.0  # Maximum delay in seconds
        
        # Initialize the client
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """
        Initialize the Google Sheets client with service account authentication.
        
        Raises:
            GoogleSheetsError: If client initialization fails
        """
        try:
            # Validate service account file exists
            service_account_path = Path(self.credentials.service_account_path)
            if not service_account_path.exists():
                raise GoogleSheetsError(
                    f"Service account file not found: {self.credentials.service_account_path}"
                )
            
            # Load credentials and create client
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = Credentials.from_service_account_file(
                self.credentials.service_account_path,
                scopes=scopes
            )
            
            self.client = gspread.authorize(creds)
            self.logger.info("Google Sheets client initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize Google Sheets client: {str(e)}"
            self.logger.error(error_msg)
            raise GoogleSheetsError(error_msg) from e
    
    def _get_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay for retry attempts.
        
        Args:
            attempt: The current attempt number (0-based)
            
        Returns:
            float: Delay in seconds
        """
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)
    
    def _retry_operation(self, operation_name: str, operation_func, *args, **kwargs) -> Any:
        """
        Execute an operation with exponential backoff retry logic.
        
        Args:
            operation_name: Name of the operation for logging
            operation_func: Function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Any: Result of the operation
            
        Raises:
            GoogleSheetsError: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                result = operation_func(*args, **kwargs)
                if attempt > 0:
                    self.logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                return result
                
            except (APIError, ConnectionError, TimeoutError) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self._get_delay(attempt)
                    self.logger.warning(
                        f"{operation_name} failed on attempt {attempt + 1}: {str(e)}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(
                        f"{operation_name} failed after {self.max_retries} attempts: {str(e)}"
                    )
            except Exception as e:
                # Non-retryable errors
                self.logger.error(f"{operation_name} failed with non-retryable error: {str(e)}")
                raise GoogleSheetsError(f"{operation_name} failed: {str(e)}") from e
        
        # All retries exhausted
        raise GoogleSheetsError(
            f"{operation_name} failed after {self.max_retries} attempts. "
            f"Last error: {str(last_exception)}"
        ) from last_exception
    
    def validate_sheet_access(self) -> bool:
        """
        Validate access to the Google Sheets spreadsheet and worksheet.
        
        Returns:
            bool: True if access is valid
            
        Raises:
            GoogleSheetsError: If validation fails
        """
        def _validate_access():
            # Open the spreadsheet
            try:
                self.spreadsheet = self.client.open_by_key(self.credentials.spreadsheet_id)
                self.logger.info(f"Successfully opened spreadsheet: {self.spreadsheet.title}")
            except SpreadsheetNotFound:
                raise GoogleSheetsError(
                    f"Spreadsheet not found with ID: {self.credentials.spreadsheet_id}. "
                    "Please check the spreadsheet ID and sharing permissions."
                )
            
            # Try to open or create the worksheet
            try:
                self.worksheet = self.spreadsheet.worksheet(self.credentials.sheet_name)
                self.logger.info(f"Found existing worksheet: {self.credentials.sheet_name}")
            except WorksheetNotFound:
                self.logger.info(f"Worksheet '{self.credentials.sheet_name}' not found. Creating...")
                self.worksheet = self.spreadsheet.add_worksheet(
                    title=self.credentials.sheet_name,
                    rows=1000,
                    cols=10
                )
                
                # Add headers to the new worksheet
                headers = ['Timestamp', 'Total USDT Value', 'Asset Breakdown', 'Conversion Failures']
                self.worksheet.append_row(headers)
                self.logger.info(f"Created new worksheet: {self.credentials.sheet_name}")
            
            # Test write permissions by getting worksheet info
            worksheet_info = self.worksheet.get_all_records(head=1)
            self.logger.info(f"Worksheet validation successful. Current rows: {len(worksheet_info) + 1}")
            
            return True
        
        return self._retry_operation("Sheet validation", _validate_access)
    
    def _format_portfolio_data(self, portfolio_value: PortfolioValue) -> List[Any]:
        """
        Format portfolio data for Google Sheets row.
        
        Args:
            portfolio_value: Portfolio value data to format
            
        Returns:
            List[Any]: Formatted row data
        """
        # Format timestamp as YYYY-MM-DD HH:MM:SS
        timestamp_str = portfolio_value.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # Format total USDT value with 2 decimal places
        total_usdt_str = f"{portfolio_value.total_usdt:.2f}"
        
        # Format asset breakdown as JSON-like string for readability
        asset_breakdown_str = ""
        if portfolio_value.asset_breakdown:
            breakdown_items = []
            for asset, value in portfolio_value.asset_breakdown.items():
                if value > 0.01:  # Only include assets worth more than $0.01
                    breakdown_items.append(f"{asset}: ${value:.2f}")
            asset_breakdown_str = "; ".join(breakdown_items)
        
        # Format conversion failures
        conversion_failures_str = ""
        if portfolio_value.conversion_failures:
            conversion_failures_str = "; ".join(portfolio_value.conversion_failures)
        
        return [
            timestamp_str,
            total_usdt_str,
            asset_breakdown_str,
            conversion_failures_str
        ]
    
    def append_portfolio_data(self, portfolio_value: PortfolioValue) -> bool:
        """
        Append portfolio data to the Google Sheets worksheet.
        
        Args:
            portfolio_value: Portfolio value data to append
            
        Returns:
            bool: True if data was successfully appended
            
        Raises:
            GoogleSheetsError: If append operation fails after all retries
        """
        if not self.worksheet:
            # Validate sheet access if not already done
            self.validate_sheet_access()
        
        def _append_data():
            row_data = self._format_portfolio_data(portfolio_value)
            self.worksheet.append_row(row_data)
            
            self.logger.info(
                f"Successfully appended portfolio data: "
                f"${portfolio_value.total_usdt:.2f} USDT at {portfolio_value.timestamp}"
            )
            return True
        
        return self._retry_operation("Append portfolio data", _append_data)
    
    def get_recent_entries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent portfolio entries from the sheet.
        
        Args:
            limit: Maximum number of entries to retrieve
            
        Returns:
            List[Dict[str, Any]]: Recent portfolio entries
            
        Raises:
            GoogleSheetsError: If retrieval fails
        """
        if not self.worksheet:
            self.validate_sheet_access()
        
        def _get_entries():
            all_records = self.worksheet.get_all_records()
            # Return the most recent entries (last N rows)
            recent_records = all_records[-limit:] if len(all_records) > limit else all_records
            return recent_records
        
        return self._retry_operation("Get recent entries", _get_entries)
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to Google Sheets and return status information.
        
        Returns:
            Dict[str, Any]: Connection status and information
        """
        try:
            self.validate_sheet_access()
            
            # Get basic sheet information
            sheet_info = {
                'status': 'success',
                'spreadsheet_title': self.spreadsheet.title,
                'worksheet_title': self.worksheet.title,
                'row_count': self.worksheet.row_count,
                'col_count': self.worksheet.col_count,
                'last_updated': datetime.now().isoformat()
            }
            
            self.logger.info("Google Sheets connection test successful")
            return sheet_info
            
        except Exception as e:
            error_info = {
                'status': 'error',
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }
            
            self.logger.error(f"Google Sheets connection test failed: {str(e)}")
            return error_info