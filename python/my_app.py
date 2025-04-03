import os
import sys
import json
import threading
import time
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# Debug information
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Python path: {sys.path}")

# Get port from environment variable
port = int(os.environ.get("PORT", 8080))
ws_port = port + 1  # WebSocket port will be HTTP port + 1
debug = os.environ.get("DEBUG", "False").lower() == "true"

# Force keyboard tracking mode (for debugging)
FORCE_KEYBOARD_MODE = os.environ.get("FORCE_KEYBOARD_MODE", "").lower()
if FORCE_KEYBOARD_MODE:
    print(f"Forcing keyboard tracking mode: {FORCE_KEYBOARD_MODE}")

# Determine platform
PLATFORM = sys.platform
IS_MACOS = PLATFORM == 'darwin'
print(f"Platform detected: {PLATFORM} (macOS: {IS_MACOS})")

# Keyboard event tracking
keyboard_events = []
is_tracking = False
keyboard_listener = None
ws_connected_clients = set()
macos_event_tap = None  # macOS specific event tap

# Define a function to make JSON responses for the simple HTTP server
def json_response(data):
    return json.dumps(data).encode('utf-8')

# Check if a module can be imported
def is_module_available(module_name):
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False

# Initialize keyboard tracking variables
KEYBOARD_AVAILABLE = False
PYNPUT_AVAILABLE = False
QUARTZ_AVAILABLE = False

# Initialize broadcast function for keyboard events
async def broadcast_event(event):
    if not ws_connected_clients:
        return
        
    # Convert event to JSON string
    event_json = json.dumps(event)
    
    # Send to all connected clients
    disconnected_clients = set()
    for client in ws_connected_clients:
        try:
            await client.send(event_json)
        except Exception:
            # Mark client for removal
            disconnected_clients.add(client)
    
    # Remove disconnected clients
    for client in disconnected_clients:
        ws_connected_clients.remove(client)

# Define a safe way to run async code from sync context #fffff cc
def run_async_in_thread(coro):
    if not ws_connected_clients:
        return
    threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()

# Define keyboard tracking functions for different backends
class KeyboardTracking:
    @staticmethod
    def create():
        """Factory method to create the appropriate keyboard tracker"""
        # Force specific backend if requested
        if FORCE_KEYBOARD_MODE == "pynput":
            return PynputKeyboardTracking() if is_module_available("pynput") else DummyKeyboardTracking()
        elif FORCE_KEYBOARD_MODE == "quartz":
            if IS_MACOS and is_module_available("Quartz"):
                return MacOSKeyboardTracking()
            return DummyKeyboardTracking()
        
        # Auto-detect available backend
        if is_module_available("pynput"):
            print("Using pynput for keyboard tracking")
            return PynputKeyboardTracking()
        elif IS_MACOS and is_module_available("Quartz"):
            print("Using macOS Quartz for keyboard tracking")
            return MacOSKeyboardTracking()
        else:
            print("No keyboard tracking method available")
            return DummyKeyboardTracking()

class DummyKeyboardTracking:
    """Dummy implementation when no keyboard tracking is available"""
    def __init__(self):
        print("WARNING: Using dummy keyboard tracking implementation")
        self.available = False
    
    def start(self):
        print("Keyboard tracking not available")
        return False
        
    def stop(self):
        return False

