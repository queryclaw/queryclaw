# QueryClaw User Manual

> [中文版](zh/USER_MANUAL.md)

**Version 0.4.x** — Database agent with write operations, safety layer, PostgreSQL support, subagent system, and multi-channel output (Feishu, DingTalk)

This manual describes how to install, configure, and use QueryClaw to chat with your database in natural language.

---

## Table of Contents

1. [What is QueryClaw?](#what-is-queryclaw)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Quick Start](#quick-start)
5. [Configuration](#configuration)
6. [Commands Reference](#commands-reference)
7. [Chat Mode](#chat-mode)
8. [Built-in Tools](#built-in-tools)
9. [Skills](#skills)
10. [Troubleshooting](#troubleshooting)

---

## What is QueryClaw?

QueryClaw is an **AI-native database agent** that lets you ask questions about your database in plain language. The agent uses a **ReACT loop** (Reasoning + Acting): it inspects the schema, runs read-only SQL, and explains execution plans — all through natural language.

**Current version (0.4.x)** supports:

- **Databases:** SQLite, MySQL, PostgreSQL  
- **LLM providers:** OpenRouter, Anthropic, OpenAI, DeepSeek, Gemini, DashScope, Moonshot (via [LiteLLM](https://github.com/BerriAI/litellm))  
- **Read tools:** Schema inspection, read-only query execution, EXPLAIN plan, subagent spawning  
- **Write tools:** `data_modify` (INSERT/UPDATE/DELETE), `ddl_execute` (CREATE/ALTER/DROP), `transaction` (BEGIN/COMMIT/ROLLBACK)  
- **Safety layer:** Policy engine, SQL AST validator, dry-run engine, human confirmation, audit logger  
- **Skills:** Data Analysis, Schema Documenter, Query Translator, Data Detective, AI Column, Test Data Factory  
- **CLI:** `onboard` (create config), `chat` (interactive or single-turn), `serve` (multi-channel mode)

---

## Requirements

- **Python** 3.10 or higher  
- **Network** access to your database and to the LLM API you choose  
- **API key** for at least one supported LLM provider  

---

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

For all optional features (PostgreSQL + Feishu + DingTalk):

```bash
pip install queryclaw[all]
```

To install a specific version:

```bash
pip install queryclaw==0.3.0
```

Verify:

```bash
queryclaw --version
```

---

## Quick Start

1. **Create configuration**

   ```bash
   queryclaw onboard
   ```

   This creates `~/.queryclaw/config.json` with default values.

2. **Edit the config**

   Open `~/.queryclaw/config.json` and set:

   - **Database:** For SQLite, set `database.type` to `"sqlite"` and `database.database` to the path of your `.db` file. For MySQL, set `type`, `host`, `port`, `database`, `user`, and `password`.
   - **LLM:** Set `api_key` for at least one provider under `providers` (e.g. `providers.anthropic.api_key` or `providers.openrouter.api_key`).

3. **Start chatting**

   Single question:

   ```bash
   queryclaw chat -m "What tables are in this database?"
   ```

   Interactive session:

   ```bash
   queryclaw chat
   ```

   Type your questions; type `exit` or `quit` to end the session.

---

## Configuration

Configuration is stored in **JSON** at `~/.queryclaw/config.json` by default. You can use a different file with `--config` / `-c`.

### Configuration structure

| Section     | Description |
|------------|-------------|
| `database` | Connection settings for the database QueryClaw will query. |
| `providers` | API keys and optional base URLs for each LLM provider. |
| `agent` | Model name, iteration limit, temperature, and token limit. |
| `safety` | Safety policy: read-only mode, row limits, confirmation rules, audit. |
| `channels` | Multi-channel output: Feishu and DingTalk configuration for `serve` mode. |

### Database

| Field      | Type   | Default    | Description |
|-----------|--------|------------|-------------|
| `type`    | string | `"sqlite"` | `"sqlite"` or `"mysql"`. |
| `host`    | string | `"localhost"` | Server host (MySQL). |
| `port`    | int    | `3306`     | Server port (MySQL). |
| `database`| string | `""`       | DB name (MySQL) or path to file (SQLite, e.g. `"/path/to/app.db"`). |
| `user`    | string | `""`       | Username (MySQL). |
| `password`| string | `""`       | Password (MySQL). |

**SQLite example:**

```json
"database": {
  "type": "sqlite",
  "database": "/path/to/mydb.db"
}
```

**MySQL example:**

```json
"database": {
  "type": "mysql",
  "host": "localhost",
  "port": 3306,
  "database": "mydb",
  "user": "myuser",
  "password": "mypass"
}
```

### Providers

Set `api_key` for at least one provider. Optional: `api_base`, `extra_headers`.

| Provider   | Config key   | Typical use |
|-----------|---------------|-------------|
| OpenRouter | `providers.openrouter` | Many models via one API; set `api_base` to `https://openrouter.ai/api/v1` if needed. |
| Anthropic  | `providers.anthropic` | Claude models (e.g. `anthropic/claude-sonnet-4-5`). |
| OpenAI     | `providers.openai`    | GPT models. |
| DeepSeek   | `providers.deepseek`  | DeepSeek models. |
| Gemini     | `providers.gemini`    | Google Gemini. |
| DashScope  | `providers.dashscope` | Alibaba Cloud. |
| Moonshot   | `providers.moonshot`  | Moonshot (Kimi). |

**Example (Anthropic):**

```json
"providers": {
  "anthropic": {
    "api_key": "sk-ant-...",
    "api_base": "",
    "extra_headers": {}
  }
}
```

**Example (OpenRouter):**

```json
"providers": {
  "openrouter": {
    "api_key": "sk-or-...",
    "api_base": "https://openrouter.ai/api/v1",
    "extra_headers": {}
  }
}
```

The agent chooses the provider from the **model** name (e.g. `openrouter/...`, `anthropic/...`). You can force a provider with `agent.provider` (see below).

### Agent

| Field            | Type   | Default                          | Description |
|------------------|--------|----------------------------------|-------------|
| `model`         | string | `"anthropic/claude-sonnet-4-5"` | Model identifier (e.g. `openrouter/meta-llama/llama-3.1-70b`, `anthropic/claude-sonnet-4-5`). |
| `provider`      | string | `"auto"`                         | `"auto"` (detect from model) or provider name (e.g. `openrouter`, `anthropic`). |
| `max_iterations`| int    | `30`                             | Max ReACT steps per turn. |
| `temperature`   | float  | `0.1`                            | LLM sampling temperature. |
| `max_tokens`    | int    | `4096`                           | Max tokens per LLM response. |

### Channels

Multi-channel output for `queryclaw serve`. Enable Feishu and/or DingTalk to receive questions and send responses through those apps.

**Feishu:**

| Field               | Type   | Description |
|---------------------|--------|-------------|
| `enabled`           | bool   | Enable Feishu channel. |
| `app_id`            | string | App ID from Feishu Open Platform. |
| `app_secret`        | string | App Secret. |
| `allow_from`        | list   | Allowed user open_ids; empty = allow all. |

**DingTalk:**

| Field               | Type   | Description |
|---------------------|--------|-------------|
| `enabled`           | bool   | Enable DingTalk channel. |
| `client_id`         | string | AppKey from DingTalk. |
| `client_secret`     | string | AppSecret. |
| `allow_from`        | list   | Allowed staff_ids; empty = allow all. |

**Channel setup guides:**

- **Feishu**: See [FEISHU_SETUP.md](FEISHU_SETUP.md)
- **DingTalk**: See [DINGTALK_SETUP.md](DINGTALK_SETUP.md)

**Example:**

```json
"channels": {
  "feishu": {
    "enabled": true,
    "app_id": "cli_xxx",
    "app_secret": "your_secret",
    "allow_from": []
  },
  "dingtalk": {
    "enabled": false,
    "client_id": "",
    "client_secret": "",
    "allow_from": []
  }
}
```

---

## Commands Reference

### Global options

- **`--version`**, **`-v`** — Print version and exit.

### `queryclaw onboard`

Creates or refreshes the configuration file.

```bash
queryclaw onboard [--config PATH] [--overwrite]
```

| Option        | Short | Description |
|---------------|-------|-------------|
| `--config`   | `-c`  | Config file path (default: `~/.queryclaw/config.json`). |
| `--overwrite`|       | Replace existing config with defaults (otherwise only missing fields are added). |

- Without `--overwrite`: if the file exists, it is loaded and saved again (missing fields get defaults).  
- With `--overwrite`: the file is replaced by the default config.

### `queryclaw chat`

Starts a chat session with the database agent.

```bash
queryclaw chat [-m MESSAGE] [--config PATH] [--no-markdown]
```

| Option         | Short | Description |
|----------------|-------|-------------|
| `--message`   | `-m`  | Single question; if omitted, interactive mode starts. |
| `--config`    | `-c`  | Config file path (default: `~/.queryclaw/config.json`). |
| `--no-markdown`|      | Render assistant replies as plain text instead of Markdown. |

**Examples:**

```bash
queryclaw chat -m "List all tables"
queryclaw chat -m "How many rows are in the users table?"
queryclaw chat
queryclaw chat -c /path/to/config.json
```

### `queryclaw serve`

Starts QueryClaw in **multi-channel mode**, listening for messages from Feishu and/or DingTalk. Users can ask questions in those apps and receive Agent responses.

```bash
queryclaw serve [--config PATH]
```

| Option      | Short | Description |
|-------------|-------|-------------|
| `--config`  | `-c`  | Config file path (default: `~/.queryclaw/config.json`). |

**Prerequisites:**

- Enable at least one channel in config (see [Channels](#channels))
- Install channel dependencies: `pip install queryclaw[feishu]` and/or `pip install queryclaw[dingtalk]`

**Note:** In channel mode, when `safety.require_confirmation` is true, destructive operations prompt the user for confirmation (reply "确认" or "取消").

---

## Chat Mode

- **Single-turn:** `queryclaw chat -m "Your question"` — one question, one answer, then exit.  
- **Interactive:** `queryclaw chat` — multiple questions in one session. Conversation history is kept in memory for the session.

**Exiting interactive mode:** Type one of: `exit`, `quit`, `/exit`, `/quit`, `:q` (case-insensitive). Or press **Ctrl+C**.

Output is rendered as **Markdown** by default; use `--no-markdown` for plain text.

---

### Safety

| Field                | Type       | Default                        | Description |
|----------------------|------------|--------------------------------|-------------|
| `read_only`          | bool       | `true`                         | When true, write operations are blocked. |
| `max_affected_rows`  | int        | `1000`                         | Threshold above which confirmation is required. |
| `require_confirmation` | bool     | `true`                         | Require human confirmation for destructive operations. |
| `allowed_tables`     | list/null  | `null`                         | If set, only these tables can be modified. `null` means all. |
| `blocked_patterns`   | list       | `["DROP DATABASE", "DROP SCHEMA"]` | SQL patterns that are always rejected. |
| `audit_enabled`      | bool       | `true`                         | Write all operations to the audit log table. |

**Example:**

```json
"safety": {
  "read_only": true,
  "max_affected_rows": 1000,
  "require_confirmation": true,
  "allowed_tables": null,
  "blocked_patterns": ["DROP DATABASE", "DROP SCHEMA"],
  "audit_enabled": true
}
```

---

## Built-in Tools

The agent uses these tools automatically during the ReACT loop. You do not call them directly.

### Read Tools

| Tool                | Description |
|---------------------|-------------|
| **schema_inspect**  | List tables; describe columns, indexes, and foreign keys for a table. |
| **query_execute**   | Run **read-only** SQL (SELECT only). Results are limited to avoid huge outputs. |
| **explain_plan**    | Show the execution plan (EXPLAIN) for a given SQL query. |
| **spawn_subagent**  | Spawn a focused subagent to handle a specific subtask (e.g. multi-table analysis). |

### Write Tools

Write tools are available when `safety.read_only` is set to `false`. They go through the full safety pipeline (policy check → SQL validation → dry-run → optional human confirmation → transaction wrapping → audit logging).

| Tool                | Description |
|---------------------|-------------|
| **data_modify**     | Execute INSERT, UPDATE, or DELETE with safety checks and impact estimation. |
| **ddl_execute**     | Execute DDL statements (CREATE, ALTER, DROP, TRUNCATE). DROP operations require confirmation. |
| **transaction**     | Explicit transaction control: BEGIN, COMMIT, or ROLLBACK for multi-statement atomic operations. |

The default safety mode is **read-only**. Set `safety.read_only` to `false` to enable write operations.

---

## Skills

Skills guide the agent’s behavior for certain kinds of tasks. The agent loads workflow instructions via the `read_skill` tool.

**Built-in skills:** data_analysis, test_data_factory, ai_column, data_detective, query_translator, schema_documenter. See [Skills Roadmap](SKILLS_ROADMAP.md) for details.

---

## Troubleshooting

### "No LLM API key configured"

- Ensure at least one of `providers.<name>.api_key` is set in `~/.queryclaw/config.json`.  
- Restart `queryclaw chat` after editing the config.

### "Failed to load config" / JSON errors

- Check that `config.json` is valid JSON (commas, quotes, no trailing commas).  
- Run `queryclaw onboard --overwrite` to regenerate a default config, then edit again.

### Database connection errors

- **SQLite:** Ensure `database.database` is the full path to an existing `.db` file and that the process has read permission.  
- **MySQL:** Check `host`, `port`, `database`, `user`, `password`. Ensure the MySQL server allows connections from your host and that the user has SELECT (and schema) privileges.  
- **PostgreSQL:** Check `host`, `port`, `database`, `user`, `password`. Default port is `5432`. Ensure `asyncpg` is installed (`pip install queryclaw[postgresql]`).

### Wrong provider or model

- Set `agent.provider` to the provider name (e.g. `openrouter`, `anthropic`) to force a specific API.  
- Use a model string that matches your provider (e.g. `openrouter/meta-llama/llama-3.1-70b`, `anthropic/claude-sonnet-4-5`).

### Version

- Check installed version: `queryclaw --version`.  
- Upgrade: `pip install -U queryclaw`.

---

## See Also

- [Feishu Setup](FEISHU_SETUP.md) | [DingTalk Setup](DINGTALK_SETUP.md)  
- [Architecture & Implementation Plan](PLAN_ARCHITECTURE.md)  
- [Skills Roadmap](SKILLS_ROADMAP.md)  
- [Phase 1 Plan (Archive)](PLAN_PHASE1_ARCHIVE.md) | [Phase 2 Plan (Archive)](PLAN_PHASE2_ARCHIVE.md)
