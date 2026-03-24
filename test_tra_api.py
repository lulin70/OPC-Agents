#!/usr/bin/env python3
"""
Test script for TRAE API connection
"""

import requests

# Test basic TRAE API connection
def test_tra_api():
    print("Testing TRAE API connection...")
    
    # Try different endpoints
    endpoints = [
        "https://api.trae.cn/v1/chat",
        "https://api.trae.cn/chat",
        "https://api.trae.cn/v1",
        "https://api.trae.cn"
    ]
    
    api_key = "sk-KCGKNVVDgnQByDOFr0Nb2A9d2gKNHB8stNTsrkoaHpPBFzU0"
    
    for endpoint in endpoints:
        print(f"\nTesting endpoint: {endpoint}")
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'gpt-4',
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are a helpful assistant.'
                },
                {
                    'role': 'user',
                    'content': 'Hello, test message'
                }
            ],
            'temperature': 0.7,
            'max_tokens': 100
        }
        
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            
            if response.status_code == 200:
                print("✓ API connection successful!")
                return True
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n✗ API connection failed for all endpoints")
    return False

if __name__ == "__main__":
    test_tra_api()