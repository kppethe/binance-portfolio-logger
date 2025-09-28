#!/usr/bin/env python3
"""
Binance Portfolio Logger Setup Validation Script

This script validates the system requirements and configuration
for the Binance Portfolio Logger application.
"""

import os
import sys
import json
import subprocess
import importlib.util
from pathlib import Path
from typing import List, Tuple, Dict, Any
import platform


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    NC = '\033[0m'  # No Color


class ValidationResult:
    """Container for validation results"""
    def __init__(self):
        self.passed: List[str] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.info: List[str] = []

    def add_pass(self, message: str):
        self.passed.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def add_error(self, message: str):
        self.errors.append(message)

    def add_info(self, message: str):
        self.info.append(message)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def print_results(self):
        """Print all validation results with colors"""
        print(f"\n{Colors.BLUE}=== Validation Results ==={Colors.NC}")
        
        if self.passed:
            print(f"\n{Colors.GREEN}✓ PASSED ({len(self.passed)}):{Colors.NC}")
            for msg in self.passed:
                print(f"  {Colors.GREEN}✓{Colors.NC} {msg}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}⚠ WARNINGS ({len(self.warnings)}):{Colors.NC}")
            for msg in self.warnings:
                print(f"  {Colors.YELLOW}⚠{Colors.NC} {msg}")
        
        if self.errors:
            print(f"\n{Colors.RED}✗ ERRORS ({len(self.errors)}):{Colors.NC}")
            for msg in self.errors:
                print(f"  {Colors.RED}✗{Colors.NC} {msg}")
        
        if self.info:
            print(f"\n{Colors.CYAN}ℹ INFO ({len(self.info)}):{Colors.NC}")
            for msg in self.info:
                print(f"  {Colors.CYAN}ℹ{Colors.NC} {msg}")


