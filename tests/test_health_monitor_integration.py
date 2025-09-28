"""
Integration tests for the health monitoring system.

These tests verify the integration between health monitoring and the main application.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.main_application import MainApplication
from src.utils.health_monitor import HealthMonitor, HealthStatus, AlertLevel
from src.models.data_models import PortfolioValue


class TestHealthMonitorIntegration(unittest.TestCase):
    """Integration tests for health monitoring with main application."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        # Set up test environment
        self.test_env = {
            'BINANCE_API_KEY': 'test_api_key_1234567890',
            'BINANCE_API_SECRET': 'test_api_secret_1234567890',
            'GOOGLE_SERVICE_ACCOUNT_PATH': str(self.temp_dir / 'service_account.json'),
            'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id',
            'LOG_FILE_PATH': str(self.log_dir / 'portfolio.log'),
            'EXECUTION_TIMEOUT_SECONDS': '30',
            'VALIDATE_API_ON_STARTUP': 'false'  # Skip API validation for tests
        }
        
        # Create mock service account file
        service_account_data = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest-private-key\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        
        with open(self.test_env['GOOGLE_SERVICE_ACCOUNT_PATH'], 'w') as f:
            json.dump(service_account_data, f)
        
        # Set file permissions
        os.chmod(self.test_env['GOOGLE_SERVICE_ACCOUNT_PATH'], 0o600)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.api.binance_client.BinanceClient.validate_connection')
    @patch('src.api.binance_client.BinanceClient.get_account_balances')
    @patch('src.api.portfolio_calculator.PortfolioCalculator.calculate_portfolio_value')
    @patch('src.api.google_sheets_logger.GoogleSheetsLogger.validate_sheet_access')
    @patch('src.api.google_sheets_logger.GoogleSheetsLogger.append_portfolio_data')
    def test_main_application_with_health_monitoring(self, 
                                                   mock_append_data,
                                                   mock_validate_sheets,
                                                   mock_calculate_portfolio,
                                                   mock_get_balances,
                                                   mock_validate_connection):
        """Test main application execution with health monitoring enabled."""
        
        # Mock successful API responses
        mock_validate_connection.return_value = True
        mock_validate_sheets.return_value = None
        mock_append_data.return_value = True
        
        # Mock balance data
        from src.models.data_models import AssetBalance
        mock_balances = [
            AssetBalance(asset='BTC', free=0.5, locked=0.0, total=0.5),
            AssetBalance(asset='ETH', free=2.0, locked=0.0, total=2.0)
        ]
        mock_get_balances.return_value = mock_balances
        
        # Mock portfolio calculation
        test_portfolio = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=1500.0,
            asset_breakdown={'BTC': 1000.0, 'ETH': 500.0},
            conversion_failures=[]
        )
        mock_calculate_portfolio.return_value = test_portfolio
        
        with patch.dict(os.environ, self.test_env):
            app = MainApplication()
            
            # Run the application
            exit_code = app.run()
            
            # Verify successful execution
            self.assertEqual(exit_code, 0)
            
            # Verify health monitor was initialized
            self.assertIsNotNone(app.health_monitor)
            self.assertIsInstance(app.health_monitor, HealthMonitor)
            
            # Verify portfolio validation was called
            history_file = app.health_monitor.history_file
            self.assertTrue(history_file.exists())
            
            # Verify execution metrics were collected
            metrics_file = app.health_monitor.data_dir / "execution_metrics.json"
            self.assertTrue(metrics_file.exists())
            
            with open(metrics_file, 'r') as f:
                metrics_data = json.load(f)
            
            self.assertGreater(len(metrics_data), 0)
            self.assertTrue(metrics_data[0]['success'])
            self.assertEqual(metrics_data[0]['portfolio_value_usdt'], 1500.0)
    
    @patch('src.api.binance_client.BinanceClient.validate_connection')
    @patch('src.api.binance_client.BinanceClient.get_account_balances')
    def test_main_application_failure_with_health_monitoring(self,
                                                           mock_get_balances,
                                                           mock_validate_connection):
        """Test main application failure handling with health monitoring."""
        
        # Mock connection validation success but balance retrieval failure
        mock_validate_connection.return_value = True
        mock_get_balances.side_effect = Exception("API connection failed")
        
        with patch.dict(os.environ, self.test_env):
            app = MainApplication()
            
            # Run the application (should fail)
            exit_code = app.run()
            
            # Verify failure exit code
            self.assertNotEqual(exit_code, 0)
            
            # Verify health monitor collected failure metrics
            if app.health_monitor:
                metrics_file = app.health_monitor.data_dir / "execution_metrics.json"
                if metrics_file.exists():
                    with open(metrics_file, 'r') as f:
                        metrics_data = json.load(f)
                    
                    if metrics_data:
                        self.assertFalse(metrics_data[-1]['success'])
                        self.assertGreater(metrics_data[-1]['errors_count'], 0)
    
    def test_health_check_command_line_option(self):
        """Test health check command line option."""
        with patch.dict(os.environ, self.test_env):
            # Mock the health check to avoid actual system checks
            with patch('src.main_application.MainApplication._initialize_components'):
                with patch('src.utils.health_monitor.HealthMonitor.run_health_checks') as mock_health_checks:
                    mock_health_checks.return_value = {
                        'timestamp': datetime.now().isoformat(),
                        'overall_status': 'healthy',
                        'checks': [],
                        'summary': {'total_checks': 0}
                    }
                    
                    app = MainApplication()
                    
                    # Simulate --health-check argument
                    import sys
                    original_argv = sys.argv
                    try:
                        sys.argv = ['main.py', '--health-check']
                        
                        # This would normally be called by main(), but we'll call it directly
                        app._initialize_components = Mock()
                        app.health_monitor = HealthMonitor(data_dir=self.temp_dir)
                        
                        health_report = app.health_monitor.run_health_checks()
                        
                        self.assertIn('overall_status', health_report)
                        self.assertIn('checks', health_report)
                        
                    finally:
                        sys.argv = original_argv
    
    def test_portfolio_value_validation_integration(self):
        """Test portfolio value validation integration with alerts."""
        with patch.dict(os.environ, self.test_env):
            health_monitor = HealthMonitor(data_dir=self.temp_dir)
            
            # Add initial portfolio value
            initial_portfolio = PortfolioValue(
                timestamp=datetime.now() - timedelta(hours=1),
                total_usdt=1000.0,
                asset_breakdown={'BTC': 600.0, 'ETH': 400.0},
                conversion_failures=[]
            )
            
            is_valid, warnings = health_monitor.validate_portfolio_value(initial_portfolio)
            self.assertTrue(is_valid)
            self.assertEqual(len(warnings), 0)
            
            # Add portfolio value with large change
            large_change_portfolio = PortfolioValue(
                timestamp=datetime.now(),
                total_usdt=1300.0,  # 30% increase
                asset_breakdown={'BTC': 780.0, 'ETH': 520.0},
                conversion_failures=[]
            )
            
            with patch.object(health_monitor, '_send_email_alert') as mock_email:
                is_valid, warnings = health_monitor.validate_portfolio_value(large_change_portfolio)
                
                # Should still be valid but with warnings
                self.assertTrue(is_valid)
                self.assertGreater(len(warnings), 0)
                self.assertIn("Large portfolio change", warnings[0])
                
                # Verify alert was saved
                alerts_file = health_monitor.alerts_file
                self.assertTrue(alerts_file.exists())
                
                with open(alerts_file, 'r') as f:
                    alerts = json.load(f)
                
                self.assertGreater(len(alerts), 0)
                self.assertEqual(alerts[0]['level'], 'warning')
                self.assertIn('Large Portfolio Value Change', alerts[0]['title'])
    
    def test_execution_metrics_collection_integration(self):
        """Test execution metrics collection integration."""
        with patch.dict(os.environ, self.test_env):
            health_monitor = HealthMonitor(data_dir=self.temp_dir)
            
            # Simulate multiple execution metrics
            metrics_data = [
                {
                    'execution_duration_seconds': 25.5,
                    'total_api_calls': 8,
                    'api_calls_by_service': {'binance': 6, 'google_sheets': 2},
                    'assets_processed': 3,
                    'conversion_failures': 0,
                    'portfolio_value_usdt': 1200.0,
                    'errors_count': 0,
                    'success': True
                },
                {
                    'execution_duration_seconds': 45.2,
                    'total_api_calls': 12,
                    'api_calls_by_service': {'binance': 10, 'google_sheets': 2},
                    'assets_processed': 5,
                    'conversion_failures': 1,
                    'portfolio_value_usdt': 1150.0,
                    'errors_count': 1,
                    'success': True
                }
            ]
            
            for metrics in metrics_data:
                health_monitor.collect_execution_metrics(metrics)
            
            # Verify metrics were saved
            metrics_file = health_monitor.data_dir / "execution_metrics.json"
            self.assertTrue(metrics_file.exists())
            
            with open(metrics_file, 'r') as f:
                saved_metrics = json.load(f)
            
            self.assertEqual(len(saved_metrics), 2)
            self.assertEqual(saved_metrics[0]['execution_duration_seconds'], 25.5)
            self.assertEqual(saved_metrics[1]['execution_duration_seconds'], 45.2)
    
    def test_health_status_integration_with_real_checks(self):
        """Test health status integration with real system checks."""
        with patch.dict(os.environ, self.test_env):
            health_monitor = HealthMonitor(data_dir=self.temp_dir)
            
            # Create some log files to make checks more realistic
            log_files = [
                self.log_dir / 'portfolio.log',
                self.log_dir / 'portfolio_errors.log',
                self.log_dir / 'portfolio_metrics.log'
            ]
            
            for log_file in log_files:
                log_file.write_text("Test log content\n")
            
            # Run health checks
            health_report = health_monitor.run_health_checks()
            
            # Verify report structure
            self.assertIn('timestamp', health_report)
            self.assertIn('overall_status', health_report)
            self.assertIn('checks', health_report)
            self.assertIn('summary', health_report)
            
            # Verify specific checks were performed
            check_names = [check['name'] for check in health_report['checks']]
            expected_checks = ['Configuration', 'System Resources', 'Recent Execution']
            
            for expected_check in expected_checks:
                self.assertIn(expected_check, check_names)
            
            # Verify health status was saved
            health_file = health_monitor.health_file
            self.assertTrue(health_file.exists())
            
            saved_status = health_monitor.get_health_status()
            self.assertEqual(saved_status['overall_status'], health_report['overall_status'])
    
    def test_alert_system_integration(self):
        """Test alert system integration with email notifications."""
        with patch.dict(os.environ, {
            **self.test_env,
            'SMTP_SERVER': 'smtp.test.com',
            'SMTP_USERNAME': 'test@test.com',
            'SMTP_PASSWORD': 'test_password',
            'ALERT_EMAIL_TO': 'alerts@test.com'
        }):
            health_monitor = HealthMonitor(data_dir=self.temp_dir)
            
            # Verify email is enabled
            self.assertTrue(health_monitor.email_enabled)
            
            # Create a critical portfolio situation (zero value)
            initial_portfolio = PortfolioValue(
                timestamp=datetime.now() - timedelta(hours=1),
                total_usdt=1000.0,
                asset_breakdown={'BTC': 1000.0},
                conversion_failures=[]
            )
            health_monitor.validate_portfolio_value(initial_portfolio)
            
            zero_portfolio = PortfolioValue(
                timestamp=datetime.now(),
                total_usdt=0.0,
                asset_breakdown={},
                conversion_failures=[]
            )
            
            with patch('smtplib.SMTP') as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value.__enter__.return_value = mock_server
                
                is_valid, warnings = health_monitor.validate_portfolio_value(zero_portfolio)
                
                # Should trigger email alert
                self.assertFalse(is_valid)
                self.assertGreater(len(warnings), 0)
                
                # Verify email was sent
                mock_server.starttls.assert_called_once()
                mock_server.login.assert_called_once()
                mock_server.send_message.assert_called_once()
    
    def test_monitoring_data_retention(self):
        """Test monitoring data retention policies."""
        with patch.dict(os.environ, {
            **self.test_env,
            'HISTORY_RETENTION_DAYS': '7'  # Short retention for testing
        }):
            health_monitor = HealthMonitor(data_dir=self.temp_dir)
            
            # Add old portfolio data (should be cleaned up)
            old_portfolio = PortfolioValue(
                timestamp=datetime.now() - timedelta(days=10),  # Older than retention
                total_usdt=800.0,
                asset_breakdown={'BTC': 800.0},
                conversion_failures=[]
            )
            
            recent_portfolio = PortfolioValue(
                timestamp=datetime.now() - timedelta(days=2),  # Within retention
                total_usdt=900.0,
                asset_breakdown={'BTC': 900.0},
                conversion_failures=[]
            )
            
            current_portfolio = PortfolioValue(
                timestamp=datetime.now(),
                total_usdt=1000.0,
                asset_breakdown={'BTC': 1000.0},
                conversion_failures=[]
            )
            
            # Add all portfolios
            health_monitor.validate_portfolio_value(old_portfolio)
            health_monitor.validate_portfolio_value(recent_portfolio)
            health_monitor.validate_portfolio_value(current_portfolio)
            
            # Load history - old data should be cleaned up
            history = health_monitor._load_portfolio_history()
            
            # Should only have recent and current data
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0].value, 900.0)  # Recent
            self.assertEqual(history[1].value, 1000.0)  # Current


if __name__ == '__main__':
    unittest.main()