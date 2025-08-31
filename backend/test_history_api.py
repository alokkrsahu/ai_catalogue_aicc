#!/usr/bin/env python3

import requests
import json

# Test the history API endpoint directly
url = "http://localhost:8000/api/projects/d61a5d4d-6c3a-4b4c-89a9-b0edf7e54a99/workflows/3e3335b5-3754-439f-99b0-95d984aa3354/history/"

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Content Type: {response.headers.get('content-type')}")
    print(f"Response Size: {len(response.content)} bytes")
    print()
    
    if response.status_code == 200:
        data = response.json()
        print("=== API RESPONSE DATA ===")
        print(json.dumps(data, indent=2, default=str))
        print()
        
        # Check for execution data
        if 'recent_executions' in data:
            print(f"✅ Found {len(data['recent_executions'])} recent_executions")
            for i, exec_data in enumerate(data['recent_executions']):
                print(f"  Execution {i+1}: {exec_data.get('execution_id', 'No ID')} - {exec_data.get('status', 'No status')}")
                if 'messages' in exec_data:
                    print(f"    Messages: {len(exec_data['messages'])}")
        else:
            print("❌ No 'recent_executions' found in response")
            print(f"Available keys: {list(data.keys())}")
    else:
        print(f"❌ API Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Request failed: {e}")
