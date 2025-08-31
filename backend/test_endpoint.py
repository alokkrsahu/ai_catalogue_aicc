#!/usr/bin/env python3

"""
Test script to verify the process_documents endpoint is working
"""

import requests
import json
import sys

def test_endpoint():
    url = "http://localhost:8000/api/projects/d61a5d4d-6c3a-4b4c-89a9-b0edf7e54a99/process_documents/"
    
    # This will be a test without authentication first to see if the endpoint exists
    try:
        response = requests.options(url)
        print(f"✅ OPTIONS request status: {response.status_code}")
        print(f"✅ Allowed methods: {response.headers.get('Allow', 'N/A')}")
        
        # Try POST without auth (should get 401 but proves endpoint exists)
        response = requests.post(url, json={})
        print(f"✅ POST request status: {response.status_code}")
        
        if response.status_code == 404:
            print("❌ Endpoint still not found (404)")
            return False
        elif response.status_code == 401:
            print("✅ Endpoint exists! (401 Unauthorized - need authentication)")
            return True
        else:
            print(f"✅ Unexpected status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return True
            
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing process_documents endpoint...")
    success = test_endpoint()
    sys.exit(0 if success else 1)
