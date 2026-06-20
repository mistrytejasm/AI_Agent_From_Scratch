import sys
import os
import time

# Reconfigure stdout/stderr to UTF-8 on Windows for emoji support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Add the project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi.testclient import TestClient
from api.main import app

def test_fastapi_endpoints():
    print("=== Starting API Integration Tests ===")
    
    # Using 'with TestClient' ensures startup and shutdown lifespan events run
    with TestClient(app) as client:
        print("\n1. Testing Redirect to Swagger Docs...")
        response = client.get("/", follow_redirects=True)
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()
        print("🟢 Redirect to Docs: OK")
        
        print("\n2. Testing GET /api/sessions (List)...")
        response = client.get("/api/sessions/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"🟢 List Sessions: OK (Found {len(response.json())} sessions)")
        
        print("\n3. Testing POST /api/sessions (Create)...")
        session_title = f"API Test Session {int(time.time())}"
        response = client.post("/api/sessions/", json={"title": session_title})
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == session_title
        session_id = data["id"]
        print(f"🟢 Create Session: OK (ID: {session_id})")
        
        try:
            print("\n4. Testing POST /api/chat (Sync Chat)...")
            chat_payload = {
                "session_id": session_id,
                "message": "Hi, please say 'API Sync OK!'",
                "user_id": "test_user_api"
            }
            response = client.post("/api/chat/", json=chat_payload)
            assert response.status_code == 200
            chat_data = response.json()
            assert chat_data["session_id"] == session_id
            print(f"   -> Agent Sync Response: '{chat_data['response'].strip()}'")
            print("🟢 Sync Chat: OK")
            
            print("\n5. Testing POST /api/chat/stream (SSE Streaming Chat)...")
            stream_payload = {
                "session_id": session_id,
                "message": "Please say 'API Streaming OK!'",
                "user_id": "test_user_api"
            }
            
            # Using stream=True allows iterating over line chunks
            tokens_received = []
            tool_calls_received = []
            
            stream_res = client.post("/api/chat/stream", json=stream_payload, headers={"Accept": "text/event-stream"})
            assert stream_res.status_code == 200
            
            # Iterate over lines of Server-Sent Events
            for line in stream_res.iter_lines():
                if not line:
                    continue
                
                decoded_line = line.strip()
                if decoded_line.startswith("data: "):
                    event_json = decoded_line[6:] # Strip 'data: ' prefix
                    try:
                        event_data = json_loads_fallback(event_json)
                        event_type = event_data.get("type")
                        
                        if event_type == "token":
                            tokens_received.append(event_data.get("content", ""))
                        elif event_type == "tool_call":
                            tool_calls_received.append(event_data.get("name"))
                            print(f"   -> SSE Tool Call Alert: {event_data.get('name')}")
                        elif event_type == "done":
                            print("   -> SSE Stream Complete Event received.")
                        elif event_type == "error":
                            print(f"   -> SSE Error: {event_data.get('detail')}")
                    except Exception as e:
                        print(f"   -> Error parsing line: {decoded_line} ({e})")
            
            full_response = "".join(tokens_received)
            print(f"   -> Agent Streamed Response: '{full_response.strip()}'")
            assert len(tokens_received) > 0, "Should receive streaming text tokens"
            print("🟢 SSE Streaming Chat: OK")
            
            print("\n6. Testing GET /api/memories (List Memories)...")
            response = client.get("/api/memories/", params={"user_id": "test_user_api"})
            assert response.status_code == 200
            memories_list = response.json()
            assert isinstance(memories_list, list)
            print(f"🟢 List Memories: OK (Found {len(memories_list)} memories for test_user_api)")
            
            print("\n7. Testing POST /api/memories/consolidate (Consolidation API)...")
            response = client.post("/api/memories/consolidate", json={"user_id": "test_user_api"})
            assert response.status_code == 200
            consol_data = response.json()
            assert consol_data["status"] == "success"
            print(f"🟢 Consolidation API: OK (merged={consol_data['duplicates_merged']}, stale_deleted={consol_data['stale_deleted']})")
            
        finally:
            print("\n8. Cleaning up: DELETE /api/sessions/{session_id}...")
            response = client.delete(f"/api/sessions/{session_id}")
            assert response.status_code == 200
            print(f"🟢 Delete Session: OK ({response.json()['message']})")

    print("\n=== All API Integration Checks Passed Successfully! ===")

def json_loads_fallback(json_str: str) -> dict:
    """Helper method to load json with basic python stdlib fallback."""
    import json
    return json.loads(json_str)

if __name__ == "__main__":
    test_fastapi_endpoints()
