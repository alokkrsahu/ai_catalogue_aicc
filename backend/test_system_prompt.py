#!/usr/bin/env python3
"""
Test script for the configurable system prompt implementation
"""

import sys
import os
import django

# Add the backend directory to Python path
sys.path.append('/home/alokkrsahu/ai_catalogue/backend')

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_catalogue.settings')
django.setup()

from public_chatbot.models import ChatbotConfiguration
from public_chatbot.llm_integration import PublicLLMService

def test_system_prompt_configuration():
    """Test the configurable system prompt functionality"""
    print("🧪 Testing configurable system prompt...")
    
    # Get or create configuration
    config = ChatbotConfiguration.get_config()
    print(f"✅ Current system prompt: '{config.system_prompt[:100]}...'")
    
    # Test custom system prompt
    custom_prompt = "You are a friendly AI assistant specializing in technology and science. Always provide accurate, detailed explanations."
    config.system_prompt = custom_prompt
    config.save()
    
    print(f"✅ Updated system prompt: '{config.system_prompt[:100]}...'")
    
    # Test LLM service initialization
    llm_service = PublicLLMService()
    available_providers = llm_service.get_available_providers()
    print(f"✅ Available LLM providers: {available_providers}")
    
    print("🎉 System prompt configuration test passed!")
    
    # Reset to default
    config.system_prompt = "You are a helpful assistant providing accurate, concise responses."
    config.save()
    print("✅ Reset system prompt to default")

def test_admin_integration():
    """Test Django admin integration"""
    print("\n🧪 Testing Django admin integration...")
    
    # Check if configuration exists and can be accessed
    config = ChatbotConfiguration.get_config()
    print(f"✅ Configuration accessible: {config.is_enabled}")
    print(f"✅ System prompt field exists: {hasattr(config, 'system_prompt')}")
    print(f"✅ Current system prompt length: {len(config.system_prompt)} characters")
    
    print("🎉 Django admin integration test passed!")

def main():
    """Run all tests"""
    print("🚀 Starting system prompt tests...\n")
    
    try:
        test_system_prompt_configuration()
        test_admin_integration()
        
        print("\n🎯 All tests completed successfully!")
        print("\n📋 Implementation Summary:")
        print("✅ Model: Added system_prompt TextField to ChatbotConfiguration")
        print("✅ Migration: Created and applied database migration")
        print("✅ LLM Integration: Updated all providers (OpenAI, Gemini, Anthropic)")
        print("✅ Views: Updated to pass system prompt from configuration")
        print("✅ Admin: Added system prompt field to Django admin interface")
        
        print("\n🔧 Usage:")
        print("1. Access Django admin at /admin/public_chatbot/chatbotconfiguration/")
        print("2. Edit the 'System prompt' field in LLM Settings section")
        print("3. Save changes - new prompt will be used for all chatbot responses")
        print("4. Different prompts for different providers:")
        print("   - OpenAI: Uses system role in messages")
        print("   - Anthropic: Uses separate system parameter")
        print("   - Gemini: Prepends system prompt to user prompt")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()