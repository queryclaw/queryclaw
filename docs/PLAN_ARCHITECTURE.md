# QueryClaw: AI-Native Database Agent -- Architecture & Implementation Plan

> Chinese version: [PLAN_ARCHITECTURE_CN.md](PLAN_ARCHITECTURE_CN.md)

## 1. Core Concept

**openclaw : OS = queryclaw : Database**

openclaw lets an LLM control a personal computer; queryclaw lets an LLM control a database instance. The user hands over a complete database (MySQL / PostgreSQL / SQLite), and the Agent autonomously explores schemas, queries data, modifies records, optimizes performance, and performs administrative tasks -- all via natural language.

## 2. Architecture Overview

Modeled after [nanobot](nanobot/nanobot/), adapted for database domain:

```mermaid
graph TB
    subgraph cli [CLI Layer]
        UserCLI["CLI (typer + prompt_toolkit)"]
    end

    subgraph core [Agent Core]
        AgentLoop["AgentLoop (ReACT)"]
        Context["ContextBuilder"]
        Skills["SkillsLoader"]
        Memory["MemoryStore"]
    end

    subgraph providers [LLM Providers]
        Registry["ProviderRegistry"]
        LiteLLM["LiteLLMProvider"]
    end

    subgraph tools [Database Tools]
        ToolReg["ToolRegistry"]
        SchemaInspect["schema_inspect"]
        QueryExec["query_execute"]
        DataModify["data_modify"]
        DDLOps["ddl_execute"]
        TxnMgmt["transaction"]
        ExplainPlan["explain_plan"]
        AdminOps["admin_ops"]
    end

    subgraph db [Database Adapters]
        DBRegistry["AdapterRegistry"]
        MySQL["MySQLAdapter"]
        PostgreSQL["PostgreSQLAdapter"]
        SQLite["SQLiteAdapter"]
    end

    subgraph safety [Safety Layer]
        Validator["QueryValidator"]
        DryRun["DryRunEngine"]
        AuditLog["AuditLogger"]
        Sandbox["SafetyPolicy"]
    end

    UserCLI --> AgentLoop
    AgentLoop --> Context
    AgentLoop --> Skills
    AgentLoop --> Memory
    AgentLoop --> Registry
    Registry --> LiteLLM
    AgentLoop --> ToolReg
    ToolReg --> SchemaInspect
    ToolReg --> QueryExec
    ToolReg --> DataModify
    ToolReg --> DDLOps
    ToolReg --> TxnMgmt
    ToolReg --> ExplainPlan
    ToolReg --> AdminOps
    SchemaInspect --> DBRegistry
    QueryExec --> DBRegistry
    DataModify --> Validator
    DDLOps --> Validator
    Validator --> DryRun
    DryRun --> AuditLog
    DBRegistry --> MySQL
    DBRegistry --> PostgreSQL
    DBRegistry --> SQLite
```

## 3. Directory Structure

```
queryclaw/
├── queryclaw/
│   ├── __init__.py
│   ├── agent/
│   │   ├── loop.py          # ReACT agent loop (ref: nanobot/agent/loop.py)
│   │   ├── context.py       # System prompt + schema context builder
│   │   ├── memory.py        # Conversation & operation memory
│   │   └── skills.py        # Skill loader (SKILL.md format)
│   ├── providers/
│   │   ├── base.py          # LLMProvider ABC (ref: nanobot/providers/base.py)
│   │   ├── registry.py      # Provider auto-detect registry
│   │   └── litellm_provider.py  # LiteLLM unified backend
│   ├── tools/
│   │   ├── base.py          # Tool ABC (ref: nanobot/agent/tools/base.py)
│   │   ├── registry.py      # ToolRegistry
│   │   ├── schema.py        # schema_inspect, schema_search
│   │   ├── query.py         # query_execute (SELECT)
│   │   ├── modify.py        # data_modify (INSERT/UPDATE/DELETE)
│   │   ├── ddl.py           # ddl_execute (CREATE/ALTER/DROP)
│   │   ├── transaction.py   # begin/commit/rollback
│   │   ├── explain.py       # EXPLAIN / query plan analysis
│   │   └── admin.py         # DB-level ops (users, grants, stats)
│   ├── db/
│   │   ├── base.py          # DatabaseAdapter ABC
│   │   ├── registry.py      # Adapter registry (by db type)
│   │   ├── mysql.py         # MySQL adapter
│   │   ├── postgresql.py    # PostgreSQL adapter
│   │   └── sqlite.py        # SQLite adapter
│   ├── safety/
│   │   ├── validator.py     # AST-based SQL validation
│   │   ├── policy.py        # Safety policy (read-only, allow-list, etc.)
│   │   ├── dry_run.py       # Dry-run engine (EXPLAIN + affected rows)
│   │   └── audit.py         # Audit log (before/after snapshots)
│   ├── config/
│   │   ├── schema.py        # Pydantic config model
│   │   └── loader.py        # Config file loader (~/.queryclaw/config.json)
│   ├── cli/
│   │   └── commands.py      # typer CLI (chat, onboard, config)
│   └── skills/              # Built-in skills (SKILL.md)
│       ├── data_analysis/
│       ├── migration/
│       ├── performance/
│       └── backup/
├── pyproject.toml
├── README.md
└── LICENSE
```

