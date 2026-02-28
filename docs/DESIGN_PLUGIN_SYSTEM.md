# QueryClaw Plugin System — Design Document

> [中文版](zh/DESIGN_PLUGIN_SYSTEM.md)

**Status**: Design / Planning  
**Phase**: 5 (Ecosystem Integration)  
**Last updated**: 2026-02-27

---

## 1. Overview

The plugin system allows third-party code to extend QueryClaw without modifying the core codebase. Plugins can add:

- **Database adapters** — Support new database types (MongoDB, Redis, ClickHouse, etc.)
- **Tools** — New agent capabilities (custom queries, integrations, workflows)
- **Skills** — New SKILL.md workflows (loaded from plugin paths)
- **Channels** — New communication channels (Telegram, Slack, Discord, etc.)
- **LLM providers** — Custom provider logic (e.g., local model wrappers)
- **Safety hooks** — Custom validation, rate limiting, or audit extensions

---

## 2. Design Goals

| Goal | Description |
|------|--------------|
| **Discoverability** | Plugins are auto-discovered via Python entry points or config |
| **Isolation** | Plugin errors do not crash the core; optional sandboxing |
| **Versioning** | Plugins declare QueryClaw version compatibility |
| **Config-driven** | Plugins can be enabled/disabled and configured via `config.json` |
| **Minimal surface** | Clear, stable plugin API; internal APIs can change |

---

## 3. Plugin Types & Extension Points

### 3.1 Database Adapter Plugin

**Extension point**: `queryclaw.db.adapters`

**Interface**: Implement `DatabaseAdapter` (or `SQLAdapter` for SQL databases)

**Example**:
```python
# my_plugin/db_clickhouse.py
from queryclaw.db.base import SQLAdapter, QueryResult

class ClickHouseAdapter(SQLAdapter):
    @property
    def db_type(self) -> str:
        return "clickhouse"
    # ... implement connect, execute, get_tables, etc.
```

**Registration** (via entry point):
```toml
# pyproject.toml
[project.entry-points."queryclaw.db.adapters"]
clickhouse = "my_plugin.db_clickhouse:ClickHouseAdapter"
```

**Config**:
```json
{
  "database": {
    "type": "clickhouse",
    "host": "localhost",
    "port": 9000
  }
}
```

---

### 3.2 Tool Plugin

**Extension point**: `queryclaw.tools`

**Interface**: Implement `Tool` base class (name, description, parameters, execute)

**Example**:
```python
# my_plugin/tools/export_csv.py
from queryclaw.tools.base import Tool

class ExportCSVTool(Tool):
    @property
    def name(self) -> str:
        return "export_csv"
    @property
    def description(self) -> str:
        return "Export query results to CSV file."
    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"sql": {...}, "path": {...}}}
    async def execute(self, sql: str, path: str, **kwargs) -> str:
        # ...
```

**Registration**:
```toml
[project.entry-points."queryclaw.tools"]
export_csv = "my_plugin.tools.export_csv:ExportCSVTool"
```

**Tool factory**: Tools may need `db`, `policy`, `audit` injected. The plugin system can support:
- **Class registration**: Plugin registers a class; QueryClaw instantiates with injected deps
- **Factory registration**: Plugin registers a factory `(db, policy, ...) -> Tool`

**Example factory**:
```python
def create_export_csv_tool(db, policy, audit=None):
    return ExportCSVTool(db=db)
```

---

### 3.3 Skill Plugin

**Extension point**: `queryclaw.skills.paths`

**Interface**: Directory path containing `SKILL.md` files (same format as built-in skills)

**Example**:
```
my_plugin/
  skills/
    custom_export/
      SKILL.md
    data_quality_report/
      SKILL.md
```

**Registration**:
```toml
[project.entry-points."queryclaw.skills.paths"]
my_plugin = "my_plugin.skills"
```

Or via config:
```json
{
  "skills": {
    "extra_paths": ["/path/to/my/skills", "my_plugin.skills"]
  }
}
```

**SkillsLoader** would merge built-in paths + plugin paths when loading.

---

### 3.4 Channel Plugin

**Extension point**: `queryclaw.channels`

**Interface**: Implement `Channel` interface (connect, send, receive, disconnect)

**Example**:
```python
# my_plugin/channels/telegram.py
from queryclaw.channels.base import Channel

class TelegramChannel(Channel):
    ...
```

**Registration**:
```toml
[project.entry-points."queryclaw.channels"]
telegram = "my_plugin.channels.telegram:TelegramChannel"
```

**Config**:
```json
{
  "serve": {
    "channel": "telegram",
    "telegram": {
      "bot_token": "...",
      "allowed_chat_ids": [...]
    }
  }
}
```

---

### 3.5 LLM Provider Plugin

**Extension point**: `queryclaw.providers`

**Interface**: Implement `LLMProvider` (chat, get_default_model)

**Use case**: Custom API wrappers, local model servers, A/B testing layers.

**Registration**:
```toml
[project.entry-points."queryclaw.providers"]
custom_provider = "my_plugin.providers.custom:CustomProvider"
```

---

### 3.6 Safety Hook Plugin

**Extension point**: `queryclaw.safety.hooks`

**Interface**: Callbacks invoked at specific points in the safety pipeline

**Example hooks**:
- `before_validate(sql, context)` → return modified SQL or raise to block
- `after_audit(entry, result)` → custom logging, metrics
- `rate_limit(operation, session)` → throttle by session

