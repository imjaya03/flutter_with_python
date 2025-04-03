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

# Keyboard event tracking
keyboard_events = []
is_tracking = False
keyboard_listener = None
ws_connected_clients = set()

# Define a function to make JSON responses for the simple HTTP server
# IMPORTANT: This function must be defined at the global scope so all code can access it
def json_response(data):
    return json.dumps(data).encode('utf-8')

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
    
    # Try to import pynput for keyboard tracking c
    try:
        from pynput import keyboard
        print("Pynput imported successfully!")
        KEYBOARD_AVAILABLE = True
        
        # Broadcast keyboard event to all connected WebSocket clients
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
                
        def on_key_press(key):
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
            if WEBSOCKET_AVAILABLE and ws_connected_clients:
                threading.Thread(target=lambda: asyncio.run(broadcast_event(event)), daemon=True).start()
            return True
            
        def on_key_release(key):
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
            if WEBSOCKET_AVAILABLE and ws_connected_clients:
                threading.Thread(target=lambda: asyncio.run(broadcast_event(event)), daemon=True).start()
            return True
            
        def start_keyboard_tracking():
            global keyboard_listener, is_tracking, keyboard_events
            
            if is_tracking:
                return False
                
            keyboard_events = []  # Clear previous events
            keyboard_listener = keyboard.Listener(
                on_press=on_key_press,
                on_release=on_key_release
            )
            keyboard_listener.start()
            is_tracking = True
            return True
            
        def stop_keyboard_tracking():
            global keyboard_listener, is_tracking
            
            if not is_tracking:
                return False
                
            if keyboard_listener:
                keyboard_listener.stop()
                is_tracking = False
                return True
            return False
            
    except ImportError as e:
        print(f"Error importing pynput: {e}")
        print("Keyboard tracking will not be available")
        KEYBOARD_AVAILABLE = False
    
    USE_FLASK = True
except ImportError as e:
    print(f"Error importing Flask: {e}")
    print("Using built-in HTTP server instead")
    USE_FLASK = False
    
    # Try to import websockets
    try:
        import websockets
        print("Websockets imported successfully!")
        WEBSOCKET_AVAILABLE = True
    except ImportError as e:
        print(f"Error importing websockets: {e}")
        print("WebSocket functionality will not be available")
        WEBSOCKET_AVAILABLE = False
    
    # Try to import pynput for keyboard tracking in non-Flask mode
    try:
        from pynput import keyboard
        print("Pynput imported successfully!")
        KEYBOARD_AVAILABLE = True
        
        # Define the same keyboard functions as in the Flask section
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
                
        def on_key_press(key):
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
            if WEBSOCKET_AVAILABLE and ws_connected_clients:
                threading.Thread(target=lambda: asyncio.run(broadcast_event(event)), daemon=True).start()
            return True
            
        def on_key_release(key):
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
            if WEBSOCKET_AVAILABLE and ws_connected_clients:
                threading.Thread(target=lambda: asyncio.run(broadcast_event(event)), daemon=True).start()
            return True
            
        def start_keyboard_tracking():
            global keyboard_listener, is_tracking, keyboard_events
            
            if is_tracking:
                return False
                
            keyboard_events = []  # Clear previous events
            keyboard_listener = keyboard.Listener(
                on_press=on_key_press,
                on_release=on_key_release
            )
            keyboard_listener.start()
            is_tracking = True
            return True
            
        def stop_keyboard_tracking():
            global keyboard_listener, is_tracking
            
            if not is_tracking:
                return False
                
            if keyboard_listener:
                keyboard_listener.stop()
                is_tracking = False
                return True
            return False
    except ImportError as e:
        print(f"Error importing pynput: {e}")
        print("Keyboard tracking will not be available")
        KEYBOARD_AVAILABLE = False

# WebSocket handler
async def websocket_handler(websocket, path):
    # Register client
    ws_connected_clients.add(websocket)
    print(f"WebSocket client connected. Path: {path}, Total clients: {len(ws_connected_clients)}")
    
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
    
    # Update the WebSocket server configuration to be more permissive
    start_server = websockets.serve(
        websocket_handler, 
        '0.0.0.0', 
        ws_port,
        ping_interval=50,
        ping_timeout=30,
        # Add origins=['*'] to allow all connections
        origins=None,  # Accept connections from any origin
        process_request=None,  # No special processing of the request
    )
    
    print(f"Starting WebSocket server on port {ws_port}")
    
    try:
        loop.run_until_complete(start_server)
        loop.run_forever()
    except Exception as e:
        print(f"Error in WebSocket server: {e}")
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
