#!/usr/bin/env python3
"""
Troubleshooting script for the Python server
This helps verify the environment and dependencies needed for keyboard tracking
"""

import sys
import platform
import importlib.util

def check_module(name):
    """Check if a module can be imported"""
    spec = importlib.util.find_spec(name)
    if spec is not None:
        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return True, "✓ Successfully imported"
        except Exception as e:
            return False, f"✗ Import error: {e}"
    else:
        return False, "✗ Module not found"

def main():
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print("\nChecking required modules:")
    
    modules = [
        "flask", 
        "websockets", 
        "pynput", 
        "objc" if platform.system() == "Darwin" else "dummy",
        "Quartz" if platform.system() == "Darwin" else "dummy"
    ]
    
    for module in modules:
        if module == "dummy":
            continue
        success, message = check_module(module)
        print(f"{module}: {message}")
    
    if platform.system() == "Darwin":
        print("\nMacOS specific troubleshooting:")
        print("1. Try installing pyobjc components:")
        print("   pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-Quartz")
        print("2. If using a virtual environment, ensure it has access to system frameworks.")
        print("3. For keyboard monitoring on macOS, you may need to grant accessibility permissions.")
    
    print("\nVerifying JSON serialization:")
    import json
    test_data = {"test": "value", "number": 42}
    try:
        serialized = json.dumps(test_data).encode('utf-8')
        print(f"✓ JSON serialization works: {serialized}")
    except Exception as e:
        print(f"✗ JSON serialization failed: {e}")

if __name__ == "__main__":
    main()


# dfggf