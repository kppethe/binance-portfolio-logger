#!/usr/bin/env python3
"""
Health monitoring system demonstration.

This script demonstrates the health monitoring capabilities of the
Binance Portfolio Logger, including portfolio value validation,
health checks, and alerting.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.health_monitor import HealthMonitor, AlertLevel
from src.models.data_models import PortfolioValue


def demo_portfolio_validation():
    """Demonstrate portfolio value validation."""
    print("=" * 60)
    print("PORTFOLIO VALUE VALIDATION DEMO")
    print("=" * 60)
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        health_monitor = HealthMonitor(data_dir=temp_dir)
        
        print("1. Adding initial portfolio value...")
        initial_portfolio = PortfolioValue(
            timestamp=datetime.now() - timedelta(hours=1),
            total_usdt=1000.0,
            asset_breakdown={'BTC': 600.0, 'ETH': 400.0},
            conversion_failures=[]
        )
        
        is_valid, warnings = health_monitor.validate_portfolio_value(initial_portfolio)
        print(f"   Valid: {is_valid}, Warnings: {len(warnings)}")
        
        print("\n2. Adding portfolio with normal change (5%)...")
        normal_change_portfolio = PortfolioValue(
            timestamp=datetime.now() - timedelta(minutes=30),
            total_usdt=1050.0,  # 5% increase
            asset_breakdown={'BTC': 630.0, 'ETH': 420.0},
            conversion_failures=[]
        )
        
        is_valid, warnings = health_monitor.validate_portfolio_value(normal_change_portfolio)
        print(f"   Valid: {is_valid}, Warnings: {len(warnings)}")
        
        print("\n3. Adding portfolio with large change (25%)...")
        large_change_portfolio = PortfolioValue(
            timestamp=datetime.now(),
            total_usdt=1312.5,  # 25% increase (above 20% threshold)
            asset_breakdown={'BTC': 787.5, 'ETH': 525.0},
            conversion_failures=[]
        )
        
        is_valid, warnings = health_monitor.validate_portfolio_value(large_change_portfolio)
        print(f"   Valid: {is_valid}, Warnings: {len(warnings)}")
        if warnings:
            print(f"   Warning: {warnings[0]}")
        
        print("\n4. Checking portfolio history...")
        history = health_monitor._load_portfolio_history()
        print(f"   History entries: {len(history)}")
        for i, h in enumerate(history, 1):
            change_str = f" ({h.change_percent:+.1f}%)" if h.change_percent else ""
            print(f"   {i}. ${h.value:.2f}{change_str}")
        
        print("\n5. Checking alerts...")
        alerts = health_monitor.get_recent_alerts(hours=1)
        print(f"   Recent alerts: {len(alerts)}")
        for alert in alerts:
            print(f"   - [{alert['level'].upper()}] {alert['title']}")


def demo_health_checks():
    """Demonstrate health check system."""
    print("\n" + "=" * 60)
    print("HEALTH CHECK SYSTEM DEMO")
    print("=" * 60)
    
    # Set up minimal environment for demo
    demo_env = {
        'BINANCE_API_KEY': 'demo_api_key_1234567890',
        'BINANCE_API_SECRET': 'demo_api_secret_1234567890',
        'GOOGLE_SPREADSHEET_ID': 'demo_spreadsheet_id'
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock service account file
        service_account_file = Path(temp_dir) / 'service_account.json'
        service_account_data = {
            "type": "service_account",
            "project_id": "demo-project",
            "client_email": "demo@demo-project.iam.gserviceaccount.com"
        }
        
        with open(service_account_file, 'w') as f:
            json.dump(service_account_data, f)
        
        demo_env['GOOGLE_SERVICE_ACCOUNT_PATH'] = str(service_account_file)
        
        # Set environment variables
        original_env = {}
        for key, value in demo_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            health_monitor = HealthMonitor(data_dir=temp_dir)
            
            print("Running health checks...")
            health_report = health_monitor.run_health_checks()
            
            print(f"\nOverall Status: {health_report['overall_status'].upper()}")
            print(f"Total Checks: {health_report['summary']['total_checks']}")
            
            print("\nIndividual Checks:")
            for check in health_report['checks']:
                status_icon = "✅" if check['status'] == 'healthy' else "⚠️" if check['status'] == 'warning' else "❌"
                print(f"  {status_icon} {check['name']}: {check['status'].upper()}")
                if check['status'] != 'healthy':
                    print(f"    └─ {check['message']}")
            
            print(f"\nHealth report saved to: {health_monitor.health_file}")
            
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def demo_execution_metrics():
    """Demonstrate execution metrics collection."""
    print("\n" + "=" * 60)
    print("EXECUTION METRICS DEMO")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        health_monitor = HealthMonitor(data_dir=temp_dir)
        
        print("1. Collecting sample execution metrics...")
        
        # Simulate multiple execution metrics
        sample_metrics = [
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
                'execution_duration_seconds': 32.1,
                'total_api_calls': 10,
                'api_calls_by_service': {'binance': 8, 'google_sheets': 2},
                'assets_processed': 4,
                'conversion_failures': 1,
                'portfolio_value_usdt': 1180.0,
                'errors_count': 0,
                'success': True
            },
            {
                'execution_duration_seconds': 15.8,
                'total_api_calls': 5,
                'api_calls_by_service': {'binance': 3, 'google_sheets': 2},
                'assets_processed': 2,
                'conversion_failures': 0,
                'portfolio_value_usdt': 1220.0,
                'errors_count': 1,
                'success': False,
                'failure_reason': 'api_error'
            }
        ]
        
        for i, metrics in enumerate(sample_metrics, 1):
            print(f"   Collecting metrics for execution {i}...")
            health_monitor.collect_execution_metrics(metrics)
        
        print("\n2. Analyzing collected metrics...")
        metrics_file = health_monitor.data_dir / "execution_metrics.json"
        
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                saved_metrics = json.load(f)
            
            successful_runs = sum(1 for m in saved_metrics if m.get('success', False))
            avg_duration = sum(m.get('execution_duration_seconds', 0) for m in saved_metrics) / len(saved_metrics)
            avg_api_calls = sum(m.get('total_api_calls', 0) for m in saved_metrics) / len(saved_metrics)
            
            print(f"   Total executions: {len(saved_metrics)}")
            print(f"   Success rate: {successful_runs}/{len(saved_metrics)} ({successful_runs/len(saved_metrics)*100:.1f}%)")
            print(f"   Average duration: {avg_duration:.1f}s")
            print(f"   Average API calls: {avg_api_calls:.1f}")
            
            print("\n   Recent executions:")
            for i, metrics in enumerate(saved_metrics, 1):
                status_icon = "✅" if metrics.get('success', False) else "❌"
                duration = metrics.get('execution_duration_seconds', 0)
                portfolio_value = metrics.get('portfolio_value_usdt', 0)
                print(f"   {status_icon} Execution {i}: {duration:.1f}s, ${portfolio_value:.2f} USDT")


def demo_alerting_system():
    """Demonstrate alerting system."""
    print("\n" + "=" * 60)
    print("ALERTING SYSTEM DEMO")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        health_monitor = HealthMonitor(data_dir=temp_dir)
        
        print("1. Creating sample alerts...")
        
        # Create different types of alerts
        from src.utils.health_monitor import Alert
        
        alerts = [
            Alert(
                level=AlertLevel.INFO,
                title="System Started",
                message="Portfolio logger started successfully",
                details={'startup_time': datetime.now().isoformat()}
            ),
            Alert(
                level=AlertLevel.WARNING,
                title="High API Usage",
                message="API call count exceeded normal threshold",
                details={'api_calls': 15, 'threshold': 10}
            ),
            Alert(
                level=AlertLevel.CRITICAL,
                title="Portfolio Value Drop",
                message="Portfolio value dropped significantly",
                details={'previous_value': 1000.0, 'current_value': 700.0, 'change_percent': -30.0}
            )
        ]
        
        for alert in alerts:
            print(f"   Creating {alert.level.value} alert: {alert.title}")
            health_monitor._save_alert(alert)
        
        print("\n2. Retrieving recent alerts...")
        recent_alerts = health_monitor.get_recent_alerts(hours=24)
        
        print(f"   Found {len(recent_alerts)} recent alerts:")
        for alert in recent_alerts:
            level_icon = "ℹ️" if alert['level'] == 'info' else "⚠️" if alert['level'] == 'warning' else "❌"
            print(f"   {level_icon} [{alert['level'].upper()}] {alert['title']}")
            print(f"      Message: {alert['message']}")
        
        print(f"\n   Alerts saved to: {health_monitor.alerts_file}")


def main():
    """Run all monitoring system demonstrations."""
    print("🔍 BINANCE PORTFOLIO LOGGER - HEALTH MONITORING DEMO")
    print("This demo showcases the health monitoring and alerting capabilities.")
    print()
    
    try:
        demo_portfolio_validation()
        demo_health_checks()
        demo_execution_metrics()
        demo_alerting_system()
        
        print("\n" + "=" * 60)
        print("DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print()
        print("Key features demonstrated:")
        print("✅ Portfolio value validation with change detection")
        print("✅ Comprehensive health check system")
        print("✅ Execution metrics collection and analysis")
        print("✅ Multi-level alerting system")
        print()
        print("To use these features in production:")
        print("1. Run 'python health_check.py' for system health status")
        print("2. Run 'python monitoring_dashboard.py' for real-time monitoring")
        print("3. Configure email alerts via environment variables")
        print("4. Set up automated health checks in your monitoring system")
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())