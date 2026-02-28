# QueryClaw: Project Progress & Planning

> [中文版](zh/PROGRESS_AND_PLAN.md)

**Last updated**: 2026-02-27  
**Current version**: 0.5.0

---

## 1. Project Overview

QueryClaw is an AI-native database agent that gives an LLM control over a database instance. Users interact via natural language; the Agent explores schemas, queries data, modifies records, and performs administrative tasks through a ReACT loop with safety guardrails.

**Core positioning**: *OpenClaw : OS = QueryClaw : Database*

---

## 2. Completed Work (Progress Summary)

### 2.1 Phase 1: MVP — Read-Only Agent ✅

| Component | Status | Notes |
|-----------|--------|-------|
| CLI | ✅ | typer + prompt_toolkit, interactive chat |
| ReACT Agent Loop | ✅ | Reason → Act → Observe → Repeat |
| LLM Provider Layer | ✅ | LiteLLM, multi-provider (OpenAI, Anthropic, Gemini, DeepSeek, etc.) |
| Database Adapters | ✅ | MySQL, SQLite |
| Tools | ✅ | `schema_inspect`, `query_execute`, `explain_plan` |
| Config System | ✅ | `~/.queryclaw/config.json` |
| Skill Loading | ✅ | Basic SKILL.md loader |

### 2.2 Phase 2: Write Operations + Safety ✅

| Component | Status | Notes |
|-----------|--------|-------|
| Write Tools | ✅ | `data_modify`, `ddl_execute`, `transaction` |
| Safety Layer | ✅ | Policy engine, SQL AST validator (sqlglot), dry-run engine, audit logger |
| Human Confirmation | ✅ | CLI prompt + channel-mode (Feishu/DingTalk) confirm/cancel |
| PostgreSQL Adapter | ✅ | asyncpg |
| Subagent System | ✅ | `spawn_subagent` for background long tasks |
| Audit Before/After Snapshots | ✅ | `SnapshotHelper` populates `before_snapshot`, `after_snapshot` in audit table |

### 2.3 Phase 4: Multi-Channel Output ✅

| Component | Status | Notes |
|-----------|--------|-------|
| Message Bus | ✅ | Event-driven, bidirectional |
| Feishu Channel | ✅ | WebSocket, optional `queryclaw[feishu]` |
| DingTalk Channel | ✅ | Stream mode, optional `queryclaw[dingtalk]` |
| `queryclaw serve` | ✅ | Run Agent in channel mode |
| Channel Confirmation | ✅ | Reply "确认"/"取消" to proceed or abort destructive ops |

### 2.4 SeekDB & Vector Search (Phase 3 Partial) ✅

| Component | Status | Notes |
|-----------|--------|-------|
| SeekDB Adapter | ✅ | Extends MySQLAdapter, port 2881, VECTOR, AI_EMBED |
| SeekDB Audit Fix | ✅ | MySQL-style DDL and `%s` placeholders |
| SeekDB Dialect Mapping | ✅ | seekdb → mysql for sqlglot |
| SeekDB Vector Search Skill | ✅ | `seekdb_vector_search` SKILL.md |

### 2.5 Skills Implemented (SKILL.md)

| Skill | Status | Phase |
|-------|--------|-------|
| AI Column | ✅ | 2 |
| Test Data Factory | ✅ | 2 |
| Data Detective | ✅ | 2 |
| Schema Documenter | ✅ | 2 |
| Query Translator | ✅ | 2 |
| Data Analysis | ✅ | 2 |
| SeekDB Vector Search | ✅ | 3 |

### 2.6 Infrastructure & Quality

| Item | Status |
|------|--------|
| `read_skill` Tool | ✅ Agent loads SKILL.md on demand |
| Skills in pip Package | ✅ `package-data` includes all SKILL.md |
| Tests | ✅ 243+ tests (safety, tools, agent, channels, etc.) |
| PyPI | ✅ Published (0.5.0) |
| Documentation | ✅ USER_MANUAL, PLAN_ARCHITECTURE, SKILLS_ROADMAP, RELEASE_NOTES (EN+ZH) |

---

## 3. Not Yet Implemented (Gap Analysis)

### 3.1 Phase 3: Advanced Skills + Memory + Cron

| Component | Status | Priority |
|-----------|--------|----------|
| **Persistent Memory** | ❌ | High |
| - Schema knowledge (MEMORY.md style) | ❌ | |
| - Operation history (HISTORY.md style) | ❌ | |
| - Database-backed storage | ❌ | |
| **Cron System** | ❌ | Medium |
| **Heartbeat** | ❌ | Medium |
| **Index Advisor Skill** | ❌ | Medium |
| **Data Healer Skill** | ❌ | Medium |
| **Anomaly Scanner Skill** | ❌ | Medium |
| **Data Masker Skill** | ❌ | Medium |
| **Smart Migrator Skill** | ❌ | Medium |
| **Change Impact Analyzer Skill** | ❌ | Low |
| **Multi-step Planning** | ❌ | Medium |

### 3.2 Phase 5: Ecosystem Integration

| Component | Status | Priority |
|-----------|--------|----------|
| MCP Server Mode | ❌ | High |
| Additional Channels (Telegram, Slack) | ❌ | Medium |
| MongoDB Adapter | ❌ | Medium |
| Multi-database Connections | ❌ | Medium |
| Web UI | ❌ | Low |
| Plugin System | ❌ | Low |
| `admin_ops` Tool | ❌ | Low |

### 3.3 Phase 5+: Vector & AI-Native DB

