"""
Main application orchestrator for Binance Portfolio Logger.

This module coordinates all components to execute the complete workflow:
configuration → balance retrieval → calculation → logging
"""
import argparse
import json
import signal
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any
import threading
from pathlib import Path

from .config.configuration_manager import ConfigurationManager, ConfigurationError
from .api.binance_client import BinanceClient
from .api.portfolio_calculator import PortfolioCalculator
from .api.google_sheets_logger import GoogleSheetsLogger, GoogleSheetsError
from .utils.error_handler import ErrorHandler, ErrorCategory
from .utils.health_monitor import HealthMonitor
from .models.data_models import PortfolioValue


class ApplicationError(Exception):
    """Base exception for application-level errors."""
    pass


class ExecutionTimeoutError(ApplicationError):
    """Raised when execution exceeds configured timeout."""
    pass


class MainApplication:
    """
    Main application orchestrator that coordinates all components.
    
    Manages the complete workflow from configuration loading through
    data logging, with timeout handling and graceful shutdown capabilities.
    """
    
    def __init__(self, config_overrides: Optional[Dict[str, Any]] = None):
        """
        Initialize the main application.
        
        Args:
            config_overrides: Optional configuration overrides from command line
        """
        self.config_overrides = config_overrides or {}
        
        # Core components
        self.config_manager: Optional[ConfigurationManager] = None
        self.binance_client: Optional[BinanceClient] = None
        self.portfolio_calculator: Optional[PortfolioCalculator] = None
        self.google_sheets_logger: Optional[GoogleSheetsLogger] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.health_monitor: Optional[HealthMonitor] = None
        
        # Execution control
        self.execution_timeout: int = 60
        self.shutdown_requested: bool = False
        self.execution_thread: Optional[threading.Thread] = None
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            print(f"\nReceived {signal_name} signal. Initiating graceful shutdown...")
            self.shutdown_requested = True
        
        # Handle SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _apply_config_overrides(self) -> None:
        """Apply command-line configuration overrides to environment."""
        import os
        
        # Map command-line arguments to environment variables
        override_mapping = {
            'timeout': 'EXECUTION_TIMEOUT_SECONDS',
            'max_retries': 'MAX_RETRIES',
            'log_file': 'LOG_FILE_PATH',
            'binance_api_key': 'BINANCE_API_KEY',
            'binance_api_secret': 'BINANCE_API_SECRET',
            'google_service_account': 'GOOGLE_SERVICE_ACCOUNT_PATH',
            'google_spreadsheet_id': 'GOOGLE_SPREADSHEET_ID',
            'google_sheet_name': 'GOOGLE_SHEET_NAME'
        }
        
        for arg_name, env_var in override_mapping.items():
            if arg_name in self.config_overrides and self.config_overrides[arg_name]:
                os.environ[env_var] = str(self.config_overrides[arg_name])
    
    def _initialize_components(self) -> None:
        """
        Initialize all application components.
        
        Raises:
            ApplicationError: If component initialization fails
        """
        try:
            # Apply configuration overrides
            self._apply_config_overrides()
            
            # Initialize configuration manager
            self.config_manager = ConfigurationManager()
            
            # Initialize error handler first for logging
            execution_config = self.config_manager.get_execution_config()
            self.execution_timeout = execution_config.timeout_seconds
            self.error_handler = ErrorHandler(execution_config.log_file_path)
            
            # Initialize health monitor
            log_dir = Path(execution_config.log_file_path).parent
            self.health_monitor = HealthMonitor(data_dir=str(log_dir))
            
            self.error_handler.log_info("Initializing application components...")
            
            # Validate all configuration
            self.config_manager.validate_configuration()
            self.error_handler.log_info("Configuration validation successful")
            
            # Run startup security validation
            self.config_manager.validate_startup_security()
            self.error_handler.log_info("Startup security validation successful")
            
            # Initialize Binance client
            binance_creds = self.config_manager.binance_credentials
            self.binance_client = BinanceClient(binance_creds)
            
            # Validate Binance connection
            if not self.binance_client.validate_connection():
                raise ApplicationError("Failed to validate Binance API connection")
            
            self.error_handler.log_info("Binance client initialized and validated")
            
            # Initialize portfolio calculator
            self.portfolio_calculator = PortfolioCalculator(self.binance_client)
            self.error_handler.log_info("Portfolio calculator initialized")
            
            # Initialize Google Sheets logger
            google_creds = self.config_manager.google_credentials
            self.google_sheets_logger = GoogleSheetsLogger(google_creds)
            
            # Validate Google Sheets access
            self.google_sheets_logger.validate_sheet_access()
            self.error_handler.log_info("Google Sheets logger initialized and validated")
            
            self.error_handler.log_info("All components initialized successfully")
            
        except ConfigurationError as e:
            error_msg = f"Configuration error during initialization: {str(e)}"
            if self.error_handler:
                self.error_handler.log_execution_failure(e, ErrorCategory.CONFIGURATION)
            else:
                print(f"ERROR: {error_msg}")
            raise ApplicationError(error_msg) from e
        
        except GoogleSheetsError as e:
            error_msg = f"Google Sheets error during initialization: {str(e)}"
            self.error_handler.log_execution_failure(e, ErrorCategory.API_ERROR)
            raise ApplicationError(error_msg) from e
        
        except Exception as e:
            error_msg = f"Unexpected error during initialization: {str(e)}"
            if self.error_handler:
                self.error_handler.log_execution_failure(e, ErrorCategory.SYSTEM)
            else:
                print(f"ERROR: {error_msg}")
            raise ApplicationError(error_msg) from e
    
    def _execute_workflow_with_timeout(self) -> PortfolioValue:
        """
        Execute the main workflow with timeout handling.
        
        Returns:
            PortfolioValue: The calculated portfolio value
            
        Raises:
            ExecutionTimeoutError: If execution exceeds timeout
            ApplicationError: If workflow execution fails
        """
        result = None
        exception = None
        
        def workflow_target():
            nonlocal result, exception
            try:
                result = self._execute_workflow()
            except Exception as e:
                exception = e
        
        # Start workflow in separate thread for timeout control
        self.execution_thread = threading.Thread(target=workflow_target)
        self.execution_thread.start()
        
        # Wait for completion or timeout
        self.execution_thread.join(timeout=self.execution_timeout)
        
        if self.execution_thread.is_alive():
            # Timeout occurred
            self.error_handler.log_warning(
                f"Execution timeout after {self.execution_timeout} seconds",
                ErrorCategory.SYSTEM
            )
            raise ExecutionTimeoutError(
                f"Portfolio logging execution exceeded timeout of {self.execution_timeout} seconds"
            )
        
        if exception:
            raise exception
        
        return result
    
    def _execute_workflow(self) -> PortfolioValue:
        """
        Execute the main portfolio logging workflow.
        
        Returns:
            PortfolioValue: The calculated portfolio value
            
        Raises:
            ApplicationError: If any step in the workflow fails
        """
        try:
            # Step 1: Retrieve account balances
            self.error_handler.log_info("Step 1: Retrieving account balances from Binance...")
            
            if self.shutdown_requested:
                raise ApplicationError("Shutdown requested during balance retrieval")
            
            start_time = time.time()
            balances = self.binance_client.get_account_balances()
            balance_time = time.time() - start_time
            
            self.error_handler.log_api_call('binance', 'get_account_balances', True, balance_time)
            self.error_handler.log_info(f"Retrieved {len(balances)} non-zero asset balances")
            
            if not balances:
                self.error_handler.log_warning("No non-zero balances found", ErrorCategory.DATA_PROCESSING)
                # Create empty portfolio value but continue to log it
                empty_portfolio = PortfolioValue(
                    timestamp=datetime.now(),
                    total_usdt=0.0,
                    asset_breakdown={},
                    conversion_failures=[]
                )
                
                # Still log the empty portfolio to Google Sheets
                self.error_handler.log_info("Step 3: Logging empty portfolio data to Google Sheets...")
                
                if self.shutdown_requested:
                    raise ApplicationError("Shutdown requested during Google Sheets logging")
                
                start_time = time.time()
                success = self.google_sheets_logger.append_portfolio_data(empty_portfolio)
                sheets_time = time.time() - start_time
                
                self.error_handler.log_api_call('google_sheets', 'append_portfolio_data', success, sheets_time)
                
                if not success:
                    raise ApplicationError("Failed to log empty portfolio data to Google Sheets")
                
                self.error_handler.log_info("Empty portfolio data successfully logged to Google Sheets")
                return empty_portfolio
            
            # Step 2: Calculate portfolio value
            self.error_handler.log_info("Step 2: Calculating portfolio value in USDT...")
            
            if self.shutdown_requested:
                raise ApplicationError("Shutdown requested during portfolio calculation")
            
            start_time = time.time()
            portfolio_value = self.portfolio_calculator.calculate_portfolio_value(balances)
            calc_time = time.time() - start_time
            
            self.error_handler.log_info(
                f"Portfolio calculation completed in {calc_time:.2f}s. "
                f"Total value: ${portfolio_value.total_usdt:.2f} USDT"
            )
            
            if portfolio_value.conversion_failures:
                self.error_handler.log_warning(
                    f"Failed to convert {len(portfolio_value.conversion_failures)} assets: "
                    f"{', '.join(portfolio_value.conversion_failures)}",
                    ErrorCategory.DATA_PROCESSING
                )
            
            # Step 3: Log to Google Sheets
            self.error_handler.log_info("Step 3: Logging portfolio data to Google Sheets...")
            
            if self.shutdown_requested:
                raise ApplicationError("Shutdown requested during Google Sheets logging")
            
            start_time = time.time()
            success = self.google_sheets_logger.append_portfolio_data(portfolio_value)
            sheets_time = time.time() - start_time
            
            self.error_handler.log_api_call('google_sheets', 'append_portfolio_data', success, sheets_time)
            
            if not success:
                raise ApplicationError("Failed to log portfolio data to Google Sheets")
            
            self.error_handler.log_info("Portfolio data successfully logged to Google Sheets")
            
            return portfolio_value
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            self.error_handler.log_execution_failure(e, ErrorCategory.SYSTEM)
            raise ApplicationError(error_msg) from e
    
    def run(self) -> int:
        """
        Run the complete portfolio logging application.
        
        Returns:
            int: Exit code (0 for success, non-zero for failure)
        """
        exit_code = 0
        
        try:
            # Initialize components
            self._initialize_components()
            
            # Log execution start
            self.error_handler.log_execution_start()
            
            # Execute workflow with timeout
            portfolio_value = self._execute_workflow_with_timeout()
            
            # Log successful completion
            assets_processed = len(portfolio_value.asset_breakdown)
            conversion_failures = len(portfolio_value.conversion_failures)
            
            self.error_handler.log_execution_success(
                portfolio_value.total_usdt,
                assets_processed,
                conversion_failures
            )
            
            # Validate portfolio value and collect metrics
            if self.health_monitor:
                # Validate portfolio value for unusual changes
                is_valid, warnings = self.health_monitor.validate_portfolio_value(portfolio_value)
                for warning in warnings:
                    self.error_handler.log_warning(warning, ErrorCategory.DATA_PROCESSING)
                
                # Collect execution metrics
                execution_metrics = self.error_handler.get_execution_metrics()
                metrics_dict = {
                    'timestamp': datetime.now().isoformat(),
                    'execution_duration_seconds': execution_metrics.execution_duration,
                    'total_api_calls': execution_metrics.total_api_calls,
                    'api_calls_by_service': dict(execution_metrics.api_calls),
                    'assets_processed': assets_processed,
                    'conversion_failures': conversion_failures,
                    'portfolio_value_usdt': portfolio_value.total_usdt,
                    'errors_count': len(execution_metrics.errors_encountered),
                    'success': True
                }
                self.health_monitor.collect_execution_metrics(metrics_dict)
            
            # Print summary to stdout for cron job visibility
            print(f"SUCCESS: Portfolio value ${portfolio_value.total_usdt:.2f} USDT "
                  f"({assets_processed} assets, {conversion_failures} conversion failures)")
            
        except ExecutionTimeoutError as e:
            self.error_handler.log_execution_failure(e, ErrorCategory.SYSTEM)
            print(f"TIMEOUT: {str(e)}")
            exit_code = 2
            
            # Collect failure metrics
            if self.health_monitor:
                execution_metrics = self.error_handler.get_execution_metrics()
                metrics_dict = {
                    'timestamp': datetime.now().isoformat(),
                    'execution_duration_seconds': execution_metrics.execution_duration,
                    'total_api_calls': execution_metrics.total_api_calls,
                    'errors_count': len(execution_metrics.errors_encountered) + 1,
                    'success': False,
                    'failure_reason': 'timeout'
                }
                self.health_monitor.collect_execution_metrics(metrics_dict)
            
        except ApplicationError as e:
            # Error already logged by component
            print(f"ERROR: {str(e)}")
            exit_code = 1
            
            # Collect failure metrics
            if self.health_monitor:
                execution_metrics = self.error_handler.get_execution_metrics()
                metrics_dict = {
                    'timestamp': datetime.now().isoformat(),
                    'execution_duration_seconds': execution_metrics.execution_duration,
                    'total_api_calls': execution_metrics.total_api_calls,
                    'errors_count': len(execution_metrics.errors_encountered) + 1,
                    'success': False,
                    'failure_reason': 'application_error'
                }
                self.health_monitor.collect_execution_metrics(metrics_dict)
            
        except Exception as e:
            error_msg = f"Unexpected application error: {str(e)}"
            if self.error_handler:
                self.error_handler.log_execution_failure(e, ErrorCategory.UNKNOWN)
            else:
                print(f"CRITICAL ERROR: {error_msg}")
            exit_code = 3
            
            # Collect failure metrics
            if self.health_monitor:
                metrics_dict = {
                    'timestamp': datetime.now().isoformat(),
                    'execution_duration_seconds': 0,
                    'total_api_calls': 0,
                    'errors_count': 1,
                    'success': False,
                    'failure_reason': 'unexpected_error'
                }
                self.health_monitor.collect_execution_metrics(metrics_dict)
        
        finally:
            self._cleanup()
        
        return exit_code
    
    def _cleanup(self) -> None:
        """Perform cleanup operations before shutdown."""
        if self.error_handler:
            self.error_handler.log_info("Performing cleanup operations...")
        
        # Cancel any running operations
        self.shutdown_requested = True
        
        # Wait for execution thread to complete if still running
        if self.execution_thread and self.execution_thread.is_alive():
            if self.error_handler:
                self.error_handler.log_info("Waiting for execution thread to complete...")
            self.execution_thread.join(timeout=5.0)
            
            if self.execution_thread.is_alive():
                if self.error_handler:
                    self.error_handler.log_warning(
                        "Execution thread did not complete within cleanup timeout",
                        ErrorCategory.SYSTEM
                    )
        
        # Close any open connections/resources
        # (Components should handle their own cleanup in destructors)
        
        if self.error_handler:
            self.error_handler.log_info("Cleanup completed")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current application status for monitoring.
        
        Returns:
            Dict containing application status information
        """
        status = {
            'timestamp': datetime.now().isoformat(),
            'shutdown_requested': self.shutdown_requested,
            'components_initialized': {
                'config_manager': self.config_manager is not None,
                'binance_client': self.binance_client is not None,
                'portfolio_calculator': self.portfolio_calculator is not None,
                'google_sheets_logger': self.google_sheets_logger is not None,
                'error_handler': self.error_handler is not None,
                'health_monitor': self.health_monitor is not None
            },
            'execution_timeout': self.execution_timeout
        }
        
        if self.error_handler:
            metrics = self.error_handler.get_execution_metrics()
            status['execution_metrics'] = {
                'execution_duration': metrics.execution_duration,
                'total_api_calls': metrics.total_api_calls,
                'api_calls_by_service': dict(metrics.api_calls),
                'errors_count': len(metrics.errors_encountered)
            }
        
        if self.health_monitor:
            status['health_status'] = self.health_monitor.get_health_status()
            status['recent_alerts'] = self.health_monitor.get_recent_alerts(hours=24)
        
        return status


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create command-line argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description='Binance Portfolio Logger - Automated portfolio tracking to Google Sheets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Run with default configuration
  %(prog)s --timeout 120                      # Set custom timeout
  %(prog)s --log-file /tmp/portfolio.log      # Use custom log file
  %(prog)s --dry-run                          # Test configuration without logging
        """
    )
    
    # Execution configuration
    parser.add_argument(
        '--timeout',
        type=int,
        metavar='SECONDS',
        help='Execution timeout in seconds (default: from config or 60)'
    )
    
    parser.add_argument(
        '--max-retries',
        type=int,
        metavar='COUNT',
        help='Maximum retry attempts for API calls (default: from config or 3)'
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        metavar='PATH',
        help='Path to log file (default: from config or /var/log/binance-portfolio.log)'
    )
    
    # Credential overrides (for testing/development)
    parser.add_argument(
        '--binance-api-key',
        type=str,
        metavar='KEY',
        help='Binance API key (overrides environment variable)'
    )
    
    parser.add_argument(
        '--binance-api-secret',
        type=str,
        metavar='SECRET',
        help='Binance API secret (overrides environment variable)'
    )
    
    parser.add_argument(
        '--google-service-account',
        type=str,
        metavar='PATH',
        help='Path to Google service account JSON file'
    )
    
    parser.add_argument(
        '--google-spreadsheet-id',
        type=str,
        metavar='ID',
        help='Google Spreadsheet ID'
    )
    
    parser.add_argument(
        '--google-sheet-name',
        type=str,
        metavar='NAME',
        help='Google Sheet name (default: "Binance Portfolio")'
    )
    
    # Utility options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test configuration and connections without logging data'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show application status and exit'
    )
    
    parser.add_argument(
        '--health-check',
        action='store_true',
        help='Run health checks and exit'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Binance Portfolio Logger 1.0.0'
    )
    
    return parser


