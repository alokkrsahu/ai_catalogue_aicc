#!/usr/bin/env python3
"""
Fixed setup script - run this from the milvus_explore directory to install the package.
"""

import subprocess
import sys
import os

def install_package():
    """Install the package in development mode."""
    try:
        print("🔧 Installing milvus_package in development mode...")
        
        # Change to the milvus_package directory
        package_dir = os.path.join(os.path.dirname(__file__), "milvus_package")
        
        if not os.path.exists(package_dir):
            print(f"❌ Package directory not found: {package_dir}")
            return False
        
        if not os.path.exists(os.path.join(package_dir, "setup.py")):
            print(f"❌ setup.py not found in {package_dir}")
            return False
        
        print(f"📁 Installing from: {package_dir}")
        
        # Install in development mode
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-e", "."
        ], capture_output=True, text=True, cwd=package_dir)
        
        if result.returncode == 0:
            print("✅ Package installed successfully!")
            return True
        else:
            print(f"❌ Installation failed: {result.stderr}")
            print(f"stdout: {result.stdout}")
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

def install_dependencies():
    """Install required dependencies."""
    try:
        print("📦 Installing dependencies...")
        
        dependencies = [
            "pymilvus>=2.3.0",
            "numpy>=1.21.0",
            "typing-extensions>=4.0.0"
        ]
        
        for dep in dependencies:
            print(f"   Installing {dep}...")
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", dep
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"   ⚠️ Warning: {dep} installation had issues")
        
        print("✅ Dependencies installation completed")
        return True
        
    except Exception as e:
        print(f"❌ Dependencies installation error: {e}")
        return False

def main():
    print("🚀 Milvus Package Setup (Fixed)")
    print("=" * 40)
    print(f"Current directory: {os.getcwd()}")
    
    # Install dependencies first
    install_dependencies()
    print()
    
    # Install package
    if install_package():
        print()
        
        # Test import
        if test_import():
            print()
            print("🎉 Package is ready to use!")
            print()
            print("Next steps:")
            print("   cd milvus_package")
            print("   python3 test_with_collections.py")
            print("   python3 live_demo.py")
            print("   python3 -m milvus_package.cli --help")
        else:
            print("⚠️ Package installed but import failed")
            print("Try running: pip install -e milvus_package/")
    else:
        print("❌ Package installation failed")
        print()
        print("Manual installation:")
        print("   cd milvus_package")
        print("   pip install -e .")

if __name__ == "__main__":
    main()
