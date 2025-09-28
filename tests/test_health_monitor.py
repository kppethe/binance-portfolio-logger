"""
Unit tests for the health monitoring system.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.utils.health_monitor import (
    HealthMonitor, HealthStatus, AlertLevel, HealthCheckResult, Alert,
    PortfolioValueHistory
)
from src.models.data_models import PortfolioValue


class TestHealthMonitor(unittest.TestCase):
    """Test cases for HealthMonitor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.health_monitor = HealthMonitor(data_dir=self.temp_dir)
        
        # Create test portfolio value
        self.test_portfolio = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=1000.0,
            asset_breakdown={'BTC': 500.0, 'ETH': 300.0, 'BNB': 200.0},
            conversion_failures=[]
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_health_monitor_initialization(self):
        """Test health monitor initialization."""
        self.assertIsInstance(self.health_monitor, HealthMonitor)
        self.assertTrue(Path(self.temp_dir).exists())
        self.assertEqual(self.health_monitor.data_dir, Path(self.temp_dir))
    
    def test_portfolio_value_validation_normal(self):
        """Test portfolio value validation with normal values."""
        # First value - should be valid
        is_valid, warnings = self.health_monitor.validate_portfolio_value(self.test_portfolio)
        self.assertTrue(is_valid)
        self.assertEqual(len(warnings), 0)
        
        # Second value with small change - should be valid
        second_portfolio = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=1050.0,  # 5% increase
            asset_breakdown={'BTC': 525.0, 'ETH': 315.0, 'BNB': 210.0},
            conversion_failures=[]
        )
        
        is_valid, warnings = self.health_monitor.validate_portfolio_value(second_portfolio)
        self.assertTrue(is_valid)
        self.assertEqual(len(warnings), 0)
    
    def test_portfolio_value_validation_large_change(self):
        """Test portfolio value validation with large changes."""
        # First value
        self.health_monitor.validate_portfolio_value(self.test_portfolio)
        
        # Second value with large change - should trigger warning
        large_change_portfolio = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=1300.0,  # 30% increase (above 20% threshold)
            asset_breakdown={'BTC': 650.0, 'ETH': 390.0, 'BNB': 260.0},
            conversion_failures=[]
        )
        
        with patch.object(self.health_monitor, '_send_alert') as mock_send_alert:
            is_valid, warnings = self.health_monitor.validate_portfolio_value(large_change_portfolio)
            
            self.assertTrue(is_valid)  # Still valid, just warning
            self.assertGreater(len(warnings), 0)
            self.assertIn("Large portfolio change detected", warnings[0])
            mock_send_alert.assert_called_once()
    
    def test_portfolio_value_validation_zero_value(self):
        """Test portfolio value validation with zero value."""
        # First value
        self.health_monitor.validate_portfolio_value(self.test_portfolio)
        
        # Zero value - should trigger critical alert
        zero_portfolio = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=0.0,
            asset_breakdown={},
            conversion_failures=[]
        )
        
        with patch.object(self.health_monitor, '_send_alert') as mock_send_alert:
            is_valid, warnings = self.health_monitor.validate_portfolio_value(zero_portfolio)
            
            self.assertFalse(is_valid)
            self.assertGreater(len(warnings), 0)
            self.assertIn("Portfolio value dropped to zero", warnings[0])
            mock_send_alert.assert_called_once()
            
            # Check that critical alert was sent
            alert_call = mock_send_alert.call_args[0][0]
            self.assertEqual(alert_call.level, AlertLevel.CRITICAL)
    
    def test_portfolio_history_persistence(self):
        """Test portfolio history saving and loading."""
        # Add some portfolio values
        portfolios = [
            PortfolioValue(
                timestamp=datetime.now() - timedelta(days=2),
                total_usdt=900.0,
                asset_breakdown={},
                conversion_failures=[]
            ),
            PortfolioValue(
                timestamp=datetime.now() - timedelta(days=1),
                total_usdt=950.0,
                asset_breakdown={},
                conversion_failures=[]
            ),
            self.test_portfolio
        ]
        
        for portfolio in portfolios:
            self.health_monitor.validate_portfolio_value(portfolio)
        
        # Load history and verify
        history = self.health_monitor._load_portfolio_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0].value, 900.0)
        self.assertEqual(history[1].value, 950.0)
        self.assertEqual(history[2].value, 1000.0)
        
        # Check change calculations
        self.assertIsNotNone(history[1].change_percent)
        self.assertIsNotNone(history[2].change_percent)
    
    def test_execution_metrics_collection(self):
        """Test execution metrics collection and storage."""
        test_metrics = {
            'execution_duration_seconds': 45.5,
            'total_api_calls': 10,
            'api_calls_by_service': {'binance': 8, 'google_sheets': 2},
            'assets_processed': 5,
            'conversion_failures': 1,
            'portfolio_value_usdt': 1000.0,
            'errors_count': 0,
            'success': True
        }
        
        self.health_monitor.collect_execution_metrics(test_metrics)
        
        # Verify metrics file was created
        metrics_file = Path(self.temp_dir) / "execution_metrics.json"
        self.assertTrue(metrics_file.exists())
        
        # Load and verify metrics
        with open(metrics_file, 'r') as f:
            saved_metrics = json.load(f)
        
        self.assertEqual(len(saved_metrics), 1)
        self.assertEqual(saved_metrics[0]['execution_duration_seconds'], 45.5)
        self.assertEqual(saved_metrics[0]['success'], True)
    
    def test_health_checks_basic(self):
        """Test basic health checks."""
        # Mock environment variables
        with patch.dict(os.environ, {
            'BINANCE_API_KEY': 'test_key',
            'BINANCE_API_SECRET': 'test_secret',
            'GOOGLE_SERVICE_ACCOUNT_PATH': '/tmp/test.json',
            'GOOGLE_SPREADSHEET_ID': 'test_sheet_id'
        }):
            # Create mock service account file
            service_account_file = Path('/tmp/test.json')
            service_account_file.write_text('{"type": "service_account"}')
            
            try:
                health_report = self.health_monitor.run_health_checks()
                
                self.assertIn('timestamp', health_report)
                self.assertIn('overall_status', health_report)
                self.assertIn('checks', health_report)
                self.assertIn('summary', health_report)
                
                # Should have multiple checks
                self.assertGreater(len(health_report['checks']), 3)
                
                # Check that we have expected check names
                check_names = [check['name'] for check in health_report['checks']]
                self.assertIn('Configuration', check_names)
                self.assertIn('System Resources', check_names)
                
            finally:
                service_account_file.unlink(missing_ok=True)
    
    def test_health_checks_missing_config(self):
        """Test health checks with missing configuration."""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            health_report = self.health_monitor.run_health_checks()
            
            # Should report critical status due to missing config
            self.assertEqual(health_report['overall_status'], HealthStatus.CRITICAL.value)
            
            # Find configuration check
            config_check = None
            for check in health_report['checks']:
                if check['name'] == 'Configuration':
                    config_check = check
                    break
            
            self.assertIsNotNone(config_check)
            self.assertEqual(config_check['status'], HealthStatus.CRITICAL.value)
    
    def test_alert_creation_and_storage(self):
        """Test alert creation and storage."""
        test_alert = Alert(
            level=AlertLevel.WARNING,
            title="Test Alert",
            message="This is a test alert",
            details={'test_key': 'test_value'}
        )
        
        with patch.object(self.health_monitor, '_send_email_alert'):
            self.health_monitor._send_alert(test_alert)
        
        # Verify alert was saved
        alerts_file = Path(self.temp_dir) / "alerts.json"
        self.assertTrue(alerts_file.exists())
        
        with open(alerts_file, 'r') as f:
            saved_alerts = json.load(f)
        
        self.assertEqual(len(saved_alerts), 1)
        self.assertEqual(saved_alerts[0]['title'], "Test Alert")
        self.assertEqual(saved_alerts[0]['level'], AlertLevel.WARNING.value)
    
    def test_recent_alerts_retrieval(self):
        """Test retrieval of recent alerts."""
        # Create alerts with different timestamps
        old_alert = Alert(
            level=AlertLevel.INFO,
            title="Old Alert",
            message="This is an old alert",
            timestamp=datetime.now() - timedelta(days=2)
        )
        
        recent_alert = Alert(
            level=AlertLevel.WARNING,
            title="Recent Alert",
            message="This is a recent alert",
            timestamp=datetime.now() - timedelta(hours=1)
        )
        
        with patch.object(self.health_monitor, '_send_email_alert'):
            self.health_monitor._send_alert(old_alert)
            self.health_monitor._send_alert(recent_alert)
        
        # Get recent alerts (last 24 hours)
        recent_alerts = self.health_monitor.get_recent_alerts(hours=24)
        
        self.assertEqual(len(recent_alerts), 1)
        self.assertEqual(recent_alerts[0]['title'], "Recent Alert")
    
    @patch('smtplib.SMTP')
    def test_email_alert_sending(self, mock_smtp):
        """Test email alert sending functionality."""
        # Configure email settings
        self.health_monitor.smtp_server = 'smtp.test.com'
        self.health_monitor.smtp_username = 'test@test.com'
        self.health_monitor.smtp_password = 'test_password'
        self.health_monitor.alert_email_to = 'alerts@test.com'
        self.health_monitor.email_enabled = True
        
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        test_alert = Alert(
            level=AlertLevel.CRITICAL,
            title="Test Critical Alert",
            message="This is a test critical alert"
        )
        
        self.health_monitor._send_email_alert(test_alert)
        
        # Verify SMTP methods were called
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@test.com', 'test_password')
        mock_server.send_message.assert_called_once()
    
    def test_portfolio_trend_analysis(self):
        """Test portfolio trend analysis for warnings."""
        # Create declining portfolio trend
        base_time = datetime.now() - timedelta(days=7)
        declining_portfolios = []
        
        for i in range(7):
            portfolio = PortfolioValue(
                timestamp=base_time + timedelta(days=i),
                total_usdt=1000.0 - (i * 50),  # Declining by $50 each day
                asset_breakdown={},
                conversion_failures=[]
            )
            declining_portfolios.append(portfolio)
        
        # Add portfolios to history
        for portfolio in declining_portfolios:
            self.health_monitor.validate_portfolio_value(portfolio)
        
        # Load history and analyze trends
        history = self.health_monitor._load_portfolio_history()
        warnings = self.health_monitor._analyze_portfolio_trends(history)
        
        # Should detect declining trend
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any("declining" in warning.lower() for warning in warnings))
    
    def test_health_status_persistence(self):
        """Test health status saving and loading."""
        # Run health checks to generate status
        with patch.dict(os.environ, {
            'BINANCE_API_KEY': 'test_key',
            'BINANCE_API_SECRET': 'test_secret',
            'GOOGLE_SERVICE_ACCOUNT_PATH': '/tmp/test.json',
            'GOOGLE_SPREADSHEET_ID': 'test_sheet_id'
        }):
            service_account_file = Path('/tmp/test.json')
            service_account_file.write_text('{"type": "service_account"}')
            
            try:
                self.health_monitor.run_health_checks()
                
                # Load saved health status
                saved_status = self.health_monitor.get_health_status()
                
                self.assertIn('timestamp', saved_status)
                self.assertIn('overall_status', saved_status)
                
            finally:
                service_account_file.unlink(missing_ok=True)
    
    def test_performance_metrics_alerting(self):
        """Test performance metrics alerting for slow execution."""
        # Set low threshold for testing
        self.health_monitor.max_execution_time = 30
        
        slow_metrics = {
            'execution_duration_seconds': 45.0,  # Above threshold
            'total_api_calls': 5,
            'errors_count': 0,
            'success': True
        }
        
        with patch.object(self.health_monitor, '_send_alert') as mock_send_alert:
            self.health_monitor.collect_execution_metrics(slow_metrics)
            
            # Should send alert for slow execution
            mock_send_alert.assert_called()
            alert_call = mock_send_alert.call_args[0][0]
            self.assertEqual(alert_call.level, AlertLevel.WARNING)
            self.assertIn("Slow Execution", alert_call.title)


