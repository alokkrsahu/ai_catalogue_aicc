#!/usr/bin/env python3

import os

print("🔍 CHECKING API KEY CONFIGURATION")
print("=" * 50)

api_keys = {
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY'), 
    'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY')
}

for key_name, key_value in api_keys.items():
    if key_value:
        if key_value == 'Dummy-Key':
            print(f"❌ {key_name}: DUMMY VALUE DETECTED - needs real API key")
        elif len(key_value) < 10:
            print(f"⚠️ {key_name}: Too short, might be invalid (length: {len(key_value)})")
        else:
            # Show first 6 and last 4 characters for verification
            masked = f"{key_value[:6]}...{key_value[-4:]}"
            print(f"✅ {key_name}: Loaded ({masked}, length: {len(key_value)})")
    else:
        print(f"❌ {key_name}: NOT SET")

print("\n" + "=" * 50)
print("✅ API KEY CHECK COMPLETE")
print("\nIf you see 'DUMMY VALUE DETECTED', update your .env file with real API keys")
