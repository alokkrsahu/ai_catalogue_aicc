#!/usr/bin/env python3

import requests
import json

print("🔍 Testing API endpoints...")
print("=" * 50)

# Test the history API endpoint first
history_url = "http://localhost:8000/api/projects/d61a5d4d-6c3a-4b4c-89a9-b0edf7e54a99/workflows/3e3335b5-3754-439f-99b0-95d984aa3354/history/"

try:
    print("📊 Testing History API...")
    response = requests.get(history_url)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {len(data.get('recent_executions', []))} recent_executions")
        
        # Get the first execution ID for testing conversation API
        if data.get('recent_executions'):
            first_execution = data['recent_executions'][0]
            execution_id = first_execution.get('execution_id')
            print(f"🎯 Testing with execution_id: {execution_id}")
            
            # Test conversation API
            conv_url = f"http://localhost:8000/api/projects/d61a5d4d-6c3a-4b4c-89a9-b0edf7e54a99/workflows/3e3335b5-3754-439f-99b0-95d984aa3354/conversation/?execution_id={execution_id}"
            
            print("\n💬 Testing Conversation API...")
            conv_response = requests.get(conv_url)
            print(f"Status Code: {conv_response.status_code}")
            
            if conv_response.status_code == 200:
                conv_data = conv_response.json()
                print(f"✅ Found {len(conv_data.get('messages', []))} messages")
                
                # Show message details
                for msg in conv_data.get('messages', [])[:3]:  # Show first 3 messages
                    print(f"  - {msg.get('agent_name')}: {msg.get('content')[:50]}...")
                    
            else:
                print(f"❌ Conversation API Error: {conv_response.status_code}")
                print(conv_response.text[:200])
        else:
            print("❌ No executions found to test conversation API")
    else:
        print(f"❌ History API Error: {response.status_code}")
        print(response.text[:200])
        
except Exception as e:
    print(f"❌ Request failed: {e}")

print("\n" + "=" * 50)
print("✅ API Testing Complete")
