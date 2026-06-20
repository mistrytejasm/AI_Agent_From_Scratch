> **Document Version:** 1.0.0
> **Last Updated:** June 20, 2026
> **Author:** TejasH MistrY

# API Test Documentation (Doc 5)

Welcome to the **API Testing & Verification Guide**. This document serves as a beginner-friendly, step-by-step manual testing guide for all REST and Server-Sent Event (SSE) streaming endpoints of the Scalable Python Chatbot.

Whether you are testing using the interactive browser-based Swagger documentation or using Postman, this guide will help you execute all API tests independently and verify database states.

---

## 🚀 Getting Started & Server Setup

Before starting the tests, you must have the local application server running.

### 1. Booting the FastAPI Server
Open a terminal in the project directory `d:\AI_Projects\Agents\Ai_Agent` and run:
```bash
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```
Leave this terminal window open. The server will hot-reload automatically if code changes.

### 2. Testing Clients
You can perform manual testing using either of the following clients:
*   **FastAPI Swagger UI (Interactive Browser Docs)**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your web browser.
*   **Postman**: Download and open the Postman desktop application.

---

## 📋 1. API Inventory

The server exposes **11 distinct endpoints** divided into three functional modules:

| API Name | HTTP Method | Endpoint URL | Description |
| :--- | :--- | :--- | :--- |
| **List Sessions** | `GET` | `/api/sessions/` | Retrieves all chat sessions sorted by last active. |
| **Create Session** | `POST` | `/api/sessions/` | Creates a new chat session with a title. |
| **Clear All Sessions** | `DELETE` | `/api/sessions/` | Deletes all saved chat sessions and history. |
| **Get Session History** | `GET` | `/api/sessions/{session_id}/messages` | Fetches chronological message history for a session. |
| **Delete Session** | `DELETE` | `/api/sessions/{session_id}` | Deletes a single chat session and its history. |
| **List Memories** | `GET` | `/api/memories/` | Lists all active long-term memories for a user. |
| **Delete Memory ID** | `DELETE` | `/api/memories/{memory_id}` | Permanently deletes a specific memory fact. |
| **Forget Topic** | `POST` | `/api/memories/forget` | Deletes memories matching a topic (or wipse `--all`). |
| **Consolidate Memories**| `POST` | `/api/memories/consolidate` | Triggers memory cleaning, duplicates, and conflicts. |
| **Synchronous Chat** | `POST` | `/api/chat/` | Sends a message to the agent (full ReAct loop). |
| **SSE Streaming Chat** | `POST` | `/api/chat/stream` | Streams tokens & tool alerts in real time. |

---

## 📂 2. Detailed API Testing Guide

---

### Module A: Session Management (`/api/sessions`)

#### 1. Create Session (`POST /api/sessions/`)
*   **Purpose**: Creates a new chat session.
*   **Business Functionality**: Powers the **"+ New Chat"** button on the frontend sidebar, creating a session in the database and returning its ID so routing can update to `/chat/{session_id}`.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/sessions/`
*   **Headers**: `Content-Type: application/json`

##### Request Body Examples
*   **Payload 1 (Valid Default)**:
    ```json
    {}
    ```
*   **Payload 2 (Valid Custom Title)**:
    ```json
    {
      "title": "React Native Scaffold Discussion"
    }
    ```
*   **Payload 3 (Negative / Invalid Types)**:
    ```json
    {
      "title": 12345
    }
    ```

##### Testing Steps
1.  **Swagger UI**:
    *   Expand `POST /api/sessions/`. Click **Try it out**.
    *   Paste Payload 2 in the request body box. Click **Execute**.
2.  **Postman**:
    *   Create a new tab. Set method to `POST`. Enter `http://127.0.0.1:8000/api/sessions/`.
    *   Go to the **Headers** tab, ensure `Content-Type` is `application/json`.
    *   Go to the **Body** tab, select **raw**, select **JSON** format, and paste Payload 2.
    *   Click **Send**.

##### Expected Responses
*   **Success (201 Created)**:
    ```json
    {
      "id": "6a3651185759bea8500b31c5",
      "title": "React Native Scaffold Discussion",
      "created_at": "2026-06-20T08:34:35.123Z",
      "updated_at": "2026-06-20T08:34:35.123Z",
      "metadata": {}
    }
    ```