class SystemValidator:
    """Validates system requirements and configuration"""
    
    def __init__(self):
        self.result = ValidationResult()
        self.app_dir = Path("/opt/binance-portfolio-logger")
        self.log_dir = Path("/var/log/binance-portfolio")
        self.user = "binance-logger"
        
    def validate_all(self) -> ValidationResult:
        """Run all validation checks"""
        print(f"{Colors.BLUE}Binance Portfolio Logger - Setup Validation{Colors.NC}")
        print("=" * 50)
        
        self.validate_system_info()
        self.validate_python_environment()
        self.validate_system_dependencies()
        self.validate_directory_structure()
        self.validate_file_permissions()
        self.validate_python_dependencies()
        self.validate_configuration()
        self.validate_credentials()
        self.validate_services()
        self.validate_network_connectivity()
        
        return self.result
    
    def validate_system_info(self):
        """Validate basic system information"""
        print(f"\n{Colors.PURPLE}Checking system information...{Colors.NC}")
        
        # OS Information
        system = platform.system()
        release = platform.release()
        machine = platform.machine()
        
        self.result.add_info(f"Operating System: {system} {release} ({machine})")
        
        if system == "Linux":
            self.result.add_pass("Running on Linux system")
            
            # Check specific distribution
            try:
                with open("/etc/os-release", "r") as f:
                    os_info = f.read()
                    if "ubuntu" in os_info.lower():
                        self.result.add_pass("Ubuntu distribution detected")
                    elif "debian" in os_info.lower():
                        self.result.add_pass("Debian distribution detected")
                    else:
                        self.result.add_warning("Non-Ubuntu/Debian distribution detected")
            except FileNotFoundError:
                self.result.add_warning("Cannot determine Linux distribution")
        else:
            self.result.add_error(f"Unsupported operating system: {system}")
    
    def validate_python_environment(self):
        """Validate Python installation and version"""
        print(f"\n{Colors.PURPLE}Checking Python environment...{Colors.NC}")
        
        # Python version
        python_version = sys.version_info
        version_str = f"{python_version.major}.{python_version.minor}.{python_version.micro}"
        
        self.result.add_info(f"Python version: {version_str}")
        
        if python_version >= (3, 9):
            self.result.add_pass(f"Python {version_str} meets minimum requirement (3.9+)")
        else:
            self.result.add_error(f"Python {version_str} is below minimum requirement (3.9+)")
        
        # Virtual environment
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            self.result.add_pass("Running in virtual environment")
            self.result.add_info(f"Virtual environment path: {sys.prefix}")
        else:
            self.result.add_warning("Not running in virtual environment")
    
    def validate_system_dependencies(self):
        """Validate required system packages"""
        print(f"\n{Colors.PURPLE}Checking system dependencies...{Colors.NC}")
        
        required_commands = [
            ("python3", "Python 3 interpreter"),
            ("pip3", "Python package manager"),
            ("cron", "Cron scheduler"),
            ("curl", "HTTP client"),
        ]
        
        for command, description in required_commands:
            if self._command_exists(command):
                self.result.add_pass(f"{description} available ({command})")
            else:
                self.result.add_error(f"{description} not found ({command})")
    
    def validate_directory_structure(self):
        """Validate application directory structure"""
        print(f"\n{Colors.PURPLE}Checking directory structure...{Colors.NC}")
        
        required_dirs = [
            (self.app_dir, "Application directory"),
            (self.app_dir / "credentials", "Credentials directory"),
            (self.log_dir, "Log directory"),
        ]
        
        for dir_path, description in required_dirs:
            if dir_path.exists():
                self.result.add_pass(f"{description} exists: {dir_path}")
            else:
                self.result.add_error(f"{description} missing: {dir_path}")
    
    def validate_file_permissions(self):
        """Validate file and directory permissions"""
        print(f"\n{Colors.PURPLE}Checking file permissions...{Colors.NC}")
        
        if not os.name == 'posix':
            self.result.add_warning("File permission checks skipped (not on POSIX system)")
            return
        
        # Check application directory permissions
        if self.app_dir.exists():
            stat_info = self.app_dir.stat()
            mode = oct(stat_info.st_mode)[-3:]
            
            if mode == "750":
                self.result.add_pass(f"Application directory permissions correct (750)")
            else:
                self.result.add_warning(f"Application directory permissions: {mode} (expected 750)")
        
        # Check credentials directory permissions
        cred_dir = self.app_dir / "credentials"
        if cred_dir.exists():
            stat_info = cred_dir.stat()
            mode = oct(stat_info.st_mode)[-3:]
            
            if mode == "700":
                self.result.add_pass(f"Credentials directory permissions correct (700)")
            else:
                self.result.add_error(f"Credentials directory permissions: {mode} (expected 700)")
        
        # Check .env file permissions
        env_file = self.app_dir / ".env"
        if env_file.exists():
            stat_info = env_file.stat()
            mode = oct(stat_info.st_mode)[-3:]
            
            if mode == "600":
                self.result.add_pass(f"Environment file permissions correct (600)")
            else:
                self.result.add_error(f"Environment file permissions: {mode} (expected 600)")
    
    def validate_python_dependencies(self):
        """Validate Python package dependencies"""
        print(f"\n{Colors.PURPLE}Checking Python dependencies...{Colors.NC}")
        
        required_packages = [
            ("binance", "python-binance"),
            ("gspread", "gspread"),
            ("dotenv", "python-dotenv"),
            ("google.auth", "google-auth"),
        ]
        
        for module_name, package_name in required_packages:
            try:
                spec = importlib.util.find_spec(module_name)
                if spec is not None:
                    self.result.add_pass(f"Python package available: {package_name}")
                else:
                    self.result.add_error(f"Python package missing: {package_name}")
            except ImportError:
                self.result.add_error(f"Python package missing: {package_name}")
    
    def validate_configuration(self):
        """Validate application configuration"""
        print(f"\n{Colors.PURPLE}Checking configuration...{Colors.NC}")
        
        env_file = self.app_dir / ".env"
        if not env_file.exists():
            self.result.add_error(f"Configuration file missing: {env_file}")
            return
        
        self.result.add_pass(f"Configuration file exists: {env_file}")
        
        # Load and validate environment variables
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            
            required_vars = [
                "BINANCE_API_KEY",
                "BINANCE_API_SECRET",
                "GOOGLE_SERVICE_ACCOUNT_PATH",
                "GOOGLE_SPREADSHEET_ID",
            ]
            
            for var in required_vars:
                value = os.getenv(var)
                if value and value != f"your_{var.lower()}_here":
                    self.result.add_pass(f"Environment variable configured: {var}")
                else:
                    self.result.add_error(f"Environment variable missing or not configured: {var}")
                    
        except ImportError:
            self.result.add_warning("Cannot validate environment variables (python-dotenv not available)")
    
    def validate_credentials(self):
        """Validate credential files"""
        print(f"\n{Colors.PURPLE}Checking credentials...{Colors.NC}")
        
        # Check Google Service Account file
        service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH")
        if service_account_path:
            service_account_file = Path(service_account_path)
            if service_account_file.exists():
                self.result.add_pass(f"Google Service Account file exists: {service_account_file}")
                
                # Validate JSON format
                try:
                    with open(service_account_file, 'r') as f:
                        json.load(f)
                    self.result.add_pass("Google Service Account file is valid JSON")
                except json.JSONDecodeError:
                    self.result.add_error("Google Service Account file is not valid JSON")
                except PermissionError:
                    self.result.add_error("Cannot read Google Service Account file (permission denied)")
            else:
                self.result.add_error(f"Google Service Account file missing: {service_account_file}")
        else:
            self.result.add_warning("Google Service Account path not configured")
    
    def validate_services(self):
        """Validate system services configuration"""
        print(f"\n{Colors.PURPLE}Checking services...{Colors.NC}")
        
        # Check if systemd service exists
        service_file = Path("/etc/systemd/system/binance-portfolio-logger.service")
        if service_file.exists():
            self.result.add_pass("Systemd service file exists")
            
            # Check if service is enabled
            try:
                result = subprocess.run(
                    ["systemctl", "is-enabled", "binance-portfolio-logger.service"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.result.add_pass("Systemd service is enabled")
                else:
                    self.result.add_warning("Systemd service is not enabled")
            except FileNotFoundError:
                self.result.add_warning("Cannot check systemd service status (systemctl not available)")
        else:
            self.result.add_info("Systemd service file not found (using cron instead)")
        
        # Check cron service
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "cron"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.result.add_pass("Cron service is active")
            else:
                self.result.add_warning("Cron service is not active")
        except FileNotFoundError:
            self.result.add_warning("Cannot check cron service status")
    
    def validate_network_connectivity(self):
        """Validate network connectivity to required services"""
        print(f"\n{Colors.PURPLE}Checking network connectivity...{Colors.NC}")
        
        endpoints = [
            ("api.binance.com", 443, "Binance API"),
            ("sheets.googleapis.com", 443, "Google Sheets API"),
        ]
        
        for host, port, description in endpoints:
            if self._test_connectivity(host, port):
                self.result.add_pass(f"Network connectivity to {description} ({host}:{port})")
            else:
                self.result.add_error(f"Cannot connect to {description} ({host}:{port})")
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in the system PATH"""
        try:
            subprocess.run(
                ["which", command],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _test_connectivity(self, host: str, port: int, timeout: int = 5) -> bool:
        """Test network connectivity to a host:port"""
        import socket
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False


def main():
    """Main validation function"""
    validator = SystemValidator()
    result = validator.validate_all()
    
    result.print_results()
    
    # Summary
    print(f"\n{Colors.BLUE}=== Summary ==={Colors.NC}")
    print(f"Passed: {Colors.GREEN}{len(result.passed)}{Colors.NC}")
    print(f"Warnings: {Colors.YELLOW}{len(result.warnings)}{Colors.NC}")
    print(f"Errors: {Colors.RED}{len(result.errors)}{Colors.NC}")
    
    if result.has_errors():
        print(f"\n{Colors.RED}Validation failed. Please fix the errors above before running the application.{Colors.NC}")
        sys.exit(1)
    elif result.warnings:
        print(f"\n{Colors.YELLOW}Validation completed with warnings. The application should work but may have issues.{Colors.NC}")
        sys.exit(0)
    else:
        print(f"\n{Colors.GREEN}Validation passed! The system is ready to run the Binance Portfolio Logger.{Colors.NC}")
        sys.exit(0)


if __name__ == "__main__":
    main()