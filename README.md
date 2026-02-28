# QueryClaw

**Your Database, Under AI Command.**

> [中文版](README_CN.md)

[![PyPI](https://img.shields.io/pypi/v/queryclaw)](https://pypi.org/project/queryclaw/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)

<!-- TODO: Add demo to docs/assets/demo.gif (asciinema or GIF), then uncomment:
![Demo](docs/assets/demo.gif)
-->

**9 tools** | **7 skills** | **4 databases** | **243+ tests** | **Multi-LLM via LiteLLM**

---

## What is QueryClaw?

**QueryClaw** is an AI-native database agent that lets you hand over an entire database instance to an LLM-powered Agent. Think of it as giving your database a brain — it can explore schemas, query data, modify records, diagnose performance, and even generate new data using AI, all through natural language.

**This is not another Text-to-SQL chatbot.** QueryClaw is a full [ReACT](https://arxiv.org/abs/2210.03629) Agent that reasons, acts, observes, and iterates — it works the way a developer thinks about data, but with the depth of a seasoned DBA.

### The Idea

[OpenClaw](https://github.com/openclaw/openclaw) proved that an LLM can safely control a personal computer. **QueryClaw asks: what if we give it a database instead?**

| | OpenClaw / nanobot | QueryClaw |
|---|---|---|
| **Controls** | Operating System | Database |
| **Interface** | Shell, filesystem, browser | SQL, schema, data |
| **Safety** | Sandboxed execution | Transaction rollback, dry-run, audit |
| **Audience** | General users | Application developers & DBAs |

## Why QueryClaw?

Developers spend countless hours on repetitive database tasks: writing queries, debugging data issues, generating test data, reviewing schema designs, analyzing performance. Most database tools are either too low-level (raw SQL clients) or too limited (drag-and-drop query builders).

QueryClaw sits in the sweet spot: **an intelligent agent that understands both your natural language intent and the database semantics**.

### Before / After

| | Traditional Workflow | With QueryClaw |
|---|---|---|
| **Query** | Write SQL by hand, guess table names | `"Show me top customers"` — Agent explores schema and builds the query |
| **Modify data** | Write UPDATE, hope WHERE is correct, no audit | Agent validates, dry-runs, asks for confirmation, records before/after snapshot |
| **Generate test data** | Write scripts, handle FK constraints manually | `"Generate 100 test users with orders"` — respects schema automatically |
| **Diagnose slow query** | Run EXPLAIN, read docs, iterate | `"Why is this query slow?"` — Agent runs EXPLAIN, suggests indexes |
| **Team collaboration** | Share SQL snippets in chat | Ask in Feishu/DingTalk, Agent replies with results directly |

### Key Differentiators

- **Autonomous reasoning** — A full ReACT agent loop, not a one-shot translator. It explores schemas, runs queries, observes results, and adjusts its approach across multiple steps
- **Safety-first writes** — Multi-layer protection for mutations: policy checks → SQL AST validation → dry-run → human confirmation → transaction wrapping → full audit with before/after snapshots
- **Multi-channel** — Use it in the terminal (`queryclaw chat`) or deploy to team messaging (`queryclaw serve`) for Feishu / DingTalk with interactive confirmation
- **Extensible skills** — Add new capabilities via `SKILL.md` markdown files — no code changes, no redeployment. The agent loads skills on demand
- **Multi-database** — MySQL, PostgreSQL, SQLite, SeekDB (OceanBase) with a clean adapter interface for adding more
- **External access** (optional) — Fetch web pages and call REST APIs when enabled; SSRF protection, timeout, and size limits keep it safe

### What You Can Do

```
> "Show me the top 10 customers by revenue last quarter"
> "Why is this query slow? Suggest indexes"
> "Generate 100 realistic test users with orders"
> "Find orphaned records and fix foreign key violations"
> "Based on product descriptions, generate a one-sentence summary column"
> "What tables are related to the orders system? Draw the relationships"
> "Fetch the API docs at https://example.com/api and summarize the endpoints" *(requires external access)*
```

## Installation

```bash
pip install queryclaw
```

For PostgreSQL support:

```bash
pip install queryclaw[postgresql]
```

For Feishu channel support:

```bash
pip install queryclaw[feishu]
```

For DingTalk channel support:

```bash
pip install queryclaw[dingtalk]
```

For all optional features (PostgreSQL + SQL validation + Feishu + DingTalk):

```bash
pip install queryclaw[all]
```

## Quick Start

```bash
# 1. Initialize configuration
queryclaw onboard

# 2. Edit config — set your database connection and LLM API key
#    Config location: ~/.queryclaw/config.json

# 3. Start chatting with your database
queryclaw chat
```

Example interaction:

```
You: What tables are in this database?
Agent: [calls schema_inspect] Found 12 tables. Here are the main ones...

You: Show me the top 5 customers by total order amount
Agent: [calls query_execute] Here are the results...

You: Add an index on orders.customer_id
Agent: ⚠️ This is a DDL operation. Proceed? [y/N]
```

For channel mode (Feishu / DingTalk):

```bash
queryclaw serve
```

## Architecture

QueryClaw uses a **ReACT (Reasoning + Acting) loop** powered by LLMs, with a modular tool and skill system:

```
                    ┌─────────────────────────┐
                    │      CLI / Channel       │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   AgentLoop (ReACT)      │
                    │  Reason → Act → Observe  │
                    │        → Repeat          │
                    └──┬──────────┬──────────┬──┘
                       │          │          │
              ┌────────▼────┐ ┌──▼──────┐ ┌▼────────────┐
              │  LLM        │ │  Tools  │ │   Skills     │
              │  Providers  │ │         │ │  (SKILL.md)  │
              └─────────────┘ └────┬────┘ └──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │       Safety Layer          │
                    │  Validate → Dry-Run → Audit │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     Database Adapters       │
                    │  MySQL│SQLite│PG│SeekDB   │
                    └─────────────────────────────┘
```

The LLM provider layer is powered by [LiteLLM](https://github.com/BerriAI/litellm), supporting OpenAI, Anthropic, Gemini, DeepSeek, and any compatible API.

## Memory & Context

QueryClaw maintains **session memory** throughout each conversation — it tracks the schemas you've explored, queries you've run, and modifications you've made, so you can build on previous steps without repeating context. The [audit trail](#full-audit-trail) also provides persistent operation history, queryable via standard SQL.

**Coming soon** (Phase 3): Persistent database-native memory — schema knowledge, learned patterns, and semantic recall that accumulates across sessions, making the Agent smarter with every use.

## Full Audit Trail

Every action QueryClaw takes is recorded in a dedicated audit table within the managed database (`_queryclaw_audit_log`). This provides:

- **Complete lineage**: From natural language prompt → generated SQL → execution result → affected rows
- **Before/after snapshots**: For data modifications, the state before and after the change is captured as JSON
- **Timestamp + session tracking**: Who asked what, when, and in which conversation
- **Rollback reference**: If something goes wrong, the audit log tells you exactly what happened and how to undo it

Example: after an `UPDATE users SET status = 'active' WHERE id = 42`, the audit log records:

```
sql_text:         UPDATE users SET status = 'active' WHERE id = 42
affected_rows:    1
before_snapshot:  [{"id": 42, "status": "inactive", "name": "Alice"}]
after_snapshot:   [{"id": 42, "status": "active", "name": "Alice"}]
```

This is not just logging — it's a full **security audit trail** that compliance teams, DBAs, and developers can query using standard SQL. Since it lives in the database itself, it's always available, always queryable, and backed by the same ACID guarantees as your data.

## Built-in Skills

QueryClaw's real power comes from its skill system. Each skill teaches the Agent a domain-specific workflow — no code changes needed, just `SKILL.md` files:

| Skill | What It Does |
|-------|-------------|
| **AI Column** | Generate column values using LLM (summaries, sentiment, translations, scores) |
| **Test Data Factory** | Generate semantically realistic test data respecting FK constraints |
| **Data Detective** | Trace data lineage across related tables to find the root cause of bugs |
| **Data Analysis** | Statistical analysis, distribution profiling, and data quality assessment |
| **Schema Documenter** | Auto-generate schema documentation with business context from naming + sampling |
| **Query Translator** | Explain complex SQL in plain language, identify issues, suggest optimizations |
| **SeekDB Vector Search** | Vector search, semantic search, AI_EMBED, hybrid search in SeekDB (OceanBase AI-native DB) |

> More skills are planned (Index Advisor, Data Healer, Anomaly Scanner, etc.) — see [Skills Roadmap](docs/SKILLS_ROADMAP.md) for the full list and priorities.

## Roadmap

> Phases are developed in parallel where feasible; numbering reflects logical grouping, not strict dependency order.

### Phase 1: MVP — Read-Only Agent *(completed)*

- Interactive CLI (typer + prompt_toolkit)
- ReACT agent loop
- LLM provider layer (LiteLLM)
- Database adapters: MySQL + SQLite
- Read-only tools: `schema_inspect`, `query_execute`, `explain_plan`, `read_skill`
- Configuration system
- Basic skill loading

### Phase 2: Write Operations + Safety *(completed)*

- PostgreSQL adapter (asyncpg)
- SeekDB adapter (OceanBase AI-native database)
- Safety layer: policy engine, SQL AST validator, dry-run engine, audit logger
- Before/after data snapshots for all DML operations
- Subagent system: `spawn_subagent` tool for delegated tasks
- Write tools: `data_modify`, `ddl_execute`, `transaction`
- Human-in-the-loop confirmation flow for destructive operations
- Skills: Schema Documenter, Query Translator, Data Detective, Data Analysis, AI Column, Test Data Factory, SeekDB Vector Search
- `SafetyConfig` in configuration system

### Phase 3: Advanced Skills + Memory

- Persistent memory (schema knowledge + operation history)
- Cron system + Heartbeat (proactive monitoring)
- Skills: Index Advisor, Data Healer, Anomaly Scanner, Smart Migrator
- Multi-step planning for complex tasks
- SeekDB Fork Table sandbox for safe experimentation

### Phase 4: Multi-Channel Output *(completed)*

- Message bus + bidirectional channels (Feishu, DingTalk)
- External access: `web_fetch` and `api_call` tools (optional, SSRF-protected)
- `queryclaw serve` — run Agent in channel mode; ask questions in Feishu/DingTalk and get responses
- Optional dependencies: `queryclaw[feishu]`, `queryclaw[dingtalk]`
- Interactive confirmation in channels — reply "confirm" or "cancel" to approve or reject destructive operations

### Phase 5: Ecosystem Integration

- MCP server mode (expose as a tool for other agents)
- Additional channels (Telegram, Slack, etc.)
- MongoDB adapter + multi-database connections
- Web UI
- Plugin system for custom tools and adapters

### Phase 5+: Vector & AI-Native DB

- **Semantic schema search** — find tables/columns by meaning over large schemas using vector embeddings
- **Hybrid queries** — combine SQL filters with vector similarity (pgvector or sidecar vector store)
- **Vectorized memory** — semantic recall across sessions; the agent gets smarter over time
- **AI-native DB integration** — unified entry point for relational, vector, and AI-native backends

> Detailed architecture plan: [docs/PLAN_ARCHITECTURE.md](docs/PLAN_ARCHITECTURE.md)

## Documentation

- **[User Manual](docs/USER_MANUAL.md)** ([中文](docs/zh/USER_MANUAL.md)) — Install, configure, and use QueryClaw (current version)
- **[Release Notes](RELEASE_NOTES.md)** ([中文](RELEASE_NOTES_CN.md)) — Version history and changelog
- [Architecture & Implementation Plan](docs/PLAN_ARCHITECTURE.md) ([中文](docs/zh/PLAN_ARCHITECTURE.md))
- [Skills Roadmap](docs/SKILLS_ROADMAP.md) ([中文](docs/zh/SKILLS_ROADMAP.md))
- [Self-Evolution Analysis (Tools & Skills)](docs/SELF_EVOLUTION_ANALYSIS.md) ([中文](docs/zh/SELF_EVOLUTION_ANALYSIS.md))

## Contributing

We welcome contributions! Whether it's a new database adapter, a creative skill idea, or a bug fix — PRs are appreciated.

## Acknowledgments

QueryClaw's architecture is deeply inspired by two pioneering projects in the AI agent space:

- **[OpenClaw](https://github.com/openclaw/openclaw)** — The original vision of giving an LLM full control of a personal computer. OpenClaw proved that autonomous AI agents can operate safely in complex environments. QueryClaw extends this philosophy from the OS to the database.
- **[nanobot](https://github.com/HKUDS/nanobot)** — An ultra-lightweight personal AI assistant that demonstrated elegant implementations of the ReACT loop, tool registry, skill system, memory, and multi-channel architecture. QueryClaw's agent core, provider layer, and skill format are directly modeled after nanobot's clean design.

Thank you to both teams for pushing the boundaries of what AI agents can do.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
