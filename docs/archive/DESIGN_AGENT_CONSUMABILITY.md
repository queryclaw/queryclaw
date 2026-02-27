# Design for Being Used by Other Agents

> [中文版](../zh/archive/DESIGN_AGENT_CONSUMABILITY.md)

This doc outlines what QueryClaw would need so that **other agents** (e.g. Cursor, Claude Desktop, orchestration agents, or custom ReACT loops) can discover, call, and compose with it reliably. It complements the existing roadmap (e.g. Phase 4 MCP) with concrete design dimensions.

---

## Current State

| Dimension | Today | Implication for other agents |
|-----------|--------|------------------------------|
| **Entry** | CLI only (`queryclaw chat`, `onboard`) | Other agents must shell out and parse stdout; no in-process or HTTP call. |
| **Config** | Single file `~/.queryclaw/config.json` | One DB + one LLM config per process; no per-request or per-session override. |
| **Output** | Markdown/text to console | No structured JSON for tool-style consumption. |
| **Session** | In-memory history inside one `AgentLoop` | No session ID or stateless single-turn API; hard to multiplex. |
| **Discovery** | None | Other agents cannot ask "what can QueryClaw do?" in a standard way. |

So today, another agent can only use QueryClaw by running the CLI and scraping output — brittle and not composable.

---

## 1. Programmatic API (Library Mode)

**Goal:** Other Python agents (or services) can call QueryClaw as a library without spawning a subprocess.

**Design:**

- **Single-turn API:**  
  `async def chat(config: Config, message: str, *, session_id: str | None = None) -> ChatResult`  
  - Accepts config (and optionally DB/LLM already constructed) and one user message.  
  - Returns a structured `ChatResult`: `content: str`, `tools_used: list[str]`, optional `session_id` for continuity.

- **Config / DB injection:**  
  - Caller can pass a `Config` object (or override only `database` / `providers` / `agent`) so that the same process can serve multiple tenants or DBs.  
  - Optional: `create_agent_loop(provider, db, **agent_opts)` for full control (e.g. custom tools, skills dir).

- **No CLI coupling:**  
  - Move the "load config → create provider → create adapter → create AgentLoop → chat" flow into a dedicated module (e.g. `queryclaw.api` or `queryclaw.runner`) so CLI and programmatic callers share the same path.

**Deliverables:**

- Public API in `queryclaw.api` (or equivalent): `chat()`, optionally `create_agent_loop()` and `ChatResult` dataclass.  
- Docs and a minimal example: "Use QueryClaw from another Python agent."

---

## 2. MCP Server (Standard Tool Exposure)

**Goal:** Expose QueryClaw so any MCP client (Cursor, Claude Desktop, etc.) can list and call its capabilities as tools.

**Design:**

- **MCP server process:**  
  - New entrypoint, e.g. `queryclaw serve-mcp` or `queryclaw mcp`, that starts an MCP server (stdio or SSE).  
  - Server implements `tools/list` and `tools/call`.  
  - Each **tool** = one QueryClaw capability.

- **Two exposure styles (choose or support both):**
  - **A. Expose low-level tools:** Map each current tool to an MCP tool: `schema_inspect`, `query_execute`, `explain_plan`. The calling agent then drives the ReACT loop itself (it has to call LLM and chain these tools).  
  - **B. Expose one high-level tool:** One MCP tool, e.g. `queryclaw_ask(question: str, database_config?: object)`. QueryClaw runs the full ReACT loop internally and returns the final answer. Easiest for a caller that just wants "ask the database in natural language."

- **Config for MCP:**  
  - Default: read `~/.queryclaw/config.json` for DB + LLM.  
  - Optional: allow per-request `database` override (e.g. for multi-DB setups) if the protocol supports it, or a fixed set of named configs.

**Deliverables:**

- MCP server implementation (stdio transport minimum).  
- Tool schema (names, descriptions, parameters) matching current tools and/or `queryclaw_ask`.  
- Short doc: "Connect Cursor / Claude Desktop to QueryClaw via MCP."

---

## 3. Structured Output for Tool Results

**Goal:** When QueryClaw is used as a "tool" by another agent, results should be machine-readable so the caller can reason over them (e.g. tables as JSON, not only markdown).

**Design:**

- **Tool return shape:**  
  - Today each tool returns a string. Add an optional **structured** mode: e.g. `QueryResult` as JSON `{ "columns": [...], "rows": [...], "summary": "..." }`, and `SchemaInspect` as `{ "tables": [...] }` or similar.  
  - Either: (1) a global option `structured_output: bool`, or (2) a separate "programmatic" tool variant that returns JSON.

- **Chat result:**  
  - Programmatic `ChatResult` can include `structured_artifacts: list[dict]` (e.g. last query result, last schema snippet) so the calling agent does not have to parse markdown.

