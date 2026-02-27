# QueryClaw Release Notes

> [中文版](RELEASE_NOTES_CN.md)

---

## 0.3.4 (2026-02-27)

### Fixes

- **MySQL LIKE `%` escape**: When executing raw SQL without parameters, literal `%` characters (e.g. in `LIKE '%keyword%'`) are now escaped to `%%` to prevent "not enough arguments for format string" errors from the aiomysql driver.
- **MySQL UTF-8 connection**: Added `use_unicode=True` and `init_command="SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci"` to reduce `UnicodeDecodeError: unexpected end of data` when handling Chinese and other multi-byte characters.

---

## 0.3.3 (2026-02-27)

### Fixes

- **Confirmation rejection**: When the user declines a confirmation prompt (y/N → N), the tool result now explicitly instructs the LLM not to retry the same operation, preventing repeated confirmation prompts.

---

## 0.3.2 (2026-02-27)

### Fixes

- **Audit table MySQL compatibility**:
  - Removed `DEFAULT` from `TEXT` columns (MySQL 5.7+ strict mode does not allow `DEFAULT` on TEXT/BLOB).
  - Renamed `timestamp` column to `logged_at` for MySQL to avoid reserved word conflicts.
  - If you have an existing broken audit table, run `DROP TABLE IF EXISTS _queryclaw_audit_log` before using write operations.

---

## 0.3.1 (2026-02-27)

### Fixes

- **MySQL auto-reconnect**: Added connection health check and automatic reconnection when the connection is lost (e.g. after DDL errors or network issues). Connection parameters are stored for seamless reconnect.
- **DataModifyTool**: When `rollback()` fails after an error, the adapter is force-closed so it can reconnect on the next use.
- **DDLExecuteTool / DataModifyTool**: Audit logging is wrapped in try-except so audit failures do not mask the real error.

---

## 0.3.0 (2026-02-27)

### Features

- **Write tools**: `data_modify` (INSERT/UPDATE/DELETE), `ddl_execute` (CREATE/ALTER/DROP), `transaction` (BEGIN/COMMIT/ROLLBACK).
- **Human-in-the-loop**: Confirmation prompts for destructive operations (DROP, high-impact updates).
- **Write skills**: AI Column, Test Data Factory.
- **Transaction support**: All database adapters (MySQL, SQLite, PostgreSQL) support explicit transactions.

---

## 0.2.0 (2026-02)

### Features

- **PostgreSQL adapter**: Async support via asyncpg.
- **Safety layer**: Policy engine, SQL AST validator (sqlglot), dry-run engine, audit logger.
- **Subagent system**: `spawn_subagent` tool for delegated tasks.
- **Read-only skills**: Schema Documenter, Query Translator, Data Detective.
- **SafetyConfig**: Configurable safety policy in `config.json`.

---

## 0.1.2 (2026-02)

### Fixes

- **Moonshot (Kimi)**: Added `reasoning_content` to assistant messages with tool calls when "thinking" is enabled, fixing API errors.

---

## 0.1.1 (2026-02)

### Changes

- Archived Phase 1 plan to docs.
- Added User Manual (EN/CN).
- Added E2E verification script.

---

## 0.1.0 (2026-02)

### Initial Release

- **Phase 1 MVP**: Read-only database agent.
- **Databases**: MySQL, SQLite.
- **Tools**: `schema_inspect`, `query_execute`, `explain_plan`.
- **LLM**: LiteLLM integration (OpenRouter, Anthropic, OpenAI, DeepSeek, Gemini, etc.).
- **CLI**: `onboard`, `chat` (interactive and single-turn).
- **Skills**: Data Analysis (built-in).
- **Config**: Pydantic-based JSON configuration.
