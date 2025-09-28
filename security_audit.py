#!/usr/bin/env python3
"""
Security audit script for Binance Portfolio Logger.

This script performs comprehensive security validation including:
- Environment variable validation
- File permission checks
- Credential format validation
- API access testing
- Configuration security audit

Usage:
    python security_audit.py [--verbose] [--json]
"""
import sys
import json
import argparse
import logging
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils.security_validator import SecurityValidator, SecurityValidationError


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def print_audit_results(results: dict, json_output: bool = False) -> None:
    """Print audit results in human-readable or JSON format."""
    if json_output:
        print(json.dumps(results, indent=2))
        return
    
    print("=" * 60)
    print("BINANCE PORTFOLIO LOGGER - SECURITY AUDIT REPORT")
    print("=" * 60)
    print(f"Audit Timestamp: {results['timestamp']}")
    print(f"Overall Status: {results['overall_status']}")
    print()
    
    # Print individual checks
    print("SECURITY CHECKS:")
    print("-" * 40)
    for check in results['checks']:
        status_symbol = "✓" if check['status'] == 'PASS' else "✗" if check['status'] == 'FAIL' else "⚠"
        print(f"{status_symbol} {check['name']}: {check['status']}")
        print(f"  {check['message']}")
        print()
    
    # Print warnings if any
    if results['warnings']:
        print("WARNINGS:")
        print("-" * 40)
        for warning in results['warnings']:
            print(f"⚠ {warning}")
        print()
    
    # Print errors if any
    if results['errors']:
        print("ERRORS:")
        print("-" * 40)
        for error in results['errors']:
            print(f"✗ {error}")
        print()
    
    # Print recommendations
    print("SECURITY RECOMMENDATIONS:")
    print("-" * 40)
    
    if results['overall_status'] == 'PASS':
        print("✓ All security checks passed!")
        print("✓ Your configuration appears to be secure.")
    else:
        print("✗ Security issues detected. Please address the errors above.")
    
    print()
    print("Additional Security Best Practices:")
    print("• Use read-only API keys when possible")
    print("• Regularly rotate API keys and credentials")
    print("• Monitor log files for suspicious activity")
    print("• Keep system and dependencies updated")
    print("• Use firewall rules to restrict network access")
    print("• Enable log rotation to prevent disk space issues")
    print("• Consider using IP whitelisting for API access")


def main():
    """Main function for security audit script."""
    parser = argparse.ArgumentParser(
        description="Security audit script for Binance Portfolio Logger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python security_audit.py                    # Run basic audit
    python security_audit.py --verbose          # Run with detailed logging
    python security_audit.py --json             # Output results as JSON
    python security_audit.py --verbose --json   # Detailed logging + JSON output
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging output'
    )
    
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='Output results in JSON format'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting security audit...")
        
        # Initialize security validator
        validator = SecurityValidator()
        
        # Run comprehensive security audit
        audit_results = validator.run_security_audit()
        
        # Print results
        print_audit_results(audit_results, args.json)
        
        # Exit with appropriate code
        if audit_results['overall_status'] == 'PASS':
            logger.info("Security audit completed successfully")
            sys.exit(0)
        else:
            logger.error("Security audit failed - issues detected")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Security audit interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Security audit failed with unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()