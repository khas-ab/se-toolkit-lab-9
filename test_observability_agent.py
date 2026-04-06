#!/usr/bin/env python3
"""Test the agent's observability tools via WebSocket."""

import asyncio
import json
import sys
from websockets.asyncio.client import connect

async def test_agent_query(question: str) -> str:
    """Send a question to the agent and get the response."""
    uri = "ws://localhost:42002/ws/chat?access_key=nanobot-key"
    
    async with connect(uri) as websocket:
        # Send the question
        await websocket.send(json.dumps({"text": question}))
        
        # Collect response chunks
        response_parts = []
        try:
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)
                if data.get("type") == "chunk":
                    response_parts.append(data.get("text", ""))
                elif data.get("type") == "done":
                    break
                elif data.get("type") == "error":
                    return f"Error: {data.get('text', 'Unknown error')}"
        except Exception as e:
            return f"Connection error: {e}"
        
        return "".join(response_parts)

async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_observability_agent.py <question>")
        sys.exit(1)
    
    question = " ".join(sys.argv[1:])
    print(f" Asking agent: {question}\n")
    response = await test_agent_query(question)
    print(f"Agent response:\n{response}")

if __name__ == "__main__":
    asyncio.run(main())
