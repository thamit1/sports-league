#!/usr/bin/env python
"""
Simple runner script for graph_generator.py
Handles dependency installation automatically.
"""

import subprocess
import sys
from pathlib import Path


def check_and_install_dependencies():
    """Check if required packages are installed, install if missing"""
    required_packages = {
        'networkx': 'networkx',
    }
    
    missing_packages = []
    
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"✓ {package_name} is installed")
        except ImportError:
            print(f"✗ {package_name} is NOT installed")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\nInstalling missing packages: {', '.join(missing_packages)}")
        for package in missing_packages:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package],
                stdout=subprocess.DEVNULL
            )
        print("✓ Dependencies installed successfully\n")
    else:
        print("✓ All dependencies are installed\n")


def main():
    """Main entry point"""
    print("=" * 60)
    print("Code Repository Knowledge Graph Generator")
    print("=" * 60)
    print()
    
    # Check dependencies
    print("Checking dependencies...")
    check_and_install_dependencies()
    
    # Import and run
    print("Starting graph generation...")
    print()
    
    try:
        from graph_generator import main as generate_graph
        generate_graph()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