## 4. Key Components (from nanobot, adapted)

### 4.1 Database Adapter Layer (`queryclaw/db/`)

Extensible multi-database support. **Phase 1 prioritizes MySQL + SQLite** (MySQL as primary target, SQLite for zero-config testing/demo). PostgreSQL deferred to Phase 2.

Two-layer abstraction to support future non-relational databases (MongoDB, Redis, Elasticsearch):

```python
class DatabaseAdapter(ABC):
    """Universal adapter interface -- all database types must implement"""
    async def connect(self, config: DBConfig) -> None
    async def execute(self, command: str, params=None) -> QueryResult
    async def get_structure(self) -> StructureInfo
    async def close(self) -> None
    @property
    def db_type(self) -> str  # "mysql", "sqlite", "mongodb", ...

class SQLAdapter(DatabaseAdapter):
    """SQL specialization -- common methods for relational databases"""
    async def get_schemas(self) -> list[SchemaInfo]
    async def get_tables(self, schema: str) -> list[TableInfo]
    async def get_columns(self, table: str) -> list[ColumnInfo]
    async def get_indexes(self, table: str) -> list[IndexInfo]
    async def get_foreign_keys(self, table: str) -> list[FKInfo]
    async def explain(self, sql: str) -> ExplainResult
    async def begin_transaction(self) -> TransactionHandle

# Future non-SQL databases implement their own specialization
# class DocumentAdapter(DatabaseAdapter): ...  # MongoDB
# class KVAdapter(DatabaseAdapter): ...        # Redis
```

User configures database type and connection in `~/.queryclaw/config.json`:

```json
{
  "database": {
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "database": "myapp",
    "user": "root",
    "password": "***"
  }
}
```

### 4.2 Agent ReACT Loop (`queryclaw/agent/loop.py`)

Same pattern as `nanobot/agent/loop.py`:

- **Reason**: LLM receives user request + schema context + conversation history
- **Act**: LLM calls database tools (inspect schema, run query, modify data...)
- **Observe**: Tool results fed back to LLM
- **Repeat** until LLM produces a final answer (no more tool calls)

### 4.3 Database Tools (`queryclaw/tools/`)

| Tool             | Description                                       | Safety Level        |
| ---------------- | ------------------------------------------------- | ------------------- |
| `schema_inspect` | List databases/schemas/tables/columns/indexes/FKs | Safe (read-only)    |
| `query_execute`  | Run SELECT queries, return results                | Safe (read-only)    |
| `explain_plan`   | Run EXPLAIN on a query, show execution plan       | Safe (read-only)    |
| `data_modify`    | INSERT / UPDATE / DELETE (via safety layer)       | Requires validation |
| `ddl_execute`    | CREATE / ALTER / DROP (via safety layer)          | Requires validation |
| `transaction`    | BEGIN / COMMIT / ROLLBACK                         | Context-dependent   |
| `admin_ops`      | User management, grants, DB stats                 | Privileged          |

### 4.4 Safety Layer (`queryclaw/safety/`)

Progressive safety:

1. **Policy check**: Is this operation type allowed? (configurable read-only / read-write / full)
2. **SQL validation**: Parse SQL AST, detect dangerous patterns (DROP DATABASE, DELETE without WHERE, etc.)
3. **Dry-run**: EXPLAIN the statement, estimate affected rows, show execution plan
4. **Human confirmation**: For destructive operations, prompt user "This will delete 1,234 rows. Proceed? [y/N]"
5. **Transaction wrap**: Auto-wrap modifications in transactions; rollback on error
6. **Audit log**: Record before/after snapshots, full SQL lineage

### 4.5 LLM Providers (`queryclaw/providers/`)

Directly reference nanobot's provider pattern:

- `LLMProvider` ABC with `chat()` method
- `LiteLLMProvider` for unified multi-provider support
- `ProviderRegistry` for auto-detection by model name / API key
- User configures in `~/.queryclaw/config.json`

### 4.6 Skills System (`queryclaw/skills/`)

SKILL.md format (same as nanobot), domain-specific:

- **data_analysis**: Summarize tables, find patterns, generate reports
- **migration**: Plan schema migrations, generate DDL, preview changes
- **performance**: Identify slow queries, suggest indexes, analyze query plans
- **backup**: Export data, create snapshots, restore points

## 5. What Can We Do With a Database Under Agent Control?

This is the exploratory core. Initial capabilities to implement:

