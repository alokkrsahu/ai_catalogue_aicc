#!/usr/bin/env python3
"""
Test DocAware test_search endpoint directly
"""

import requests
import json

# Test the DocAware endpoint directly
def test_docaware_endpoint():
    base_url = "http://localhost:8000"
    
    # First, let's see if the docaware endpoints are available
    try:
        print("🧪 Testing DocAware search_methods endpoint...")
        response = requests.get(f"{base_url}/api/agent-orchestration/docaware/search_methods/")
        print(f"📊 Status: {response.status_code}")
        print(f"📝 Response: {response.text[:500]}...")
        
        if response.status_code == 401:
            print("🚨 Authentication required - need to test with proper token")
            return
        
        print("\n" + "="*50)
        print("🧪 Testing DocAware test_search endpoint...")
        
        # Test data
        test_data = {
            "project_id": "8660355a-7fd0-4434-a380-7cf80442603c",
            "method": "hybrid_search", 
            "parameters": {
                "index_type": "AUTOINDEX",
                "metric_type": "COSINE",
                "search_limit": 5,
                "relevance_threshold": 0.7
            },
            "query": "test query"
        }
        
        response = requests.post(
            f"{base_url}/api/agent-orchestration/docaware/test_search/",
            json=test_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"📊 Status: {response.status_code}")
        print(f"📝 Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Endpoint is working!")
        else:
            print(f"❌ Endpoint returned status {response.status_code}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"🚨 Connection error: {e}")
        print("Is the Django server running on localhost:8000?")
    except Exception as e:
        print(f"🚨 Error: {e}")

if __name__ == "__main__":
    test_docaware_endpoint()
