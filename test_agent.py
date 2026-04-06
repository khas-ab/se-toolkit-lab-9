#!/usr/bin/env python3
"""Simple WebSocket client to test the nanobot agent."""

import asyncio
import json
import sys

import websockets

# Get access key from .env.docker.secret
def get_access_key():
    try:
        with open(".env.docker.secret") as f:
            for line in f:
                if line.startswith("NANOBOT_ACCESS_KEY="):
                    return line.strip().split("=", 1)[1]
    except FileNotFoundError:
        pass
    return ""

async def test_agent(message: str):
    access_key = get_access_key()
    ws_url = f"ws://localhost:42002/ws/chat?access_key={access_key}"
    
    print(f"Connecting to {ws_url}...")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"Sending: {message}")
            await websocket.send(json.dumps({"content": message}))
            
            # Receive responses
            responses = []
            async for response in websocket:
                data = json.loads(response)
                print(f"Agent: {data.get('content', '')}")
                responses.append(data.get('content', ''))
                # Stop after getting a complete response
                if data.get('type') == 'text' and not data.get('in_progress', False):
                    break
            
            return '\n'.join(responses)
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    message = sys.argv[1] if len(sys.argv) > 1 else "What went wrong?"
    result = asyncio.run(test_agent(message))
    if result:
        print("\n--- Full Response ---")
        print(result)
