# AI Agent From Scratch — Complete Project Documentation

> **Single Source of Truth** — This document captures the full architecture, implementation history, design decisions, database schemas, tool integrations, strategies, and roadmap for the **Scalable Python AI Agent** project.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Technology Stack & Dependencies](#4-technology-stack--dependencies)
5. [Component Deep-Dives](#5-component-deep-dives)
   - 5.1 [Configuration Layer](#51-configuration-layer)
   - 5.2 [Database Layer](#52-database-layer)
   - 5.3 [LLM Provider Layer](#53-llm-provider-layer)
   - 5.4 [Memory Layer](#54-memory-layer)
   - 5.5 [Agent Layer](#55-agent-layer)
   - 5.6 [Tool Execution Framework](#56-tool-execution-framework)
   - 5.7 [CLI Interface](#57-cli-interface)
6. [Database Schema Design](#6-database-schema-design)
7. [Design Patterns & Architectural Decisions](#7-design-patterns--architectural-decisions)
8. [Implementation History](#8-implementation-history)
9. [Strategies & Methodologies](#9-strategies--methodologies)
10. [Current Capabilities](#10-current-capabilities)
11. [Known Challenges & Resolutions](#11-known-challenges--resolutions)
12. [Future Roadmap](#12-future-roadmap)
13. [Setup & Configuration Guide](#13-setup--configuration-guide)

---

## 1. Project Overview

### Purpose
Build a **production-grade, scalable, terminal-based AI chatbot** entirely from scratch using Python — without relying on orchestration frameworks like LangChain or LlamaIndex. The goal is to deeply understand every layer of an AI agent system by hand-crafting each component.

### Goals
- **Learn by building**: Every module (LLM client, memory, tools, agent loop) is written from scratch to understand how modern AI agent frameworks work internally.
- **Production readiness**: Async I/O everywhere, retry logic with exponential backoff, connection pooling, and clean error handling.
- **Extensibility**: Abstract base classes at every boundary so components (LLM providers, memory backends, agent strategies) can be swapped without rewriting the core.
- **Scalability path**: The architecture is explicitly designed to evolve from a simple chatbot into a multi-agent system with long-term memory, vector search, and advanced RAG capabilities.

### Vision
Evolve from a single conversational agent into a **multi-agent orchestration system** with:
- Long-term memory via MongoDB Atlas Vector Search
- Multi-agent routing and coordination
- Advanced RAG (Retrieval-Augmented Generation) with query expansion
- Real-time tool execution with parallel concurrency

---

## 2. High-Level Architecture

The system follows **Clean Architecture** principles with clearly separated layers. Each layer communicates through abstract interfaces, making components independently testable and replaceable.

```
┌──────────────────────────────────────────────────────────────┐
│                     CLI Interface (main.py)                   │
│                   Session Management + Rich UI                │
├──────────────────────────────────────────────────────────────┤
│                     Agent Layer (agent/)                      │
│              SimpleAgent: Orchestration + Tool Loop           │
├──────────────┬───────────────────────────┬───────────────────┤
│  Memory      │     LLM Provider          │    Tool Framework  │
│  (memory/)   │     (llm/)                │    (tools/)        │
│  Short-Term  │     Groq Cloud            │    Registry +      │
│  Context     │     AsyncGroq Client      │    8 Functions     │
│  Window      │     Retry + Backoff       │    Auto-Schema     │
├──────────────┴───────────────────────────┴───────────────────┤
│                   Database Layer (database/)                   │
│              MongoDB Atlas via Motor (Async)                  │
├──────────────────────────────────────────────────────────────┤
│                 Configuration (config/settings.py)            │
│                Pydantic Settings + .env Loader                │
└──────────────────────────────────────────────────────────────┘
```

### System Component Relationship Diagram

This diagram shows how every class and module connects and depends on each other across the full system:

```mermaid
graph TB
    subgraph CLI["CLI Interface"]
        MAIN["main.py<br/>Entry Point"]
    end

    subgraph AGENT["Agent Layer"]
        BA["BaseAgent<br/>(Abstract)"]
        SA["SimpleAgent<br/>(Concrete)"]
        SA -.->|implements| BA
    end

    subgraph MEMORY["Memory Layer"]
        BM["BaseMemory<br/>(Abstract)"]
        MH["MongoDBChatHistory<br/>(Concrete)"]
        STM["ShortTermMemory<br/>(Manager)"]
        MH -.->|implements| BM
        STM -->|delegates to| MH
    end

    subgraph LLM_LAYER["LLM Provider Layer"]
        BL["BaseLLM<br/>(Abstract)"]
        GP["GroqProvider<br/>(Concrete)"]
        GP -.->|implements| BL
    end

    subgraph TOOLS["Tool Framework"]
        TR["ToolRegistry<br/>(Singleton)"]
        BT["BaseTool<br/>(Wrapper)"]
        TD["@tool Decorator"]
        CALC["calculate"]
        SEARCH["search_web"]
        FETCH["fetch_webpage"]
        TIME_L["get_current_time"]
        TIME_W["get_world_time"]
        FLIST["list_directory"]
        FREAD["read_file"]
        FWRITE["write_file"]
        TD -->|wraps into| BT
        BT -->|registers in| TR
        CALC & SEARCH & FETCH & TIME_L & TIME_W & FLIST & FREAD & FWRITE -->|decorated by| TD
    end

    subgraph DB["Database Layer"]
        DC["DatabaseConnection<br/>(Singleton)"]
        MM["MessageModel<br/>(Pydantic)"]
        SM["SessionModel<br/>(Pydantic)"]
    end

    subgraph CONFIG["Configuration"]
        SETTINGS["Settings<br/>(Pydantic BaseSettings)"]
        ENV[".env File"]
        ENV -->|loaded by| SETTINGS
    end

    MAIN -->|creates & runs| SA
    MAIN -->|creates| STM
    MAIN -->|creates| GP
    MAIN -->|calls| DC
    SA -->|uses| STM
    SA -->|uses| GP
    SA -->|uses| TR
    MH -->|reads/writes via| DC
    MH -->|validates with| MM
    MH -->|validates with| SM
    DC -->|reads config from| SETTINGS
    GP -->|reads config from| SETTINGS
    STM -->|reads config from| SETTINGS

    DC -->|connects to| ATLAS[("MongoDB Atlas")]
    GP -->|calls API| GROQ_API(("Groq Cloud API"))
    SEARCH -->|calls API| TAVILY(("Tavily API"))
    TIME_W -->|calls API| TIMEAPI(("TimeAPI.io"))
```

### Data Flow (User Message → Response)

```mermaid
sequenceDiagram
    autonumber
    actor User as User (Terminal)
    participant CLI as CLI Engine (main.py)
    participant Agent as SimpleAgent
    participant Memory as ShortTermMemory
    participant DB as MongoDB (MongoDBChatHistory)
    participant LLM as GroqProvider (Groq Cloud)
    participant Tools as ToolRegistry

    User->>CLI: Enters message "What time is it in Tokyo?"
    CLI->>Agent: run_stream(session_id, user_input)
    Agent->>DB: Save user message to 'messages' collection
    Agent->>Memory: get_context(session_id)
    Memory->>DB: Load recent messages (sliding window)
    Memory-->>Agent: [system_prompt + datetime, ...recent_messages]
    Agent->>LLM: generate(context, tools=schemas)
    LLM-->>Agent: Response with tool_call: get_world_time(Asia/Tokyo)
    Agent->>DB: Save assistant tool_call message
    Agent->>Tools: registry.execute("get_world_time", {iana_timezone: "Asia/Tokyo"})
    Tools-->>Agent: "Current time in Asia/Tokyo: Saturday, June 13, 2026, 08:45:13 PM"
    Agent->>DB: Save tool response message
    Agent->>LLM: Re-generate with tool result in context
    LLM-->>Agent: Final text response
    Agent->>DB: Save assistant response
    Agent-->>CLI: Yield text tokens (typewriter stream)
    CLI-->>User: Display streaming response via Rich Live
```

---

## 3. Directory Structure

```text
ai_agent/                              # Project Root
│
├── config/                            # Configuration Layer
│   ├── __init__.py
│   └── settings.py                    # Pydantic BaseSettings (loads .env)
│
├── database/                          # Database Layer
│   ├── __init__.py
│   ├── connection.py                  # Async MongoDB connection manager (Motor)
│   └── models.py                      # Pydantic schemas: MessageModel, SessionModel
│
├── llm/                               # LLM Provider Layer
│   ├── __init__.py
│   ├── base.py                        # Abstract BaseLLM interface
│   └── groq_provider.py              # Concrete Groq Cloud implementation
│
├── memory/                            # Memory Layer
│   ├── __init__.py
│   ├── base.py                        # Abstract BaseMemory interface
│   ├── mongo_history.py              # MongoDB persistence (CRUD for sessions/messages)
│   └── short_term.py                 # Sliding context window + system prompt injection
│
├── agent/                             # Agent Layer
│   ├── __init__.py
│   ├── base.py                        # Abstract BaseAgent interface
│   └── simple_agent.py              # Orchestrator: tool loop + query expansion + streaming
│
├── tools/                             # Tool Execution Framework
│   ├── __init__.py                    # Central import hub (triggers @tool registration)
│   ├── base.py                        # BaseTool class + @tool decorator + schema generator
│   ├── registry.py                    # Singleton ToolRegistry (register, lookup, execute)
│   ├── math_tools.py                 # Safe calculator via AST parsing
│   ├── search_tools.py              # Tavily web search + webpage fetcher
│   ├── time_tools.py                # System clock + World Clock API (TimeAPI.io)
│   └── file_tools.py                # Sandboxed file read/write/list operations
│
├── cli/                               # CLI Interface (legacy; functionality moved to main.py)
│   ├── __init__.py
│   └── main.py                        # (Empty — CLI logic consolidated into root main.py)
│
├── Test_Scripts/                      # Manual test scripts
├── .env                               # Secret credentials (git-ignored)
├── .env.template                      # Template for environment setup
├── .gitignore                         # Git exclusions
├── main.py                            # Root entry point — session manager + chat loop
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Project metadata
├── truncate_db.py                     # Utility script to clear database collections
└── README.md                          # User-facing project README
```

---

## 4. Technology Stack & Dependencies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.10+ | Core programming language |
| **LLM Provider** | Groq Cloud API (`groq`) | Ultra-fast LLM inference (Llama 3 models) |
| **Database** | MongoDB Atlas (`motor`) | Async document storage for sessions & messages |
| **Schema Validation** | Pydantic v2 (`pydantic`, `pydantic-settings`) | Type-safe config and data models |
| **Environment** | `python-dotenv` | Loads `.env` variables at startup |
| **CLI UI** | `rich` | Terminal panels, spinners, live streaming text |
| **Retry Logic** | `tenacity` | Exponential backoff on API rate limits (HTTP 429) |
| **Web Search** | Tavily API (`tavily-python`) | Real-time search with topic/time filtering |
| **World Clock** | TimeAPI.io (free REST API) | IANA timezone-based current time lookups |

### `requirements.txt`
```
groq
motor
pydantic
pydantic-settings
python-dotenv
rich
tenacity
tavily-python
```

---

## 5. Component Deep-Dives

### 5.1 Configuration Layer

**File**: `config/settings.py`

**What it does**: Centralizes all application configuration in a single Pydantic `BaseSettings` class that automatically loads values from the `.env` file with type validation and default fallbacks.

**Why it exists**: Hard-coding API keys or connection strings is a security risk and makes deployments fragile. Pydantic Settings provides:
- Automatic `.env` loading without boilerplate
- Type coercion (e.g., `MAX_MESSAGES` string → `int`)
- Validation at startup (fails fast if required keys are missing)
- A single `settings` singleton importable from anywhere

**Configuration Fields**:

| Field | Type | Default | Source | Purpose |
|-------|------|---------|--------|---------|
| `groq_api_key` | `str` | Required | `GROQ_API_KEY` | Authentication for Groq Cloud |
| `groq_default_model` | `str` | `llama3-8b-8192` | `GROQ_DEFAULT_MODEL` | Default LLM model identifier |
| `mongodb_uri` | `str` | Required | `MONGODB_URI` | MongoDB Atlas connection string |
| `mongodb_db_name` | `str` | `chatbot_db` | `MONGODB_DB_NAME` | Target database name |
| `tavily_api_key` | `str` | Required | `TAVILY_API_KEY` | Tavily search API key |
| `max_messages` | `int` | `5` | `MAX_MESSAGES` | Sliding window size for context |

**Design Decision**: Using `alias` mapping (e.g., `alias="GROQ_API_KEY"`) lets us keep Pythonic snake_case field names while reading SCREAMING_SNAKE_CASE environment variables. The `extra="ignore"` config silently skips unknown `.env` entries.

#### Configuration Loading Workflow

```mermaid
flowchart LR
    A[".env File"] -->|Pydantic reads| B["SettingsConfigDict<br/>env_file='.env'"]
    B --> C{"Validate & Cast Types"}
    C -->|All required keys present| D["Settings Instance Created<br/>(Module-Level Singleton)"]
    C -->|Missing GROQ_API_KEY<br/>or MONGODB_URI| E["ValidationError<br/>App Fails Fast at Startup"]
    D --> F["config.settings.settings"]
    F -->|imported by| G["database/connection.py"]
    F -->|imported by| H["llm/groq_provider.py"]
    F -->|imported by| I["memory/short_term.py"]
    F -->|imported by| J["tools/search_tools.py"]
```

---

### 5.2 Database Layer

#### 5.2.1 Connection Manager (`database/connection.py`)

**What it does**: Manages the lifecycle of the async MongoDB connection pool using Motor's `AsyncIOMotorClient`.

**Key Design**:
- **Singleton Pattern**: `db_client = DatabaseConnection()` creates a single instance shared across the entire application. This avoids opening multiple connection pools.
- **Lazy Initialization**: The connection is only opened when `db_client.db` is first accessed, not at import time. This prevents connection errors during testing or import-only operations.
- **Graceful Shutdown**: `disconnect()` cleanly closes all pooled connections, called when the user types `/exit`.

**Why Motor (not PyMongo)**: Motor is the official async wrapper around PyMongo. Since our entire agent loop is `async`, using synchronous PyMongo would block the event loop during database operations, destroying concurrency.

#### Database Connection Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Idle: Module imported
    Idle --> Connected: db_client.connect() or db_client.db accessed
    note right of Connected
        Motor opens connection pool
        to MongoDB Atlas cluster
    end note
    Connected --> Connected: db_client.db (returns cached instance)
    Connected --> Idle: db_client.disconnect()
    note left of Idle
        Called on /exit command
        Closes all pooled connections
    end note
    Idle --> [*]: Application exits
```

#### 5.2.2 Data Models (`database/models.py`)

**What it does**: Defines Pydantic v2 schemas for MongoDB documents, providing type validation before any database write and consistent serialization when reading.

**Models**:

**`MessageModel`** — Represents a single chat message (user, assistant, or tool).

| Field | Type | Purpose |
|-------|------|---------|
| `id` | `Optional[PyObjectId]` | MongoDB `_id`, auto-generated |
| `session_id` | `PyObjectId` | Foreign key linking to parent session |
| `role` | `str` | Message author: `user`, `assistant`, `system`, or `tool` |
| `content` | `Optional[str]` | Text content (nullable for tool-call-only messages) |
| `tool_calls` | `Optional[List[Dict]]` | Array of tool invocation requests from the LLM |
| `tool_call_id` | `Optional[str]` | Links a tool response back to its request |
| `timestamp` | `datetime` | UTC creation time |
| `token_count` | `Optional[int]` | Reserved for future token tracking |
| `metadata` | `Dict[str, Any]` | Flexible extension field |

**`SessionModel`** — Represents a chat conversation thread.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | `Optional[PyObjectId]` | MongoDB `_id` |
| `title` | `str` | Human-readable session name |
| `created_at` | `datetime` | UTC creation time |
| `updated_at` | `datetime` | UTC last activity time |
| `metadata` | `Dict[str, Any]` | Flexible extension field |

**`PyObjectId`** — Custom Pydantic type using `BeforeValidator` to transparently convert BSON `ObjectId` objects to strings, solving the Pydantic v2 serialization incompatibility with MongoDB's native ID type.

#### Database Entity Relationship Diagram

```mermaid
erDiagram
    SESSIONS ||--o{ MESSAGES : "contains"
    SESSIONS {
        ObjectId _id PK
        string title
        datetime created_at
        datetime updated_at
        object metadata
    }
    MESSAGES {
        ObjectId _id PK
        ObjectId session_id FK
        string role "user | assistant | system | tool"
        string content "nullable for tool-call messages"
        array tool_calls "nullable - LLM tool requests"
        string tool_call_id "nullable - links response to request"
        datetime timestamp
        int token_count "reserved for future use"
        object metadata
    }
```

---

### 5.3 LLM Provider Layer

#### 5.3.1 Abstract Interface (`llm/base.py`)

Defines the contract that all LLM providers must implement:

```python
class BaseLLM(ABC):
    async def generate(messages, tools=None, **kwargs) -> Dict[str, Any]
    async def stream(messages, tools=None, **kwargs) -> AsyncGenerator[str, None]
```

**Why abstract**: Allows swapping Groq for OpenAI, Anthropic, or local models without changing agent code. The agent only depends on `BaseLLM`, never on `GroqProvider` directly.

#### 5.3.2 Groq Provider (`llm/groq_provider.py`)

**What it does**: Implements `BaseLLM` using Groq's `AsyncGroq` client for ultra-fast inference.

**Key Features**:
- **`generate()` method**: Non-streaming call used during tool execution loops. Returns a dictionary with `role`, `content`, and optionally `tool_calls`. Tool calls are parsed from the raw Groq response into our standardized format matching the `MessageModel` schema.
- **`stream()` method**: Streaming call used for final text responses. Yields content delta tokens chunk-by-chunk for real-time typewriter display.
- **Retry with Tenacity**: The `@retry` decorator on `generate()` automatically retries up to 3 times with exponential backoff (2s → 4s → 10s) on any exception, critical for handling Groq's rate limits (HTTP 429).
- **Tool Schema Pass-Through**: Both methods accept an optional `tools` parameter (list of OpenAI-compatible function schemas). When present, the LLM can decide to invoke a tool instead of returning text.

**Design Decision**: The `generate()` method normalizes the Groq SDK response into a plain Python dictionary. This decouples the rest of the system from Groq's SDK objects, making provider swaps trivial.

#### LLM Provider Workflow: generate() vs stream()

```mermaid
flowchart TB
    subgraph GENERATE["generate() - Non-Streaming"]
        direction TB
        G1["Receive messages + tool schemas"] --> G2["Build API args<br/>(model, messages, tools, stream=False)"]
        G2 --> G3{"Call Groq API"}
        G3 -->|Success| G4["Parse response.choices[0].message"]
        G3 -->|Exception| G5["Tenacity Retry<br/>(attempt 1/3)"]
        G5 -->|Wait 2s exponential| G3
        G5 -->|All 3 attempts fail| G6["Reraise Exception"]
        G4 --> G7{"Has tool_calls?"}
        G7 -->|Yes| G8["Return dict with role, content, tool_calls"]
        G7 -->|No| G9["Return dict with role, content"]
    end

    subgraph STREAM["stream() - Streaming"]
        direction TB
        S1["Receive messages + tool schemas"] --> S2["Build API args<br/>(model, messages, tools, stream=True)"]
        S2 --> S3["Call Groq API"]
        S3 --> S4["Async iterate over chunks"]
        S4 --> S5{"chunk.delta.content exists?"}
        S5 -->|Yes| S6["yield content token"]
        S5 -->|No| S7["Skip chunk"]
        S6 --> S4
        S7 --> S4
    end

    AGENT_LOOP["Agent Loop"] -->|Tool execution phase| GENERATE
    AGENT_LOOP -->|Final text response phase| STREAM
```

#### Retry Logic with Tenacity

```mermaid
sequenceDiagram
    participant Agent
    participant GroqProvider
    participant GroqAPI as Groq Cloud API

    Agent->>GroqProvider: generate(messages, tools)
    GroqProvider->>GroqAPI: POST /chat/completions
    GroqAPI-->>GroqProvider: HTTP 429 Rate Limit
    Note over GroqProvider: Tenacity: Attempt 1 failed
    Note over GroqProvider: Wait 2 seconds
    GroqProvider->>GroqAPI: POST /chat/completions (retry)
    GroqAPI-->>GroqProvider: HTTP 200 OK
    GroqProvider-->>Agent: Normalized response dict
```

---

### 5.4 Memory Layer

#### 5.4.1 Abstract Interface (`memory/base.py`)

```python
class BaseMemory(ABC):
    async def add_message(session_id, role, content, **kwargs) -> None
    async def get_messages(session_id, **kwargs) -> List[Dict]
    async def clear(session_id) -> None
```

**Why abstract**: Enables replacing MongoDB with Redis, SQLite, or even in-memory storage without touching the agent or CLI code.

#### 5.4.2 MongoDB Chat History (`memory/mongo_history.py`)

**What it does**: Implements `BaseMemory` as the persistent storage engine using MongoDB Atlas.

**Key Operations**:
- **`create_session()`**: Inserts a new `SessionModel` document and returns its string ID.
- **`get_all_sessions()`**: Retrieves all sessions sorted by `updated_at` descending (most recent first) for the session picker UI.
- **`add_message()`**: Validates and inserts a `MessageModel` document, then updates the parent session's `updated_at` timestamp. Handles optional `tool_calls` and `tool_call_id` fields transparently.
- **`get_messages()`**: Loads all messages for a session sorted chronologically, forwarding tool metadata fields for LLM context reconstruction.
- **`clear()`**: Deletes all messages for a session and resets its `updated_at`.

**Design Decision**: Messages store the `session_id` as a BSON `ObjectId` (not string) for efficient MongoDB indexing, but the public API accepts and returns strings for simplicity.

#### 5.4.3 Short-Term Memory Manager (`memory/short_term.py`)

**What it does**: Sits between the agent and the persistence layer, managing the **sliding context window** and **system prompt injection**.

**Key Features**:
1. **Sliding Window**: Limits the number of historical messages sent to the LLM to `max_messages` (default: 5 from `.env`). This prevents context overflow and controls token costs.
2. **Dynamic System Prompt**: On every `get_context()` call, injects the current system date/time and host timezone abbreviation (e.g., `IST`, `EST`) into the system prompt. This grounds the LLM in the real current moment.
3. **Grounding Rules**: The default system prompt contains strict instructions:
   - Always use tools for real-time queries
   - Never fabricate URLs or links
   - Cite sources with markdown links from tool results only
   - Use `search_web` for foreign timezone queries

#### Short-Term Memory Context Building Pipeline

```mermaid
flowchart TB
    A["Agent calls get_context(session_id)"] --> B["ShortTermMemory.get_context()"]
    B --> C["Delegate to MongoDBChatHistory.get_messages()"]
    C --> D[("MongoDB Atlas<br/>messages collection")]
    D -->|"All messages for session<br/>(sorted by timestamp)"| E["Raw Messages Array"]
    E --> F{"len > max_messages?"}
    F -->|Yes| G["Slice: messages[-max_messages:]<br/>(Keep only last N)"]
    F -->|No| H["Use all messages"]
    G --> I["Recent Messages"]
    H --> I
    I --> J["Capture Current Time<br/>datetime.now()"]
    J --> K["Get Timezone Name<br/>e.g. IST, EST, UTC"]
    K --> L["Build Dynamic System Prompt"]

    subgraph PROMPT["System Prompt Assembly"]
        L --> M["Base Rules:<br/>• Use tools for real-time queries<br/>• Never fabricate URLs<br/>• Cite sources inline<br/>• Use search for timezone queries"]
        M --> N["Append: Current System Date/Time:<br/>Friday, June 13, 2026, 08:45 PM (IST)"]
    end

    N --> O["Final Context Array"]

    subgraph OUTPUT["Returned to Agent"]
        O --> P["[0] System Message (prompt + datetime)"]
        O --> Q["[1] Recent user message"]
        O --> R["[2] Recent assistant message"]
        O --> S["[...] Up to max_messages"]
    end
```

#### Memory Layer Internal Architecture

```mermaid
flowchart LR
    subgraph PUBLIC_API["Public API (used by Agent)"]
        ADD["add_message()"]
        CTX["get_context()"]
        CLR["clear()"]
    end

    subgraph STM["ShortTermMemory"]
        WINDOW["Sliding Window<br/>(max_messages)"]
        PROMPT["System Prompt<br/>+ DateTime Injection"]
    end

    subgraph PERSIST["MongoDBChatHistory (BaseMemory)"]
        CRUD["CRUD Operations"]
        SESS["Session Management"]
    end

    ADD -->|delegates| CRUD
    CTX -->|1. loads from| CRUD
    CTX -->|2. applies| WINDOW
    CTX -->|3. prepends| PROMPT
    CLR -->|delegates| CRUD
    CRUD --> DB[("MongoDB Atlas")]
    SESS --> DB
```

---

### 5.5 Agent Layer

#### 5.5.1 Abstract Interface (`agent/base.py`)

```python
class BaseAgent(ABC):
    async def run(session_id, user_input) -> str          # Complete response
    async def run_stream(session_id, user_input) -> AsyncGenerator[str, None]  # Streaming
```

#### 5.5.2 Simple Agent (`agent/simple_agent.py`)

**What it does**: The brain of the system — orchestrates the full think-act-observe loop.

**Core Loop (both `run` and `run_stream`)**:
```
1. Save user message to DB
2. WHILE True:
   a. Get context (system prompt + history) from ShortTermMemory
   b. Call LLM.generate(context, tools=schemas)
   c. IF response contains tool_calls:
      - Save assistant tool-call message to DB
      - FOR each tool_call:
        - Execute tool via registry (or expand+search for search_web)
        - Save tool result to DB
      - CONTINUE loop (re-generate with tool results in context)
   d. ELSE (text response):
      - Save assistant response to DB
      - Return/yield the text
      - BREAK
```

#### Agent ReAct Loop Flowchart (Think → Act → Observe)

```mermaid
flowchart TB
    START(["User sends message"]) --> SAVE_USER["Save user message to DB"]
    SAVE_USER --> LOOP_START

    subgraph LOOP["Agent While Loop"]
        LOOP_START["Get context from ShortTermMemory<br/>(system prompt + sliding window)"] --> LLM_CALL["Call LLM.generate()<br/>(context + tool schemas)"]
        LLM_CALL --> DECISION{"Response type?"}

        DECISION -->|"Contains tool_calls"| SAVE_TC["Save assistant tool-call<br/>message to DB"]
        SAVE_TC --> TOOL_LOOP

        subgraph TOOL_LOOP["For each tool_call"]
            TC_CHECK{"Is search_web?"} -->|Yes| EXPAND["Query Expansion<br/>_expand_and_search()"]
            TC_CHECK -->|No| DIRECT["registry.execute()<br/>Direct tool call"]
            EXPAND --> SAVE_RESULT["Save tool result to DB<br/>(role: tool)"]
            DIRECT --> SAVE_RESULT
        end

        SAVE_RESULT --> LOOP_START

        DECISION -->|"Contains text content<br/>(no tool_calls)"| FINAL["Save assistant response to DB"]
    end

    FINAL --> YIELD(["Return/Yield text to CLI"])

    style EXPAND fill:#ffd700,color:#000
    style DECISION fill:#4169e1,color:#fff
    style FINAL fill:#32cd32,color:#000
```

#### Query Expansion & Parallel Search Workflow

```mermaid
sequenceDiagram
    autonumber
    participant Agent as SimpleAgent
    participant LLM as GroqProvider
    participant Tavily1 as Tavily (Query 1)
    participant Tavily2 as Tavily (Query 2)
    participant Tavily3 as Tavily (Query 3)

    Note over Agent: LLM requested search_web("latest AI news")
    Agent->>LLM: "Generate 2 alternative search queries for 'latest AI news'"
    LLM-->>Agent: "recent artificial intelligence developments" + "AI breakthroughs 2026"

    par Parallel Execution (asyncio.gather)
        Agent->>Tavily1: search("latest AI news")
        Agent->>Tavily2: search("recent artificial intelligence developments")
        Agent->>Tavily3: search("AI breakthroughs 2026")
    end

    Tavily1-->>Agent: 5 results
    Tavily2-->>Agent: 5 results
    Tavily3-->>Agent: Error (handled gracefully)

    Note over Agent: De-duplicate by URL
    Note over Agent: Combine unique results
    Agent-->>Agent: Return 8 unique results (3 duplicates removed)
```

#### Streaming Protocol Between Agent and CLI

```mermaid
sequenceDiagram
    participant CLI as CLI (main.py)
    participant Agent as SimpleAgent.run_stream()
    participant LLM as GroqProvider
    participant Tools as ToolRegistry

    CLI->>Agent: async for token in run_stream()

    Note over Agent: First LLM call returns tool_calls
    Agent-->>CLI: yield "__TOOL_CALL__:search_web:{...}"
    Note over CLI: Display yellow 🔧 Running tool indicator
    Agent->>Tools: Execute search_web
    Tools-->>Agent: Search results

    Note over Agent: Second LLM call returns text
    loop Typewriter chunks (12 chars, 10ms delay)
        Agent-->>CLI: yield "The latest n"
        Agent-->>CLI: yield "ews in AI in"
        Agent-->>CLI: yield "cludes..."
    end
    Note over CLI: Rich Live renders text progressively
```

**Key Features**:

**1. Tool Execution Loop (Recursive)**
When the LLM responds with `tool_calls` instead of text, the agent:
- Saves the tool-call message to maintain context integrity
- Executes each tool via the `ToolRegistry`
- Saves each tool result as a `role: "tool"` message
- Loops back to let the LLM see the results and decide next action

This recursive loop allows multi-step reasoning (e.g., search → read webpage → synthesize).

**2. Query Expansion (`_expand_and_search`)**
For `search_web` calls, the agent intercepts and enhances the search:
- Asks the LLM to generate 2 alternative query phrasings
- Fires all 3 queries (original + 2 variants) **in parallel** using `asyncio.gather(return_exceptions=True)`
- De-duplicates results by URL
- Returns combined, enriched search results

This significantly improves search coverage and reduces the chance of missing relevant information.

**3. Streaming Protocol**
The `run_stream` method yields two types of tokens:
- `__TOOL_CALL__:{name}:{args_json}` — Signals the CLI to display a tool execution indicator
- Regular text chunks (12 characters at a time with 10ms delay) — Creates a typewriter effect

**4. Concurrency Safety**
`asyncio.gather(*tasks, return_exceptions=True)` ensures a single failed search query doesn't crash the entire search expansion. Failed tasks are logged and skipped.

---

### 5.6 Tool Execution Framework

The tool system uses a **decorator-based auto-registration pattern** inspired by FastAPI's approach.

#### Tool Registration Flow (Startup)

```mermaid
flowchart TB
    subgraph STARTUP["Application Startup (import tools)"]
        IMPORT["main.py: import tools"] --> INIT["tools/__init__.py executed"]
        INIT --> IMPORT_MATH["from tools.math_tools import calculate"]
        INIT --> IMPORT_SEARCH["from tools.search_tools import search_web, fetch_webpage"]
        INIT --> IMPORT_TIME["from tools.time_tools import get_current_time, get_world_time"]
        INIT --> IMPORT_FILE["from tools.file_tools import list_directory, read_file, write_file"]
    end

    subgraph DECORATOR["@tool Decorator Execution (per function)"]
        D1["Extract function name<br/>(func.__name__)"] --> D2["Extract docstring<br/>(func.__doc__)"]
        D2 --> D3["generate_schema(func)<br/>Inspect signature → JSON Schema"]
        D3 --> D4["Create BaseTool instance<br/>(name, description, schema, func)"]
        D4 --> D5["registry.register(tool)<br/>Add to singleton dict"]
        D5 --> D6["Print: [Registry] Registered tool: name"]
    end

    IMPORT_MATH --> DECORATOR
    IMPORT_SEARCH --> DECORATOR
    IMPORT_TIME --> DECORATOR
    IMPORT_FILE --> DECORATOR

    D6 --> READY["ToolRegistry Ready<br/>8 tools available"]
```

#### Tool Execution Pipeline (Runtime)

```mermaid
sequenceDiagram
    autonumber
    participant LLM as Groq LLM
    participant Agent as SimpleAgent
    participant Registry as ToolRegistry
    participant BT as BaseTool
    participant Func as Tool Function

    LLM-->>Agent: Response with tool_calls array
    Note over Agent: Parse tool name + JSON arguments
    Agent->>Registry: execute("calculate", {expression: "25 * 17"})
    Registry->>Registry: get_tool("calculate")
    Registry->>BT: tool.execute(expression="25 * 17")
    BT->>BT: Check: is func async?
    alt Async function
        BT->>Func: await func(**kwargs)
    else Sync function
        BT->>Func: func(**kwargs)
    end
    Func-->>BT: 425
    BT-->>Registry: "425" (stringified)
    Registry-->>Agent: "425"
    Agent->>Agent: Save tool result to DB (role: tool)
```

#### 5.6.1 Base Tool & Decorator (`tools/base.py`)

**`BaseTool` class**: Wraps any Python function with metadata (name, description, parameter schema) and provides a universal `execute()` method that handles both sync and async functions.

**`@tool` decorator**: When applied to a function:
1. Extracts the function name as the tool name
2. Extracts the docstring as the tool description
3. Auto-generates an OpenAI-compatible JSON schema from the function signature using `inspect`
4. Instantiates a `BaseTool` and registers it in the global `ToolRegistry`

**`generate_schema()` function**: Introspects function parameters using `inspect.signature()` and maps Python types to JSON Schema types:

| Python Type | JSON Schema Type |
|-------------|-----------------|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list` | `array` |
| `dict` | `object` |

Parameters without defaults are marked as `required`.

#### Schema Generation Example

```mermaid
flowchart LR
    subgraph PYTHON["Python Function"]
        FUNC["def search_web(<br/>  query: str,<br/>  topic: str = 'general'<br/>)"]
    end

    subgraph SCHEMA["Generated JSON Schema"]
        JSON["{ type: object,<br/>  properties: {<br/>    query: {type: string},<br/>    topic: {type: string}<br/>  },<br/>  required: ['query']<br/>}"]
    end

    FUNC -->|"generate_schema()<br/>inspect.signature()"| JSON
```

#### 5.6.2 Tool Registry (`tools/registry.py`)

**What it does**: Singleton registry that stores all registered tools and provides lookup + execution.

**Methods**:
- `register(tool)` — Adds a `BaseTool` to the internal dictionary (logs on registration)
- `get_tool(name)` — Retrieves by name
- `get_all_tool_schemas()` — Converts all tools to OpenAI function-calling format for LLM consumption
- `execute(name, arguments)` — Looks up and executes a tool, returning the string result

#### 5.6.3 Registered Tools

| # | Tool Name | File | Description |
|---|-----------|------|-------------|
| 1 | `calculate` | `math_tools.py` | Safe math evaluation using AST parsing (no `eval()`). Supports `+`, `-`, `*`, `/`, `**`, brackets. |
| 2 | `search_web` | `search_tools.py` | Tavily-powered web search with topic (`general`/`news`), depth (`basic`/`advanced`), and time range (`day`/`week`/`month`) filtering. Includes automatic topic fallback. |
| 3 | `fetch_webpage` | `search_tools.py` | Downloads and strips HTML from a URL, returning clean text (truncated at 4000 chars). |
| 4 | `get_current_time` | `time_tools.py` | Returns the host system's local date and time. |
| 5 | `get_world_time` | `time_tools.py` | Queries TimeAPI.io for the current time in any IANA timezone (e.g., `Asia/Tokyo`). |
| 6 | `list_directory` | `file_tools.py` | Lists files and folders in a sandboxed workspace directory. |
| 7 | `read_file` | `file_tools.py` | Reads text file content from within the workspace sandbox. |
| 8 | `write_file` | `file_tools.py` | Writes content to a file within the workspace sandbox. |

**Security**: File tools enforce a sandbox boundary using `is_safe_path()`, which verifies that all file operations resolve to paths within the project's working directory. Path traversal attacks (e.g., `../../etc/passwd`) are blocked.

#### Search Tool Resilience Flow

```mermaid
flowchart TB
    A["search_web() called"] --> B{"topic == 'news'?"}
    B -->|No| C["Build API args<br/>(query, depth, topic=general)"]
    B -->|Yes| D["Build API args<br/>(query, depth, topic=news)"]
    C --> E{"time_range != 'none'?"}
    D --> E
    E -->|Yes| F["Map time_range:<br/>day→d, week→w, month→m, year→y"]
    E -->|No| G["No time filter"]
    F --> H["Call Tavily API"]
    G --> H
    H --> I{"API Response?"}
    I -->|Success| J["Format results:<br/>Title + URL + Content"]
    I -->|Error + topic was news| K["Fallback: Retry with topic=general"]
    I -->|Error + topic was general| L["Return error message"]
    K --> H
    J --> M["Return formatted results string"]
```

---

### 5.7 CLI Interface

**File**: `main.py` (root entry point)

**What it does**: Provides the interactive terminal interface with session management, chat history display, and real-time streaming output.

#### CLI Application Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Init: python main.py

    state Init {
        [*] --> ConnectDB: db_client.connect()
        ConnectDB --> ShowWelcome: Display Rich Panel
        ShowWelcome --> CreateComponents: Init MongoDBChatHistory, ShortTermMemory, GroqProvider, SimpleAgent
    }

    Init --> SessionManager

    state SessionManager {
        [*] --> ShowMenu: "1. New  2. Load Existing"
        ShowMenu --> NewSession: User picks 1
        ShowMenu --> LoadSession: User picks 2
        NewSession --> EnterTitle: Prompt for title
        EnterTitle --> CreateInDB: db_history.create_session()
        LoadSession --> ListSessions: Show all sessions from DB
        ListSessions --> PickSession: User selects number
        PickSession --> ReplayHistory: Load and display past messages
    }

    SessionManager --> ChatLoop

    state ChatLoop {
        [*] --> WaitInput: Prompt "You:"
        WaitInput --> CheckCommand

        state CheckCommand <<choice>>
        CheckCommand --> ExitCmd: /exit
        CheckCommand --> ClearCmd: /clear
        CheckCommand --> ProcessMsg: Regular message

        ClearCmd --> WaitInput: Clear session history
        ProcessMsg --> StreamResponse: agent.run_stream()

        state StreamResponse {
            [*] --> CheckToken
            CheckToken --> ShowTool: __TOOL_CALL__ token
            CheckToken --> ShowText: Text token
            ShowTool --> CheckToken: Display 🔧 indicator
            ShowText --> CheckToken: Update Rich Live display
            CheckToken --> [*]: Stream complete
        }

        StreamResponse --> WaitInput
    }

    ExitCmd --> Cleanup: db_client.disconnect()
    Cleanup --> [*]
```

#### Token Rendering Flow in CLI

```mermaid
flowchart TB
    A["Receive token from agent.run_stream()"] --> B{"Starts with __TOOL_CALL__?"}
    B -->|Yes| C["Stop any active Rich Live display"]
    C --> D["Parse: _, tool_name, args_json = token.split(':')"]
    D --> E["Display: 🔧 Running tool: tool_name(args)... (yellow)"]
    B -->|No| F{"Rich Live active?"}
    F -->|No| G["Create new Rich Live display"]
    F -->|Yes| H["Append token to response_text"]
    G --> H
    H --> I["live.update(Text(response_text))<br/>Typewriter effect at 15 FPS"]
```

**Key Components**:

**1. Session Manager (`get_or_create_session`)**:
- Displays a menu: "Start New" or "Load Existing"
- Lists all sessions from MongoDB sorted by last activity
- Returns the selected/created session ID

**2. Chat Loop**:
- Prompts user input with Rich formatting
- Handles slash commands: `/exit` (quit) and `/clear` (wipe session history)
- Iterates over `agent.run_stream()` tokens:
  - Tool call tokens → Displays `🔧 Running tool: tool_name(args)...` in yellow
  - Text tokens → Accumulates and renders via `Rich.Live` for typewriter effect
- Graceful exit: Closes MongoDB connection pool

**3. History Replay**:
When loading an existing session, the CLI replays past messages (filtering out internal tool calls/results) so the user sees their conversation context.

**Rich Library Usage**:
- `Panel` — Boxed welcome screen and session manager
- `Prompt` / `IntPrompt` — Styled user input collection
- `Live` + `Text` — Real-time typewriter response rendering
- Color markup — Cyan for user, green for assistant, yellow for tools, red for errors

---

## 6. Database Schema Design

### Collections

The application uses **2 MongoDB collections** in the `chatbot_db` database:

#### `sessions` Collection
```json
{
  "_id": ObjectId("..."),
  "title": "My Coding Chat",
  "created_at": ISODate("2026-06-07T13:00:00Z"),
  "updated_at": ISODate("2026-06-13T15:30:00Z"),
  "metadata": {}
}
```

#### `messages` Collection
```json
{
  "_id": ObjectId("..."),
  "session_id": ObjectId("..."),          // Links to sessions._id
  "role": "assistant",                     // "user" | "assistant" | "system" | "tool"
  "content": "The current time in Tokyo is 8:45 PM.",
  "tool_calls": [                          // Only on assistant tool-request messages
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "get_world_time",
        "arguments": "{\"iana_timezone\": \"Asia/Tokyo\"}"
      }
    }
  ],
  "tool_call_id": "call_abc123",           // Only on tool response messages
  "timestamp": ISODate("2026-06-13T15:30:05Z"),
  "token_count": null,
  "metadata": {}
}
```

### Schema Scaling Strategy

| Phase | New Collections | New Fields | Purpose |
|-------|----------------|------------|---------|
| **Current** | `sessions`, `messages` | — | Basic chat + tool execution |
| **Phase 4** | `memories` | `fact`, `embedding[384]`, `category` | Long-term memory via Atlas Vector Search |
| **Future** | `agents` | `agent_id`, `capabilities`, `model` | Multi-agent configuration |
| **Future** | — (in `messages`) | `sender_agent_id`, `is_internal` | Track agent-to-agent communication |

---

## 7. Design Patterns & Architectural Decisions

### 7.1 Clean Architecture (Hexagonal / Ports & Adapters)

Every major boundary has an **abstract interface** (port) and a **concrete implementation** (adapter):

| Layer | Port (Abstract) | Adapter (Concrete) |
|-------|-----------------|-------------------|
| LLM | `BaseLLM` | `GroqProvider` |
| Memory | `BaseMemory` | `MongoDBChatHistory` |
| Agent | `BaseAgent` | `SimpleAgent` |

**Why**: Vendor independence. Switching from Groq to OpenAI requires only creating an `OpenAIProvider` implementing `BaseLLM`. Zero changes to agent, memory, or CLI code.

#### Ports & Adapters Diagram

```mermaid
flowchart TB
    subgraph CORE["Core Business Logic (Agent)"]
        SA["SimpleAgent"]
    end

    subgraph PORTS["Ports (Abstract Interfaces)"]
        P_LLM["BaseLLM"]
        P_MEM["BaseMemory"]
        P_AGENT["BaseAgent"]
    end

    subgraph ADAPTERS_CURRENT["Current Adapters"]
        A_GROQ["GroqProvider<br/>(Groq Cloud)"]
        A_MONGO["MongoDBChatHistory<br/>(MongoDB Atlas)"]
    end

    subgraph ADAPTERS_FUTURE["Future Swappable Adapters"]
        F_OPENAI["OpenAIProvider<br/>(GPT-4)"]
        F_LOCAL["OllamaProvider<br/>(Local LLM)"]
        F_REDIS["RedisChatHistory<br/>(Redis)"]
        F_SQLITE["SQLiteChatHistory<br/>(SQLite)"]
    end

    SA -->|depends on| P_LLM
    SA -->|depends on| P_MEM
    SA -.->|implements| P_AGENT

    A_GROQ -.->|implements| P_LLM
    F_OPENAI -.->|implements| P_LLM
    F_LOCAL -.->|implements| P_LLM

    A_MONGO -.->|implements| P_MEM
    F_REDIS -.->|implements| P_MEM
    F_SQLITE -.->|implements| P_MEM

    style ADAPTERS_FUTURE fill:#2d2d2d,stroke:#666,stroke-dasharray:5 5
    style CORE fill:#1a5276,color:#fff
```

### 7.2 Singleton Pattern

Used for shared, expensive-to-create resources:
- `db_client` (DatabaseConnection) — Single connection pool
- `registry` (ToolRegistry) — Single tool catalog
- `settings` (Settings) — Single config instance

### 7.3 Decorator Pattern (Tool Registration)

The `@tool` decorator transforms plain functions into registered, schema-documented tools with zero boilerplate:

```python
@tool
def calculate(expression: str) -> str:
    """Safely evaluates a basic mathematical expression."""
    # Implementation...
```

This single decorator: extracts metadata, generates JSON schema, creates a `BaseTool` wrapper, and registers it globally.

### 7.4 Strategy Pattern (Agent Orchestration)

The agent's `_expand_and_search` method intercepts `search_web` calls to apply a **query expansion strategy**. This pattern allows swapping search strategies (e.g., simple pass-through vs. expanded parallel) without modifying the core agent loop.

### 7.5 Observer/Event Pattern (Streaming Protocol)

The `run_stream` method uses a custom **event protocol** via special token prefixes (`__TOOL_CALL__:`) to signal the CLI about tool executions vs. text responses. This decouples the agent's internal processing from the UI rendering logic.

### 7.6 Async-First Design

Every I/O operation is asynchronous:
- Database reads/writes → `motor` (async MongoDB driver)
- LLM API calls → `AsyncGroq` client
- HTTP requests in tools → `urllib.request` (sync, but fast for small payloads)
- Parallel searches → `asyncio.gather()`

### 7.7 Fail-Safe Concurrency

`asyncio.gather(*tasks, return_exceptions=True)` in parallel search ensures:
- A single failed query doesn't crash the entire search
- Failed results are logged and gracefully skipped
- Successful results are still processed and returned

---

## 8. Implementation History

### Phase 1: Foundation (Steps 1–8)

| Step | Component | What Was Built | Why |
|------|-----------|---------------|-----|
| 1 | Project Setup | Directory structure, empty files | Establish modular layout |
| 2 | `requirements.txt`, `.env.template` | Dependency manifest + env template | Reproducible environment |
| 3 | `config/settings.py` | Pydantic BaseSettings with `.env` loading | Type-safe centralized config |
| 4 | `database/models.py` | MessageModel + SessionModel schemas | Validated data contracts |
| 5 | `database/connection.py` | Motor AsyncIOMotorClient singleton | Async MongoDB connection pool |
| 6 | `llm/base.py`, `llm/groq_provider.py` | Abstract LLM + Groq implementation | LLM abstraction with retry logic |
| 7 | `memory/base.py`, `memory/mongo_history.py`, `memory/short_term.py` | Memory interfaces + MongoDB persistence + context windowing | Chat history + sliding window |
| 8 | `agent/base.py`, `agent/simple_agent.py`, `main.py` | Agent loop + CLI + entry point | Core chat functionality |

### Phase 2: Tool Execution (Steps 9–14)

| Step | Component | What Was Built | Why |
|------|-----------|---------------|-----|
| 9 | `tools/base.py` | BaseTool class + `@tool` decorator + `generate_schema()` | Auto-registration framework |
| 10 | `tools/registry.py` | ToolRegistry singleton | Central tool catalog |
| 11 | `tools/math_tools.py` | Safe calculator using AST parsing | First tool validation |
| 12 | `database/models.py` | Added `tool_calls`, `tool_call_id` fields | Support tool message flow |
| 13 | `llm/groq_provider.py` | Tool schema pass-through in `generate()` | Enable function calling |
| 14 | `agent/simple_agent.py`, `main.py` | Recursive tool loop + CLI tool indicators | Full tool execution pipeline |

### Phase 3: RAG & Search Upgrade (Steps 15–19)

| Step | Component | What Was Built | Why |
|------|-----------|---------------|-----|
| 15 | `tools/search_tools.py` | Tavily integration with topic/depth/time_range | Real-time web search |
| 16 | `agent/simple_agent.py` | Query expansion + parallel search | Improved search coverage |
| 17 | `memory/short_term.py` | Citation and grounding rules in system prompt | Prevent hallucinated links |

### Phase 3.5–3.8: Bug Fixes & Resilience (Steps 20–27)

| Step | Issue | Resolution |
|------|-------|------------|
| 20 | Tavily 422 errors on `time_range` | Added abbreviation mapping (`day` → `d`, etc.) |
| 21 | LLM fabricating URLs | Strengthened system prompt with strict anti-hallucination rules |
| 22 | Timezone math errors | Deprecated manual timezone tool; added `search_web` fallback |
| 23 | Search topic crashes | Implemented automatic `news` → `general` fallback |
| 24 | Missing host timezone | Injected `tz_name` (e.g., `IST`) into dynamic system prompt |
| 25 | `time_range` on general topic | Enforced `time_range` only for `news` topic searches |
| 26 | Parallel search crashes | Added `return_exceptions=True` to `asyncio.gather()` |
| 27 | Inaccurate foreign times | Built `get_world_time` tool using TimeAPI.io free REST API |

---

## 9. Strategies & Methodologies

### 9.1 Development Strategy: Step-by-Step Layered Build
Each component was built from the **bottom up** (dependencies first):
1. Configuration → 2. Database → 3. LLM → 4. Memory → 5. Agent → 6. CLI → 7. Tools

This ensured each layer could be independently verified before integrating with the next.

### 9.2 Testing Strategy: Manual Verification
After each phase, manual verification was performed:
- Database writes checked via MongoDB Atlas dashboard
- Tool execution validated through CLI interaction
- Search results verified by comparing to actual web content

### 9.3 Error Handling Strategy: Defense in Depth
- **Config layer**: Pydantic fails fast on missing required environment variables
- **Database layer**: Lazy connection prevents import-time failures
- **LLM layer**: Tenacity retries with exponential backoff on API errors
- **Tool layer**: Every tool wraps execution in try/except, returning error strings instead of crashing
- **Agent layer**: `return_exceptions=True` in parallel tasks prevents cascade failures
- **Search layer**: Automatic topic fallback (`news` → `general`) on API restrictions

### 9.4 Security Strategy
- **Environment Isolation**: API keys stored in `.env`, never committed (`.gitignore`)
- **File Sandbox**: All file tools validate paths stay within workspace boundary
- **Safe Math**: Calculator uses AST parsing instead of `eval()`, preventing code injection
- **Input Validation**: Pydantic schemas validate all data before database insertion

### 9.5 Prompt Engineering Strategy
The system prompt evolved through multiple iterations to achieve:
- **Grounding**: Forces tool use for real-time queries (prevents stale knowledge)
- **Anti-hallucination**: Prohibits fabricating URLs or using pre-trained knowledge for time-sensitive answers
- **Citation enforcement**: Requires inline markdown links from tool-provided URLs only
- **Timezone awareness**: Injects current host time + timezone abbreviation for relative time calculations

---

## 10. Current Capabilities

### What the Agent Can Do
- ✅ Interactive terminal conversations with real-time streaming responses
- ✅ Session management: Create, load, switch between chat sessions
- ✅ Persistent chat history across sessions (MongoDB Atlas)
- ✅ Safe mathematical calculations (AST-based)
- ✅ Real-time web search with query expansion and parallel execution
- ✅ Webpage content fetching and text extraction
- ✅ World clock: Accurate current time for any IANA timezone
- ✅ Host system time and date awareness
- ✅ Sandboxed file system operations (read, write, list)
- ✅ Multi-tool orchestration: Agent can chain multiple tools in a single turn
- ✅ Grounded responses with source citations
- ✅ Graceful error handling and automatic retries

### Registered Tools Summary
```
[Registry] Registered tool: calculate
[Registry] Registered tool: get_current_time
[Registry] Registered tool: get_world_time
[Registry] Registered tool: search_web
[Registry] Registered tool: fetch_webpage
[Registry] Registered tool: list_directory
[Registry] Registered tool: read_file
[Registry] Registered tool: write_file
```

---

## 11. Known Challenges & Resolutions

### Challenge 1: Tavily API 422 Errors
**Problem**: Tavily rejected `time_range` values like `"day"` (expected single-character abbreviations).
**Resolution**: Added a mapping dictionary converting human-readable values to API abbreviations (`day` → `d`).

### Challenge 2: LLM Hallucinating URLs
**Problem**: The LLM would fabricate plausible-looking URLs (e.g., `https://example.com/article`) in citations.
**Resolution**: Added explicit anti-hallucination instructions to the system prompt: "NEVER fabricate, hallucinate, or guess links. You are ONLY allowed to use URLs explicitly returned by your search tools."

### Challenge 3: Timezone Math Accuracy
**Problem**: Asking the LLM to manually calculate timezone offsets produced incorrect results.
**Resolution**: Built a dedicated `get_world_time` tool that queries TimeAPI.io's free REST API for authoritative timezone data. No LLM math required.

### Challenge 4: Parallel Search Crashes
**Problem**: If one of three parallel search queries failed, `asyncio.gather()` would raise and abort all results.
**Resolution**: Added `return_exceptions=True` to `asyncio.gather()`, catching failures per-task and skipping them.

### Challenge 5: Tavily Free Tier Topic Restrictions
**Problem**: Tavily's free API key sometimes rejects `topic: "news"`.
**Resolution**: Implemented automatic fallback: if a `news` search fails, retry with `topic: "general"`.

---

## 12. Future Roadmap

### Phase 4: Long-Term Memory (Atlas Vector Search)
**Status**: Planned (next phase)

| Component | File | Description |
|-----------|------|-------------|
| Memory schema | `database/models.py` | New `MemoryModel` with `fact`, `embedding[384]`, `category` |
| Embeddings client | `llm/embeddings.py` | Hugging Face free Inference API (`all-MiniLM-L6-v2`) |
| Long-term manager | `memory/long_term.py` | Vector storage + `$vectorSearch` retrieval |
| Fact extraction | `agent/simple_agent.py` | Background LLM call to extract persistent facts |
| Context injection | `memory/short_term.py` | Prepend relevant memories to system prompt |

**Workflow**: After each conversation turn, the agent extracts key facts (e.g., "User prefers Python", "User runs Windows"). These facts are embedded as 384-dimensional vectors and stored in MongoDB. On future turns, the most semantically relevant facts are retrieved via cosine similarity search and injected into the system prompt.

### Phase 5: Multi-Agent System
- Define specialized sub-agents (CoderAgent, SearchAgent, AnalystAgent)
- Build an OrchestratorAgent that routes queries to the appropriate sub-agent
- Add `sender_agent_id` and `is_internal` fields to `MessageModel`
- Create an `agents` collection for agent configuration storage

### Phase 6: API Layer
- Wrap the agent behind a FastAPI REST endpoint
- Add WebSocket support for real-time streaming
- Implement authentication and rate limiting

### Phase 7: Advanced RAG
- Hybrid search: combine vector similarity with keyword matching
- Document chunking and hierarchical retrieval
- Re-ranking with cross-encoders

---

## 13. Setup & Configuration Guide

### Prerequisites
1. **Python 3.10+** installed
2. **Groq API Key** — [Get free key](https://console.groq.com/)
3. **MongoDB Atlas Cluster** — [Create free cluster](https://www.mongodb.com/atlas)
4. **Tavily API Key** — [Get free key](https://tavily.com)

### Installation

```bash
# Clone the project
cd d:\AI_Projects\Agents\Ai_Agent

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

```bash
# Copy template
copy .env.template .env    # Windows
# cp .env.template .env    # macOS/Linux
```

Edit `.env` with your credentials:
```env
# Groq API Configuration
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_DEFAULT_MODEL=llama3-8b-8192

# MongoDB Atlas Configuration
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB_NAME=chatbot_db

# Tavily API Configuration
TAVILY_API_KEY=tvly-your_actual_key_here
```

### Running the Application

```bash
python main.py
```

### CLI Commands
| Command | Action |
|---------|--------|
| `/exit` | Safely close connections and quit |
| `/clear` | Delete all messages in the current session |

---

> **Document Version**: 1.0.0
> **Last Updated**: June 13, 2026
> **Author**: TejasH MistrY
