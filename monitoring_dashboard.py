#!/usr/bin/env python3
"""
Monitoring dashboard for Binance Portfolio Logger.

This script provides a comprehensive view of the system's health status,
recent alerts, portfolio trends, and execution metrics.

Usage:
    python monitoring_dashboard.py [--refresh-interval SECONDS] [--json]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from src.utils.health_monitor import HealthMonitor, HealthStatus, AlertLevel
except ImportError as e:
    print(f"ERROR: Failed to import health monitor: {e}")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(1)


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def format_timestamp(timestamp_str):
    """Format timestamp for display."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp_str


def format_duration(seconds):
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def get_status_emoji(status):
    """Get emoji for status."""
    emoji_map = {
        HealthStatus.HEALTHY.value: '✅',
        HealthStatus.WARNING.value: '⚠️',
        HealthStatus.CRITICAL.value: '❌',
        HealthStatus.UNKNOWN.value: '❓',
        AlertLevel.INFO.value: 'ℹ️',
        AlertLevel.WARNING.value: '⚠️',
        AlertLevel.CRITICAL.value: '❌'
    }
    return emoji_map.get(status, '❓')


def display_dashboard(health_monitor, show_json=False):
    """Display the monitoring dashboard."""
    if not show_json:
        clear_screen()
        print("=" * 80)
        print("🔍 BINANCE PORTFOLIO LOGGER - MONITORING DASHBOARD")
        print("=" * 80)
        print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    # Get current health status
    health_status = health_monitor.get_health_status()
    
    # Get recent alerts
    recent_alerts = health_monitor.get_recent_alerts(hours=24)
    
    # Get execution metrics
    metrics_file = health_monitor.data_dir / "execution_metrics.json"
    execution_metrics = []
    if metrics_file.exists():
        try:
            with open(metrics_file, 'r') as f:
                execution_metrics = json.load(f)[-10:]  # Last 10 executions
        except:
            pass
    
    # Get portfolio history
    portfolio_history = health_monitor._load_portfolio_history()
    recent_history = portfolio_history[-7:] if len(portfolio_history) > 7 else portfolio_history
    
    if show_json:
        dashboard_data = {
            'timestamp': datetime.now().isoformat(),
            'health_status': health_status,
            'recent_alerts': recent_alerts,
            'execution_metrics': execution_metrics,
            'portfolio_history': [h.to_dict() for h in recent_history]
        }
        print(json.dumps(dashboard_data, indent=2))
        return
    
    # Display health status
    print("🏥 SYSTEM HEALTH STATUS")
    print("-" * 40)
    
    overall_status = health_status.get('overall_status', 'unknown')
    status_emoji = get_status_emoji(overall_status)
    print(f"Overall Status: {status_emoji} {overall_status.upper()}")
    
    if 'checks' in health_status:
        print("\nHealth Checks:")
        for check in health_status['checks']:
            check_emoji = get_status_emoji(check['status'])
            print(f"  {check_emoji} {check['name']}: {check['status'].upper()}")
            if check['status'] != HealthStatus.HEALTHY.value:
                print(f"    └─ {check['message']}")
    
    print()
    
    # Display recent alerts
    print("🚨 RECENT ALERTS (Last 24 Hours)")
    print("-" * 40)
    
    if recent_alerts:
        for alert in recent_alerts[-5:]:  # Show last 5 alerts
            alert_emoji = get_status_emoji(alert['level'])
            timestamp = format_timestamp(alert['timestamp'])
            print(f"{alert_emoji} [{alert['level'].upper()}] {alert['title']}")
            print(f"    Time: {timestamp}")
            print(f"    Message: {alert['message']}")
            print()
    else:
        print("✅ No recent alerts")
        print()
    
    # Display execution metrics
    print("📊 EXECUTION METRICS (Last 10 Runs)")
    print("-" * 40)
    
    if execution_metrics:
        successful_runs = sum(1 for m in execution_metrics if m.get('success', False))
        avg_duration = sum(m.get('execution_duration_seconds', 0) for m in execution_metrics) / len(execution_metrics)
        avg_api_calls = sum(m.get('total_api_calls', 0) for m in execution_metrics) / len(execution_metrics)
        
        print(f"Success Rate: {successful_runs}/{len(execution_metrics)} ({successful_runs/len(execution_metrics)*100:.1f}%)")
        print(f"Average Duration: {format_duration(avg_duration)}")
        print(f"Average API Calls: {avg_api_calls:.1f}")
        print()
        
        print("Recent Executions:")
        for i, metrics in enumerate(execution_metrics[-5:], 1):
            status_icon = "✅" if metrics.get('success', False) else "❌"
            timestamp = format_timestamp(metrics.get('timestamp', ''))
            duration = format_duration(metrics.get('execution_duration_seconds', 0))
            portfolio_value = metrics.get('portfolio_value_usdt', 0)
            
            print(f"  {status_icon} Run {len(execution_metrics)-5+i}: {timestamp}")
            print(f"    Duration: {duration}, Portfolio: ${portfolio_value:.2f} USDT")
            
            if not metrics.get('success', False):
                failure_reason = metrics.get('failure_reason', 'unknown')
                print(f"    Failure: {failure_reason}")
        print()
    else:
        print("No execution metrics available")
        print()
    
    # Display portfolio trends
    print("📈 PORTFOLIO TRENDS (Last 7 Days)")
    print("-" * 40)
    
    if recent_history:
        current_value = recent_history[-1].value
        print(f"Current Value: ${current_value:.2f} USDT")
        
        if len(recent_history) > 1:
            previous_value = recent_history[0].value
            if previous_value > 0:
                change_percent = ((current_value - previous_value) / previous_value) * 100
                change_icon = "📈" if change_percent > 0 else "📉" if change_percent < 0 else "➡️"
                print(f"7-Day Change: {change_icon} {change_percent:+.2f}% (${current_value - previous_value:+.2f})")
            
            # Show trend
            print("\nRecent Values:")
            for i, history in enumerate(recent_history[-5:]):
                timestamp = history.timestamp.strftime('%m-%d %H:%M')
                change_str = ""
                if history.change_percent is not None:
                    change_str = f" ({history.change_percent:+.1f}%)"
                print(f"  {timestamp}: ${history.value:.2f}{change_str}")
        print()
    else:
        print("No portfolio history available")
        print()
    
    # Display system information
    print("💻 SYSTEM INFORMATION")
    print("-" * 40)
    
    # Check disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage(health_monitor.data_dir)
        free_percent = (free / total) * 100
        disk_icon = "💾" if free_percent > 15 else "⚠️" if free_percent > 5 else "❌"
        print(f"Disk Space: {disk_icon} {free_percent:.1f}% free ({free/(1024**3):.1f} GB)")
    except:
        print("Disk Space: ❓ Unable to check")
    
    # Check log files
    log_files = [
        health_monitor.data_dir / "portfolio.log",
        health_monitor.data_dir / "portfolio_errors.log",
        health_monitor.data_dir / "portfolio_metrics.log"
    ]
    
    accessible_logs = sum(1 for log_file in log_files if log_file.exists())
    log_icon = "📝" if accessible_logs == len(log_files) else "⚠️"
    print(f"Log Files: {log_icon} {accessible_logs}/{len(log_files)} accessible")
    
    print()
    print("=" * 80)
    print("Press Ctrl+C to exit")


