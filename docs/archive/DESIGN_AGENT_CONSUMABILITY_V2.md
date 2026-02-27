# Designing QueryClaw for Other Agents — v2

> [中文版](../zh/archive/DESIGN_AGENT_CONSUMABILITY_V2.md)

## The Core Tension: Who Thinks?

QueryClaw is an **Agent** — it has its own LLM, its own ReACT loop, its own reasoning. When another Agent wants to use it, the fundamental question is:

**Who does the thinking?**

This isn't just an API design question. It determines the entire architecture. There are three fundamentally different consumption patterns, and they require different surfaces:

| Pattern | Who reasons? | What QueryClaw provides | Analogy |
|---------|-------------|-------------------------|---------|
| **A. Smart Tool** | Caller's LLM | Database operations + safety | A wrench |
| **B. Expert Agent** | QueryClaw's LLM | End-to-end answers | A consultant |
| **C. Knowledge Source** | Caller's LLM | Domain expertise as text | A textbook |

Most "how to make X usable by agents" analyses jump to "add MCP server" or "add HTTP API" without asking which of these the caller actually needs. The answer is: **all three, and the architecture must cleanly separate them.**

---

## Pattern A: Smart Tool (No Inner LLM)

**What it means:** The calling agent already has its own LLM and ReACT loop. It just needs database operations — inspect schema, run SELECT, show EXPLAIN — as callable tools. QueryClaw acts as a **database abstraction layer with safety guardrails**, not an agent.

**Why this matters:** This is by far the most common integration pattern today. When Cursor, Claude Desktop, or a custom orchestration agent wants "database capabilities," it wants to add `schema_inspect` and `query_execute` to its *own* tool list, not delegate to a separate agent with a separate LLM.

**What the current architecture has:**

- `SchemaInspectTool`, `QueryExecuteTool`, `ExplainPlanTool` — these are clean, standalone, and already implement the `Tool` ABC with JSON Schema parameters.
- `SQLAdapter` and `AdapterRegistry` — database-agnostic abstraction.
- Read-only safety checks in `QueryExecuteTool._check_readonly()`.

**What's missing:**

1. **No way to use these tools without constructing the full `AgentLoop`.**  
   Today: CLI → Config → Provider → Adapter → AgentLoop → tools.  
   Needed: Adapter → tools, directly. The tools should be usable *without* an LLM provider.

2. **MCP server exposing individual tools.**  
   An MCP server that maps each `Tool` to an MCP tool. The caller's LLM sees them in its own tool list. No inner LLM involved.

3. **Structured output.**  
   Tools currently return formatted text strings (`to_text()`). Another agent's LLM can parse these, but a JSON mode would be more reliable:
   ```json
   {"columns": ["id", "name"], "rows": [[1, "Alice"], [2, "Bob"]], "row_count": 2}
   ```

**Design principle:** The tool layer must be **independently instantiable** — just give it a database connection, get callable tools. No LLM, no config file, no agent loop required.

---

## Pattern B: Expert Agent (Full Inner LLM)

**What it means:** The calling agent has a complex question ("Why is this query slow? What indexes should I add?") and wants to delegate the entire investigation to QueryClaw. QueryClaw uses its own LLM + ReACT loop + skills to reason through multiple steps and return a comprehensive answer.

**When this is the right pattern:**

- The question requires multi-step reasoning (inspect schema → run query → explain → analyze → suggest).
- The calling agent doesn't have database domain expertise in its context.
- The caller wants a "second opinion" from a specialist.

**The "two LLMs" problem:**

When Pattern B is used, two LLMs are running — the caller's and QueryClaw's. This has real consequences:

| Concern | Impact |
|---------|--------|
| **Cost** | Double LLM calls (caller reasons about what to delegate, then QueryClaw reasons about the database). |
| **Latency** | The caller waits for QueryClaw's full multi-step loop to complete. |
| **Context loss** | The caller's context (conversation history, user intent, broader task) is compressed into a single question string. QueryClaw doesn't know the bigger picture. |
| **Model mismatch** | The caller might use GPT-4o, QueryClaw uses Claude. Different models have different SQL generation strengths. |

**Design decisions:**

1. **Allow the caller to inject its own LLM provider.**  
   Instead of `queryclaw_ask(question)` always using QueryClaw's configured LLM, let the caller optionally pass a provider (or API key + model). This way:
   - Cost is attributable to the caller.
   - The caller can ensure model consistency.
   - QueryClaw contributes its tools, skills, and safety — not its LLM.

2. **Observable execution (not just final answer).**  
   The caller might want to see intermediate steps: "QueryClaw inspected 3 tables, ran 2 queries, then analyzed the EXPLAIN output." This is critical for:
   - **Audit:** What SQL was actually executed?
   - **Learning:** The calling agent can learn from QueryClaw's approach.
   - **Interruption:** "Stop, that's the wrong table."
   
   Design: An event stream or callback interface:
   ```python
   async for event in queryclaw.chat_stream(question):
       # event.type: "tool_call" | "tool_result" | "thinking" | "final_answer"
   ```