*   **Error (422 Unprocessable Entity)**: If request schema is broken.

##### Validation Checklist
- [ ] Status code is `201`.
- [ ] Response contains a 24-character hex `"id"` string. Save this ID for the next steps.
- [ ] Timestamp format matches ISO UTC format.

---

#### 2. List Sessions (`GET /api/sessions/`)
*   **Purpose**: Fetch all chat sessions.
*   **Business Functionality**: Populates the sidebar conversation history list on startup.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/sessions/`

##### Request Body Examples
*   **Payloads**: *None (GET requests do not take body payloads).*

##### Testing Steps
1.  **Swagger UI**: Expand `GET /api/sessions/`, click **Try it out**, click **Execute**.
2.  **Postman**: Set method to `GET`, enter `http://127.0.0.1:8000/api/sessions/`, click **Send**.

##### Expected Responses
*   **Success (200 OK)**:
    ```json
    [
      {
        "id": "6a3651185759bea8500b31c5",
        "title": "React Native Scaffold Discussion",
        "created_at": "2026-06-20T08:34:35.123Z",
        "updated_at": "2026-06-20T08:34:35.123Z",
        "metadata": {}
      }
    ]
    ```

##### Validation Checklist
- [ ] Status code is `200`.
- [ ] Response is a JSON list.
- [ ] The session created in the previous step is present.

---

#### 3. Get Session History (`GET /api/sessions/{session_id}/messages`)
*   **Purpose**: Loads past messages for a conversation.
*   **Business Functionality**: Fills the chat bubble feed when clicking an existing chat in the sidebar.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/sessions/{session_id}/messages`
*   **Path Parameters**: `session_id` (Hex string ObjectId of target session).

##### Testing Steps
1.  **Swagger UI**: Expand `GET /api/sessions/{session_id}/messages`, click **Try it out**, enter your session ID in the `session_id` parameter box, click **Execute**.
2.  **Postman**: Set method to `GET`, enter `http://127.0.0.1:8000/api/sessions/<your_session_id>/messages`, click **Send**.

##### Expected Responses
*   **Success (200 OK)**:
    ```json
    [
      {
        "role": "user",
        "content": "Hello, how can I scaffold a React Native app?",
        "timestamp": "2026-06-20T08:35:00Z",
        "tool_calls": null,
        "tool_call_id": null,
        "metadata": {}
      }
    ]
    ```
*   **Error (404 Not Found)**:
    ```json
    {
      "detail": "Session with ID '6a3651185759bea8500b3999' not found."
    }
    ```

##### Validation Checklist
- [ ] Status code is `200` for valid ID, `404` for invalid ID.
- [ ] Messages are sorted chronologically.

---

#### 4. Delete Session (`DELETE /api/sessions/{session_id}`)
*   **Purpose**: Delete a session and its message history.
*   **Business Functionality**: Handles the "Trash" sidebar icon.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/sessions/{session_id}`
*   **Path Parameters**: `session_id`.

##### Testing Steps
1.  **Postman**: Set method to `DELETE`, enter `http://127.0.0.1:8000/api/sessions/<your_session_id>`, click **Send**.

##### Expected Responses
*   **Success (200 OK)**:
    ```json
    {
      "status": "success",
      "message": "Session '6a3651185759bea8500b31c5' and all message history successfully deleted."
    }
    ```

##### Validation Checklist
- [ ] Status is `success`.
- [ ] Performing `GET /api/sessions/{session_id}/messages` now returns a `404`.

---

### Module B: Chat & Agent Execution (`/api/chat`)

---

#### 5. Synchronous Chat (`POST /api/chat/`)
*   **Purpose**: Sends user input to the agent and gets a full, resolved text response.
*   **Business Functionality**: Standard conversational messages.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/chat/`
*   **Headers**: `Content-Type: application/json`

##### Request Body Examples
*   **Payload 1 (Valid Fact Injection)**:
    ```json
    {
      "session_id": "6a3651185759bea8500b31c5",
      "message": "My name is Tejas and I build APIs in Python.",
      "user_id": "default_user"
    }
    ```
*   **Payload 2 (Negative / Missing Session ID)**:
    ```json
    {
      "message": "Hi"
    }
    ```

##### Testing Steps
1.  **Swagger UI**: Expand `POST /api/chat/`. Click **Try it out**. Paste Payload 1 (replacing the session ID with an active one). Click **Execute**.
2.  **Postman**: Set method to `POST`. Enter `http://127.0.0.1:8000/api/chat/`. Select Body -> raw -> JSON. Paste Payload 1. Click **Send**.

