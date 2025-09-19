#!/usr/bin/env python3
"""
Enhanced Public Chatbot Tracking Test
Tests both regular and streaming endpoints with comprehensive tracking verification
"""

import requests
import json
import time
import threading
from datetime import datetime
import uuid

# Configuration
BASE_URL = "http://localhost:8000"
REGULAR_ENDPOINT = f"{BASE_URL}/api/public-chatbot/"
STREAMING_ENDPOINT = f"{BASE_URL}/api/public-chatbot/stream/"

def test_regular_endpoint():
    """Test the regular chatbot endpoint with tracking"""
    print("🔄 Testing Regular Chatbot Endpoint...")

    test_message = f"Hello! This is a test message from {datetime.now().isoformat()}"
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"

    payload = {
        "message": test_message,
        "session_id": session_id,
        "conversation": [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "Origin": "http://localhost:3000",
        "User-Agent": "PublicChatbotTest/1.0"
    }

    try:
        print(f"📤 Sending request to: {REGULAR_ENDPOINT}")
        print(f"📝 Message: {test_message[:50]}...")

        response = requests.post(
            REGULAR_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=30
        )

        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Regular endpoint test PASSED")
            print(f"📊 Response data keys: {list(data.keys())}")
            print(f"🆔 Request ID: {data.get('request_id', 'Not found')}")

            if 'metadata' in data:
                metadata = data['metadata']
                print(f"📊 Response time: {metadata.get('response_time_ms', 'N/A')}ms")
                print(f"🔍 ChromaDB results: {metadata.get('chroma_results_found', 'N/A')}")
                print(f"🤖 LLM provider: {metadata.get('llm_provider_used', 'N/A')}")

            return data.get('request_id')
        else:
            print(f"❌ Regular endpoint test FAILED")
            print(f"📄 Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Regular endpoint test ERROR: {e}")
        return None

def test_streaming_endpoint():
    """Test the streaming chatbot endpoint with tracking"""
    print("\n🌊 Testing Streaming Chatbot Endpoint...")

    test_message = f"Hello! This is a streaming test from {datetime.now().isoformat()}"
    session_id = f"stream_test_{uuid.uuid4().hex[:8]}"

    payload = {
        "message": test_message,
        "session_id": session_id,
        "conversation": []
    }

    headers = {
        "Content-Type": "application/json",
        "Origin": "http://localhost:3000",
        "User-Agent": "PublicChatbotStreamTest/1.0",
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache"
    }

    try:
        print(f"📤 Sending streaming request to: {STREAMING_ENDPOINT}")
        print(f"📝 Message: {test_message[:50]}...")

        response = requests.post(
            STREAMING_ENDPOINT,
            json=payload,
            headers=headers,
            stream=True,
            timeout=60
        )

        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Content-Type: {response.headers.get('content-type', 'Not set')}")

        if response.status_code == 200:
            print("✅ Streaming endpoint connected successfully")

            # Collect streaming data
            collected_content = ""
            chunk_count = 0
            request_id = None
            completion_data = None

            print("📺 Streaming response:")
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    chunk_count += 1
                    data_str = line[6:]  # Remove "data: " prefix

                    if data_str == "[DONE]":
                        print("🏁 Stream completed")
                        break

                    try:
                        chunk_data = json.loads(data_str)
                        chunk_type = chunk_data.get('type', 'unknown')

                        if chunk_type == 'content':
                            content = chunk_data.get('content', '')
                            collected_content += content
                            print(f"📝 Content chunk: '{content[:20]}...'")
                            request_id = chunk_data.get('request_id')

                        elif chunk_type == 'completion':
                            completion_data = chunk_data
                            print(f"✅ Completion data received")
                            print(f"📊 Total content length: {len(chunk_data.get('total_content', ''))}")
                            print(f"⏱️ Response time: {chunk_data.get('response_time_ms', 'N/A')}ms")
                            print(f"🎯 Tokens used: {chunk_data.get('tokens_used', 'N/A')}")

                    except json.JSONDecodeError:
                        print(f"⚠️ Could not parse chunk: {data_str[:50]}...")

            print(f"\n📊 Streaming Summary:")
            print(f"   Chunks received: {chunk_count}")
            print(f"   Content length: {len(collected_content)}")
            print(f"   Request ID: {request_id}")
            print(f"   Completion tracking: {'✅' if completion_data else '❌'}")

            return request_id
        else:
            print(f"❌ Streaming endpoint test FAILED")
            print(f"📄 Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Streaming endpoint test ERROR: {e}")
        return None

def test_error_scenarios():
    """Test error scenarios to verify tracking works correctly"""
    print("\n🚨 Testing Error Scenarios...")

    # Test 1: Empty message
    print("📋 Test 1: Empty message")
    try:
        response = requests.post(
            REGULAR_ENDPOINT,
            json={"message": ""},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"   Status: {response.status_code} (expected 400)")
        if response.status_code == 400:
            print("   ✅ Empty message handled correctly")
        else:
            print("   ❌ Unexpected response for empty message")
    except Exception as e:
        print(f"   ❌ Error testing empty message: {e}")

    # Test 2: Invalid JSON
    print("📋 Test 2: Invalid JSON")
    try:
        response = requests.post(
            REGULAR_ENDPOINT,
            data="invalid json",
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"   Status: {response.status_code} (expected 400)")
        if response.status_code == 400:
            print("   ✅ Invalid JSON handled correctly")
        else:
            print("   ❌ Unexpected response for invalid JSON")
    except Exception as e:
        print(f"   ❌ Error testing invalid JSON: {e}")

def check_backend_logs():
    """Check if tracking logs are appearing"""
    print("\n📋 Checking Backend Logs for Tracking Messages...")
    print("💡 Run this command to see tracking logs:")
    print("   docker compose logs backend | grep 'TRACKING' | tail -10")
    print("\n🔍 Look for messages like:")
    print("   📝 TRACKING: Created request record [pub_...]")
    print("   📝 TRACKING STREAM: Created request record [stream_...]")
    print("   ✅ TRACKING STREAM: Updated completion for [...]")

def main():
    """Run comprehensive tests"""
    print("🚀 Enhanced Public Chatbot Tracking Test Suite")
    print("=" * 60)

    # Test regular endpoint
    regular_request_id = test_regular_endpoint()

    # Wait a moment between tests
    time.sleep(2)

    # Test streaming endpoint
    streaming_request_id = test_streaming_endpoint()

    # Wait a moment between tests
    time.sleep(2)

    # Test error scenarios
    test_error_scenarios()

    # Show log checking instructions
    check_backend_logs()

    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   Regular endpoint: {'✅ PASSED' if regular_request_id else '❌ FAILED'}")
    print(f"   Streaming endpoint: {'✅ PASSED' if streaming_request_id else '❌ FAILED'}")

    if regular_request_id or streaming_request_id:
        print(f"\n🎯 Next Steps:")
        print(f"   1. Check Django admin: {BASE_URL}/admin/public_chatbot/publicchatrequest/")
        print(f"   2. Look for request IDs:")
        if regular_request_id:
            print(f"      • Regular: {regular_request_id}")
        if streaming_request_id:
            print(f"      • Streaming: {streaming_request_id}")
        print(f"   3. Verify tracking data is complete")

    print("\n✨ Test completed!")

if __name__ == "__main__":
    main()