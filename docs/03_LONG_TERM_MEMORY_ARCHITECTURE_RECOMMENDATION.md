# Long-Term Memory Architecture — Strategic Recommendation

> **Document Version:** 1.0.0
> **Last Updated:** June 20, 2026
> **Author:** TejasH MistrY

> **Decision Document** — Recommends the optimal long-term memory architecture for our AI Agent project, answering all strategic questions about memory strategies, frameworks, databases, and pipeline design.

---

## Table of Contents

1. [Our Project Context](#1-our-project-context)
2. [Architecture Recommendation](#2-architecture-recommendation)
3. [Memory Strategies to Implement](#3-memory-strategies-to-implement)
4. [Custom Build vs Framework (Mem0)](#4-custom-build-vs-framework-mem0)
5. [Database Technology Decision](#5-database-technology-decision)
6. [Complete Memory Pipeline Design](#6-complete-memory-pipeline-design)
7. [Industry Standard Analysis](#7-industry-standard-analysis)
8. [Phased Implementation Roadmap](#8-phased-implementation-roadmap)
9. [Summary of Decisions](#9-summary-of-decisions)

---

## 1. Our Project Context

Before making any recommendations, here is what makes our project unique and what constrains our decisions:

### What We Have Today

```mermaid
flowchart LR
    subgraph CURRENT["Current Architecture (Phase 1-3)"]
        CLI["CLI (Rich)"] --> AGENT["SimpleAgent"]
        AGENT --> STM["ShortTermMemory<br/>(Sliding Window, last 5 msgs)"]
        AGENT --> LLM["GroqProvider<br/>(Llama 3 via AsyncGroq)"]
        AGENT --> TOOLS["ToolRegistry<br/>(8 tools: search, time, calc, file)"]
        STM --> DB[("MongoDB Atlas<br/>sessions + messages")]
    end
```

### Our Constraints

| Constraint | Impact on Decision |
|-----------|-------------------|
| **Built from scratch** (no LangChain/LlamaIndex) | Must implement memory layer ourselves — but that's the goal |
| **MongoDB Atlas (free tier)** | 512MB storage, native Vector Search available — single database for everything |
| **Groq as LLM provider** | Ultra-fast inference, but limited models — great for extraction calls |
| **Single developer** | Architecture must be implementable step-by-step, not require massive parallelism |
| **Learning project → production goal** | Start simple, evolve — don't over-engineer Phase 4 |
| **Python async-first** | Everything must work with `asyncio` and `motor` |

### Our Goals

| Goal | Priority |
|------|----------|
| Agent remembers user across sessions (preferences, context) | 🔴 Critical |
| Zero added latency to user responses | 🔴 Critical |
| Zero additional infrastructure cost | 🟡 High |
| Production-grade quality (not a toy) | 🟡 High |
| Extensible to knowledge graphs later | 🟢 Nice to have |
| Multi-user support | 🟢 Nice to have (future) |

---

## 2. Architecture Recommendation

### The Verdict: **Vector Search + Auto-Extraction (ChatGPT-Inspired)**

After analyzing all production systems (ChatGPT, Claude, Perplexity) and frameworks (Mem0, MemGPT, Zep), the recommended architecture for our project is:

> **Custom-built Semantic Memory with Vector Search + LLM-powered Auto-Extraction** — the same fundamental pattern used by ChatGPT's memory system and Claude's synthesis engine, tailored for our MongoDB Atlas + Groq stack.

### Why This Architecture

```mermaid
flowchart TB
    subgraph DECISION["Decision Matrix"]
        direction TB
        Q1["Need: Remember user across sessions"] -->|"Requires"| A1["Persistent fact storage<br/>= Vector DB"]
        Q2["Need: Zero latency impact"] -->|"Requires"| A2["Async background extraction<br/>= asyncio.create_task()"]
        Q3["Need: Zero additional cost"] -->|"Requires"| A3["Use existing MongoDB Atlas<br/>+ Free HuggingFace API"]
        Q4["Need: Production quality"] -->|"Requires"| A4["Same pattern as ChatGPT<br/>= Proven at scale"]
        Q5["Need: Extensible to KG"] -->|"Requires"| A5["Schema supports entities<br/>= Future-proof document design"]
    end

    A1 --> RESULT["Vector Search + Auto-Extraction<br/>on MongoDB Atlas"]
    A2 --> RESULT
    A3 --> RESULT
    A4 --> RESULT
    A5 --> RESULT

    style RESULT fill:#32cd32,color:#000,stroke:#228b22,stroke-width:3px
```

### What This Architecture Looks Like

```mermaid
flowchart TB
    USER(["User"]) --> CLI["CLI Interface"]
    CLI --> AGENT["SimpleAgent"]

    subgraph MEMORY_SYSTEM["Memory System (Existing + New)"]
        subgraph EXISTING["✅ Already Built"]
            STM["ShortTermMemory<br/>(Sliding Window)"]
        end

        subgraph NEW["🆕 Phase 4 — New Components"]
            LTM["LongTermMemory<br/>(Vector Search Manager)"]
            EMBED_CLIENT["EmbeddingClient<br/>(HuggingFace API)"]
            FACT_EXT["FactExtractor<br/>(Async Background)"]
        end
    end

    AGENT -->|"1. Get context"| STM
    STM -->|"2. Retrieve relevant facts"| LTM
    LTM -->|"3. Vector search"| EMBED_CLIENT
    EMBED_CLIENT --> ATLAS[("MongoDB Atlas<br/>memories collection<br/>+ Vector Index")]
    ATLAS --> LTM
    LTM -->|"4. Return top-5 facts"| STM
    STM -->|"5. Inject into system prompt"| AGENT

    AGENT --> LLM["GroqProvider"]
    LLM --> RESPONSE["Response to User"]

    RESPONSE -->|"6. Background task"| FACT_EXT
    FACT_EXT -->|"7. LLM extracts facts"| LLM
    FACT_EXT -->|"8. Embed & store"| EMBED_CLIENT

    style NEW fill:#1a1a2e,color:#fff,stroke:#ffd700,stroke-width:2px
    style EXISTING fill:#16213e,color:#fff
```

---

## 3. Memory Strategies to Implement

### Which memory types to implement and in what order

| Memory Type | Implement? | Phase | Rationale |
|-------------|-----------|-------|-----------|
| **Working Memory (Short-Term)** | ✅ Already done | Phase 1 | Our `ShortTermMemory` sliding window |
| **Semantic Memory (Facts)** | ✅ Yes — Core of Phase 4 | Phase 4A | The "remembering user" capability everyone expects |
| **Episodic Memory (Experience Logs)** | ✅ Yes — Lightweight | Phase 4B | Our existing `messages` collection IS episodic memory — we just add summarization |
| **Procedural Memory (Rules)** | ✅ Already done | Phase 1 | Our system prompt + tool definitions |
| **Knowledge Graph Memory** | ❌ Not now — Phase 6 | Future | Over-engineered for current scope; schema prepared for it |

### Detailed Strategy for Each

#### 🟢 Semantic Memory (Phase 4A — Build First)

**What**: Store factual knowledge about the user as embedded vectors in MongoDB Atlas.

**Examples**:
- "User prefers Python and React"
- "User runs Windows OS with VS Code"
- "User's project uses MongoDB Atlas and Groq"

**Implementation**:
```
User says something → Agent responds →
Background: LLM extracts facts →
Embed facts via HuggingFace → Store in memories collection →
Next query: Vector search retrieves relevant facts →
Inject into system prompt before LLM call
```

#### 🟡 Episodic Memory (Phase 4B — Add After Semantic)

**What**: Summarize past sessions into condensed digests, stored as searchable memories.

**Examples**:
- "On June 13, 2026: Discussed search tools, built query expansion, resolved timezone issues"
- "On June 14, 2026: Reviewed long-term memory architectures, decided on Vector Search approach"

**Implementation**:
```
Session ends (or every N messages) →
LLM summarizes the session into 2-3 sentence digest →
Embed and store in memories collection with category="episode" →
Future sessions: Retrieve relevant past episodes alongside semantic facts
```

> **Key Insight**: We don't need a separate database or system for episodic memory. By adding a `category` field to our memory documents, the same collection and vector index serves both semantic AND episodic memories.

#### 🟢 Procedural Memory (Already Exists)

Our system prompt + `@tool` decorator schema + grounding rules = procedural memory. No changes needed.

#### ❌ Knowledge Graph Memory (Not Now, Schema-Ready)

We include an `entities` and `relationships` field in the memory document schema (both optional, default `null`). This means:
- **Phase 4**: Fields exist but are unused — zero overhead
- **Phase 6**: We can populate them without schema migration

---

## 4. Custom Build vs Framework (Mem0)

### The Question

> Should we use Mem0 (open-source memory framework) or build our own memory layer?

### The Answer: **Build Custom**

```mermaid
flowchart TB
    subgraph MEM0_OPTION["Option A: Use Mem0"]
        M0_PRO1["✅ Pre-built extraction engine"]
        M0_PRO2["✅ Knowledge graph support"]
        M0_PRO3["✅ Deduplication built-in"]
        M0_CON1["❌ Adds new dependency"]
        M0_CON2["❌ Requires Qdrant/Chroma (not MongoDB)"]
        M0_CON3["❌ Defeats 'build from scratch' philosophy"]
        M0_CON4["❌ Less control over retrieval ranking"]
        M0_CON5["❌ May conflict with our async architecture"]
    end

    subgraph CUSTOM_OPTION["Option B: Build Custom (Recommended)"]
        C_PRO1["✅ Full control over every operation"]
        C_PRO2["✅ Uses existing MongoDB Atlas (no new infra)"]
        C_PRO3["✅ Aligns with 'learn by building' philosophy"]
        C_PRO4["✅ Async-first from day one"]
        C_PRO5["✅ Same pattern as ChatGPT/Claude (proven)"]
        C_CON1["❌ More code to write"]
        C_CON2["❌ Must implement dedup logic ourselves"]
    end

    CUSTOM_OPTION --> WINNER["✅ Custom Build Wins"]

    style WINNER fill:#32cd32,color:#000,stroke:#228b22,stroke-width:3px
```

### Why Custom Wins for Our Project

| Factor | Mem0 | Custom Build | Winner |
|--------|------|-------------|--------|
| **Learning value** | Low (black box) | Very High (understand internals) | Custom |
| **Infrastructure** | Needs Qdrant/Chroma | Uses existing MongoDB | Custom |
| **Async compatibility** | Uncertain | Guaranteed (we design it) | Custom |
| **Cost** | Free + vector DB cost | Free (Atlas free tier) | Custom |
| **Codebase alignment** | Foreign patterns | Follows our Clean Architecture | Custom |
| **Production capability** | Excellent | Excellent (same pattern as ChatGPT) | Tie |
| **Knowledge graph** | Built-in | Future phase | Mem0 |
| **Speed to implement** | Faster (pre-built) | Slightly slower (but not by much) | Mem0 |

> **Bottom line**: Mem0 is an excellent framework, but using it would violate our core project goal ("build from scratch to learn"). Our custom implementation follows the exact same architectural pattern that ChatGPT uses — it's proven at massive scale, and building it ourselves gives us deep understanding.

---

## 5. Database Technology Decision

### The Decision: **MongoDB Atlas (Vector Search) — Single Database for Everything**

```mermaid
flowchart TB
    subgraph OPTIONS["Database Options Evaluated"]
        OPT1["Pinecone<br/>(Dedicated Vector DB)"]
        OPT2["Qdrant<br/>(Open-Source Vector DB)"]
        OPT3["PostgreSQL + pgvector<br/>(Relational + Vector)"]
        OPT4["MongoDB Atlas<br/>(Document + Vector)"]
        OPT5["Redis<br/>(Cache + Vector)"]
    end

    OPT4 --> CHOSEN["✅ Chosen: MongoDB Atlas Vector Search"]

    subgraph REASONS["Why Atlas Wins"]
        R1["Already in our stack<br/>(sessions + messages)"]
        R2["Native $vectorSearch<br/>(HNSW algorithm)"]
        R3["Free tier: 512MB<br/>(~500K memories)"]
        R4["Single connection pool<br/>(existing motor client)"]
        R5["Filter + Vector in one query<br/>(compound index)"]
        R6["No additional infrastructure<br/>(no Qdrant/Pinecone setup)"]
    end

    CHOSEN --> REASONS

    style CHOSEN fill:#ffd700,color:#000,stroke:#b8860b,stroke-width:3px
```

### Why NOT the Others

| Database | Why We Rejected It |
|----------|-------------------|
| **Pinecone** | Additional service, additional cost, additional latency, additional dependency |
| **Qdrant** | Requires running a separate service (Docker or cloud), overkill for our scale |
| **PostgreSQL** | Would require migrating from MongoDB — massive architectural change |
| **Redis** | Great for caching but not for persistent vector search at scale |

### What Atlas Vector Search Gives Us

| Feature | Detail |
|---------|--------|
| **Algorithm** | HNSW (Hierarchical Navigable Small World) — same as Pinecone |
| **Similarity** | Cosine, Euclidean, or Dot Product |
| **Max Dimensions** | 4096 (we use 384) |
| **Filters** | Pre-filter by any field (`user_id`, `category`, `is_current`) |
| **Aggregation** | Full MongoDB aggregation pipeline after vector search |
| **Cost** | Free on M0 (shared) tier |

### Memory Collection Schema

```json
{
  "_id": "ObjectId(...)",
  "user_id": "default_user",
  "fact": "User prefers Python for backend and React for frontend",
  "embedding": [0.023, -0.142, 0.891, "...384 floats"],
  "category": "user_preference",
  "source_session_id": "ObjectId(...)",
  "source_message": "I usually work with Python and React",
  "entities": null,
  "relationships": null,
  "created_at": "2026-06-14T12:00:00Z",
  "last_accessed": "2026-06-14T15:30:00Z",
  "access_count": 3,
  "confidence": 0.92,
  "is_current": true,
  "metadata": {}
}
```

### Vector Search Index Configuration

```json
{
  "name": "memory_vector_index",
  "type": "vectorSearch",
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "user_id"
    },
    {
      "type": "filter",
      "path": "category"
    },
    {
      "type": "filter",
      "path": "is_current"
    }
  ]
}
```

---

## 6. Complete Memory Pipeline Design

### 6.1 End-to-End Flow (Single User Turn)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as CLI Interface
    participant Agent as SimpleAgent
    participant STM as ShortTermMemory
    participant LTM as LongTermMemory
    participant Embed as EmbeddingClient
    participant Atlas as MongoDB Atlas
    participant LLM as GroqProvider
    participant Extract as FactExtractor

    User->>CLI: "What testing library should I use?"
    CLI->>Agent: run_stream(session_id, user_input)

    Note over Agent: Step 1: Save user message
    Agent->>Atlas: Save user message to messages collection

    Note over Agent,LTM: Step 2: Retrieve relevant memories
    Agent->>LTM: retrieve(session_id, user_query)
    LTM->>Embed: embed(user_query)
    Embed-->>LTM: query_vector [0.045, -0.231, ...]
    LTM->>Atlas: $vectorSearch(query_vector, limit=5, filter={is_current: true})
    Atlas-->>LTM: ["User prefers React", "User uses Python", "User IDE: VS Code"]
    LTM-->>Agent: Top 5 relevant facts

    Note over Agent,STM: Step 3: Build context with memories
    Agent->>STM: get_context(session_id, memories=facts)
    STM-->>Agent: [system_prompt + memories + datetime, ...recent_messages]

    Note over Agent,LLM: Step 4: Generate response
    Agent->>LLM: generate(context, tools)
    LLM-->>Agent: "Since you use React, I'd recommend React Testing Library..."
    Agent-->>CLI: Stream response to user
    CLI-->>User: Display response

    Note over Agent,Extract: Step 5: Background extraction (non-blocking)
    Agent->>Extract: asyncio.create_task(extract_and_store(...))
    Note over Extract: Does NOT block user response

    Extract->>LLM: "Extract long-term facts from this exchange"
    LLM-->>Extract: ["User interested in testing libraries"]
    Extract->>Embed: embed(new_fact)
    Embed-->>Extract: fact_vector
    Extract->>Atlas: Check for duplicates (similarity > 0.9)
    alt New unique fact
        Extract->>Atlas: INSERT memory document
    else Duplicate found
        Extract->>Atlas: UPDATE access_count, last_accessed
    end
```

### 6.2 Memory Extraction Pipeline

```mermaid
flowchart TB
    START["Conversation Turn Complete<br/>(user_input + agent_response)"]

    START --> FILTER{{"Worth extracting?"}}

    FILTER -->|"Skip if:"| SKIP["No extraction<br/>• Greeting only ('hi', 'thanks')<br/>• Tool-only response (calc, time)<br/>• Very short exchange (< 20 tokens)<br/>• User input is a command (/exit)"]

    FILTER -->|"Extract if:"| EXTRACT["Contains personal info,<br/>preferences, project details,<br/>or technical context"]

    EXTRACT --> LLM_CALL["LLM Extraction Call<br/>(Use fast model: llama3-8b)"]

    LLM_CALL --> PARSE["Parse JSON array<br/>of fact strings"]

    PARSE --> LOOP["For each fact:"]

    LOOP --> EMBED_F["Embed fact → vector"]
    EMBED_F --> DEDUP["Search existing memories<br/>(cosine similarity > 0.9)"]

    DEDUP --> MATCH{{"Match found?"}}

    MATCH -->|"Exact duplicate<br/>(similarity > 0.95)"| BUMP["Bump access_count<br/>Update last_accessed"]

    MATCH -->|"Similar but updated<br/>(0.9 < similarity < 0.95)"| UPDATE["Update fact text<br/>Re-embed vector<br/>Mark old as is_current=false"]

    MATCH -->|"No match<br/>(similarity < 0.9)"| INSERT["Insert new memory<br/>(fact + vector + metadata)"]

    BUMP --> NEXT["Next fact"]
    UPDATE --> NEXT
    INSERT --> NEXT
    NEXT --> LOOP

    style LLM_CALL fill:#ffd700,color:#000
    style SKIP fill:#dc3545,color:#fff
```

### 6.3 Memory Retrieval & Ranking Pipeline

```mermaid
flowchart TB
    QUERY["User Query"] --> EMBED_Q["Step 1: Embed Query<br/>→ query_vector (384 dims)"]

    EMBED_Q --> SEARCH["Step 2: Atlas $vectorSearch<br/>(limit=20, numCandidates=100)"]

    SEARCH --> CANDIDATES["20 Candidate Memories"]

    CANDIDATES --> RANK["Step 3: Multi-Signal Re-Ranking"]

    subgraph SIGNALS["Ranking Signals"]
        S1["Semantic Score<br/>cosine_similarity × 0.50"]
        S2["Recency Score<br/>decay(days_since_access) × 0.25"]
        S3["Frequency Score<br/>(access_count / max_count) × 0.15"]
        S4["Category Boost<br/>(+0.10 if category matches)"]
    end

    RANK --> S1 & S2 & S3 & S4

    S1 & S2 & S3 & S4 --> COMBINED["Step 4: Final Score =<br/>Σ(signal × weight)"]

    COMBINED --> SORT["Step 5: Sort by final_score DESC"]
    SORT --> TOP_K["Step 6: Take Top-5"]
    TOP_K --> DEDUP_R["Step 7: Deduplicate<br/>(Remove near-identical phrasing)"]
    DEDUP_R --> FORMAT["Step 8: Format for Injection"]

    FORMAT --> OUTPUT["Output:<br/>'User Context:<br/>• User prefers React (0.92)<br/>• User runs Windows (0.85)<br/>• User IDE: VS Code (0.78)<br/>• User builds with MongoDB (0.71)<br/>• User learning AI agents (0.68)'"]

    style OUTPUT fill:#32cd32,color:#000
```

### 6.4 Memory Consolidation (Dreaming Process)

This is inspired by ChatGPT's "Dreaming" and Claude's "Auto-Dream" — a background process that keeps memory healthy.

```mermaid
flowchart TB
    TRIGGER["Trigger Conditions:<br/>• Every 100 messages<br/>• Every session end<br/>• Manual /consolidate command"]

    TRIGGER --> LOAD["Load all memories<br/>for current user"]

    LOAD --> HEALTH["Memory Health Check"]

    subgraph CHECKS["Health Checks"]
        CHECK_STALE["1. Stale memories<br/>(access_count=0 AND age > 30 days)"]
        CHECK_CONFLICT["2. Contradictions<br/>(similarity > 0.8 but different content)"]
        CHECK_DUPE["3. Near-duplicates<br/>(similarity > 0.95)"]
        CHECK_COUNT["4. Memory bloat<br/>(total > 200 for this user)"]
    end

    HEALTH --> CHECK_STALE & CHECK_CONFLICT & CHECK_DUPE & CHECK_COUNT

    CHECK_STALE --> ACT_STALE["Action: Delete stale memories"]
    CHECK_CONFLICT --> ACT_CONFLICT["Action: Keep newest,<br/>mark older as is_current=false"]
    CHECK_DUPE --> ACT_DUPE["Action: Merge into<br/>single comprehensive fact"]
    CHECK_COUNT --> ACT_BLOAT["Action: LLM summarizes<br/>category groups into<br/>condensed profile facts"]

    ACT_STALE & ACT_CONFLICT & ACT_DUPE & ACT_BLOAT --> DONE["Consolidated Memory Store<br/>(Smaller, cleaner, more current)"]

    style TRIGGER fill:#4169e1,color:#fff
    style DONE fill:#32cd32,color:#000
```

### 6.5 Memory Forgetting (User Control)

```mermaid
flowchart TB
    subgraph COMMANDS["User Commands"]
        CMD1["/memories<br/>Show all stored memories"]
        CMD2["/forget [topic]<br/>Delete memories matching topic"]
        CMD3["/forget --all<br/>Delete ALL memories"]
        CMD4["/consolidate<br/>Run memory cleanup now"]
    end

    CMD1 --> LIST["Query all memories<br/>Display as numbered list<br/>Show category + date"]

    CMD2 --> SEARCH_DEL["Embed topic → vector search<br/>Show matching memories<br/>Confirm deletion<br/>Delete confirmed memories"]

    CMD3 --> CONFIRM["Are you sure? (y/n)<br/>Delete all memory documents<br/>for this user"]

    CMD4 --> CONSOLIDATE["Run consolidation pipeline<br/>Report: deleted N stale,<br/>merged M duplicates,<br/>resolved K conflicts"]
```

---

## 7. Industry Standard Analysis

### How Production Systems Actually Work (Simplified)

| System | What They Really Do | Complexity Level |
|--------|-------------------|-----------------|
| **ChatGPT** | Store text facts in a notepad → inject into system prompt → auto-curate with "Dreaming" background process | Medium |
| **Claude** | Synthesize 24-hour compressed profile → inject at session start → separate Chat Search for history | Medium |
| **Perplexity** | Profile + Spaces + RAG over conversation history → inject alongside web search results | Medium |
| **Google Gemini** | Activity log + preference extraction → inject into system prompt | Low-Medium |

> **Key Insight**: Even the most sophisticated production systems (ChatGPT, Claude) use fundamentally simple patterns — **extract facts → store → retrieve → inject into prompt**. The sophistication is in the *quality* of extraction, the *efficiency* of retrieval, and the *freshness* of the data. None of them use exotic architectures.

### The Industry Standard Pattern (What We're Implementing)

```mermaid
flowchart LR
    subgraph STANDARD["Industry Standard Pattern (2025-2026)"]
        A["User speaks"] --> B["Agent responds"]
        B --> C["Background: Extract facts<br/>(LLM call)"]
        C --> D["Embed + Store<br/>(Vector DB)"]
        D --> E["Next query arrives"]
        E --> F["Retrieve relevant facts<br/>(Vector search)"]
        F --> G["Inject into system prompt"]
        G --> H["LLM generates<br/>(personalized response)"]
        H --> A
    end
```

This is exactly what we're building. The pattern is identical across ChatGPT, Claude, and our system — the only differences are scale and the sophistication of the curation/consolidation layer.

---

## 8. Phased Implementation Roadmap

### Phase 4A: Core Semantic Memory (Build First)

```mermaid
flowchart LR
    subgraph P4A["Phase 4A: Core Memory (3-4 days)"]
        S1["Step 1:<br/>MemoryModel<br/>(database/models.py)"]
        S2["Step 2:<br/>EmbeddingClient<br/>(llm/embeddings.py)"]
        S3["Step 3:<br/>Atlas Vector Index<br/>(MongoDB Dashboard)"]
        S4["Step 4:<br/>LongTermMemory<br/>(memory/long_term.py)"]
        S5["Step 5:<br/>Integrate into Agent<br/>(agent/simple_agent.py)"]
        S6["Step 6:<br/>Context Injection<br/>(memory/short_term.py)"]

        S1 --> S2 --> S3 --> S4 --> S5 --> S6
    end
```

| Step | File | What Gets Built |
|------|------|----------------|
| 1 | `database/models.py` | `MemoryModel` Pydantic schema (fact, embedding, category, timestamps) |
| 2 | `llm/embeddings.py` | `EmbeddingClient` — async HuggingFace Inference API calls |
| 3 | MongoDB Atlas Dashboard | Create `memories` collection + vector search index |
| 4 | `memory/long_term.py` | `LongTermMemory` class — store, retrieve, search, delete methods |
| 5 | `agent/simple_agent.py` | Background fact extraction + retrieval in agent loop |
| 6 | `memory/short_term.py` | Inject retrieved memories into system prompt |

### Phase 4B: Episodic Memory + Consolidation

| Step | What Gets Built |
|------|----------------|
| 7 | Session summary generation (end-of-session digest) |
| 8 | Consolidation/Dreaming pipeline (prune, merge, resolve) |
| 9 | `/memories`, `/forget`, `/consolidate` CLI commands |

### Phase 4C: Advanced Features (Polish)

| Step | What Gets Built |
|------|----------------|
| 10 | Multi-signal re-ranking (recency, frequency, category) |
| 11 | Memory confidence scoring |
| 12 | Automatic staleness detection and decay |

---

## 9. Summary of Decisions

| Question | Decision | Reasoning |
|----------|----------|-----------|
| **Best memory architecture?** | Vector Search + Auto-Extraction | Same pattern as ChatGPT/Claude — proven at scale, matches our stack |
| **Which memory strategies?** | Semantic (core) + Episodic (lightweight) + Procedural (existing) | Covers 95% of use cases; KG deferred to Phase 6 |
| **Mem0 or custom?** | Custom build | Aligns with "build from scratch" philosophy; uses existing MongoDB; full control |
| **Database technology?** | MongoDB Atlas Vector Search | Already in our stack; free tier; native $vectorSearch; single connection pool |
| **Embedding model?** | `all-MiniLM-L6-v2` via HuggingFace | Free, 384-dim, fast, proven quality for semantic search |
| **Extraction approach?** | Async background LLM call (llama3-8b) | Zero latency impact; cheap model for extraction; same Groq provider |
| **Retrieval strategy?** | Top-5 vector search + multi-signal re-ranking | Balances relevance vs context window budget |
| **Consolidation strategy?** | ChatGPT-inspired "Dreaming" | Background prune/merge/resolve every 100 messages or session end |
| **User control?** | `/memories`, `/forget`, `/consolidate` commands | Transparency + privacy + user agency |
| **Industry standard?** | Extract → Embed → Store → Retrieve → Inject | Every major system uses this exact loop |

### Final Architecture Diagram

```mermaid
flowchart TB
    USER(["User"]) --> CLI["CLI Interface<br/>(Rich Terminal)"]

    CLI --> AGENT["SimpleAgent<br/>(Orchestrator)"]

    subgraph CORE["Agent Core (Existing)"]
        LLM["GroqProvider<br/>(Llama 3)"]
        TOOLS["ToolRegistry<br/>(8 tools)"]
    end

    subgraph MEMORY["Memory System"]
        subgraph SHORT["Short-Term (Existing)"]
            STM["ShortTermMemory<br/>(Sliding Window + System Prompt)"]
        end

        subgraph LONG["Long-Term (Phase 4 — NEW)"]
            LTM["LongTermMemory<br/>(Vector Search Manager)"]
            EMBED["EmbeddingClient<br/>(HuggingFace free API)"]
            EXTRACT["FactExtractor<br/>(Async Background)"]
            CONSOLIDATE["Consolidator<br/>(Dreaming Engine)"]
        end
    end

    subgraph STORAGE["MongoDB Atlas (Single Database)"]
        SESSIONS[("sessions")]
        MESSAGES[("messages")]
        MEMORIES[("memories<br/>+ Vector Index")]
    end

    AGENT --> LLM
    AGENT --> TOOLS
    AGENT -->|"1. Retrieve"| LTM
    LTM --> EMBED
    EMBED --> MEMORIES
    LTM -->|"2. Facts"| STM
    STM -->|"3. Context"| AGENT
    AGENT -->|"4. Response"| CLI
    CLI --> USER

    AGENT -->|"5. Background"| EXTRACT
    EXTRACT --> LLM
    EXTRACT --> EMBED

    CONSOLIDATE -->|"Periodic"| MEMORIES

    STM --> SESSIONS & MESSAGES

    style LONG fill:#0d1b2a,color:#fff,stroke:#ffd700,stroke-width:2px
    style SHORT fill:#1b2838,color:#fff
    style MEMORIES fill:#ffd700,color:#000
```

---

> [!IMPORTANT]
> **Next Step**: Once you approve this architecture, I will create the detailed implementation plan (`implementation_plan.md`) with exact file changes, code structures, and step-by-step build order for Phase 4A.

---

> **Document Version**: 1.0.0
> **Last Updated**: June 14, 2026
> **Purpose**: Strategic architecture decision for Phase 4 — Long-Term Memory
> **Author**: TejasH MistrY