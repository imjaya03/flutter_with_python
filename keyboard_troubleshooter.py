#!/usr/bin/env python3
"""
Keyboard Tracking Troubleshooter

This script provides detailed diagnostic information about
keyboard tracking capabilities and tests different methods.
"""

import sys
import platform
import os
import time
import importlib
from threading import Thread

# Define colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print a header with formatting"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")

def print_success(text):
    """Print a success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_warning(text):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠️ {text}{Colors.END}")

def print_error(text):
    """Print an error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def is_module_available(module_name):
    """Check if a module can be imported"""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False

# Display system information
print_header("SYSTEM INFORMATION")
print(f"Python version: {platform.python_version()}")
print(f"System: {platform.system()} {platform.release()} {platform.machine()}")
print(f"Python executable: {sys.executable}")

# Check for basic requirements
print_header("CHECKING MODULES")
pynput_available = is_module_available("pynput")
if pynput_available:
    print_success("pynput module is available")
else:
    print_error("pynput module is not available")

# macOS-specific checks
is_macos = platform.system() == 'Darwin'
macos_modules_available = False

if is_macos:
    print_header("MACOS-SPECIFIC CHECKS")
    
    objc_available = is_module_available("objc")
    if objc_available:
        print_success("objc module is available")
    else:
        print_error("objc module is not available")
        
    appkit_available = is_module_available("AppKit")
    if appkit_available:
        print_success("AppKit module is available")
    else:
        print_error("AppKit module is not available")
        
    quartz_available = is_module_available("Quartz")
    if quartz_available:
        print_success("Quartz module is available")
    else:
        print_error("Quartz module is not available")
    
    macos_modules_available = objc_available and appkit_available and quartz_available
    
    # Check for accessibility permissions
    print_header("ACCESSIBILITY PERMISSIONS CHECK")
    
    if macos_modules_available:
        try:
            import Quartz
            
            # Try to create an event tap to test permissions
            def dummy_callback(proxy, event_type, event, refcon):
                return event
                
            event_tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
                dummy_callback,
                None
            )
            
            if event_tap:
                print_success("Event tap created successfully - accessibility permissions appear to be granted")
                Quartz.CFRelease(event_tap)  # Clean up the event tap
            else:
                print_error("Could not create event tap - accessibility permissions may be missing")
                
        except Exception as e:
            print_error(f"Error testing accessibility permissions: {e}")
            
        # Provide instructions for macOS accessibility permissions
        print("\nTo grant accessibility permissions:")
        print("1. Open System Preferences > Security & Privacy > Privacy")
        print("2. Select 'Accessibility' from the sidebar")
        print("3. Click the lock icon and enter your password")
        print("4. Add or check the box for Terminal or your Python application")
    else:
        print_warning("Cannot check accessibility permissions - required modules are missing")

# Test keyboard monitoring with pynput if available
if pynput_available:
    print_header("TESTING KEYBOARD MONITORING WITH PYNPUT")
    print("This will attempt to monitor keyboard events for 5 seconds.")
    print("Please type a few keys to test if they're detected.")
    
    try:
        from pynput import keyboard
        events = []
        
        def on_press(key):
            try:
                key_char = key.char
            except AttributeError:
                key_char = str(key)
            events.append(f"Press: {key_char}")
            print(f"Detected key press: {key_char}")
        
        def on_release(key):
            try:
                key_char = key.char
            except AttributeError:
                key_char = str(key)
            events.append(f"Release: {key_char}")
            print(f"Detected key release: {key_char}")
        
        input("\nPress Enter to start monitoring keyboard events...")
        print("Monitoring keyboard events for 5 seconds... (type something)")
        
        # Start listener
        listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        listener.start()
        
        # Wait for events
        time.sleep(5)
        
        # Stop listener
        listener.stop()
        listener.join()
        
        if events:
            print_success(f"Successfully detected {len(events)} keyboard events with pynput!")
        else:
            print_warning("No keyboard events detected with pynput.")
            
    except Exception as e:
        print_error(f"Error testing pynput: {e}")