**Deliverables:**

- Optional structured format for each built-in tool (schema + example).  
- `ChatResult` (or equivalent) with optional structured fields for last tool outputs.

---

## 4. Session and Stateless Modes

**Goal:** Support both "one question → one answer" (stateless) and "multi-turn with memory" (session) when used by another agent.

**Design:**

- **Stateless:**  
  - Single call: no session ID, no history. Each `chat()` is independent. Easiest for embedding inside another agent's single tool call.

- **Session (stateful):**  
  - Caller passes `session_id`. Server (or in-process store) keeps conversation history keyed by `session_id`.  
  - Enables "follow-up questions" and context across calls.  
  - Requires a session store: in-memory (single process) or Redis/DB (multi-process).

- **Scoping:**  
  - Optional: `session_id` or `tenant_id` in config so that different callers get isolated config/history.

**Deliverables:**

- `chat(..., session_id=None)` semantics documented; in-memory session store for single-process use.  
- Optional: persistent session store (e.g. Redis) for Phase 4 server mode.

---

## 5. Discovery and Schema

**Goal:** Other agents can discover what QueryClaw can do and what parameters each capability expects.

**Design:**

- **MCP:** `tools/list` returns tool names, descriptions, and parameter JSON Schema — already aligned with current `Tool.to_schema()`.  
- **Programmatic:** Export `get_tool_definitions() -> list[dict]` (and optionally skill list) so a Python caller can build its own tool list or OpenAPI fragment.  
- **Docs:** A single "capability matrix" (markdown or JSON): tools, parameters, example inputs/outputs, and whether they are read-only or write.

**Deliverables:**

- `get_tool_definitions()` (or equivalent) in public API.  
- Capability matrix doc or schema file (e.g. `docs/capabilities.json`).

---

## 6. Security and Multi-Tenant (When Used as a Service)

**Goal:** When QueryClaw is invoked by many agents or users, identity, limits, and scope must be clear.

**Design:**

- **Identity:**  
  - Each request (or MCP connection) can carry an optional `caller_id` or `api_key`. Logged in audit trail; used for rate limits or config lookup.

- **Config per caller:**  
  - Optional: map `caller_id` / `api_key` to a dedicated config (e.g. which DB this caller is allowed to use, read-only vs write).  
  - Default: single shared config (current behavior).

- **Rate limits and timeouts:**  
  - Max iterations per request, max token per request, optional rate limit per caller to avoid abuse.

- **Read-only vs write:**  
  - Phase 1 is read-only; when write tools exist, expose a clear "read_only" mode for external agents so they can be restricted to SELECT + explain.

**Deliverables:**

- Documented behavior: single-tenant (current) vs optional multi-tenant (config + identity).  
- When implementing MCP or HTTP server: optional `caller_id`, timeout, and read_only flag.

---

## 7. Optional: HTTP API

**Goal:** Non-Python agents (or remote callers) can call QueryClaw without MCP or subprocess.

**Design:**

- **REST or SSE:**  
  - `POST /chat` with `{ "message": "...", "session_id": "...", "config_overrides": {} }` → `{ "content": "...", "tools_used": [...], "structured_artifacts": [...] }`.  
  - Optional: SSE for streaming if we add streaming support later.

- **Auth:**  
  - API key or bearer token; maps to identity and optional config.

- **Scope:**  
  - Can be Phase 4; MCP + programmatic API may be enough for most "other agents" in the short term.

**Deliverables:**

- Optional HTTP server (e.g. FastAPI) with `/chat` and optional `/tools` (list).  
- OpenAPI schema for integration.

---

## 8. Summary: What to Add

| Area | What to add | Priority |
|------|-------------|----------|
| **Programmatic API** | `queryclaw.api.chat()`, `ChatResult`, config injection; optional `create_agent_loop()` | High |
| **MCP server** | `queryclaw serve-mcp`; expose tools (low-level and/or `queryclaw_ask`); tool list + call | High |
| **Structured output** | Optional JSON for tool results and `ChatResult.structured_artifacts` | Medium |
| **Session** | `session_id` in `chat()`, in-memory (and later persistent) session store | Medium |
| **Discovery** | `get_tool_definitions()`, capability matrix doc/schema | Medium |
| **Security / multi-tenant** | Optional `caller_id`, config per caller, timeouts, read_only | When serving multiple agents |
| **HTTP API** | Optional REST `/chat` + OpenAPI | Phase 4 / lower priority |

Implementing **programmatic API** and **MCP server** first gives other agents a standard way to discover and call QueryClaw; **structured output** and **session** make composition and stateful conversations practical. Security and HTTP can follow when QueryClaw is deployed as a shared service.