def main():
    """Main entry point for monitoring dashboard."""
    parser = argparse.ArgumentParser(
        description='Monitoring dashboard for Binance Portfolio Logger',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python monitoring_dashboard.py                    # Show dashboard once
  python monitoring_dashboard.py --refresh 30      # Auto-refresh every 30 seconds
  python monitoring_dashboard.py --json            # Output JSON data
        """
    )
    
    parser.add_argument(
        '--refresh-interval',
        '--refresh',
        type=int,
        metavar='SECONDS',
        help='Auto-refresh interval in seconds (default: show once and exit)'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output data in JSON format'
    )
    
    parser.add_argument(
        '--data-dir',
        type=str,
        default='/var/log/binance-portfolio',
        help='Directory for monitoring data (default: /var/log/binance-portfolio)'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize health monitor
        health_monitor = HealthMonitor(data_dir=args.data_dir)
        
        if args.refresh_interval:
            # Continuous monitoring mode
            if args.json:
                print("ERROR: JSON mode cannot be used with refresh interval")
                return 1
            
            print(f"Starting monitoring dashboard with {args.refresh_interval}s refresh interval...")
            print("Press Ctrl+C to exit")
            time.sleep(2)
            
            try:
                while True:
                    display_dashboard(health_monitor, show_json=False)
                    time.sleep(args.refresh_interval)
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
                return 0
        else:
            # Single display mode
            display_dashboard(health_monitor, show_json=args.json)
            return 0
            
    except Exception as e:
        if args.json:
            error_data = {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            print(json.dumps(error_data, indent=2))
        else:
            print(f"ERROR: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())