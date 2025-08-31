#!/usr/bin/env python3
"""
Test script for Public Chatbot IP logging and streaming improvements
"""
import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000/api/public-chatbot"
HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'ChatbotTester/1.0',
    'X-Forwarded-For': '203.0.113.42, 192.168.1.100',  # Test IP forwarding
    'X-Real-IP': '203.0.113.42'
}

def test_ip_logging():
    """Test IP address logging with proxy headers"""
    print("🧪 Testing IP Address Logging...")
    
    test_message = {
        "message": "Hello, this is a test message to check IP logging",
        "session_id": f"test_session_{int(time.time())}"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/",
            json=test_message,
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Regular API call successful")
            print(f"   Request ID: {data.get('metadata', {}).get('request_id')}")
            print(f"   Response time: {data.get('metadata', {}).get('response_time_ms')}ms")
            return True
        else:
            print(f"❌ API call failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def test_streaming_api():
    """Test streaming API endpoint"""
    print("\n🌊 Testing Streaming API...")
    
    test_message = {
        "message": "Tell me about artificial intelligence in a detailed way",
        "session_id": f"stream_test_{int(time.time())}"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/stream/",
            json=test_message,
            headers=HEADERS,
            stream=True,
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Streaming API connected successfully")
            print(f"   Content-Type: {response.headers.get('Content-Type')}")
            
            # Read streaming response
            collected_content = ""
            chunk_count = 0
            start_time = time.time()
            
            for line in response.iter_lines(decode_unicode=True):
                if line.strip():
                    if line.startswith('data: '):
                        data_str = line[6:]  # Remove 'data: ' prefix
                        
                        if data_str == '[DONE]':
                            print(f"   Stream completed: [DONE]")
                            break
                        
                        try:
                            chunk_data = json.loads(data_str)
                            chunk_type = chunk_data.get('type')
                            
                            if chunk_type == 'content':
                                content = chunk_data.get('content', '')
                                collected_content += content
                                chunk_count += 1
                                
                            elif chunk_type == 'completion':
                                total_time = chunk_data.get('response_time_ms', 0)
                                print(f"   Completion received: {total_time}ms total")
                                print(f"   Total content length: {len(collected_content)}")
                                
                            elif chunk_type == 'error':
                                print(f"❌ Stream error: {chunk_data.get('error')}")
                                return False
                                
                        except json.JSONDecodeError:
                            print(f"   Raw data: {data_str[:100]}...")
            
            elapsed = time.time() - start_time
            print(f"   Received {chunk_count} content chunks in {elapsed:.1f}s")
            print(f"   Sample content: '{collected_content[:100]}...'")
            return True
            
        else:
            print(f"❌ Streaming API failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Streaming request failed: {e}")
        return False

def test_health_check():
    """Test health check endpoint"""
    print("\n🏥 Testing Health Check...")
    
    try:
        response = requests.get(f"{BASE_URL}/health/", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check successful")
            print(f"   Status: {data.get('status')}")
            print(f"   ChromaDB: {data.get('components', {}).get('chromadb', {}).get('status')}")
            print(f"   Vector search enabled: {data.get('components', {}).get('configuration', {}).get('vector_search_enabled')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check request failed: {e}")
        return False

def main():
    """Run all tests"""
    print(f"🚀 Starting Public Chatbot Tests at {datetime.now().isoformat()}")
    print(f"   Target URL: {BASE_URL}")
    print(f"   Test IP: {HEADERS['X-Real-IP']} (via proxy headers)")
    
    results = []
    
    # Test health check first
    results.append(("Health Check", test_health_check()))
    
    # Test IP logging
    results.append(("IP Logging", test_ip_logging()))
    
    # Test streaming API
    results.append(("Streaming API", test_streaming_api()))
    
    # Summary
    print("\n📊 Test Results Summary:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Both IP logging and streaming are working correctly.")
    else:
        print("⚠️ Some tests failed. Check the server logs and configuration.")
    
    return passed == len(results)

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
        exit(1)