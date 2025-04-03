#!/usr/bin/env python3
"""
macOS Permissions Helper

This script helps users set up the required permissions for keyboard monitoring on macOS.
It provides instructions and tests if the permissions are correctly configured.
"""

import sys
import os
import subprocess

def check_macos_version():
    """Check if we're running on macOS and get the version"""
    if sys.platform != 'darwin':
        return False, "Not running on macOS"
    
    try:
        # Get macOS version
        result = subprocess.run(['sw_vers', '-productVersion'], 
                               capture_output=True, text=True, check=True)
        version = result.stdout.strip()
        return True, f"macOS {version}"
    except Exception as e:
        return True, f"macOS (version unknown): {e}"

def check_accessibility_permissions():
    """Check if the Terminal app has accessibility permissions"""
    try:
        # This command checks if Terminal is allowed to control the computer
        result = subprocess.run([
            'osascript', 
            '-e', 
            'tell application "System Events" to keystroke ""'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return True, "Accessibility permissions appear to be granted"
        else:
            return False, f"Accessibility permissions not granted: {result.stderr}"
    except Exception as e:
        return False, f"Error checking permissions: {e}"

def print_instructions():
    """Print instructions for setting up permissions on macOS"""
    print("\n" + "="*70)
    print("INSTRUCTIONS FOR ENABLING KEYBOARD MONITORING ON MACOS")
    print("="*70)
    
    print("\nTo allow keyboard monitoring, you need to grant permissions to Terminal:")
    print("\n1. Open System Preferences > Security & Privacy > Privacy")
    print("2. Select 'Accessibility' from the sidebar")
    print("3. Click the lock icon to make changes (you may need to enter your password)")
    print("4. Find and check 'Terminal' in the list")
    print("   - If Terminal is not in the list, click '+' and add it manually")
    print("5. Restart Terminal after granting permissions")
    
    print("\nAdditional notes:")
    print("- If using a virtual environment, grant permissions to the Python executable")
    print("- On newer macOS versions, you might need to grant permissions to")
    print("  the Python app itself rather than Terminal")
    print("- For Flutter integration, the Flutter process might need permissions too")
    print("\nAfter granting permissions, run this script again to verify.\n")

def main():
    print("macOS Keyboard Monitoring Permission Helper")
    is_macos, version_info = check_macos_version()
    
    if not is_macos:
        print(f"This script is for macOS only. Detected: {version_info}")
        sys.exit(1)
    
    print(f"Detected: {version_info}")
    
    has_permissions, perm_message = check_accessibility_permissions()
    print(f"Accessibility status: {perm_message}")
    
    if has_permissions:
        print("\n✅ Good news! Terminal appears to have the required permissions.")
        print("   Keyboard monitoring should work correctly.")
    else:
        print("\n❌ Terminal does not have the required permissions.")
        print_instructions()
        
    print("\nTo test if permissions are working correctly, this script will try")
    print("to monitor a few key presses.")
    
    input("\nPress Enter to start the test (you will need to press some keys) or Ctrl+C to exit: ")
    
    try:
        print("\nListening for key presses for 5 seconds... Type something:")
        
        # Try to import the necessary libraries
        try:
            import Quartz
            from AppKit import NSEvent
            
            # Set up a simple event tap for testing
            def callback(proxy, event_type, event, refcon):
                if event_type in (Quartz.kCGEventKeyDown,):
                    keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                    print(f"Key pressed! (keycode: {keycode})")
                return event
            
            # Create a test event tap
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
                callback,
                None
            )
            
            if not tap:
                print("❌ Failed to create event tap. Accessibility permissions are likely missing.")
                print_instructions()
                return
            
            # Set up the run loop
            run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            Quartz.CFRunLoopAddSource(
                Quartz.CFRunLoopGetCurrent(),
                run_loop_source,
                Quartz.kCFRunLoopCommonModes
            )
            Quartz.CGEventTapEnable(tap, True)
            
            # Run for a short time
            import time
            timeout = time.time() + 5  # 5 seconds
            while time.time() < timeout:
                Quartz.CFRunLoopRunInMode(
                    Quartz.kCFRunLoopDefaultMode, 
                    0.1,  # Run for short intervals
                    False
                )
            
            print("\n✅ Test completed. If you saw 'Key pressed!' messages, permissions are working!")
            print("   If not, you may need to grant accessibility permissions.")
            
        except ImportError as e:
            print(f"\n❌ Could not import required libraries: {e}")
            print("   Please make sure pyobjc is installed:")
            print("   pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-Quartz")
            
    except KeyboardInterrupt:
        print("\nTest cancelled.")

if __name__ == "__main__":
    main()