**Registration**:
```toml
[project.entry-points."queryclaw.safety.hooks"]
my_hooks = "my_plugin.safety:MySafetyHooks"
```

---

## 4. Discovery & Loading

### 4.1 Entry Points (Primary)

Use `importlib.metadata.entry_points()` (Python 3.10+) to discover plugins:

```python
def load_plugins():
    eps = entry_points(group="queryclaw.db.adapters")
    for ep in eps:
        adapter_cls = ep.load()
        AdapterRegistry.register(ep.name, adapter_cls)
```

### 4.2 Config-based Override

`config.json` can explicitly enable/disable plugins:

```json
{
  "plugins": {
    "enabled": ["clickhouse", "export_csv", "telegram"],
    "disabled": ["experimental_feature"],
    "paths": ["/opt/queryclaw-plugins"]
  }
}
```

### 4.3 Load Order

1. Built-in components (always loaded)
2. Entry point plugins (from installed packages)
3. Path plugins (from `plugins.paths`)
4. Config can disable any of the above

---

## 5. Lifecycle

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Discover  │ ──► │   Validate   │ ──► │   Load      │
│  (entry pts)│     │  (version,   │     │  (register  │
│             │     │   deps)      │     │   in reg.)  │
└─────────────┘     └──────────────┘     └─────────────┘
                                 │
                                 ▼
                    ┌──────────────┐     ┌─────────────┐
                    │   Activate   │ ──► │   Unload    │
                    │  (on serve/  │     │  (optional) │
                    │   chat start)│     │             │
                    └──────────────┘     └─────────────┘
```

**Validate**: Check `queryclaw_version` in plugin metadata (e.g., `>=0.5.0,<0.7`).

---

## 6. Plugin Metadata

Each plugin package can declare:

```toml
# pyproject.toml
[project]
name = "queryclaw-clickhouse"
version = "0.1.0"
dependencies = ["queryclaw>=0.5.0,<0.7"]

[project.entry-points."queryclaw.db.adapters"]
clickhouse = "queryclaw_clickhouse:ClickHouseAdapter"
```

Optional metadata (e.g., in a `queryclaw_plugin.json` or `MANIFEST`):

```json
{
  "id": "queryclaw-clickhouse",
  "name": "ClickHouse Adapter",
  "description": "Connect QueryClaw to ClickHouse",
  "queryclaw_version": ">=0.5.0,<0.7",
  "author": "...",
  "license": "MIT"
}
```

---

## 7. Security & Sandboxing

| Concern | Approach |
|---------|----------|
| **Malicious plugins** | Plugins run in same process; trust model: install from trusted sources (PyPI, internal). No sandbox by default. |
| **Plugin errors** | Wrap plugin execution in try/except; log and continue. Optionally disable plugin after N failures. |
| **Resource limits** | Optional: timeout per tool execution; memory limits (advanced). |
| **Sensitive data** | Plugins receive only what QueryClaw passes (db, config). No raw env access unless plugin explicitly reads it. |

**Future**: Optional sandbox (e.g., subprocess, restricted execution) for untrusted plugins — not in initial design.

---

## 8. Implementation Phases

### Phase 5a: Adapter & Tool Plugins (MVP)

- Add `PluginLoader` that discovers entry points
- Extend `AdapterRegistry` to accept plugin-registered adapters
- Extend `ToolRegistry` to accept plugin-registered tools (with factory support)
- Config: `plugins.enabled`, `plugins.disabled`
- CLI: `queryclaw plugins list` to show loaded plugins

### Phase 5b: Skill & Channel Plugins

- Extend `SkillsLoader` to include plugin skill paths
- Channel registry + plugin channel loading
- Config: `serve.channel` can be plugin name

### Phase 5c: Provider & Safety Hooks

- Provider plugin support
- Safety hook interface and invocation points
- Documentation for plugin authors

---

## 9. Example: Full Plugin Package

```
queryclaw-clickhouse/
├── pyproject.toml
├── src/
│   └── queryclaw_clickhouse/
│       ├── __init__.py
│       ├── adapter.py      # ClickHouseAdapter
│       └── queryclaw_plugin.json
└── README.md
```

**pyproject.toml**:
```toml
[project]
name = "queryclaw-clickhouse"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["queryclaw>=0.5.0", "clickhouse-connect"]

[project.entry-points."queryclaw.db.adapters"]
clickhouse = "queryclaw_clickhouse.adapter:ClickHouseAdapter"
```

**Usage**:
```bash
pip install queryclaw queryclaw-clickhouse
# config.json: database.type = "clickhouse"
```

---

## 10. Comparison with Alternatives

| Approach | Pros | Cons |
|----------|------|------|
| **Entry points** | Standard, discoverable, no config for discovery | Requires package install |
| **MCP servers** | External process, language-agnostic | Heavier; separate protocol |
| **Config-only (paths)** | Simple, no code | Manual path management |
| **Plugin marketplace** | Central discovery | Requires infra |

**Recommendation**: Start with entry points for adapters and tools; add config paths for skills. MCP can later be a way to expose QueryClaw as a tool to other agents, and also to consume external tools as plugins.

---

## 11. References

- [Python Packaging](https://packaging.python.org/) — entry points
- [importlib.metadata.entry_points](https://docs.python.org/3/library/importlib.metadata.html#entry-points)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — for future tool integration