3. **Context injection (the caller provides context to QueryClaw).**  
   Instead of QueryClaw discovering everything from scratch, the caller can inject hints:
   ```python
   queryclaw.chat(question, context_hints={
       "relevant_tables": ["orders", "customers"],
       "business_context": "We're investigating a revenue drop in Q4",
   })
   ```
   This avoids redundant schema scanning and makes the inner agent's reasoning more focused.

---

## Pattern C: Knowledge Source (No Execution)

**What it means:** The calling agent only needs QueryClaw's domain knowledge — how to safely query databases, how to analyze performance, how to explore data — injected into its own context. No tool execution, no database connection. Just expertise as text.

**This is what Skills already are**, but currently they're only loaded into QueryClaw's own system prompt. They could be exported:

1. **As MCP resources:** `queryclaw://skills/data_analysis` returns the skill content. The calling agent injects it into its own system prompt.

2. **As a schema summary service:** `queryclaw://schema/summary` returns the database schema in a format suitable for another agent's context. The calling agent doesn't need `schema_inspect` as a tool — it just wants the schema as context.

3. **As prompt fragments:** QueryClaw's safety guidelines, SQL best practices, and database-specific tips, exported as reusable text blocks.

**Why this pattern is underrated:** Most of QueryClaw's value to a calling agent might not be in running SQL — the caller can do that via any DB client. The value is in *knowing how* to reason about databases: what to check, what pitfalls to avoid, how to interpret EXPLAIN output. That knowledge lives in Skills and in the system prompt. Exporting it is cheap, safe, and immediately useful.

---

## The Unbundled Architecture

The key insight is: **QueryClaw's current monolithic flow (CLI → Config → Provider → Adapter → AgentLoop → tools → response) must be unbundled into independently addressable layers:**

```
┌─────────────────────────────────────────────────┐
│                 Consumption Surfaces             │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ MCP Tools│  │ Prog.API │  │ CLI (current) │  │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘  │
│       │              │               │           │
├───────┴──────────────┴───────────────┴───────────┤
│            Orchestration Layer (optional)         │
│  ┌──────────────────────────────────────────┐    │
│  │  AgentLoop (ReACT) — needs LLM provider  │    │
│  │  ContextBuilder — needs DB + skills       │    │
│  │  MemoryStore — session state              │    │
│  └──────────────────────────────────────────┘    │
│                    ↕ optional                     │
├──────────────────────────────────────────────────┤
│              Core Layer (no LLM needed)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Tools   │  │ Safety   │  │   Skills     │   │
│  │(schema,  │  │(readonly │  │  (SKILL.md)  │   │
│  │ query,   │  │ check,   │  │              │   │
│  │ explain) │  │ limits)  │  │              │   │
│  └────┬─────┘  └──────────┘  └──────────────┘   │
│       │                                          │
├───────┴──────────────────────────────────────────┤
│               Database Layer                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ SQLite   │  │  MySQL   │  │ (PostgreSQL) │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
└──────────────────────────────────────────────────┘
```

**The Core Layer (tools + safety + skills) is usable without any LLM.** The Orchestration Layer (AgentLoop) is optional — you add it when you want QueryClaw to think for itself. The Consumption Surfaces (MCP, API, CLI) are interchangeable entry points.

---

## Five Design Decisions That Matter Most

### 1. LLM Ownership: Bring Your Own vs. Built-In

| Approach | Pros | Cons |
|----------|------|------|
| **BYOLLM** (caller provides LLM) | Cost attribution, model consistency, caller controls reasoning | Caller must handle ReACT loop or pass provider to QueryClaw |
| **Built-in** (QueryClaw uses own LLM) | Simpler API, caller just sends a question | Two LLMs running, context loss, cost opacity |
| **Both** (default built-in, optional override) | Maximum flexibility | More API surface |

**Recommendation:** Support both. Default to built-in (Pattern B), but allow injecting a provider or using tools without any LLM (Pattern A). This is the `create_agent_loop(provider=caller_provider)` vs. `tools = get_tools(db_adapter)` distinction.

### 2. Granularity: Tools vs. Agent vs. Both

Expose **both** individual tools and the agent-level `ask()`:

- `schema_inspect`, `query_execute`, `explain_plan` — for callers that want to drive reasoning themselves (Pattern A).
- `queryclaw_ask(question)` — for callers that want to delegate (Pattern B).

Don't force a choice. In MCP: list all of them. The caller picks.

### 3. Output Contract: Text vs. Structured vs. Streaming

