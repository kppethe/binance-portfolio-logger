#!/usr/bin/env python3
"""
Demo script showing how to use the ErrorHandler for portfolio logging.

This script demonstrates the key features of the ErrorHandler:
- Execution tracking
- API error handling
- Performance metrics
- Log sanitization
- Structured logging
"""

import time
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.error_handler import ErrorHandler, ErrorCategory


def simulate_portfolio_logging():
    """Simulate a portfolio logging execution with the ErrorHandler."""
    
    # Initialize error handler (in production, this would be /var/log/binance-portfolio/portfolio.log)
    log_file = "logs/demo_portfolio.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    error_handler = ErrorHandler(log_file)
    
    try:
        # Start execution tracking
        error_handler.log_execution_start()
        
        # Simulate configuration loading with sensitive data
        error_handler.log_info("Loading configuration from environment variables")
        config_message = 'Configuration loaded: api_key="sk_live_demo123456789012345678901234", spreadsheet_id="1ABC123XYZ"'
        error_handler.log_info(config_message)  # This will be sanitized
        
        # Simulate successful API calls
        error_handler.log_info("Connecting to Binance API...")
        time.sleep(0.1)  # Simulate network delay
        error_handler.log_api_call('binance', 'get_account_info', True, 0.150)
        
        error_handler.log_info("Fetching account balances...")
        time.sleep(0.2)
        error_handler.log_api_call('binance', 'get_balances', True, 0.200)
        
        error_handler.log_info("Retrieving current market prices...")
        time.sleep(0.3)
        error_handler.log_api_call('binance', 'get_all_prices', True, 0.300)
        
        # Simulate some warnings
        error_handler.log_warning("Asset DOGE has very low balance (0.001), including in calculations", ErrorCategory.DATA_PROCESSING)
        error_handler.log_warning("Asset XRP conversion path not optimal, using BTC pair", ErrorCategory.DATA_PROCESSING)
        
        # Simulate Google Sheets logging
        error_handler.log_info("Logging portfolio data to Google Sheets...")
        time.sleep(0.1)
        error_handler.log_api_call('google_sheets', 'append_row', True, 0.450)
        
        # Complete successfully
        portfolio_value = 3247.89
        assets_processed = 8
        conversion_failures = 1
        
        error_handler.log_execution_success(portfolio_value, assets_processed, conversion_failures)
        
        print(f"✅ Portfolio logging completed successfully!")
        print(f"💰 Portfolio value: ${portfolio_value:.2f} USDT")
        print(f"📊 Assets processed: {assets_processed}")
        print(f"⚠️  Conversion failures: {conversion_failures}")
        
        # Show metrics
        metrics = error_handler.get_execution_metrics()
        print(f"⏱️  Execution time: {metrics.execution_duration:.3f}s")
        print(f"🔗 Total API calls: {metrics.total_api_calls}")
        print(f"📝 Log files created:")
        print(f"   - Main log: {log_file}")
        print(f"   - Metrics log: {log_file.replace('.log', '_metrics.log')}")
        
    except Exception as e:
        # Handle any errors
        error_handler.log_execution_failure(e, ErrorCategory.SYSTEM)
        print(f"❌ Portfolio logging failed: {str(e)}")
        
        # Show error metrics
        metrics = error_handler.get_execution_metrics()
        print(f"⏱️  Execution time: {metrics.execution_duration:.3f}s")
        print(f"🚨 Errors encountered: {len(metrics.errors_encountered)}")


def simulate_api_error_handling():
    """Demonstrate API error handling and retry logic."""
    
    log_file = "logs/demo_api_errors.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    error_handler = ErrorHandler(log_file)
    
    error_handler.log_execution_start()
    
    print("\n🔄 Demonstrating API error handling...")
    
    # Simulate rate limit error (should retry)
    rate_limit_error = Exception("Rate limit exceeded - 429 Too Many Requests")
    should_retry = error_handler.handle_api_error(rate_limit_error, 'binance', 'get_prices')
    print(f"Rate limit error - Retry recommended: {should_retry}")
    
    # Simulate authentication error (should not retry)
    auth_error = Exception("Invalid API signature - 401 Unauthorized")
    should_retry = error_handler.handle_api_error(auth_error, 'binance', 'get_balances')
    print(f"Authentication error - Retry recommended: {should_retry}")
    
    # Simulate network error (should retry)
    network_error = Exception("Connection timeout after 30 seconds")
    should_retry = error_handler.handle_api_error(network_error, 'google_sheets', 'append_data')
    print(f"Network error - Retry recommended: {should_retry}")
    
    # Complete with failure
    final_error = ValueError("Too many consecutive API failures")
    error_handler.log_execution_failure(final_error, ErrorCategory.API_ERROR)
    
    print(f"📝 Error log created: {log_file.replace('.log', '_errors.log')}")


def demonstrate_log_sanitization():
    """Show how sensitive data is sanitized in logs."""
    
    log_file = "logs/demo_sanitization.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    error_handler = ErrorHandler(log_file)
    
    print("\n🔒 Demonstrating log sanitization...")
    
    # These messages contain sensitive data that will be sanitized
    sensitive_messages = [
        'Binance API configured with api_key="sk_live_abcdef123456789012345678901234"',
        'Google credentials loaded from file with client_secret="GOCSPX-xyz123456789012345678901234"',
        'Database connection: password="mySecretPassword123" for user admin',
        'JWT token received: token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"'
    ]
    
    for message in sensitive_messages:
        error_handler.log_info(message)
        print(f"Original: {message}")
        sanitized = error_handler._sanitize_message(message)
        print(f"Sanitized: {sanitized}")
        print()
    
    print(f"📝 Sanitized logs written to: {log_file}")


def create_logrotate_config_demo():
    """Demonstrate logrotate configuration creation."""
    
    log_file = "logs/demo_portfolio.log"
    error_handler = ErrorHandler(log_file)
    
    print("\n🔄 Creating logrotate configuration...")
    
    config_path = "logs/demo_logrotate_config"
    config_content = error_handler.create_log_rotation_config(config_path)
    
    print("Logrotate configuration created:")
    print("=" * 50)
    print(config_content)
    print("=" * 50)
    print(f"Configuration saved to: {config_path}")


if __name__ == "__main__":
    print("🚀 ErrorHandler Demo - Binance Portfolio Logger")
    print("=" * 60)
    
    # Demo 1: Successful portfolio logging
    print("\n1️⃣  Successful Portfolio Logging Workflow")
    print("-" * 40)
    simulate_portfolio_logging()
    
    # Demo 2: API error handling
    print("\n2️⃣  API Error Handling")
    print("-" * 40)
    simulate_api_error_handling()
    
    # Demo 3: Log sanitization
    print("\n3️⃣  Log Sanitization")
    print("-" * 40)
    demonstrate_log_sanitization()
    
    # Demo 4: Logrotate configuration
    print("\n4️⃣  Logrotate Configuration")
    print("-" * 40)
    create_logrotate_config_demo()
    
    print("\n✨ Demo completed! Check the 'logs/' directory for generated log files.")
    print("\nKey features demonstrated:")
    print("  ✅ Execution tracking with start/success/failure logging")
    print("  ✅ API call tracking and error categorization")
    print("  ✅ Performance metrics collection")
    print("  ✅ Sensitive data sanitization")
    print("  ✅ Structured logging with rotation")
    print("  ✅ Comprehensive error handling")