##### Expected Responses
*   **Success (200 OK)**:
    ```json
    {
      "session_id": "6a3651185759bea8500b31c5",
      "response": "Nice to meet you, Tejas! I have noted down that you build web APIs in Python."
    }
    ```
*   **Error (404 Not Found)**: If the session ID is missing or incorrect.

##### Validation Checklist
- [ ] Response status code is `200`.
- [ ] Agent extracts facts in background (check memories in the next module).

---

#### 6. SSE Streaming Chat (`POST /api/chat/stream`)
*   **Purpose**: Streams agent response typewriter tokens and tool alert progress blocks.
*   **Business Functionality**: Animates assistant bubbles in real time.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/chat/stream`
*   **Headers**: `Content-Type: application/json`, `Accept: text/event-stream`

##### Request Body Examples
*   **Payload 1 (Triggering Tool - World Clock)**:
    ```json
    {
      "session_id": "6a3651185759bea8500b31c5",
      "message": "What time is it in Tokyo right now?",
      "user_id": "default_user"
    }
    ```
*   **Payload 2 (Triggering Tool - Web Search)**:
    ```json
    {
      "session_id": "6a3651185759bea8500b31c5",
      "message": "Search the web for the latest SpaceX launch update.",
      "user_id": "default_user"
    }
    ```

##### Testing Steps (Important: Postman does not stream dynamically in standard headers tab unless configured, but CMD line `curl` demonstrates it perfectly)
1.  **Command Prompt (cmd)**:
    ```cmd
    curl.exe -X POST "http://127.0.0.1:8000/api/chat/stream" -H "Content-Type: application/json" -H "Accept: text/event-stream" -d "{\"session_id\": \"YOUR_SESSION_ID\", \"message\": \"What time is it in Tokyo?\", \"user_id\": \"default_user\"}"
    ```
2.  **Swagger UI**: Click **Try it out**, fill in the body with Payload 1, click **Execute**. You will see the response field loading and streaming data chunks.

##### Expected Responses
*   **Success Event-Stream Output (200 OK)**:
    ```text
    data: {"type": "tool_call", "name": "get_world_time", "arguments": "{\"iana_timezone\": \"Asia/Tokyo\"}"}
    
    data: {"type": "token", "content": "The"}
    data: {"type": "token", "content": " current"}
    data: {"type": "token", "content": " time"}
    data: {"type": "token", "content": " in"}
    data: {"type": "token", "content": " Tokyo"}
    ...
    data: {"type": "done"}
    ```

##### Validation Checklist
- [ ] Content-Type header in response is `text/event-stream`.
- [ ] Outputs are formatted as `data: { ... }\n\n`.
- [ ] Events have valid `"type"` values: `tool_call`, `token`, or `done`.

---

### Module C: Long-Term Memories (`/api/memories`)

---

#### 7. List Memories (`GET /api/memories/`)
*   **Purpose**: View all facts learned about a user.
*   **Business Functionality**: Memory configuration profile settings dashboard.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/memories/`
*   **Query Parameters**: `user_id` (string, default: `default_user`).

##### Testing Steps
1.  **Postman**: Set method to `GET`, enter `http://127.0.0.1:8000/api/memories/?user_id=default_user`, click **Send**.

##### Expected Responses
*   **Success (200 OK)**:
    ```json
    [
      {
        "id": "6a3651185759bea8500b5555",
        "fact": "User is named Tejas.",
        "category": "personal_info",
        "confidence": 0.95,
        "access_count": 2,
        "created_at": "2026-06-20T08:34:00Z",
        "last_accessed": "2026-06-20T08:38:00Z",
        "metadata": {}
      },
      {
        "id": "6a3651185759bea8500b6666",
        "fact": "User builds APIs in Python.",
        "category": "project_detail",
        "confidence": 0.90,
        "access_count": 1,
        "created_at": "2026-06-20T08:34:05Z",
        "last_accessed": "2026-06-20T08:34:05Z",
        "metadata": {}
      }
    ]
    ```

