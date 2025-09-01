#!/usr/bin/env python3
"""
Test script for Public Chatbot API CORS configuration
Tests CORS headers for both regular and streaming endpoints
"""

import requests
import json
import sys

def test_cors_preflight(url, origin):
    """Test CORS preflight request"""
    print(f"\n🔍 Testing CORS preflight for {url} from origin {origin}")
    
    try:
        response = requests.options(
            url,
            headers={
                'Origin': origin,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type',
            },
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin', 'Not set')}")
        print(f"   Access-Control-Allow-Methods: {response.headers.get('Access-Control-Allow-Methods', 'Not set')}")
        print(f"   Access-Control-Allow-Headers: {response.headers.get('Access-Control-Allow-Headers', 'Not set')}")
        
        return response.status_code == 200 and 'Access-Control-Allow-Origin' in response.headers
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_cors_actual_request(url, origin):
    """Test actual POST request with CORS"""
    print(f"\n📨 Testing actual POST request to {url} from origin {origin}")
    
    try:
        response = requests.post(
            url,
            headers={
                'Origin': origin,
                'Content-Type': 'application/json',
            },
            json={'message': 'Hello, this is a CORS test'},
            timeout=30
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin', 'Not set')}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response status: {data.get('status', 'unknown')}")
            print(f"   Response message: {data.get('response', 'No response')[:100]}...")
        else:
            print(f"   Error response: {response.text[:200]}...")
        
        return 'Access-Control-Allow-Origin' in response.headers
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Main test function"""
    if len(sys.argv) < 2:
        print("Usage: python test_cors.py <base_url>")
        print("Example: python test_cors.py https://aicc.uksouth.cloudapp.azure.com")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    
    # Test endpoints
    endpoints = [
        f"{base_url}/api/public-chatbot/",
        f"{base_url}/api/public-chatbot/stream/",
        f"{base_url}/api/public-chatbot/health/",
    ]
    
    # Test origins
    origins = [
        'https://oxfordcompetencycenters.github.io',
        'http://localhost:3000',
        'http://localhost:5173',
        'https://aicc.uksouth.cloudapp.azure.com',
    ]
    
    print("🚀 Public Chatbot API CORS Testing")
    print("=" * 50)
    
    all_passed = True
    
    for endpoint in endpoints:
        print(f"\n📍 Testing endpoint: {endpoint}")
        
        for origin in origins:
            # Test preflight
            preflight_pass = test_cors_preflight(endpoint, origin)
            
            # Test actual request (only for main endpoint)
            if '/health/' in endpoint:
                # Health endpoint is GET, test it separately
                try:
                    response = requests.get(
                        endpoint,
                        headers={'Origin': origin},
                        timeout=10
                    )
                    actual_pass = 'Access-Control-Allow-Origin' in response.headers
                    print(f"   GET request CORS: {'✅ Pass' if actual_pass else '❌ Fail'}")
                except Exception as e:
                    print(f"   GET request error: {e}")
                    actual_pass = False
            elif endpoint.endswith('/'):
                # Main chatbot endpoint
                actual_pass = test_cors_actual_request(endpoint, origin)
            else:
                actual_pass = True  # Skip actual test for stream endpoint
            
            test_passed = preflight_pass and actual_pass
            print(f"   Overall: {'✅ Pass' if test_passed else '❌ Fail'}")
            
            if not test_passed:
                all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All CORS tests passed!")
    else:
        print("❌ Some CORS tests failed. Check the server configuration.")
    
    print("\n💡 If tests fail, ensure:")
    print("   1. The server is running and accessible")
    print("   2. CORS middleware is properly configured")
    print("   3. Public chatbot endpoints are enabled")
    print("   4. Origins are properly whitelisted")

if __name__ == '__main__':
    main()
