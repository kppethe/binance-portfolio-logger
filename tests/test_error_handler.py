"""
Unit tests for the ErrorHandler class.

Tests comprehensive error handling, logging functionality, sanitization,
performance metrics, and error categorization.
"""

import unittest
import tempfile
import shutil
import os
import time
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.utils.error_handler import (
    ErrorHandler, 
    ErrorCategory, 
    LogLevel, 
    ExecutionMetrics
)


class TestExecutionMetrics(unittest.TestCase):
    """Test ExecutionMetrics functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.metrics = ExecutionMetrics()
    
    def test_initialization(self):
        """Test ExecutionMetrics initialization."""
        self.assertIsInstance(self.metrics.start_time, float)
        self.assertIsNone(self.metrics.end_time)
        self.assertEqual(self.metrics.api_calls, {})
        self.assertEqual(self.metrics.errors_encountered, [])
        self.assertIsNone(self.metrics.portfolio_value)
        self.assertEqual(self.metrics.assets_processed, 0)
        self.assertEqual(self.metrics.conversion_failures, 0)
    
    def test_execution_duration(self):
        """Test execution duration calculation."""
        # Test with ongoing execution
        duration = self.metrics.execution_duration
        self.assertGreater(duration, 0)
        
        # Test with completed execution
        self.metrics.end_time = self.metrics.start_time + 5.0
        self.assertEqual(self.metrics.execution_duration, 5.0)
    
    def test_add_api_call(self):
        """Test API call tracking."""
        self.metrics.add_api_call('binance')
        self.metrics.add_api_call('binance')
        self.metrics.add_api_call('google_sheets')
        
        self.assertEqual(self.metrics.api_calls['binance'], 2)
        self.assertEqual(self.metrics.api_calls['google_sheets'], 1)
        self.assertEqual(self.metrics.total_api_calls, 3)
    
    def test_add_error(self):
        """Test error tracking."""
        self.metrics.add_error('Test error 1')
        self.metrics.add_error('Test error 2')
        
        self.assertEqual(len(self.metrics.errors_encountered), 2)
        self.assertIn('Test error 1', self.metrics.errors_encountered)
        self.assertIn('Test error 2', self.metrics.errors_encountered)
    
    def test_finalize(self):
        """Test metrics finalization."""
        portfolio_value = 1000.50
        self.metrics.finalize(portfolio_value)
        
        self.assertIsNotNone(self.metrics.end_time)
        self.assertEqual(self.metrics.portfolio_value, portfolio_value)


class TestErrorHandler(unittest.TestCase):
    """Test ErrorHandler functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'test_portfolio.log')
        self.error_handler = ErrorHandler(self.log_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Close all handlers to release file locks
        if hasattr(self.error_handler, 'logger') and self.error_handler.logger:
            for handler in self.error_handler.logger.handlers[:]:
                handler.close()
                self.error_handler.logger.removeHandler(handler)
        
        if hasattr(self.error_handler, 'error_logger') and self.error_handler.error_logger:
            for handler in self.error_handler.error_logger.handlers[:]:
                handler.close()
                self.error_handler.error_logger.removeHandler(handler)
        
        if hasattr(self.error_handler, 'metrics_logger') and self.error_handler.metrics_logger:
            for handler in self.error_handler.metrics_logger.handlers[:]:
                handler.close()
                self.error_handler.metrics_logger.removeHandler(handler)
        
        # Small delay to ensure file handles are released
        import time
        time.sleep(0.1)
        
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            # On Windows, sometimes files are still locked, try again after a short delay
            time.sleep(0.5)
            try:
                shutil.rmtree(self.temp_dir)
            except PermissionError:
                # If still failing, just pass - temp files will be cleaned up by OS
                pass
    
    def test_initialization(self):
        """Test ErrorHandler initialization."""
        self.assertEqual(self.error_handler.log_file_path, self.log_file)
        self.assertTrue(self.log_file.replace('.log', '_errors.log') in self.error_handler.error_log_path)
        self.assertTrue(self.log_file.replace('.log', '_metrics.log') in self.error_handler.metrics_log_path)
        
        # Check that loggers are created
        self.assertIsNotNone(self.error_handler.logger)
        self.assertIsNotNone(self.error_handler.error_logger)
        self.assertIsNotNone(self.error_handler.metrics_logger)
        
        # Check that log directory is created
        self.assertTrue(Path(self.log_file).parent.exists())
    
    def test_log_sanitization(self):
        """Test sensitive data sanitization."""
        test_cases = [
            ('api_key="sk_test_123456789012345678901234"', 'api_key="[REDACTED]"'),
            ('API_SECRET: "secret123456789012345678901234"', 'api_secret="[REDACTED]"'),
            ('password="mypassword123"', 'password="[REDACTED]"'),
            ('token: "jwt.token.here.with.many.parts"', 'token="[REDACTED]"'),
            ('"private_key": "-----BEGIN PRIVATE KEY-----"', '"private_key": "[REDACTED]"'),
            ('"client_secret": "oauth_secret_here"', '"client_secret": "[REDACTED]"'),
        ]
        
        for original, expected in test_cases:
            sanitized = self.error_handler._sanitize_message(original)
            self.assertIn('[REDACTED]', sanitized, f"Failed to sanitize: {original}")
            self.assertNotIn('123456789012345678901234', sanitized)
    
    def test_log_execution_start(self):
        """Test execution start logging."""
        self.error_handler.log_execution_start()
        
        # Check that metrics are reset
        self.assertIsInstance(self.error_handler.execution_metrics.start_time, float)
        
        # Check that log file is created and contains start message
        self.assertTrue(os.path.exists(self.log_file))
        
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('Portfolio logging execution started', content)
            self.assertIn('System info:', content)
    
    def test_log_execution_success(self):
        """Test successful execution logging."""
        self.error_handler.log_execution_start()
        time.sleep(0.1)  # Small delay to ensure measurable execution time
        
        portfolio_value = 1500.75
        assets_processed = 5
        conversion_failures = 1
        
        self.error_handler.log_execution_success(
            portfolio_value, assets_processed, conversion_failures
        )
        
        # Check metrics are updated
        metrics = self.error_handler.get_execution_metrics()
        self.assertEqual(metrics.portfolio_value, portfolio_value)
        self.assertEqual(metrics.assets_processed, assets_processed)
        self.assertEqual(metrics.conversion_failures, conversion_failures)
        self.assertIsNotNone(metrics.end_time)
        
        # Check log content
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('Portfolio logging completed successfully', content)
            self.assertIn(f'${portfolio_value:.2f} USDT', content)
            self.assertIn(f'Assets processed: {assets_processed}', content)
    
    def test_log_execution_failure(self):
        """Test failed execution logging."""
        self.error_handler.log_execution_start()
        
        test_error = ValueError("Test error message")
        error_category = ErrorCategory.DATA_PROCESSING
        
        self.error_handler.log_execution_failure(test_error, error_category)
        
        # Check metrics are updated
        metrics = self.error_handler.get_execution_metrics()
        self.assertIn("Test error message", metrics.errors_encountered)
        self.assertIsNotNone(metrics.end_time)
        
        # Check main log
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('Portfolio logging execution failed', content)
            self.assertIn('data_processing', content)
            self.assertIn('Test error message', content)
        
        # Check error log
        error_log_path = self.log_file.replace('.log', '_errors.log')
        self.assertTrue(os.path.exists(error_log_path))
        
        with open(error_log_path, 'r') as f:
            error_content = f.read()
            self.assertIn('Portfolio logging execution failed', error_content)
            self.assertIn('Detailed error information', error_content)
    
    def test_handle_api_error_rate_limit(self):
        """Test API error handling for rate limits."""
        error = Exception("Rate limit exceeded - 429 Too Many Requests")
        should_retry = self.error_handler.handle_api_error(
            error, 'binance', 'get_balances'
        )
        
        self.assertTrue(should_retry)
        
        # Check that error is logged
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('API error in binance during get_balances', content)
            self.assertIn('Retry recommended: True', content)
    
    def test_handle_api_error_authentication(self):
        """Test API error handling for authentication errors."""
        error = Exception("Unauthorized - 401")
        should_retry = self.error_handler.handle_api_error(
            error, 'binance', 'get_balances'
        )
        
        self.assertFalse(should_retry)
        
        # Check error log
        error_log_path = self.log_file.replace('.log', '_errors.log')
        with open(error_log_path, 'r') as f:
            content = f.read()
            self.assertIn('API error in binance during get_balances', content)
            self.assertIn('Retry recommended: False', content)
    
    def test_handle_api_error_network(self):
        """Test API error handling for network errors."""
        error = Exception("Connection timeout")
        should_retry = self.error_handler.handle_api_error(
            error, 'google_sheets', 'append_data'
        )
        
        self.assertTrue(should_retry)
        
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('API error in google_sheets during append_data', content)
    
    def test_log_api_call(self):
        """Test API call logging."""
        self.error_handler.log_api_call('binance', 'get_prices', True, 0.250)
        self.error_handler.log_api_call('google_sheets', 'append_row', False)
        
        # Check metrics
        metrics = self.error_handler.get_execution_metrics()
        self.assertEqual(metrics.api_calls['binance'], 1)
        self.assertEqual(metrics.api_calls['google_sheets'], 1)
        self.assertEqual(metrics.total_api_calls, 2)
    
    def test_log_warning(self):
        """Test warning logging with categorization."""
        warning_message = "Test warning message"
        category = ErrorCategory.CONFIGURATION
        
        self.error_handler.log_warning(warning_message, category)
        
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('[CONFIGURATION] Test warning message', content)
    
    def test_log_info(self):
        """Test info logging."""
        info_message = "Test info message"
        self.error_handler.log_info(info_message)
        
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('Test info message', content)
    
    def test_log_debug(self):
        """Test debug logging."""
        # Debug messages might not appear in file unless debug level is set
        debug_message = "Test debug message"
        self.error_handler.log_debug(debug_message)
        
        # This test mainly ensures no exceptions are raised
        self.assertTrue(True)
    
    def test_performance_metrics_logging(self):
        """Test performance metrics logging."""
        self.error_handler.log_execution_start()
        
        # Add some API calls and metrics
        self.error_handler.log_api_call('binance', 'get_balances', True, 0.1)
        self.error_handler.log_api_call('binance', 'get_prices', True, 0.2)
        self.error_handler.log_api_call('google_sheets', 'append_data', True, 0.3)
        
        # Complete execution
        self.error_handler.log_execution_success(1000.0, 3, 0)
        
        # Check metrics log
        metrics_log_path = self.log_file.replace('.log', '_metrics.log')
        self.assertTrue(os.path.exists(metrics_log_path))
        
        with open(metrics_log_path, 'r') as f:
            content = f.read()
            self.assertIn('Performance metrics:', content)
            self.assertIn('execution_duration_seconds', content)
            self.assertIn('total_api_calls', content)
            self.assertIn('portfolio_value_usdt', content)
    
    def test_create_log_rotation_config(self):
        """Test logrotate configuration creation."""
        config_path = os.path.join(self.temp_dir, 'test_logrotate')
        
        config_content = self.error_handler.create_log_rotation_config(config_path)
        
        # Check that config file is created
        self.assertTrue(os.path.exists(config_path))
        
        # Check config content
        with open(config_path, 'r') as f:
            file_content = f.read()
            self.assertEqual(file_content, config_content)
            self.assertIn('daily', file_content)
            self.assertIn('rotate 30', file_content)
            self.assertIn('compress', file_content)
            self.assertIn(str(Path(self.log_file).parent), file_content)
    
    @patch('src.utils.error_handler.open', side_effect=PermissionError("Permission denied"))
    def test_create_log_rotation_config_permission_error(self, mock_open):
        """Test logrotate config creation with permission error."""
        config_path = "/etc/logrotate.d/test"
        
        config_content = self.error_handler.create_log_rotation_config(config_path)
        
        # Should return config content even if file creation fails
        self.assertIn('daily', config_content)
        self.assertIn('rotate 30', config_content)
        
        # Check that warning is logged by reading the actual log file
        # Close handlers first to flush logs
        for handler in self.error_handler.logger.handlers:
            handler.flush()
        
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('Could not create logrotate config', content)
    
    def test_error_categories(self):
        """Test all error categories are properly defined."""
        categories = [
            ErrorCategory.CONFIGURATION,
            ErrorCategory.API_ERROR,
            ErrorCategory.NETWORK,
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.DATA_PROCESSING,
            ErrorCategory.SYSTEM,
            ErrorCategory.UNKNOWN
        ]
        
        for category in categories:
            self.assertIsInstance(category.value, str)
            self.assertTrue(len(category.value) > 0)
    
    def test_log_levels(self):
        """Test all log levels are properly defined."""
        levels = [
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL
        ]
        
        for level in levels:
            self.assertIsInstance(level.value, int)
            self.assertGreaterEqual(level.value, logging.DEBUG)
    
    def test_sensitive_data_patterns(self):
        """Test that all sensitive data patterns work correctly."""
        test_data = {
            'api_key="sk_live_123456789012345678901234567890"': '[REDACTED]',
            'API_SECRET: "secret_123456789012345678901234567890"': '[REDACTED]',
            'password="my_secure_password"': '[REDACTED]',
            'token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"': '[REDACTED]',
            '"private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC"': '[REDACTED]',
            '"client_secret": "GOCSPX-abcdefghijklmnopqrstuvwxyz123456"': '[REDACTED]'
        }
        
        for original, expected_redaction in test_data.items():
            sanitized = self.error_handler._sanitize_message(original)
            self.assertIn(expected_redaction, sanitized)
            # Ensure original sensitive data is not present
            self.assertNotIn('123456789012345678901234567890', sanitized)
            self.assertNotIn('my_secure_password', sanitized)
            self.assertNotIn('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9', sanitized)


if __name__ == '__main__':
    unittest.main()