| Component | Status | Priority |
|-----------|--------|----------|
| pgvector / Vector Column Support | ❌ | Medium |
| Semantic Schema Search | ❌ | Medium |
| Hybrid Query (SQL + Vector) | ❌ | Medium |
| Vectorized Memory | ❌ | Medium |
| AI Column: Embedding Generation | ❌ | Medium |

### 3.4 Skills Not Yet Implemented

| Skill | Priority | Phase |
|-------|----------|-------|
| Index Advisor | Medium | 3 |
| Data Healer | Medium | 3 |
| Anomaly Scanner | Medium | 3 |
| Data Masker | Medium | 3 |
| Smart Migrator | Medium | 3 |
| Change Impact Analyzer | Low | 3 |
| Capacity Planner | Low | 5 |
| Compliance Scanner | Low | 5 |
| Permission Auditor | Low | 5 |
| API Scaffolding | Low | 5 |
| Cross-DB Sync Checker | Low | 5 |

---

## 4. Recommended Next Steps (Planning)

### 4.1 Short-term (0.5.x — Next 1–2 Months)

**Goal**: Strengthen core value and production readiness.

| # | Task | Effort | Value |
|---|------|--------|-------|
| 1 | **Persistent Memory** | Medium | High — Schema knowledge + operation history in DB; Agent gets smarter over time |
| 2 | **Index Advisor Skill** | Medium | High — Common DBA need; leverages existing EXPLAIN + schema tools |
| 3 | **MCP Server Mode** | Medium | High — Expose QueryClaw as tool for other agents (Cursor, Claude Desktop, etc.) |
| 4 | **Data Healer Skill** | Medium | Medium — FK integrity, format checks, semantic dirty data |
| 5 | **Channel UX Improvements** | Low | Medium — Better confirmation prompts, error messages in Feishu/DingTalk |

### 4.2 Mid-term (0.6.x — 2–4 Months)

**Goal**: Expand skills and operational capabilities.

| # | Task | Effort | Value |
|---|------|--------|-------|
| 1 | **Cron + Heartbeat** | Medium | Medium — Scheduled health checks, proactive monitoring |
| 2 | **Anomaly Scanner Skill** | Medium | Medium — Distribution analysis, outlier detection |
| 3 | **Smart Migrator Skill** | Medium | Medium — NL → migration scripts, rollback, dry-run |
| 4 | **Data Masker Skill** | Medium | Medium — PII detection, anonymization |
| 5 | **Multi-step Planning** | High | High — Complex multi-table tasks |
| 6 | **Telegram / Slack Channel** | Low | Medium — Broader channel coverage |

### 4.3 Long-term (0.7+ — 4+ Months)

**Goal**: Ecosystem and vector/AI-native integration.

| # | Task | Effort | Value |
|---|------|--------|-------|
| 1 | **MongoDB Adapter** | Medium | Medium — Document DB support |
| 2 | **Multi-database Connections** | High | Medium — Compare/sync across DBs |
| 3 | **pgvector / Vector Support** | Medium | High — Semantic schema search, hybrid query |
| 4 | **Vectorized Memory** | Medium | High — Semantic recall |
| 5 | **Web UI** | High | Medium — Broader accessibility |
| 6 | **Plugin System** | High | Medium — Community extensions |

---

## 5. Priority Matrix

```
                    High Value
                         │
    Index Advisor        │  Persistent Memory
    Data Healer          │  MCP Server
                         │
    ─────────────────────┼─────────────────────
                         │
    Anomaly Scanner      │  Cron/Heartbeat
    Smart Migrator       │  Multi-step Planning
    Data Masker          │
                         │
                    Low Value
                         
         Low Effort ───────────── High Effort
```

**Recommended focus order**:
1. Persistent Memory (foundation for smarter Agent)
2. MCP Server (ecosystem reach)
3. Index Advisor (high-frequency DBA need)
4. Data Healer (data governance)
5. Cron + Heartbeat (operational maturity)

---

## 6. Risk & Dependency Notes

| Risk | Mitigation |
|------|------------|
| Memory design complexity | Start with simple DB table (schema_facts, operation_log); defer semantic/vector recall to Phase 5+ |
| MCP protocol changes | Follow MCP spec; abstract transport layer |
| Skill quality varies | Add skill-specific tests; document expected workflows |
| Channel API changes | Feishu/DingTalk SDK versions; pin optional deps |

---

## 7. Version Roadmap (Tentative)

| Version | Focus | Target |
|---------|-------|--------|
| 0.5.x | Stability, minor fixes | Current |
| 0.6.0 | Persistent Memory + Index Advisor | ~1 month |
| 0.6.x | MCP Server + Data Healer | ~2 months |
| 0.7.0 | Cron + Heartbeat + Anomaly Scanner | ~3 months |
| 0.8.0 | Vector support, MongoDB | ~4+ months |

---

## 8. References

- [PLAN_ARCHITECTURE.md](PLAN_ARCHITECTURE.md) — Full architecture
- [SKILLS_ROADMAP.md](SKILLS_ROADMAP.md) — Skill catalog and priorities
- [DESIGN_PLUGIN_SYSTEM.md](DESIGN_PLUGIN_SYSTEM.md) — Plugin system design (adapters, tools, skills, channels)
- [PLAN_SEEKDB_FORK_SANDBOX.md](PLAN_SEEKDB_FORK_SANDBOX.md) — SeekDB Fork Table sandbox plan
- [RELEASE_NOTES.md](../RELEASE_NOTES.md) — Version history
- [USER_MANUAL.md](USER_MANUAL.md) — User guide
