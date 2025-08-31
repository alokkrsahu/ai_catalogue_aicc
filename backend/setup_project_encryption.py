#!/usr/bin/env python3
"""
Complete setup script for PROJECT_API_KEY_ENCRYPTION_KEY
This script will:
1. Generate a new encryption key if none exists
2. Add it to the .env file
3. Test the encryption system
4. Show you how to restart Docker to pick up changes
"""

import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet

def find_env_file():
    """Find the .env file in the project"""
    possible_paths = [
        Path("../.env"),  # Parent directory (project root)  
        Path(".env"),     # Current directory
        Path("/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/.env"),  # Absolute path
    ]
    
    for path in possible_paths:
        if path.exists():
            return path.resolve()
    
    return None

def check_existing_key():
    """Check if PROJECT_API_KEY_ENCRYPTION_KEY already exists"""
    env_file = find_env_file()
    
    if not env_file:
        print("❌ No .env file found!")
        return False, None
    
    try:
        with open(env_file, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('PROJECT_API_KEY_ENCRYPTION_KEY=') and not stripped.startswith('#'):
                # Extract the value
                value = stripped.split('=', 1)[1]
                if value and value.strip():
                    return True, env_file
        
        return False, env_file
        
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False, env_file

def generate_and_add_key():
    """Generate encryption key and add to .env file"""
    print("🔑 SETTING UP PROJECT API KEY ENCRYPTION")
    print("="*60)
    
    # Check existing key
    has_key, env_file = check_existing_key()
    
    if has_key:
        print(f"✅ PROJECT_API_KEY_ENCRYPTION_KEY already exists in {env_file}")
        print("   No action needed - key is already configured")
        return True
    
    if not env_file:
        print("❌ Could not find .env file!")
        print("💡 Please create one by copying .env.example:")
        print("   cp .env.example .env")
        return False
    
    print(f"📂 Using .env file: {env_file}")
    
    # Generate new key
    print("🔧 Generating new encryption key...")
    key = Fernet.generate_key()
    key_string = key.decode()
    
    # Add to .env file
    try:
        with open(env_file, 'a') as f:
            f.write(f"\n# Project API Key Encryption (Auto-generated)\n")
            f.write(f"PROJECT_API_KEY_ENCRYPTION_KEY={key_string}\n")
        
        print(f"✅ Added PROJECT_API_KEY_ENCRYPTION_KEY to {env_file}")
        print(f"   Key length: {len(key_string)} characters")
        
        # Test the key by trying to load it
        os.environ['PROJECT_API_KEY_ENCRYPTION_KEY'] = key_string
        test_encryption()
        
        return True
        
    except Exception as e:
        print(f"❌ Error adding key to .env file: {e}")
        return False

def test_encryption():
    """Test that the encryption system works"""
    print("\n🔐 Testing encryption system...")
    
    try:
        # Add current directory to path for imports
        sys.path.insert(0, str(Path(__file__).parent))
        
        # Import the encryption service
        from project_api_keys.encryption import ProjectAPIKeyEncryption
        
        encryption_service = ProjectAPIKeyEncryption()
        
        # Test encryption/decryption
        test_project_id = "test-project-12345"
        test_api_key = "sk-test-key-abcdef123456"
        
        encrypted = encryption_service.encrypt_api_key(test_project_id, test_api_key)
        decrypted = encryption_service.decrypt_api_key(test_project_id, encrypted)
        
        if decrypted == test_api_key:
            print("✅ Encryption test successful!")
            return True
        else:
            print("❌ Encryption test failed - decrypted value doesn't match")
            return False
            
    except ImportError as e:
        print(f"⚠️  Cannot test encryption (Django not initialized): {e}")
        print("   Key was added successfully - test after Docker restart")
        return True
    except Exception as e:
        print(f"❌ Encryption test failed: {e}")
        return False

def show_next_steps():
    """Show user what to do next"""
    print("\n" + "="*60)
    print("🚀 NEXT STEPS")
    print("="*60)
    print()
    print("1️⃣  RESTART YOUR DOCKER CONTAINERS:")
    print("   cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue")
    print("   ./script/start-dev.sh")
    print()
    print("2️⃣  VERIFY THE SETUP:")
    print("   docker exec -it ai_catalogue_backend python3 diagnose_project_keys.py")
    print()
    print("3️⃣  ADD REAL API KEYS TO .env (replace Dummy-Key values):")
    print("   - OPENAI_API_KEY=sk-your-real-openai-key")
    print("   - GOOGLE_API_KEY=your-real-google-key")  
    print("   - ANTHROPIC_API_KEY=your-real-anthropic-key")
    print()
    print("4️⃣  TEST WORKFLOW EXECUTION:")
    print("   Try running 'Tell me a poem' workflow again")
    print()
    print("⚠️  IMPORTANT: Keep your encryption key secure!")
    print("   Never commit .env file to version control")

def main():
    """Main setup function"""
    print("🔧 PROJECT API KEY ENCRYPTION SETUP")
    print("="*60)
    
    success = generate_and_add_key()
    
    if success:
        show_next_steps()
        print("\n✅ Setup complete!")
    else:
        print("\n❌ Setup failed - please check errors above")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
