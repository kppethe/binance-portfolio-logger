"""
Integration test for ErrorHandler to demonstrate real-world usage.
"""

import unittest
import tempfile
import shutil
import os
import time
from pathlib import Path

from src.utils.error_handler import ErrorHandler, ErrorCategory


class TestErrorHandlerIntegration(unittest.TestCase):
    """Integration test for ErrorHandler in realistic scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'portfolio.log')
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
        
        time.sleep(0.1)
        
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            time.sleep(0.5)
            try:
                shutil.rmtree(self.temp_dir)
            except PermissionError:
                pass
    
    def test_successful_portfolio_logging_workflow(self):
        """Test complete successful portfolio logging workflow."""
        # Start execution
        self.error_handler.log_execution_start()
        
        # Simulate API calls
        self.error_handler.log_api_call('binance', 'get_account_info', True, 0.150)
        self.error_handler.log_api_call('binance', 'get_all_prices', True, 0.300)
        self.error_handler.log_api_call('google_sheets', 'append_row', True, 0.450)
        
        # Log some info messages
        self.error_handler.log_info("Retrieved 5 assets with non-zero balances")
        self.error_handler.log_info("Successfully converted 4 assets to USDT")
        self.error_handler.log_warning("Asset XYZ has no conversion path available", ErrorCategory.DATA_PROCESSING)
        
        # Complete execution successfully
        portfolio_value = 2500.75
        assets_processed = 5
        conversion_failures = 1
        
        self.error_handler.log_execution_success(portfolio_value, assets_processed, conversion_failures)
        
        # Verify metrics
        metrics = self.error_handler.get_execution_metrics()
        self.assertEqual(metrics.portfolio_value, portfolio_value)
        self.assertEqual(metrics.assets_processed, assets_processed)
        self.assertEqual(metrics.conversion_failures, conversion_failures)
        self.assertEqual(metrics.total_api_calls, 3)
        self.assertEqual(metrics.api_calls['binance'], 2)
        self.assertEqual(metrics.api_calls['google_sheets'], 1)
        
        # Verify log files exist and contain expected content
        self.assertTrue(os.path.exists(self.log_file))
        self.assertTrue(os.path.exists(self.log_file.replace('.log', '_metrics.log')))
        
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('Portfolio logging execution started', content)
            self.assertIn('Portfolio logging completed successfully', content)
            self.assertIn('$2500.75 USDT', content)
            self.assertIn('Retrieved 5 assets with non-zero balances', content)
            self.assertIn('[DATA_PROCESSING] Asset XYZ has no conversion path', content)
        
        with open(self.log_file.replace('.log', '_metrics.log'), 'r') as f:
            metrics_content = f.read()
            self.assertIn('Performance metrics:', metrics_content)
            self.assertIn('portfolio_value_usdt', metrics_content)
            self.assertIn('total_api_calls', metrics_content)
    
    def test_failed_portfolio_logging_workflow(self):
        """Test portfolio logging workflow with failures."""
        # Start execution
        self.error_handler.log_execution_start()
        
        # Simulate some successful API calls
        self.error_handler.log_api_call('binance', 'get_account_info', True, 0.120)
        
        # Simulate API error
        api_error = Exception("Rate limit exceeded - 429 Too Many Requests")
        should_retry = self.error_handler.handle_api_error(api_error, 'binance', 'get_all_prices')
        self.assertTrue(should_retry)
        
        # Simulate authentication error (should not retry)
        auth_error = Exception("Invalid API key - 401 Unauthorized")
        should_retry = self.error_handler.handle_api_error(auth_error, 'binance', 'get_balances')
        self.assertFalse(should_retry)
        
        # Log failure
        final_error = ValueError("Unable to authenticate with Binance API")
        self.error_handler.log_execution_failure(final_error, ErrorCategory.AUTHENTICATION)
        
        # Verify metrics
        metrics = self.error_handler.get_execution_metrics()
        self.assertEqual(len(metrics.errors_encountered), 3)  # 2 API errors + 1 final error
        self.assertIn("Unable to authenticate with Binance API", metrics.errors_encountered[-1])  # Last error
        self.assertEqual(metrics.total_api_calls, 1)
        self.assertIsNone(metrics.portfolio_value)
        
        # Verify error logging
        error_log_path = self.log_file.replace('.log', '_errors.log')
        self.assertTrue(os.path.exists(error_log_path))
        
        with open(error_log_path, 'r') as f:
            error_content = f.read()
            self.assertIn('Portfolio logging execution failed', error_content)
            self.assertIn('authentication', error_content)
            self.assertIn('Detailed error information', error_content)
    
    def test_sensitive_data_sanitization_in_real_scenario(self):
        """Test that sensitive data is properly sanitized in realistic logging scenarios."""
        # Simulate logging configuration with sensitive data
        config_message = 'Loading configuration: api_key="sk_live_abcdef123456789012345678901234", api_secret="secret_xyz789012345678901234567890"'
        self.error_handler.log_info(config_message)
        
        # Simulate error with sensitive data
        error_with_secrets = Exception('Authentication failed for api_key="sk_test_123456789012345678901234" with password="mySecretPassword123"')
        self.error_handler.log_execution_failure(error_with_secrets, ErrorCategory.AUTHENTICATION)
        
        # Verify sanitization in main log
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('[REDACTED]', content)
            self.assertNotIn('sk_live_abcdef123456789012345678901234', content)
            self.assertNotIn('secret_xyz789012345678901234567890', content)
            self.assertNotIn('sk_test_123456789012345678901234', content)
            self.assertNotIn('mySecretPassword123', content)
        
        # Verify sanitization in error log
        error_log_path = self.log_file.replace('.log', '_errors.log')
        with open(error_log_path, 'r') as f:
            error_content = f.read()
            self.assertIn('[REDACTED]', error_content)
            self.assertNotIn('sk_live_abcdef123456789012345678901234', error_content)
            self.assertNotIn('mySecretPassword123', error_content)
    
    def test_log_rotation_config_generation(self):
        """Test logrotate configuration generation."""
        config_path = os.path.join(self.temp_dir, 'test_logrotate')
        
        config_content = self.error_handler.create_log_rotation_config(config_path)
        
        # Verify config file is created
        self.assertTrue(os.path.exists(config_path))
        
        # Verify config content
        with open(config_path, 'r') as f:
            file_content = f.read()
            self.assertIn('daily', file_content)
            self.assertIn('rotate 30', file_content)
            self.assertIn('compress', file_content)
            self.assertIn('delaycompress', file_content)
            self.assertIn('missingok', file_content)
            self.assertIn('notifempty', file_content)
            self.assertIn('create 644 binance-logger binance-logger', file_content)
            self.assertIn(str(Path(self.log_file).parent), file_content)
        
        # Verify info message is logged
        with open(self.log_file, 'r') as f:
            content = f.read()
            self.assertIn('Created logrotate configuration', content)


if __name__ == '__main__':
    unittest.main()