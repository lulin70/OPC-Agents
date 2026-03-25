#!/usr/bin/env python3
"""
Test script to verify LLM connection functionality
"""

from opc_manager import OPCManager

def test_llm_connection():
    """Test LLM connection functionality"""
    print("=== Testing LLM Connection ===")
    
    # Initialize OPC Manager
    manager = OPCManager()
    
    # Test GLM model
    print("\n1. Testing GLM model...")
    try:
        response = manager.call_llm_api("你好，请问你是谁？", "glm")
        if response:
            print(f"✓ GLM API response: {response}")
        else:
            print("✗ GLM API call failed")
    except Exception as e:
        print(f"✗ Error testing GLM: {e}")
    
    # Test default model
    print("\n2. Testing default model...")
    try:
        response = manager.call_llm_api("你好，请问你是谁？")
        if response:
            print(f"✓ Default model response: {response}")
        else:
            print("✗ Default model call failed")
    except Exception as e:
        print(f"✗ Error testing default model: {e}")
    
    # Test trae_request with GLM
    print("\n3. Testing trae_request with GLM...")
    try:
        response = manager.trae_request("你好，请问你是谁？", "test_agent", "glm")
        print(f"trae_request response: {response}")
    except Exception as e:
        print(f"✗ Error testing trae_request: {e}")

if __name__ == "__main__":
    test_llm_connection()
