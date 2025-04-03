#!/usr/bin/env python3
"""
WebSocket Test Client
This script helps test your WebSocket server without Flutter.
It connects to the WebSocket server and sends test commands.
"""

import asyncio
import json
import sys
import websockets

async def test_websocket_connection(uri="ws://localhost:8081/"):
    """Test a WebSocket connection to the specified URI"""
    print(f"Attempting to connect to {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket server!")
            
            # Wait for the initial status message
            response = await websocket.recv()
            print(f"Received: {response}")
            data = json.loads(response)
            print(f"Server status: Keyboard tracking {'available' if data.get('keyboardAvailable') else 'not available'}")
            
            # Send a command
            command = {"command": "start_tracking"}
            print(f"Sending command: {command}")
            await websocket.send(json.dumps(command))
            
            # Wait for the response
            response = await websocket.recv()
            print(f"Received response: {response}")
            
            # Keep connection open for a few seconds to receive events
            print("Listening for events for 10 seconds...")
            for _ in range(10):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    print(f"Received event: {response}")
                except asyncio.TimeoutError:
                    # No data received within the timeout period
                    print(".", end="", flush=True)
            
            # Stop tracking
            command = {"command": "stop_tracking"}
            print(f"\nSending command: {command}")
            await websocket.send(json.dumps(command))
            
            # Wait for the response
            response = await websocket.recv()
            print(f"Received response: {response}")
            
    except Exception as e:
        print(f"Error connecting to WebSocket: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # Get WebSocket port from command line argument or use default
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    uri = f"ws://localhost:{port}/"
    
    print(f"WebSocket Test Client for port {port}")
    print("This will help diagnose any connection issues with your WebSocket server")
    
    asyncio.run(test_websocket_connection(uri))
