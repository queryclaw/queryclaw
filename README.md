# QueryClaw

**Your Database, Under AI Command.**

> [中文版](README_CN.md)

[![PyPI](https://img.shields.io/pypi/v/queryclaw)](https://pypi.org/project/queryclaw/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)

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

### What You Can Do

```
> "Show me the top 10 customers by revenue last quarter"
> "Why is this query slow? Suggest indexes"
> "Generate 100 realistic test users with orders"
> "Find orphaned records and fix foreign key violations"
> "Based on product descriptions, generate a one-sentence summary column"
> "What tables are related to the orders system? Draw the relationships"
> "Check if there's any PII stored in plaintext"
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
                    │  MySQL │ SQLite │ PostgreSQL │
                    └─────────────────────────────┘
```

**Key design choices:**

- **Multi-database**: Adapter-based architecture supports MySQL (primary), SQLite, PostgreSQL, with extensibility for MongoDB, Redis, and more
- **Multi-LLM**: Unified provider layer via [LiteLLM](https://github.com/BerriAI/litellm) — use OpenAI, Anthropic, Gemini, DeepSeek, or any compatible API
- **Extensible skills**: Add new capabilities via `SKILL.md` files — no code changes needed
- **Safety-first**: Progressive safety with policy checks, SQL AST validation, dry-runs, transaction wrapping, human confirmation, and full audit logging

## Database-Native Memory — Smarter With Every Use

Unlike file-based memory in general-purpose agents, QueryClaw stores its memory **directly in the database it manages** — the most natural and reliable place for structured data.

Every interaction teaches the Agent something: table relationships, business meanings of columns, common query patterns, data quirks. This knowledge is persisted and accumulates over time:

- **Schema knowledge**: "The `status` column in `orders` uses 1=pending, 2=shipped, 3=completed"
- **Learned patterns**: "This team usually queries `daily_sales` grouped by region"
- **Operation history**: "Last Tuesday we added an index on `users.email` to fix the slow login query"

The more you use QueryClaw, the less you need to explain. It remembers your database the way a seasoned DBA remembers the systems they've managed for years — except it never forgets.

## Full Audit Trail — Every Operation, Recorded

Every action QueryClaw takes is recorded in a dedicated audit table within the managed database (`_queryclaw_audit_log`). This provides:

- **Complete lineage**: From natural language prompt → generated SQL → execution result → affected rows
- **Before/after snapshots**: For data modifications, the state before and after the change
- **Timestamp + session tracking**: Who asked what, when, and in which conversation
- **Rollback reference**: If something goes wrong, the audit log tells you exactly what happened and how to undo it

This is not just logging — it's a full **security audit trail** that compliance teams, DBAs, and developers can query using standard SQL. Since it lives in the database itself, it's always available, always queryable, and backed by the same ACID guarantees as your data.

## Built-in Skills

QueryClaw's real power comes from its skill system. Each skill teaches the Agent a domain-specific workflow:

| Skill | What It Does |
|-------|-------------|
| **AI Column** | Generate column values using LLM (summaries, sentiment, translations, scores) |
| **Test Data Factory** | Generate semantically realistic test data respecting FK constraints |
| **Data Detective** | Trace data lineage across related tables to find the root cause of bugs |
| **Schema Documenter** | Auto-generate schema documentation with business context from naming + sampling |
| **Query Translator** | Explain complex SQL in plain language, identify issues, suggest optimizations |
| **Index Advisor** | Analyze slow queries, suggest indexes, estimate write impact |
| **Data Healer** | Find and fix dirty data — orphans, format inconsistencies, semantic errors |
| **Data Masker** | Auto-detect PII columns and generate realistic anonymized data |
| **Anomaly Scanner** | Proactively detect outliers, distribution shifts, and suspicious patterns |
| **Smart Migrator** | Generate migration scripts from natural language, with rollback and dry-run |

> Full list with priorities: [docs/SKILLS_ROADMAP.md](docs/SKILLS_ROADMAP.md)

## Roadmap

### Phase 1: MVP — Read-Only Agent *(completed)*

- Interactive CLI (typer + prompt_toolkit)
- ReACT agent loop
- LLM provider layer (LiteLLM)
- Database adapters: MySQL + SQLite
- Read-only tools: `schema_inspect`, `query_execute`, `explain_plan`
- Configuration system
- Basic skill loading

### Phase 2: Write Operations + Safety *(completed)*

- PostgreSQL adapter (asyncpg)
- Safety layer: policy engine, SQL AST validator, dry-run engine, audit logger
- Subagent system: `spawn_subagent` tool for delegated tasks
- Write tools: `data_modify`, `ddl_execute`, `transaction`
- Human-in-the-loop confirmation flow for destructive operations
- Read-only skills: Schema Documenter, Query Translator, Data Detective
- Write skills: AI Column, Test Data Factory
- `SafetyConfig` in configuration system

### Phase 3: Advanced Skills + Memory

- Persistent memory (schema knowledge + operation history)
- Cron system + Heartbeat (proactive monitoring)
- Skills: Index Advisor, Data Healer, Anomaly Scanner, Smart Migrator
- Multi-step planning for complex tasks

### Phase 4: Multi-Channel Output *(completed)*

- Message bus + bidirectional channels (Feishu, DingTalk)
- `queryclaw serve` — run Agent in channel mode; ask questions in Feishu/DingTalk and get responses
- Optional dependencies: `queryclaw[feishu]`, `queryclaw[dingtalk]`
- Destructive operations rejected in channel mode when `require_confirmation=True`

### Phase 4+: Ecosystem Integration

- MCP server mode (expose as a tool for other agents)
- Additional channels (Telegram, Slack, etc.)
- MongoDB adapter + multi-database connections
- Web UI
- Plugin system for custom tools and adapters

### Vector & AI-Native DB (Phase 4+)

Combining with vector stores and AI-native databases unlocks new capabilities:

| Direction | Highlight |
|-----------|-----------|
| **Vector + Schema** | Semantic schema search — find tables/columns by meaning (e.g. "tables about user auth") over large schemas; RAG over schema + docs. |
| **Vector + Query** | Hybrid queries — SQL filters plus vector similarity (e.g. "orders semantically similar to this description"); works with pgvector or sidecar vector store. |
| **Vector + Memory** | Semantic recall — memory stored as embeddings; "similar to that slow query we fixed" retrieves past solutions; makes the agent smarter over time. |
| **Vector + AI Column** | One-click embedding columns — generate and store embeddings for a column (e.g. `description`) for similarity search, dedup, clustering inside the same DB. |
| **AI-Native DB** | Single agent entry — use the DB's built-in NL2SQL when appropriate; use QueryClaw's ReACT + skills for complex, multi-step, or skill-based tasks. |
| **AI-Native DB** | Skills on top — Test Data Factory, Data Detective, AI Column, compliance scan; unified memory and audit across relational, vector, and AI-native backends. |

> Detailed architecture plan: [docs/PLAN_ARCHITECTURE.md](docs/PLAN_ARCHITECTURE.md)

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

## Documentation

- **[User Manual](docs/USER_MANUAL.md)** ([中文](docs/USER_MANUAL_CN.md)) — Install, configure, and use QueryClaw (current version)
- **[Release Notes](RELEASE_NOTES.md)** ([中文](RELEASE_NOTES_CN.md)) — Version history and changelog
- [Architecture & Implementation Plan](docs/PLAN_ARCHITECTURE.md) ([中文](docs/PLAN_ARCHITECTURE_CN.md))
- [Skills Roadmap](docs/SKILLS_ROADMAP.md) ([中文](docs/SKILLS_ROADMAP_CN.md))
- [Self-Evolution Analysis (Tools & Skills)](docs/SELF_EVOLUTION_ANALYSIS.md) ([中文](docs/SELF_EVOLUTION_ANALYSIS_CN.md))

## Contributing

We welcome contributions! Whether it's a new database adapter, a creative skill idea, or a bug fix — PRs are appreciated.

## Acknowledgments

QueryClaw's architecture is deeply inspired by two pioneering projects in the AI agent space:

- **[OpenClaw](https://github.com/openclaw/openclaw)** — The original vision of giving an LLM full control of a personal computer. OpenClaw proved that autonomous AI agents can operate safely in complex environments. QueryClaw extends this philosophy from the OS to the database.
- **[nanobot](https://github.com/HKUDS/nanobot)** — An ultra-lightweight personal AI assistant that demonstrated elegant implementations of the ReACT loop, tool registry, skill system, memory, and multi-channel architecture. QueryClaw's agent core, provider layer, and skill format are directly modeled after nanobot's clean design.

Thank you to both teams for pushing the boundaries of what AI agents can do.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