class PynputKeyboardTracking:
    """Pynput-based keyboard tracking implementation"""
    def __init__(self):
        try:
            from pynput import keyboard
            self.keyboard = keyboard
            self.available = True
            self.listener = None
            print("Pynput keyboard tracking initialized")
        except ImportError as e:
            print(f"Failed to initialize pynput: {e}")
            self.available = False
    
    def start(self):
        global is_tracking, keyboard_events
        if not self.available or is_tracking:
            return False
        
        try:
            keyboard_events = []
            self.listener = self.keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self.listener.start()
            is_tracking = True
            print("Pynput keyboard tracking started")
            return True
        except Exception as e:
            print(f"Error starting pynput keyboard tracking: {e}")
            return False
    
    def stop(self):
        global is_tracking
        if not is_tracking:
            return False
        
        if self.listener:
            self.listener.stop()
            self.listener = None
            is_tracking = False
            print("Pynput keyboard tracking stopped")
            return True
        return False
    
    def _on_key_press(self, key):
        try:
            key_char = key.char
        except AttributeError:
            key_char = str(key)
        
        event = {
            "type": "press",
            "key": key_char,
            "timestamp": time.time()
        }
        keyboard_events.append(event)
        print(f"Key pressed: {key_char}")
        
        # Schedule broadcasting using a separate thread to avoid asyncio issues
        run_async_in_thread(broadcast_event(event))
        return True
        
    def _on_key_release(self, key):
        try:
            key_char = key.char
        except AttributeError:
            key_char = str(key)
            
        event = {
            "type": "release",
            "key": key_char,
            "timestamp": time.time()
        }
        keyboard_events.append(event)
        
        # Schedule broadcasting using a separate thread to avoid asyncio issues
        run_async_in_thread(broadcast_event(event))
        return True

class MacOSKeyboardTracking:
    """macOS-specific keyboard tracking implementation"""
    def __init__(self):
        try:
            # Test imports but do minimal initialization here
            import Quartz
            from AppKit import NSEvent
            self.Quartz = Quartz
            self.NSEvent = NSEvent
            self.available = True
            self.event_tap = None
            self.run_loop_source = None
            self.thread = None
            print("macOS Quartz keyboard tracking initialized")
        except ImportError as e:
            print(f"Failed to initialize macOS Quartz keyboard tracking: {e}")
            self.available = False
    
    def start(self):
        global is_tracking, keyboard_events
        if not self.available or is_tracking:
            return False
        
        try:
            keyboard_events = []
            
            # Create callback function for event tap
            def callback(proxy, event_type, event, refcon):
                if event_type in (self.Quartz.kCGEventKeyDown, self.Quartz.kCGEventKeyUp):
                    key_code = self.Quartz.CGEventGetIntegerValueField(event, self.Quartz.kCGKeyboardEventKeycode)
                    
                    # Get character representation
                    ns_event = self.NSEvent.eventWithCGEvent_(event)
                    if ns_event:
                        characters = ns_event.charactersIgnoringModifiers()
                        key_char = characters if characters else f"Key({key_code})"
                    else:
                        key_char = f"Key({key_code})"
                    
                    # Create event data
                    event_type_str = "press" if event_type == self.Quartz.kCGEventKeyDown else "release"
                    
                    event_data = {
                        "type": event_type_str,
                        "key": key_char,
                        "keycode": int(key_code),
                        "timestamp": time.time()
                    }
                    keyboard_events.append(event_data)
                    print(f"Key {event_type_str}: {key_char} (code: {key_code})")
                    
                    # Schedule broadcasting in a separate thread
                    run_async_in_thread(broadcast_event(event_data))
                
                # Pass event through to the system
                return event
                
            # Create event tap
            print("Creating macOS Quartz event tap...")
            self.event_tap = self.Quartz.CGEventTapCreate(
                self.Quartz.kCGSessionEventTap,  # Get events at session level
                self.Quartz.kCGHeadInsertEventTap,  # Insert at head of event chain
                self.Quartz.kCGEventTapOptionDefault,  # Default options
                self.Quartz.CGEventMaskBit(self.Quartz.kCGEventKeyDown) | 
                self.Quartz.CGEventMaskBit(self.Quartz.kCGEventKeyUp),  # Monitor key down and up
                callback,  # Callback function
                None  # User data (not used)
            )
            
            if not self.event_tap:
                print("Failed to create event tap. Accessibility permissions may be needed.")
                return False
            
            # Create run loop source and add to current run loop
            print("Setting up macOS run loop source...")
            self.run_loop_source = self.Quartz.CFMachPortCreateRunLoopSource(
                None, self.event_tap, 0
            )
            
            # Enable the event tap
            self.Quartz.CGEventTapEnable(self.event_tap, True)
            
            # Start run loop in a separate thread
            def run_loop_thread():
                run_loop = self.Quartz.CFRunLoopGetCurrent()
                self.Quartz.CFRunLoopAddSource(
                    run_loop,
                    self.run_loop_source,
                    self.Quartz.kCFRunLoopCommonModes
                )
                print("macOS run loop starting...")
                self.Quartz.CFRunLoopRun()
                print("macOS run loop ended")
            
            self.thread = threading.Thread(target=run_loop_thread, daemon=True)
            self.thread.start()
            
            is_tracking = True
            print("macOS Quartz keyboard tracking started")
            return True
        except Exception as e:
            import traceback
            print(f"Error starting macOS keyboard tracking: {e}")
            traceback.print_exc()
            return False
    
    def stop(self):
        global is_tracking
        if not is_tracking or not self.event_tap:
            return False
        
        try:
            # Disable the event tap
            self.Quartz.CGEventTapEnable(self.event_tap, False)
            
            # Stop the run loop
            try:
                if hasattr(self.Quartz, 'CFRunLoopStop') and hasattr(self.Quartz, 'CFRunLoopGetCurrent'):
                    self.Quartz.CFRunLoopStop(self.Quartz.CFRunLoopGetCurrent())
            except Exception as e:
                print(f"Warning: Couldn't stop run loop cleanly: {e}")
            
            self.event_tap = None
            self.run_loop_source = None
            is_tracking = False
            print("macOS Quartz keyboard tracking stopped")
            return True
        except Exception as e:
            print(f"Error stopping macOS keyboard tracking: {e}")
            return False

