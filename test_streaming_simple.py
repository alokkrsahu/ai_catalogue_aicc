#!/usr/bin/env python3
"""
Simple streaming test with better error handling
"""
import requests
import json

def test_streaming_simple():
    """Test streaming API with minimal payload"""
    url = "http://localhost:8000/api/public-chatbot/stream/"
    
    payload = {
        "message": "Hello, how are you?"
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
    }
    
    try:
        print("🌊 Testing streaming API...")
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ Connection successful, reading stream...")
            
            for line in response.iter_lines(decode_unicode=True):
                if line.strip():
                    print(f"Raw line: {repr(line)}")
                    
                    if line.startswith('data: '):
                        data_str = line[6:]  # Remove 'data: '
                        
                        if data_str == '[DONE]':
                            print("✅ Stream completed!")
                            break
                        
                        try:
                            data = json.loads(data_str)
                            print(f"Parsed data: {data}")
                            
                            if data.get('type') == 'content':
                                print(f"Content: {data.get('content')}")
                            elif data.get('type') == 'error':
                                print(f"❌ Stream error: {data.get('error')}")
                                break
                                
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON parse error: {e}")
                            print(f"Raw data: {repr(data_str)}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response text: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_streaming_simple()