Three modes, negotiated per call:

| Mode | When | Format |
|------|------|--------|
| **Text** | Human-facing, or caller's LLM will interpret | Markdown string (current) |
| **Structured** | Machine-to-machine, or caller wants to post-process | JSON with typed fields |
| **Streaming** | Caller wants intermediate steps or real-time progress | Event stream (tool_call, tool_result, final_answer) |

**Minimum for agent consumption:** Structured mode for tools. Streaming for the agent-level `ask()` is a strong nice-to-have.

### 4. Context Sharing: Avoiding Redundant Work

When another agent calls QueryClaw, it often already knows something about the database (from a previous call, or from its own context). Avoid re-scanning:

- **Schema caching:** Already implemented (`_schema_cache`). Make it shareable across sessions.
- **Context hints:** Let the caller pass `relevant_tables`, `business_context`, or even a pre-built schema summary. This saves QueryClaw from re-discovering what the caller already knows.
- **Exportable context:** Let the caller *read* QueryClaw's context (`get_schema_summary()`, `get_skills_summary()`) and inject it into its own system prompt — Pattern C.

### 5. Safety as a Separable Concern

Safety (read-only checks, row limits, future: SQL AST validation, audit logging) should be a **middleware**, not hardcoded into tools:

```python
safety = SafetyPolicy(read_only=True, max_rows=100, audit=True)
tools = get_tools(db_adapter, safety=safety)
```

This lets different callers have different safety policies. An internal admin agent might have `read_only=False`; an external agent gets `read_only=True`. Critical for multi-tenant and for the Phase 2 write-operations transition.

---

## Concrete Implementation Roadmap

### Step 1: Unbundle the Core Layer (enable Pattern A)

- **`queryclaw.api.get_tools(db_adapter, safety=None) -> list[Tool]`** — return tool instances, no LLM required.
- **`queryclaw.api.connect(db_type, **kwargs) -> SQLAdapter`** — shortcut to create a connected adapter.
- Each tool gets an optional `structured=True` parameter that returns JSON instead of text.

This alone makes QueryClaw usable by any Python agent that wants database tools.

### Step 2: MCP Server (enable Pattern A + B for MCP clients)

- `queryclaw serve-mcp` (stdio transport).
- Expose individual tools (Pattern A) AND `queryclaw_ask` (Pattern B).
- MCP resources for schema summary and skill content (Pattern C).

### Step 3: Agent-level API with LLM injection (enable Pattern B, properly)

- **`queryclaw.api.ask(question, config=None, provider=None, ...) -> ChatResult`**
- If `provider` is given, use it; otherwise use config's provider.
- `ChatResult` includes `content`, `tools_used`, `structured_artifacts`, and optionally `events` (list of intermediate steps).

### Step 4: Observable Execution

- `async for event in queryclaw.api.ask_stream(question, ...):`
- Event types: `schema_loaded`, `tool_call`, `tool_result`, `reasoning`, `final_answer`.
- Enables audit, learning, and interruption by the calling agent.

### Step 5: Safety Policy Object

- `SafetyPolicy(read_only=True, max_rows=100, allowed_tables=None, audit=True, require_confirmation=False)`
- Passed to tools or agent; governs what operations are permitted.
- Different callers can have different policies.

---

## What Not to Build (Anti-Patterns)

| Anti-pattern | Why it's wrong |
|-------------|----------------|
| **HTTP API as the primary integration** | Agents increasingly use MCP or in-process calls; HTTP adds latency, serialization, and deployment complexity. Build MCP + library API first; HTTP last. |
| **Always run two LLMs** | If the caller already has an LLM, don't force a second one. Expose tools directly (Pattern A). |
| **Hide intermediate steps** | An "oracle" API that only returns final answers prevents audit, learning, and debugging. Always make execution observable. |
| **Monolithic config** | A single `config.json` shared by all callers doesn't work for multi-agent setups. Config must be injectable per call. |
| **Tools that require CLI context** | Tools should be pure functions of (database + parameters + safety policy). No dependency on terminal, prompt_toolkit, or rich rendering. |

---

## Summary

The question "how to make QueryClaw usable by other agents" is really three questions:

1. **How to expose database tools without an inner LLM?** (Pattern A — unbundle the Core Layer)
2. **How to let another agent delegate a complex question?** (Pattern B — injectable LLM, observable execution, context sharing)
3. **How to share database expertise without execution?** (Pattern C — exportable skills and context)

The architectural principle: **unbundle the monolith into independently addressable layers (database → tools+safety → optional agent → consumption surface), so that each pattern can be served without dragging in unnecessary machinery.**

The most impactful first step is **Step 1: unbundle the Core Layer** — a `get_tools(db_adapter)` function that returns usable tools without any LLM, config file, or CLI involved. Everything else builds on that foundation.
