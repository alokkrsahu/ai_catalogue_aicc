#!/usr/bin/env python3
"""
Test syntax of the views file
"""
import sys
import os

# Add the backend directory to Python path
sys.path.append('/home/alokkrsahu/ai_catalogue/backend')

try:
    print("Testing import of public_chatbot.views...")
    from public_chatbot import views
    print("✅ Views imported successfully")
    
    # Check if function exists
    if hasattr(views, 'public_chat_stream_api'):
        print("✅ public_chat_stream_api function exists")
    else:
        print("❌ public_chat_stream_api function not found")
    
    print("✅ No syntax errors found")
    
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    print(f"   Line {e.lineno}: {e.text}")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    
except Exception as e:
    print(f"❌ Other error: {e}")
    import traceback
    traceback.print_exc()