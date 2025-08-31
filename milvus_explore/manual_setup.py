#!/usr/bin/env python3
"""
Manual setup script to install the package in development mode.
"""

import subprocess
import sys
import os

def install_package():
    """Install the package in development mode."""
    try:
        print("🔧 Installing package in development mode...")
        
        # Install in development mode
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-e", "."
        ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        if result.returncode == 0:
            print("✅ Package installed successfully!")
            return True
        else:
            print(f"❌ Installation failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Installation error: {e}")
        return False

def test_import():
    """Test if the package can be imported."""
    try:
        print("🧪 Testing package import...")
        
        # Test import
        from milvus_package import ConcurrentSearchEngine, ConnectionConfig
        print("✅ Package import successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def main():
    print("🚀 Manual Package Setup")
    print("=" * 30)
    
    # Install package
    if install_package():
        print()
        
        # Test import
        if test_import():
            print()
            print("🎉 Package is ready to use!")
            print()
            print("Next steps:")
            print("   python3 quickstart.py")
            print("   python3 examples.py")
            print("   python3 -m milvus_package.cli --help")
        else:
            print("⚠️ Package installed but import failed")
    else:
        print("❌ Package installation failed")

if __name__ == "__main__":
    main()
