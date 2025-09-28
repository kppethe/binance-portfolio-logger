#!/usr/bin/env python3
"""
Demo script for the main application orchestrator.

This script demonstrates how the main application coordinates all components
to execute the complete portfolio logging workflow.
"""
import os
import sys
import tempfile
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.main_application import MainApplication


def create_demo_environment():
    """Create a demo environment with mock credentials."""
    temp_dir = tempfile.mkdtemp()
    
    # Create mock service account file
    service_account_path = os.path.join(temp_dir, 'service_account.json')
    service_account_content = '''
    {
        "type": "service_account",
        "project_id": "demo-project",
        "private_key_id": "demo-key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\\ndemo-private-key\\n-----END PRIVATE KEY-----\\n",
        "client_email": "demo@demo-project.iam.gserviceaccount.com",
        "client_id": "demo-client-id",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
    '''
    
    with open(service_account_path, 'w') as f:
        f.write(service_account_content)
    
    # Set file permissions
    os.chmod(service_account_path, 0o600)
    
    # Set up demo environment variables
    demo_env = {
        'BINANCE_API_KEY': 'demo_api_key_12345678901234567890',
        'BINANCE_API_SECRET': 'demo_api_secret_12345678901234567890',
        'GOOGLE_SERVICE_ACCOUNT_PATH': service_account_path,
        'GOOGLE_SPREADSHEET_ID': 'demo_spreadsheet_id_12345',
        'GOOGLE_SHEET_NAME': 'Demo Portfolio',
        'LOG_FILE_PATH': os.path.join(temp_dir, 'demo_portfolio.log'),
        'EXECUTION_TIMEOUT_SECONDS': '30',
        'MAX_RETRIES': '2'
    }
    
    # Apply environment variables
    for key, value in demo_env.items():
        os.environ[key] = value
    
    return temp_dir


def demo_main_application():
    """Demonstrate the main application functionality."""
    print("=== Binance Portfolio Logger - Main Application Demo ===\n")
    
    # Create demo environment
    temp_dir = create_demo_environment()
    
    try:
        print("1. Testing Application Initialization")
        print("-" * 40)
        
        # Test dry run mode
        print("Testing dry-run mode (configuration validation)...")
        app = MainApplication()
        
        try:
            app._initialize_components()
            print("✓ Configuration validation would succeed with real credentials")
        except Exception as e:
            print(f"✗ Configuration validation failed (expected with demo credentials): {e}")
        
        print("\n2. Testing Command-Line Interface")
        print("-" * 40)
        
        # Test argument parsing
        from src.main_application import create_argument_parser
        
        parser = create_argument_parser()
        
        # Test various argument combinations
        test_args = [
            ['--timeout', '120'],
            ['--max-retries', '5'],
            ['--log-file', '/tmp/custom.log'],
            ['--dry-run'],
            ['--status']
        ]
        
        for args in test_args:
            try:
                parsed = parser.parse_args(args)
                print(f"✓ Arguments {args} parsed successfully")
            except SystemExit:
                # Expected for --help, --version, etc.
                print(f"✓ Arguments {args} handled correctly (system exit)")
        
        print("\n3. Testing Configuration Overrides")
        print("-" * 40)
        
        config_overrides = {
            'timeout': 90,
            'max_retries': 4,
            'log_file': '/tmp/override.log'
        }
        
        app_with_overrides = MainApplication(config_overrides)
        app_with_overrides._apply_config_overrides()
        
        print("✓ Configuration overrides applied:")
        print(f"  - Timeout: {os.environ.get('EXECUTION_TIMEOUT_SECONDS')}")
        print(f"  - Max retries: {os.environ.get('MAX_RETRIES')}")
        print(f"  - Log file: {os.environ.get('LOG_FILE_PATH')}")
        
        print("\n4. Testing Application Status")
        print("-" * 40)
        
        status = app.get_status()
        print("✓ Application status retrieved:")
        print(f"  - Timestamp: {status['timestamp']}")
        print(f"  - Shutdown requested: {status['shutdown_requested']}")
        print(f"  - Execution timeout: {status['execution_timeout']}")
        print(f"  - Components initialized: {status['components_initialized']}")
        
        print("\n5. Workflow Overview")
        print("-" * 40)
        
        print("The main application orchestrator coordinates the following workflow:")
        print("  1. Configuration → Load and validate all credentials and settings")
        print("  2. Balance Retrieval → Fetch account balances from Binance API")
        print("  3. Portfolio Calculation → Convert all assets to USDT values")
        print("  4. Data Logging → Append portfolio data to Google Sheets")
        print("  5. Cleanup → Perform graceful shutdown and resource cleanup")
        
        print("\nKey Features:")
        print("  ✓ Execution timeout handling with configurable limits")
        print("  ✓ Graceful shutdown on SIGINT/SIGTERM signals")
        print("  ✓ Command-line argument parsing for configuration overrides")
        print("  ✓ Comprehensive error handling and logging")
        print("  ✓ Integration tests for complete workflow validation")
        print("  ✓ Dry-run mode for testing without actual data logging")
        print("  ✓ Status reporting for monitoring and debugging")
        
        print("\n6. Usage Examples")
        print("-" * 40)
        
        print("Normal execution:")
        print("  python main.py")
        print()
        print("With custom timeout:")
        print("  python main.py --timeout 120")
        print()
        print("Dry run (test configuration):")
        print("  python main.py --dry-run")
        print()
        print("Show status:")
        print("  python main.py --status")
        print()
        print("Cron job example:")
        print("  0 8 * * * /path/to/python /path/to/main.py >> /var/log/cron.log 2>&1")
        
    finally:
        # Clean up temporary directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("\n=== Demo Complete ===")


if __name__ == '__main__':
    demo_main_application()