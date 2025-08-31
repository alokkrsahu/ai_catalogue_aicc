#!/usr/bin/env python3
"""
Simple script to generate encryption key for Project API Keys
Run this once to generate your PROJECT_API_KEY_ENCRYPTION_KEY
"""

try:
    from cryptography.fernet import Fernet
    
    print("🔑 Generating Project API Key Encryption Key...")
    print("=" * 50)
    
    # Generate a new Fernet key
    key = Fernet.generate_key()
    key_string = key.decode()
    
    print("")
    print("✅ SUCCESS! Add this to your environment:")
    print("=" * 50)
    print(f"PROJECT_API_KEY_ENCRYPTION_KEY={key_string}")
    print("=" * 50)
    print("")
    print("💡 To set it temporarily:")
    print(f"export PROJECT_API_KEY_ENCRYPTION_KEY='{key_string}'")
    print("")
    print("💡 To add to your .env file:")
    print(f"echo 'PROJECT_API_KEY_ENCRYPTION_KEY={key_string}' >> .env")
    print("")
    print("⚠️  IMPORTANT: Keep this key secure and never commit it to version control!")
    
except ImportError:
    print("❌ ERROR: cryptography package not installed")
    print("Install with: pip install cryptography")
except Exception as e:
    print(f"❌ ERROR: {e}")