- **Natural Language Querying**: "Show me the top 10 customers by revenue last quarter"
- **Schema Exploration**: "What tables are related to the orders system? Show me the ER relationships"
- **Data Analysis**: "Are there any anomalies in the transaction data from this week?"
- **Safe Data Modification**: "Update all users with expired subscriptions to inactive status" (with dry-run + confirmation)
- **Schema Evolution**: "Add a `last_login` column to the users table" (with migration plan)
- **Performance Diagnostics**: "Why is this query slow?" (EXPLAIN analysis + index suggestions)
- **Data Quality Checks**: "Find orphaned records, duplicate entries, or NULL violations"
- **Report Generation**: "Generate a monthly sales summary grouped by region"
- **Backup & Restore**: "Create a snapshot of the orders table before I make changes"
- **Access Control Review**: "Show me all database users and their privileges"

## 6. Advanced Features Analysis (from nanobot)

### Near-term (Phase 2-3)

- **A. Subagent system**: Background long-running tasks (large-scale analysis, full table scans, cross-table checks)
- **B. Memory system**: Two-layer memory (MEMORY.md for schema knowledge, HISTORY.md for operation log)
- **C. Cron system**: Scheduled health checks, performance monitoring, data quality audits
- **D. Heartbeat**: Proactive database monitoring and anomaly alerts
- **E. Message bus + channels**: Push results/alerts to Telegram, Slack, Feishu, etc.

### Long-term (Phase 4+)

- **F. MCP server mode**: Expose queryclaw as MCP tool for other agents
- **G. Multi-database connections**: Connect to multiple databases simultaneously
- **H. Data lineage tracking**: Full operation audit trail
- **I. NL-to-stored-procedures/views**: Persist common queries as DB objects
- **J. Migration orchestration**: Generate and preview migration scripts
- **K. Intelligent index advisor**: Analyze slow queries, suggest indexes

---

## 7. Multi-Database Expansion Roadmap

| Database | Phase | Adapter Layer | Notes |
|----------|-------|---------------|-------|
| **MySQL** | Phase 1 (primary) | `SQLAdapter` | Most common production DB |
| **SQLite** | Phase 1 | `SQLAdapter` | Zero-config for dev/test/demo |
| **PostgreSQL** | Phase 2-3 | `SQLAdapter` | Rich ecosystem, advanced SQL |
| **MongoDB** | Phase 4+ | `DocumentAdapter` | Document-oriented, MQL |
| **Redis** | Phase 4+ | `KVAdapter` | Key-Value, command-based |
| **Elasticsearch** | Future | `SearchAdapter` | Full-text search & analytics |
| **ClickHouse** | Future | `SQLAdapter` | Columnar analytics |

---

## 8. Implementation Phases (Updated)

### Phase 1: MVP -- Read-Only Agent (current)

- CLI with interactive chat (typer + prompt_toolkit)
- ReACT agent loop (from nanobot pattern)
- LLM provider layer (LiteLLM)
- Database adapter layer (**MySQL + SQLite first**)
- Tools: `schema_inspect`, `query_execute`, `explain_plan`
- Basic config system
- Basic skill loading

### Phase 2: Write Operations + Safety + PostgreSQL

- Tools: `data_modify`, `ddl_execute`, `transaction`
- Safety layer: validator, dry-run, audit log
- Human-in-the-loop confirmation for destructive ops
- PostgreSQL adapter
- Subagent system (background long tasks)

### Phase 3: Advanced Skills + Memory + Cron

- Built-in skills: data_analysis, migration, performance, backup
- Persistent memory (operation history, learned schema knowledge)
- Cron system + Heartbeat (proactive monitoring)
- Multi-step planning for complex tasks

### Phase 4: Ecosystem Integration + More Databases

- MCP server mode (expose as MCP tool for other agents)
- Message bus + multi-channel output (Telegram, Feishu, etc.)
- MongoDB adapter
- Multi-database simultaneous connections
- Web UI (optional)
- Plugin system for custom tools/adapters

---

## Phase 1 Todos

- **phase1-db-adapter**: Implement DatabaseAdapter + SQLAdapter ABC + MySQL adapter + SQLite adapter (`queryclaw/db/`)
- **phase1-providers**: Port LLM provider layer (base, registry, litellm_provider) from nanobot to `queryclaw/providers/`
- **phase1-tools**: Implement Tool ABC + ToolRegistry + read-only tools (schema_inspect, query_execute, explain_plan)
- **phase1-agent**: Implement ReACT AgentLoop + ContextBuilder with schema-aware system prompt
- **phase1-config**: Config system (Pydantic schema + loader) for DB connection + LLM provider settings
- **phase1-cli**: CLI with interactive chat mode (typer + prompt_toolkit)
- **phase1-skills**: SkillsLoader + at least one built-in skill (e.g. data_analysis)
