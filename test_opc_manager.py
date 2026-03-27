#!/usr/bin/env python3

from opc_manager import OPCManager

# 尝试使用debug_mode参数初始化
print("Testing OPCManager initialization with debug_mode parameter...")
try:
    manager = OPCManager(debug_mode=True)
    print("Success! OPCManager initialized with debug_mode=True")
except Exception as e:
    print(f"Error: {e}")
    
# 尝试不使用debug_mode参数初始化
print("\nTesting OPCManager initialization without debug_mode parameter...")
try:
    manager = OPCManager()
    print("Success! OPCManager initialized without debug_mode parameter")
except Exception as e:
    print(f"Error: {e}")