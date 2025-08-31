#!/usr/bin/env python3
"""
Check and setup PROJECT_API_KEY_ENCRYPTION_KEY for the project
"""

import os
import sys
from pathlib import Path

def check_env_file():
    """Check if .env file exists and contains the encryption key"""
    
    print("🔍 CHECKING PROJECT ENCRYPTION KEY SETUP")
    print("=" * 60)
    
    # Check different possible locations for .env file
    possible_paths = [
        Path("../.env"),  # Parent directory (project root)
        Path(".env"),     # Current directory
        Path("/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/.env")  # Absolute path
    ]
    
    env_file = None
    for path in possible_paths:
        if path.exists():
            env_file = path
            print(f"✅ Found .env file at: {path.absolute()}")
            break
    
    if not env_file:
        print("❌ No .env file found in expected locations:")
        for path in possible_paths:
            print(f"   - {path.absolute()}")
        print("\n💡 Create .env file by copying .env.example:")
        print("cp .env.example .env")
        return False
    
    # Read and check the env file
    try:
        with open(env_file, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        found_key = False
        found_commented = False
        
        print(f"\n📂 Reading .env file ({len(lines)} lines, {len(content)} characters)")
        print("🔍 Searching for PROJECT_API_KEY_ENCRYPTION_KEY...")
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if 'PROJECT_API_KEY_ENCRYPTION_KEY' in stripped:
                print(f"\n📍 Found at line {i}: {stripped[:50]}...")
                
                if stripped.startswith('#'):
                    found_commented = True
                    print("❌ KEY