def main() -> int:
    """
    Main entry point for the application.
    
    Returns:
        int: Exit code
    """
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Convert arguments to configuration overrides
    config_overrides = {}
    for arg_name, arg_value in vars(args).items():
        if arg_value is not None and arg_name not in ['dry_run', 'status']:
            config_overrides[arg_name] = arg_value
    
    try:
        app = MainApplication(config_overrides)
        
        # Handle special modes
        if args.status:
            status = app.get_status()
            print(f"Application Status: {status}")
            return 0
        
        if args.health_check:
            try:
                app._initialize_components()
                health_report = app.health_monitor.run_health_checks()
                print(json.dumps(health_report, indent=2))
                
                # Return appropriate exit code based on health status
                if health_report['overall_status'] == 'critical':
                    return 2
                elif health_report['overall_status'] == 'warning':
                    return 1
                else:
                    return 0
            except Exception as e:
                print(f"Health check failed: {e}")
                return 3
        
        if args.dry_run:
            print("DRY RUN MODE: Testing configuration and connections...")
            try:
                app._initialize_components()
                print("SUCCESS: All components initialized and validated successfully")
                return 0
            except Exception as e:
                print(f"FAILED: {str(e)}")
                return 1
        
        # Normal execution
        return app.run()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return 1


if __name__ == '__main__':
    sys.exit(main())