# Test macOS-specific keyboard monitoring if available
if is_macos and macos_modules_available:
    print_header("TESTING KEYBOARD MONITORING WITH MACOS QUARTZ")
    print("This will attempt to monitor keyboard events for 5 seconds using macOS Quartz.")
    print("Please type a few keys to test if they're detected.")
    
    try:
        import Quartz
        from AppKit import NSEvent
        events = []
        stop_flag = False
        
        def callback(proxy, event_type, event, refcon):
            if event_type in (Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp):
                key_code = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                
                # Get character representation
                ns_event = NSEvent.eventWithCGEvent_(event)
                if ns_event:
                    characters = ns_event.charactersIgnoringModifiers()
                    key_char = characters if characters else f"Key({key_code})"
                else:
                    key_char = f"Key({key_code})"
                
                event_type_str = "Press" if event_type == Quartz.kCGEventKeyDown else "Release"
                events.append(f"{event_type_str}: {key_char} (code: {key_code})")
                print(f"Detected {event_type_str.lower()}: {key_char} (code: {key_code})")
            
            return event
        
        def run_event_loop():
            # Create event tap
            event_tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) | 
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp),
                callback,
                None
            )
            
            if not event_tap:
                print_error("Could not create event tap - accessibility permissions may be missing")
                return
            
            # Create run loop source
            run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, event_tap, 0)
            run_loop = Quartz.CFRunLoopGetCurrent()
            Quartz.CFRunLoopAddSource(run_loop, run_loop_source, Quartz.kCFRunLoopCommonModes)
            
            # Enable the event tap
            Quartz.CGEventTapEnable(event_tap, True)
            
            # Run the loop until stop_flag is set
            while not stop_flag:
                result = Quartz.CFRunLoopRunInMode(
                    Quartz.kCFRunLoopDefaultMode,
                    0.1,  # Run for short intervals
                    False
                )
                
            # Clean up
            Quartz.CGEventTapEnable(event_tap, False)
        
        input("\nPress Enter to start monitoring keyboard events with macOS Quartz...")
        print("Monitoring keyboard events for 5 seconds... (type something)")
        
        # Start event loop in a separate thread
        loop_thread = Thread(target=run_event_loop)
        loop_thread.daemon = True
        loop_thread.start()
        
        # Wait for events
        time.sleep(5)
        
        # Stop the event loop
        stop_flag = True
        time.sleep(0.2)  # Give it a moment to stop
        
        if events:
            print_success(f"Successfully detected {len(events)} keyboard events with macOS Quartz!")
        else:
            print_warning("No keyboard events detected with macOS Quartz.")
            
    except Exception as e:
        print_error(f"Error testing macOS Quartz: {e}")
        import traceback
        traceback.print_exc()

# Print summary and recommendations
print_header("SUMMARY AND RECOMMENDATIONS")

keyboard_tracking_available = pynput_available or (is_macos and macos_modules_available)

if keyboard_tracking_available:
    print_success("Keyboard tracking should be available")
    
    if is_macos:
        if macos_modules_available:
            print("Recommended method for macOS: Quartz (native)")
        elif pynput_available:
            print("Using pynput for keyboard tracking on macOS (may be less reliable)")
    else:
        print("Recommended method: pynput")
else:
    print_error("No keyboard tracking methods are available")
    
    if is_macos:
        print("\nFor macOS, install the required dependencies:")
        print("  pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-Quartz")
    else:
        print("\nInstall pynput:")
        print("  pip install pynput")

print("\nMake sure to run the build_python_bundle.sh script after installing dependencies")
print("to ensure they are included in the app.zip file.")

if is_macos:
    print("\nReminder: macOS requires accessibility permissions for keyboard monitoring.")
