"""Mock Hermes ACP server for testing.

This script simulates the Hermes Agent Client Protocol (ACP) over stdio.
It reads JSON-RPC requests from stdin and writes JSON-RPC responses to stdout.
"""
from __future__ import annotations

import json
import sys


def handle_request(req: dict) -> list[dict]:
    """Process a single JSON-RPC request and return a list of JSON-RPC responses/notifications to send back."""
    responses = []
    req_id = req.get("id")
    method = req.get("method")
    
    # 1. Always acknowledge the request if it has an id
    if req_id is not None:
        result = {}
        if method == "initialize":
            result = {"protocolVersion": 1, "agentInfo": {"name": "mock", "version": "1.0"}}
        elif method == "session/new":
            result = {"sessionId": "mock-session-id"}
        elif method == "session/prompt":
            result = {"stopReason": "end_turn"}
        else:
            # Just in case
            result = {"sessionId": "mock-session-id"}
            
        responses.append({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        })

    # 2. Simulate streaming updates for the prompt method
    if method == "session/prompt":
        session_id = req.get("params", {}).get("sessionId", "test-session")
        
        # Simulate an agent message chunk
        responses.append({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {
                        "type": "text",
                        "text": "Hello from mock hermes!"
                    }
                }
            }
        })
        
        # Simulate a tool call
        responses.append({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call",
                    "toolCallId": "call_123",
                    "title": "Test Tool"
                }
            }
        })
        
    return responses


def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line_str = line.strip()
            if not line_str:
                continue
                
            req = json.loads(line_str)
            responses = handle_request(req)
            
            for resp in responses:
                out = json.dumps(resp) + "\n"
                sys.stdout.write(out)
                sys.stdout.flush()
                
        except Exception as e:
            print(f"Mock error: {e}", file=sys.stderr)
            sys.stderr.flush()
            break

if __name__ == "__main__":
    main()