# Create the appropriate keyboard tracker
keyboard_tracker = KeyboardTracking.create()
KEYBOARD_AVAILABLE = keyboard_tracker.available

# Set up the start and stop functions
def start_keyboard_tracking():
    return keyboard_tracker.start()

def stop_keyboard_tracking():
    return keyboard_tracker.stop()

# Try to import required packages
try:
    # Look for packages in the same directory as this script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flask import Flask, jsonify, request
    print("Flask imported successfully!")
    
    # Try to import websockets
    try:
        import websockets
        print("Websockets imported successfully!")
        WEBSOCKET_AVAILABLE = True
    except ImportError as e:
        print(f"Error importing websockets: {e}")
        print("WebSocket functionality will not be available")
        WEBSOCKET_AVAILABLE = False

    USE_FLASK = True
except ImportError as e:
    print(f"Error importing Flask: {e}")
    print("Using built-in HTTP server instead")
    USE_FLASK = False
    
    # Try to import websockets for non-Flask mode
    try:
        import websockets
        print("Websockets imported successfully!")
        WEBSOCKET_AVAILABLE = True
    except ImportError as e:
        print(f"Error importing websockets: {e}")
        print("WebSocket functionality will not be available")
        WEBSOCKET_AVAILABLE = False

# WebSocket handler with improved debugging
async def websocket_handler(websocket, path):
    # Register client
    ws_connected_clients.add(websocket)
    client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    print(f"WebSocket client connected from {client_info}. Path: '{path}', Total clients: {len(ws_connected_clients)}")
    
    try:
        # Send initial status
        await websocket.send(json.dumps({
            "type": "status", 
            "isTracking": is_tracking,
            "keyboardAvailable": KEYBOARD_AVAILABLE
        }))
        
        # Send existing events if tracking is already active
        if is_tracking and keyboard_events:
            await websocket.send(json.dumps({
                "type": "init_events",
                "events": keyboard_events
            }))
        
        # Keep connection open and handle commands
        async for message in websocket:
            try:
                data = json.loads(message)
                command = data.get('command')
                print(f"Received WebSocket command: {command}")
                
                if command == 'start_tracking':
                    if KEYBOARD_AVAILABLE:
                        success = start_keyboard_tracking()
                        await websocket.send(json.dumps({
                            "type": "command_response",
                            "command": "start_tracking",
                            "success": success,
                            "message": "Keyboard tracking started" if success else "Keyboard tracking already running"
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "command_response",
                            "command": "start_tracking",
                            "success": False,
                            "message": "Keyboard tracking not available on this platform"
                        }))
                    
                elif command == 'stop_tracking':
                    if KEYBOARD_AVAILABLE:
                        success = stop_keyboard_tracking()
                        await websocket.send(json.dumps({
                            "type": "command_response",
                            "command": "stop_tracking",
                            "success": success,
                            "message": "Keyboard tracking stopped" if success else "Keyboard tracking not running"
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "command_response",
                            "command": "stop_tracking",
                            "success": False,
                            "message": "Keyboard tracking not available on this platform"
                        }))
                    
                elif command == 'get_events':
                    await websocket.send(json.dumps({
                        "type": "events",
                        "events": keyboard_events,
                        "isTracking": is_tracking
                    }))
                else:
                    print(f"Unknown WebSocket command: {command}")
            except json.JSONDecodeError:
                print("Invalid JSON received via WebSocket")
                pass
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"WebSocket connection closed: {e}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Unregister client
        ws_connected_clients.remove(websocket)
        print(f"WebSocket client disconnected. Remaining clients: {len(ws_connected_clients)}")

