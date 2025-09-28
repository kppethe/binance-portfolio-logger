#!/usr/bin/env python3
"""
Main entry point for Binance Portfolio Logger.

This script serves as the primary executable for the portfolio logging application.
It can be run directly or scheduled via cron for automated portfolio tracking.
"""
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from src.main_application import main

if __name__ == '__main__':
    sys.exit(main())