##### Validation Checklist
- [ ] Facts match what you taught the agent in Step 5 (Chat).
- [ ] Copy the value of a memory `"id"` string for deletion testing.

---

#### 8. Delete Memory ID (`DELETE /api/memories/{memory_id}`)
*   **Purpose**: Forget a single memory fact by ID.
*   **Business Functionality**: Allows users to delete individual memory cards.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/memories/{memory_id}`
*   **Path Parameters**: `memory_id`.

##### Testing Steps
1.  **Postman**: Set method to `DELETE`, enter `http://127.0.0.1:8000/api/memories/<memory_id>`, click **Send**.

##### Expected Responses
*   **Success (200 OK)**:
    ```json
    {
      "status": "success",
      "message": "Memory fact '6a3651185759bea8500b5555' permanently deleted."
    }
    ```

##### Validation Checklist
- [ ] Status code is `200`.
- [ ] Repeating `GET /api/memories/` shows the deleted memory has disappeared.

---

#### 9. Forget Topic (`POST /api/memories/forget`)
*   **Purpose**: Delete memories by keyword regex or semantic similarity.
*   **Business Functionality**: "Search and Forget" bar.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/memories/forget`
*   **Headers**: `Content-Type: application/json`

##### Request Body Examples
*   **Payload 1 (Topic Specific)**:
    ```json
    {
      "topic": "Python",
      "user_id": "default_user"
    }
    ```
*   **Payload 2 (Wipe All Memories)**:
    ```json
    {
      "topic": "--all",
      "user_id": "default_user"
    }
    ```

##### Testing Steps
1.  **Postman**: Set method to `POST`, enter `http://127.0.0.1:8000/api/memories/forget`, select Body -> raw -> JSON, paste Payload 1, click **Send**.

##### Expected Responses
*   **Success (200 OK)**:
    ```json
    {
      "status": "success",
      "topic": "Python",
      "deleted_count": 1
    }
    ```

##### Validation Checklist
- [ ] Response shows `"deleted_count"` reflecting the matching documents deleted.

---

#### 10. Consolidate Memories (`POST /api/memories/consolidate`)
*   **Purpose**: Manually clean up duplicates, contradictions, and stale records.
*   **Business Functionality**: "Optimize Memory" button in settings.

##### Request Details
*   **URL**: `http://127.0.0.1:8000/api/memories/consolidate`
*   **Headers**: `Content-Type: application/json`

##### Request Body Examples
*   **Payload 1**:
    ```json
    {
      "user_id": "default_user"
    }
    ```

##### Testing Steps
1.  **Swagger UI**: Expand `POST /api/memories/consolidate`, click **Try it out**, edit the body to represent `"default_user"`, click **Execute**.

##### Expected Responses
*   **Success (200 OK)**:
    ```json
    {
      "status": "success",
      "stale_deleted": 0,
      "duplicates_merged": 0,
      "conflicts_resolved": 0,
      "categories_summarized": 0
    }
    ```

##### Validation Checklist
- [ ] Status is `success`.
- [ ] Returns fields showing numeric metrics of actions completed.

---

## 🔍 3. Post-Testing Validation Checklist (Summary)

After running through the manual tests, always verify the following database states:

### 1. Database Health Check
*   Open MongoDB Compass or Atlas Dashboard.
*   Check the `sessions` collection:
    *   Verify session documents have `title` and `updated_at` dates.
*   Check the `messages` collection:
    *   Verify message documents link correctly to `session_id`.
    *   Ensure tool response messages contain `tool_call_id` and role `"tool"`.
*   Check the `memories` collection:
    *   Verify stored documents have an `embedding` array of **384 numbers**.
    *   Verify `access_count` increments on duplicate stores.

### 2. Error Response Health Check
*   Verify that passing a malformed session ID hex string (e.g. `xyz`) raises a `500` or `422` error rather than crashing the Python server thread.
*   Ensure that requesting missing routes (e.g., `/api/missing`) returns a `404` status with JSON format: `{"detail": "Not Found"}`.