class TestHealthCheckResult(unittest.TestCase):
    """Test cases for HealthCheckResult class."""
    
    def test_health_check_result_creation(self):
        """Test health check result creation and serialization."""
        result = HealthCheckResult(
            name="Test Check",
            status=HealthStatus.HEALTHY,
            message="All good",
            details={'key': 'value'}
        )
        
        self.assertEqual(result.name, "Test Check")
        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertEqual(result.message, "All good")
        self.assertEqual(result.details['key'], 'value')
        
        # Test serialization
        result_dict = result.to_dict()
        self.assertEqual(result_dict['name'], "Test Check")
        self.assertEqual(result_dict['status'], HealthStatus.HEALTHY.value)
        self.assertIn('timestamp', result_dict)


class TestAlert(unittest.TestCase):
    """Test cases for Alert class."""
    
    def test_alert_creation(self):
        """Test alert creation and serialization."""
        alert = Alert(
            level=AlertLevel.CRITICAL,
            title="Critical Issue",
            message="Something went wrong",
            details={'error_code': 500}
        )
        
        self.assertEqual(alert.level, AlertLevel.CRITICAL)
        self.assertEqual(alert.title, "Critical Issue")
        self.assertEqual(alert.message, "Something went wrong")
        self.assertEqual(alert.details['error_code'], 500)
        
        # Test serialization
        alert_dict = alert.to_dict()
        self.assertEqual(alert_dict['level'], AlertLevel.CRITICAL.value)
        self.assertEqual(alert_dict['title'], "Critical Issue")
        self.assertIn('timestamp', alert_dict)


class TestPortfolioValueHistory(unittest.TestCase):
    """Test cases for PortfolioValueHistory class."""
    
    def test_portfolio_value_history_creation(self):
        """Test portfolio value history creation and serialization."""
        history = PortfolioValueHistory(
            timestamp=datetime.now(),
            value=1000.0,
            change_percent=5.0,
            change_absolute=50.0
        )
        
        self.assertEqual(history.value, 1000.0)
        self.assertEqual(history.change_percent, 5.0)
        self.assertEqual(history.change_absolute, 50.0)
        
        # Test serialization
        history_dict = history.to_dict()
        self.assertEqual(history_dict['value'], 1000.0)
        self.assertEqual(history_dict['change_percent'], 5.0)
        self.assertIn('timestamp', history_dict)


if __name__ == '__main__':
    unittest.main()