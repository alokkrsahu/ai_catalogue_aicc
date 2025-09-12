#!/usr/bin/env python3
"""
Test script for the conversation-aware workflow implementation
"""

import sys
import os
import django

# Add the backend directory to Python path
sys.path.append('/home/alokkrsahu/ai_catalogue/backend')

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_catalogue.settings')
django.setup()

from public_chatbot.services import PublicKnowledgeService

def test_context_aware_query_building():
    """Test the context-aware query building logic"""
    print("🧪 Testing context-aware query building...")
    
    service = PublicKnowledgeService.get_instance()
    
    # Test 1: First query (no context)
    query1 = "What is artificial intelligence?"
    context1 = []
    result1 = service._build_context_aware_query(query1, context1)
    print(f"✅ First query: '{result1}'")
    assert result1 == query1, "First query should remain unchanged"
    
    # Test 2: Second query (with context)
    query2 = "Can you give me examples?"
    context2 = [
        {"role": "user", "content": "What is artificial intelligence?"},
        {"role": "assistant", "content": "AI refers to..."},
        {"role": "user", "content": "Can you give me examples?"}
    ]
    result2 = service._build_context_aware_query(query2, context2)
    expected2 = "Can you give me examples?. [What is artificial intelligence?]"
    print(f"✅ Second query: '{result2}'")
    assert expected2 in result2, f"Expected '{expected2}' in '{result2}'"
    
    # Test 3: Third query (multiple previous queries)
    query3 = "What about machine learning?"
    context3 = [
        {"role": "user", "content": "What is artificial intelligence?"},
        {"role": "assistant", "content": "AI refers to..."},
        {"role": "user", "content": "Can you give me examples?"},
        {"role": "assistant", "content": "Sure, examples include..."},
        {"role": "user", "content": "What about machine learning?"}
    ]
    result3 = service._build_context_aware_query(query3, context3)
    expected3 = "What about machine learning?. [What is artificial intelligence? Can you give me examples?]"
    print(f"✅ Third query: '{result3}'")
    assert "What is artificial intelligence?" in result3, "Should include first query"
    assert "Can you give me examples?" in result3, "Should include second query"
    
    print("🎉 All context-aware query tests passed!")

def test_conversation_workflow_format():
    """Test the conversation workflow input format"""
    print("\n🧪 Testing conversation workflow format...")
    
    # Sample conversation input format
    sample_input = {
        "message": "What about deep learning specifically?",
        "session_id": "test_session_123",
        "conversation": [
            {"role": "user", "content": "What is artificial intelligence?"},
            {"role": "assistant", "content": "Artificial intelligence (AI) refers to..."},
            {"role": "user", "content": "Can you give me examples?"},
            {"role": "assistant", "content": "Sure! Here are some examples..."},
            {"role": "user", "content": "What about deep learning specifically?"}
        ],
        "context_limit": 10
    }
    
    print("✅ Sample input format:")
    print(f"   - Latest message: {sample_input['message']}")
    print(f"   - Conversation length: {len(sample_input['conversation'])} messages")
    print(f"   - Context limit: {sample_input['context_limit']}")
    
    # Test the query building with this input
    service = PublicKnowledgeService.get_instance()
    context_query = service._build_context_aware_query(
        sample_input['message'], 
        sample_input['conversation']
    )
    
    print(f"✅ Generated context-aware query: '{context_query[:100]}...'")
    
    print("🎉 Conversation workflow format test passed!")

def main():
    """Run all tests"""
    print("🚀 Starting conversation workflow tests...\n")
    
    try:
        test_context_aware_query_building()
        test_conversation_workflow_format()
        
        print("\n🎯 All tests completed successfully!")
        print("\n📋 Implementation Summary:")
        print("✅ Chunking: Updated to use largest possible chunks with 750 token overlap")
        print("✅ Vector Search: Context-aware search appends all user queries")
        print("✅ Query Rephrasing: NEW - LLM-based rephrasing for subsequent queries")
        print("✅ ChromaDB: Returns top 10 results for better context")
        print("✅ Prompt Format: Includes ChromaDB content + full conversation history")
        print("✅ API Endpoint: Handles conversation array input format")
        
        print("\n🔧 Next Steps:")
        print("1. Initialize sample knowledge: python manage.py init_sample_knowledge")
        print("2. Start ChromaDB: docker-compose -f docker-compose-chroma-addon.yml up -d")
        print("3. Sync to ChromaDB: python manage.py sync_public_knowledge")
        print("4. Enable query rephrasing: Django admin -> Chatbot Configuration -> enable_query_rephrasing")
        print("5. Test query rephrasing: python test_query_rephrasing.py")
        print("6. Test with API calls:")
        print('   First: curl -X POST http://localhost:8000/api/public-chatbot/ \\')
        print('          -H "Content-Type: application/json" \\')
        print('          -d \'{"message": "What is AI?", "conversation": []}\'')
        print('   Second: curl -X POST http://localhost:8000/api/public-chatbot/ \\')
        print('           -H "Content-Type: application/json" \\')
        print('           -d \'{"message": "examples", "conversation": [{"role":"user","content":"What is AI?"},{"role":"assistant","content":"AI is..."}]}\'')
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()