# Function to start WebSocket server
def start_websocket_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Troubleshooting: Add debug message about path handling
    print(f"WebSocket server will accept connections on ws://localhost:{ws_port}/")
    print("Note: Any path after the hostname will be passed to the handler")
    
    # Create a fully permissive WebSocket server with no origins checking
    # This is needed to prevent the 403 errors
    try:
        # For older websockets versions (before 10.0)
        if hasattr(websockets, 'server'):
            start_server = websockets.serve(
                websocket_handler, 
                '0.0.0.0', 
                ws_port,
                ping_interval=30,
                ping_timeout=10,
                # Explicitly disable origin checking 
                origins=None,
                # Remove process_request parameter which can cause issues
            )
        else:
            # For newer websockets versions (10.0+)
            start_server = websockets.serve(
                websocket_handler, 
                '0.0.0.0', 
                ws_port,
                ping_interval=30,
                ping_timeout=10
            )
    
        print(f"Starting WebSocket server on port {ws_port}")
        
        # Log connection information to help with debugging
        print(f"WebSocket URL for clients: ws://localhost:{ws_port}/")
        
        loop.run_until_complete(start_server)
        loop.run_forever()
    except Exception as e:
        print(f"Error in WebSocket server: {e}")
        # Add more detailed error tracing
        import traceback
        traceback.print_exc()
    finally:
        loop.close()

# Start WebSocket server in a separate thread if available
if WEBSOCKET_AVAILABLE:
    ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()

# Flask application
if USE_FLASK:
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        ws_status = f"WebSocket server running on port {ws_port}" if WEBSOCKET_AVAILABLE else "WebSocket not available"
        return jsonify({
            "message": f"Python Flask API is running on port {port}",
            "websocket": ws_status,
            "webSocketPort": ws_port if WEBSOCKET_AVAILABLE else None
        })
    
    @app.route('/api/hello')
    def hello():
        return jsonify({"message": "Hello from Python!"})
    
    @app.route('/api/keyboard/start', methods=['POST'])
    def start_keyboard():
        if not KEYBOARD_AVAILABLE:
            return jsonify({"success": False, "message": "Keyboard tracking not available"})
        
        success = start_keyboard_tracking()
        return jsonify({
            "success": success,
            "message": "Keyboard tracking started" if success else "Keyboard tracking already running"
        })
    
    @app.route('/api/keyboard/stop', methods=['POST'])
    def stop_keyboard():
        if not KEYBOARD_AVAILABLE:
            return jsonify({"success": False, "message": "Keyboard tracking not available"})
        
        success = stop_keyboard_tracking()
        return jsonify({
            "success": success,
            "message": "Keyboard tracking stopped" if success else "Keyboard tracking not running"
        })
    
    @app.route('/api/keyboard/events')
    def get_events():
        global keyboard_events
        return jsonify({
            "events": keyboard_events,
            "isTracking": is_tracking
        })
    
    @app.route('/api/keyboard/status')
    def get_status():
        return jsonify({
            "isTracking": is_tracking,
            "eventsCount": len(keyboard_events),
            "keyboardAvailable": KEYBOARD_AVAILABLE,
            "websocketAvailable": WEBSOCKET_AVAILABLE,
            "websocketPort": ws_port if WEBSOCKET_AVAILABLE else None
        })
    
    if __name__ == '__main__':
        print(f"Starting Flask server on port {port}, debug mode: {debug}")
        app.run(host='0.0.0.0', port=port, debug=debug)

