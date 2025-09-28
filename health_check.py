#!/usr/bin/env python3
"""
Health check script for Binance Portfolio Logger.

This script can be run independently to check the health status of the
portfolio logger system. It's designed to be used by monitoring systems
or run manually for troubleshooting.

Usage:
    python health_check.py [--json] [--verbose] [--check-api]
    
Exit codes:
    0: All systems healthy
    1: Warnings detected
    2: Critical issues detected
    3: Script error
"""

import argparse
import json
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from src.utils.health_monitor import HealthMonitor, HealthStatus
except ImportError as e:
    print(f"ERROR: Failed to import health monitor: {e}")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(3)


def main():
    """Main entry point for health check script."""
    parser = argparse.ArgumentParser(
        description='Health check script for Binance Portfolio Logger',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0: All systems healthy
  1: Warnings detected  
  2: Critical issues detected
  3: Script error

Examples:
  python health_check.py                    # Basic health check
  python health_check.py --json             # JSON output for monitoring
  python health_check.py --verbose          # Detailed output
  python health_check.py --check-api        # Include API connectivity test
        """
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed information for each check'
    )
    
    parser.add_argument(
        '--check-api',
        action='store_true',
        help='Include API connectivity test (slower)'
    )
    
    parser.add_argument(
        '--data-dir',
        type=str,
        default='/var/log/binance-portfolio',
        help='Directory for monitoring data (default: /var/log/binance-portfolio)'
    )
    
    args = parser.parse_args()
    
    try:
        # Set environment variable for API check if requested
        if args.check_api:
            import os
            os.environ['HEALTH_CHECK_API'] = 'true'
        
        # Initialize health monitor
        health_monitor = HealthMonitor(data_dir=args.data_dir)
        
        # Run health checks
        health_report = health_monitor.run_health_checks()
        
        # Determine exit code
        overall_status = health_report['overall_status']
        if overall_status == HealthStatus.HEALTHY.value:
            exit_code = 0
        elif overall_status == HealthStatus.WARNING.value:
            exit_code = 1
        elif overall_status == HealthStatus.CRITICAL.value:
            exit_code = 2
        else:
            exit_code = 1  # Unknown status treated as warning
        
        # Output results
        if args.json:
            print(json.dumps(health_report, indent=2))
        else:
            print_human_readable_report(health_report, args.verbose)
        
        return exit_code
        
    except Exception as e:
        error_msg = f"Health check script error: {e}"
        
        if args.json:
            error_report = {
                'timestamp': health_report.get('timestamp', 'unknown') if 'health_report' in locals() else 'unknown',
                'overall_status': HealthStatus.CRITICAL.value,
                'error': error_msg,
                'checks': []
            }
            print(json.dumps(error_report, indent=2))
        else:
            print(f"ERROR: {error_msg}")
        
        return 3


def print_human_readable_report(health_report, verbose=False):
    """Print health report in human-readable format."""
    overall_status = health_report['overall_status']
    timestamp = health_report['timestamp']
    
    # Status emoji mapping
    status_emoji = {
        HealthStatus.HEALTHY.value: '✅',
        HealthStatus.WARNING.value: '⚠️',
        HealthStatus.CRITICAL.value: '❌',
        HealthStatus.UNKNOWN.value: '❓'
    }
    
    # Print header
    emoji = status_emoji.get(overall_status, '❓')
    print(f"\n{emoji} Binance Portfolio Logger Health Check")
    print(f"Overall Status: {overall_status.upper()}")
    print(f"Timestamp: {timestamp}")
    print("-" * 50)
    
    # Print individual checks
    for check in health_report['checks']:
        check_emoji = status_emoji.get(check['status'], '❓')
        print(f"{check_emoji} {check['name']}: {check['status'].upper()}")
        
        if verbose or check['status'] != HealthStatus.HEALTHY.value:
            print(f"   Message: {check['message']}")
            
            if verbose and check.get('details'):
                print(f"   Details: {json.dumps(check['details'], indent=6)}")
        
        print()
    
    # Print summary
    summary = health_report.get('summary', {})
    if summary:
        print("Summary:")
        print(f"  Total checks: {summary.get('total_checks', 0)}")
        
        status_counts = summary.get('status_counts', {})
        for status, count in status_counts.items():
            if count > 0:
                emoji = status_emoji.get(status, '❓')
                print(f"  {emoji} {status.title()}: {count}")
        
        critical_issues = summary.get('critical_issues', [])
        if critical_issues:
            print(f"  Critical issues: {', '.join(critical_issues)}")
        
        warnings = summary.get('warnings', [])
        if warnings:
            print(f"  Warnings: {', '.join(warnings)}")
    
    print()


if __name__ == '__main__':
    sys.exit(main())