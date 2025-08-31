#!/usr/bin/env python3
"""
Generate PROJECT_API_KEY_ENCRYPTION_KEY and add it to .env file
This script will:
1. Generate a secure encryption key
2. Add it to your .env file  
3. Show you how to restart Docker containers
4. Verify the configuration
"""

import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet

def find_env_file():
    """Find the .env file in the project root"""
    # Look in the parent directory (project root)
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    env_file = project_root / '.env'
    
    if env_file.exists():
        return env_file
    
    # Try current directory as fallback
    env_file_current = current_dir / '.env'
    if env_file_current.exists():
        return env_file_current
    
    return None

def check_existing_key(env_file):
    """Check if PROJECT_API_KEY_ENCRYPTION_KEY already exists"""
    try:
        with open(env_file, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('PROJECT_API_KEY_ENCRYPTION_KEY=') and not stripped.startswith('#'):
                value = stripped.split('=', 1)[1]
                if value and value.strip():
                    return True, value.strip()
        
        return False, None
        
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False, None

def generate_encryption_key():
    """Generate a new Fernet encryption key"""
    key = Fernet.generate_key()
    return key.decode()

def add_key_to_env(env_file, encryption_key):
    """Add the encryption key to .env file"""
    try:
        # Read existing content
        with open(env_file, 'r') as f:
            content = f.read()
        
        # Check if key already exists (including commented versions)
        lines = content.split('\n')
        key_exists = False
        updated_lines = []
        
        for line in lines:
            if 'PROJECT_API_KEY_ENCRYPTION_KEY' in line:
                if line.strip().startswith('#'):
                    # Replace commented version
                    updated_lines.append(f"PROJECT_API_KEY_ENCRYPTION_KEY={encryption_key}")
                    key_exists = True
                    print("✅ Replaced commented encryption key")
                elif line.strip().startswith('PROJECT_API_KEY_ENCRYPTION_KEY='):
                    # Update existing key
                    updated_lines.append(f"PROJECT_API_KEY_ENCRYPTION_KEY={encryption_key}")
                    key_exists = True
                    print("✅ Updated existing encryption key")
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)
        
        # If key doesn't exist, add it
        if not key_exists:
            updated_lines.extend([
                "",
                "# Project API Key Encryption (Auto-generated)",
                "# This key is used to encrypt/decrypt project-specific API keys in the database",
                f"PROJECT_API_KEY_ENCRYPTION_KEY={encryption_key}"
            ])
            print("✅ Added new encryption key to .env file")
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.write('\n'.join(updated_lines))
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False

def main():
    """Main function to setup PROJECT_API_KEY_ENCRYPTION_KEY"""
    print("🔐 PROJECT API KEY ENCRYPTION SETUP")
    print("="*60)
    
    # Find .env file
    env_file = find_env_file()
    if not env_file:
        print("❌ Could not find .env file!")
        print("💡 Please ensure .env file exists in project root")
        print("   You can create one by copying .env.example")
        return 1
    
    print(f"📂 Found .env file: {env_file}")
    
    # Check if key already exists
    has_key, existing_key = check_existing_key(env_file)
    
    if has_key:
        print(f"✅ PROJECT_API_KEY_ENCRYPTION_KEY already exists")
        print(f"   Key preview: {existing_key[:10]}...{existing_key[-8:]}")
        print(f"   Length: {len(existing_key)} characters")
        
        # Verify it's a valid Fernet key
        try:
            Fernet(existing_key.encode())
            print("✅ Existing key is valid Fernet format")
            
            print("\n🐳 DOCKER RESTART REQUIRED:")
            print("The key exists but Docker containers need to be restarted to pick it up")
            show_restart_instructions()
            return 0
            
        except Exception as e:
            print(f"⚠️  Existing key appears invalid: {e}")
            print("Generating a new key...")
    
    # Generate new encryption key
    print("🔧 Generating new PROJECT_API_KEY_ENCRYPTION_KEY...")
    encryption_key = generate_encryption_key()
    print(f"✅ Generated encryption key: {len(encryption_key)} characters")
    
    # Add to .env file
    if add_key_to_env(env_file, encryption_key):
        print(f"✅ Successfully added PROJECT_API_KEY_ENCRYPTION_KEY to {env_file}")
        
        # Verify the key was added correctly
        has_key_now, _ = check_existing_key(env_file)
        if has_key_now:
            print("✅ Verification: Key successfully written to .env file")
        else:
            print("⚠️  Verification failed: Key may not have been written correctly")
        
        show_restart_instructions()
        show_verification_instructions()
        
        return 0
    else:
        print("❌ Failed to add encryption key to .env file")
        return 1

def show_restart_instructions():
    """Show how to restart Docker containers"""
    print("\n" + "="*60)
    print("🚀 NEXT STEPS - RESTART DOCKER CONTAINERS")
    print("="*60)
    print()
    print("1. Navigate to your project root:")
    print("   cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue")
    print()
    print("2. Restart Docker containers to pick up the new environment variable:")
    print("   ./script/start-dev.sh")
    print()
    print("   This will:")
    print("   - Stop all running containers")
    print("   - Rebuild containers with new environment variables")
    print("   - Start all services with the PROJECT_API_KEY_ENCRYPTION_KEY")

def show_verification_instructions():
    """Show how to verify the setup works"""
    print("\n" + "="*60)
    print("🔍 VERIFICATION STEPS")
    print("="*60)
    print()
    print("After restarting Docker, verify the setup:")
    print()
    print("1. Check if the environment variable is available in the container:")
    print("   docker exec -it ai_catalogue_backend env | grep PROJECT_API_KEY_ENCRYPTION_KEY")
    print()
    print("2. Run the diagnostic script to test encryption:")
    print("   docker exec -it ai_catalogue_backend python3 diagnose_project_keys.py")
    print()
    print("3. Try the 'Tell me a poem' workflow again")
    print("   - It should now work with the encryption key properly configured")
    print()
    print("Expected results after restart:")
    print("✅ Environment variable loaded in container")
    print("✅ Encryption system working") 
    print("✅ Workflow executions succeed")

if __name__ == "__main__":
    sys.exit(main())