# Fallback HTTP server
else:
    class SimpleHTTPHandler(BaseHTTPRequestHandler):
        def _set_headers(self, content_type='application/json'):
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
        
        def do_OPTIONS(self):
            self._set_headers()
            self.wfile.write(json_response({}))
            
        def do_GET(self):
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            if path == '/':
                self._set_headers()
                ws_status = f"WebSocket server running on port {ws_port}" if WEBSOCKET_AVAILABLE else "WebSocket not available"
                response = {
                    "message": f"Python HTTP server is running on port {port} (Flask not available)",
                    "websocket": ws_status,
                    "webSocketPort": ws_port if WEBSOCKET_AVAILABLE else None
                }
                self.wfile.write(json_response(response))
            elif path == '/api/hello':
                self._set_headers()
                response = {"message": "Hello from Python (without Flask)!"}
                self.wfile.write(json_response(response))
            elif path == '/api/keyboard/events':
                self._set_headers()
                response = {"events": keyboard_events, "isTracking": is_tracking}
                self.wfile.write(json_response(response))
            elif path == '/api/keyboard/status':
                self._set_headers()
                response = {
                    "isTracking": is_tracking,
                    "eventsCount": len(keyboard_events),
                    "keyboardAvailable": KEYBOARD_AVAILABLE,
                    "websocketAvailable": WEBSOCKET_AVAILABLE,
                    "websocketPort": ws_port if WEBSOCKET_AVAILABLE else None
                }
                self.wfile.write(json_response(response))
            else:
                self._set_headers()
                response = {"error": "Not found", "path": self.path}
                self.wfile.write(json_response(response))
                
        def do_POST(self):
            content_length = int(self.headers['Content-Length']) if 'Content-Length' in self.headers else 0
            post_data = self.rfile.read(content_length)
            
            if self.path == '/api/keyboard/start':
                if not KEYBOARD_AVAILABLE:
                    self._set_headers()
                    response = {"success": False, "message": "Keyboard tracking not available"}
                    self.wfile.write(json_response(response))
                    return
                
                success = start_keyboard_tracking()
                self._set_headers()
                response = {
                    "success": success,
                    "message": "Keyboard tracking started" if success else "Keyboard tracking already running"
                }
                self.wfile.write(json_response(response))
            elif self.path == '/api/keyboard/stop':
                if not KEYBOARD_AVAILABLE:
                    self._set_headers()
                    response = {"success": False, "message": "Keyboard tracking not available"}
                    self.wfile.write(json_response(response))
                    return
                
                success = stop_keyboard_tracking()
                self._set_headers()
                response = {
                    "success": success,
                    "message": "Keyboard tracking stopped" if success else "Keyboard tracking not running"
                }
                self.wfile.write(json_response(response))
            else:
                self._set_headers()
                response = {"error": "Not found", "path": self.path}
                self.wfile.write(json_response(response))
    
    print(f"Starting simple HTTP server on port {port}")
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPHandler)
    server.serve_forever()
