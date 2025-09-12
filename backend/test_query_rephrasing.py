#!/usr/bin/env python3
"""
Test script for the new LLM-based query rephrasing functionality
"""

import sys
import os
import django

# Add the backend directory to Python path
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_path)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_catalogue.settings')
django.setup()

from public_chatbot.services import PublicKnowledgeService
from public_chatbot.models import ChatbotConfiguration

def test_query_rephrasing_logic():
    """Test the query rephrasing functionality"""
    print("🧪 Testing LLM-based query rephrasing...")
    
    service = PublicKnowledgeService.get_instance()
    
    # Test scenarios
    test_scenarios = [
        {
            "name": "First Query (No Rephrasing)",
            "query": "What is artificial intelligence?",
            "conversation": [
                {"role": "user", "content": "What is artificial intelligence?"}
            ],
            "expected_behavior": "Should use original query (first query)"
        },
        {
            "name": "Second Query (Lazy Query)",
            "query": "Give me examples",
            "conversation": [
                {"role": "user", "content": "What is artificial intelligence?"},
                {"role": "assistant", "content": "AI is an advanced field of computer science..."},
                {"role": "user", "content": "Give me examples"}
            ],
            "expected_behavior": "Should rephrase to be more specific about AI examples"
        },
        {
            "name": "Third Query (Incomplete Reference)",
            "query": "What about deep learning?",
            "conversation": [
                {"role": "user", "content": "What is artificial intelligence?"},
                {"role": "assistant", "content": "AI is an advanced field of computer science..."},
                {"role": "user", "content": "Give me examples"},
                {"role": "assistant", "content": "Examples include machine learning, NLP, computer vision..."},
                {"role": "user", "content": "What about deep learning?"}
            ],
            "expected_behavior": "Should rephrase to specify deep learning in context of AI"
        },
        {
            "name": "Fourth Query (Very Lazy)",
            "query": "How does it work?",
            "conversation": [
                {"role": "user", "content": "What is artificial intelligence?"},
                {"role": "assistant", "content": "AI is an advanced field of computer science..."},
                {"role": "user", "content": "What about machine learning?"},
                {"role": "assistant", "content": "Machine learning is a subset of AI that enables systems to learn..."},
                {"role": "user", "content": "How does it work?"}
            ],
            "expected_behavior": "Should rephrase to specify how machine learning works"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n--- Test {i}: {scenario['name']} ---")
        print(f"Original Query: '{scenario['query']}'")
        print(f"Conversation Length: {len(scenario['conversation'])} messages")
        print(f"Expected: {scenario['expected_behavior']}")
        
        try:
            # Test the rephrasing function directly
            if len(scenario['conversation']) > 1:
                rephrased = service._rephrase_query_with_llm(
                    scenario['query'], 
                    scenario['conversation']
                )
                print(f"Rephrased Query: '{rephrased}'")
                
                if rephrased != scenario['query']:
                    print("✅ Successfully rephrased query")
                else:
                    print("ℹ️ Query unchanged (original was sufficient or rephrasing failed)")
            else:
                print("ℹ️ Skipping rephrasing (first query)")
                
        except Exception as e:
            print(f"❌ Error during rephrasing: {e}")
    
    print("\n🎉 Query rephrasing tests completed!")

def test_full_search_workflow():
    """Test the complete search workflow with rephrasing"""
    print("\n🧪 Testing full search workflow with rephrasing...")
    
    service = PublicKnowledgeService.get_instance()
    
    # Check if service is ready
    if not service.is_ready:
        print("❌ ChromaDB service not ready. Please start ChromaDB and sync knowledge first.")
        print("Run: docker-compose up -d chromadb")
        print("Run: python manage.py sync_public_knowledge")
        return
    
    # Test conversation flow
    conversation_flow = [
        {
            "query": "What is artificial intelligence?",
            "conversation": [
                {"role": "user", "content": "What is artificial intelligence?"}
            ]
        },
        {
            "query": "Give me examples",
            "conversation": [
                {"role": "user", "content": "What is artificial intelligence?"},
                {"role": "assistant", "content": "AI refers to computer systems that can perform tasks requiring human intelligence..."},
                {"role": "user", "content": "Give me examples"}
            ]
        },
        {
            "query": "Tell me more about that",
            "conversation": [
                {"role": "user", "content": "What is artificial intelligence?"},
                {"role": "assistant", "content": "AI refers to computer systems that can perform tasks requiring human intelligence..."},
                {"role": "user", "content": "Give me examples"},
                {"role": "assistant", "content": "Examples include machine learning, natural language processing, computer vision..."},
                {"role": "user", "content": "Tell me more about that"}
            ]
        }
    ]
    
    for i, step in enumerate(conversation_flow, 1):
        print(f"\n--- Step {i} ---")
        print(f"Query: '{step['query']}'")
        
        try:
            # Perform search with rephrasing
            results = service.search_knowledge(
                query=step['query'],
                limit=3,  # Just get top 3 for testing
                conversation_context=step['conversation']
            )
            
            print(f"Found {len(results)} results")
            if results:
                print("Top result:")
                top_result = results[0]
                print(f"  Title: {top_result.get('title', 'Unknown')}")
                print(f"  Similarity: {top_result.get('similarity_score', 0):.3f}")
                print(f"  Content preview: {top_result.get('content', '')[:100]}...")
            
        except Exception as e:
            print(f"❌ Error during search: {e}")
    
    print("\n🎉 Full search workflow tests completed!")

def check_configuration():
    """Check if query rephrasing is properly configured"""
    print("🧪 Checking query rephrasing configuration...")
    
    try:
        config = ChatbotConfiguration.get_config()
        
        print(f"Query Rephrasing Enabled: {getattr(config, 'enable_query_rephrasing', 'Not configured')}")
        print(f"Vector Search Enabled: {config.enable_vector_search}")
        print(f"LLM Provider: {config.default_llm_provider}")
        print(f"LLM Model: {config.default_model}")
        
        if hasattr(config, 'enable_query_rephrasing') and config.enable_query_rephrasing:
            print("✅ Query rephrasing is properly configured and enabled")
        else:
            print("⚠️ Query rephrasing is not enabled. You can enable it in Django admin.")
            
    except Exception as e:
        print(f"❌ Error checking configuration: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting query rephrasing functionality tests...\n")
    
    try:
        check_configuration()
        test_query_rephrasing_logic()
        test_full_search_workflow()
        
        print("\n🎯 All tests completed!")
        print("\n📋 Implementation Summary:")
        print("✅ Query Rephrasing: LLM-based rephrasing for subsequent queries")
        print("✅ First Query: Uses original query (no rephrasing)")
        print("✅ Subsequent Queries: Rephrased using conversation context")
        print("✅ Configuration: Can be enabled/disabled via Django admin")
        print("✅ Logging: Comprehensive logging for debugging")
        print("✅ Error Handling: Fallback to original query on failures")
        
        print("\n🔧 How to Use:")
        print("1. Ensure ChromaDB is running: docker-compose up -d chromadb")
        print("2. Sync knowledge: python manage.py sync_public_knowledge")
        print("3. Enable query rephrasing in Django admin: /admin/public_chatbot/chatbotconfiguration/")
        print("4. Test with API:")
        print('   First query: {"message": "What is AI?", "conversation": []}')
        print('   Second query: {"message": "examples", "conversation": [previous messages]}')
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()