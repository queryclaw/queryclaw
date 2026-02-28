# QueryClaw Release Notes

> [中文版](RELEASE_NOTES_CN.md)

---

## 0.5.5 (2026-02-28)

### Improvements

- **Message compaction in agent loop**: Old tool results (e.g. SKILL.md content from `read_skill`) are automatically truncated in subsequent LLM iterations, preventing the same ~1000-token payload from being re-sent on every call.
- **Memory truncation**: Long assistant responses (>800 chars) are truncated when stored in conversation history, keeping future prompts lean.
- **SELECT-only constraint**: Added explicit `query_execute` SELECT-only reminders in interaction guidelines and the `data_detective` skill to reduce wasted LLM calls from invalid SQL attempts.

---

## 0.5.4 (2026-02-28)

### Improvements

- **Token optimization**: System prompt schema section now lists only table names and row counts instead of full column definitions (~3000 tokens saved per LLM call). The LLM uses `schema_inspect` on demand for column details.
- **Filter internal tables**: `_queryclaw_audit_log` and other internal tables are excluded from the schema summary.
- **Compact guidelines**: Interaction guidelines condensed from 4 subsections to 8 concise rules, removing redundancy with the Skills section (~350 tokens saved).

---

## 0.5.3 (2026-02-28)

### Fixes

- **Debug mode**: `queryclaw chat --debug` now prints the full LLM prompt without truncation (previously each message was cut at 800 characters). The complete system prompt, including the full Database Schema section, is now visible in the log.

---

## 0.5.2 (2026-02-28)

### Changes

- **System prompt improvements**: Refined agent identity and guidelines. Identity now includes database type, explicit tool list with descriptions (schema_inspect, query_execute, explain_plan, read_skill, data_modify, ddl_execute, transaction, spawn_subagent), and a clear safety pipeline for write mode. Guidelines reorganized into Response Style, Workflow, Skills, and Integrity; added instructions for formatting results, always loading skills via read_skill, and confirming scope before modifications.

---

## 0.5.1 (2026-02-28)

### Features

- **Chat debug mode**: `queryclaw chat --debug` (or `-d`) prints each LLM prompt to the console for debugging. Useful for inspecting system prompts, tool calls, and conversation context.

### Changes

- `queryclaw/agent/loop.py`: Add `log_prompt` to `_run_agent_loop`; `chat(debug=...)` controls it.
- `queryclaw/cli/commands.py`: Add `--debug` / `-d` option to `chat` command.

---

## 0.5.0 (2026-02-27)

### Changes

- Version bump to 0.5.0.

---

## 0.4.12 (2026-02-27)

### Features

- **Audit before/after snapshots**: The audit table (`_queryclaw_audit_log`) now populates `before_snapshot` and `after_snapshot` for data modifications. For UPDATE: before = old row data, after = new row data. For DELETE: before = deleted rows, after = empty. For INSERT: before = empty, after = inserted values (parsed from VALUES clause). Snapshots are JSON, limited to 100 rows and ~50KB.

### Fixes

- **SeekDB audit compatibility**: SeekDB (OceanBase) uses MySQL protocol but previously fell through to SQLite DDL/placeholders, causing `AUTOINCREMENT` syntax error and "not all arguments converted" in audit. Now SeekDB uses MySQL-style DDL and `%s` placeholders.
- **SeekDB dialect mapping**: `data_modify` and `ddl_execute` now map SeekDB to MySQL dialect for sqlglot parsing (SeekDB is not a sqlglot dialect).

### Changes

- `queryclaw/safety/snapshot.py`: New SnapshotHelper for before/after row capture.
- `queryclaw/safety/audit.py`: Treat `seekdb` like `mysql` for table creation and INSERT.
- `queryclaw/tools/modify.py`: Integrate SnapshotHelper; map seekdb → mysql dialect.
- `queryclaw/tools/ddl.py`: Map seekdb → mysql dialect.
- Tests: `test_audit_snapshots_populated` for UPDATE/DELETE/INSERT snapshot verification.

---

## 0.4.11 (2026-02-26)

### Features

- **SeekDB adapter**: New database adapter for SeekDB (OceanBase AI-native search database). Uses MySQL protocol, default port 2881. Supports VECTOR type, l2_distance, cosine_distance, AI_EMBED.
- **SeekDB Vector Search skill**: New skill `seekdb_vector_search` for vector search, semantic search, AI_EMBED, and hybrid search workflows in SeekDB.

### Changes

- `queryclaw/db/seekdb.py`: SeekDBAdapter extends MySQLAdapter.
- `queryclaw/skills/seekdb_vector_search/SKILL.md`: Vector search workflow documentation.
- `queryclaw/db/registry.py`: Registered `seekdb` adapter.
- `queryclaw/config/schema.py`: Added `seekdb` to DatabaseConfig.type.
- README, USER_MANUAL, PLAN_ARCHITECTURE, SKILLS_ROADMAP: Updated (EN + ZH) with SeekDB.
- Tests: Added SeekDB adapter tests (integration tests skip when no SeekDB instance).

---

## 0.4.10 (2026-02-27)

### Changes

- **USER_MANUAL simplification**: Moved detailed channel setup (Feishu, DingTalk) and Skills content to separate docs. Added FEISHU_SETUP, DINGTALK_SETUP; Skills section now links to SKILLS_ROADMAP.
- **Channel confirmation note**: Updated serve mode description — destructive ops now prompt for confirmation (reply 确认/取消) instead of being rejected.
- **See Also**: Added links to Feishu and DingTalk setup guides.

---

## 0.4.9 (2026-02-27)

### Fixes

- **Skills not included in pip package**: The `queryclaw/skills/` directory (6 built-in SKILL.md files) was not included when installing from PyPI. Added `[tool.setuptools.package-data]` so all skills are now bundled. Users who `pip install queryclaw` will get data_analysis, test_data_factory, ai_column, data_detective, query_translator, schema_documenter.

---

## 0.4.8 (2026-02-26)

### Features

- **`read_skill` tool**: Agent can now load Skill workflow instructions on demand. When the user's request matches a skill (e.g. generate test data → test_data_factory), the agent calls `read_skill(skill_name)` to load the full SKILL.md content before following the workflow.
- **Skills system prompt fix**: Replaced the broken "read with read_file" instruction with "call read_skill(skill_name='...') when relevant". The agent now has a working path to access Skills.

### Changes

- `tools/read_skill.py`: New ReadSkillTool; reads from SkillsLoader, returns stripped SKILL.md content.
- `agent/skills.py`: `build_skills_summary()` now instructs to call read_skill instead of read_file.
- `agent/context.py`: Identity guideline updated to direct agent to call read_skill before following skill workflows.
- `agent/loop.py`: Register ReadSkillTool (always, no safety dependency).
- Design docs: DESIGN_READ_SKILL_TOOL, FIX_SKILLS_INJECTION.

---

## 0.4.7 (2026-02-26)

### Features

- **Channel-mode confirmation flow**: When `require_confirmation=True`, destructive operations (INSERT/UPDATE/DELETE/DDL) in Feishu/DingTalk now prompt for user confirmation instead of being rejected. Users reply "确认" or "取消" in the chat to proceed or abort.
- **ConfirmationStore**: Tracks pending confirmations per session; inbound messages with confirm/cancel keywords resolve the pending future before reaching the agent.
- **Tests**: Added `TestChannelConfirmation` in `test_bus_channels.py` for intercept, keyword parsing, and cancel behavior.

### Changes

- `MessageBus`: Added `register_confirmation`, `cancel_confirmation`; `publish_inbound` intercepts confirm/cancel replies for pending sessions.
- `AgentLoop`: Sets `_current_msg` during processing for channel callback to access session context.
- `cli/commands.py`: `_channel_confirm_callback` sends confirmation prompt via outbound and awaits user reply (300s timeout).

---

## 0.4.6 (2026-02-27)

### Changes

- **Removed `queryclaw feishu-test`**: The CLI command was removed. Use `queryclaw serve` to establish the Feishu WebSocket connection before saving event subscription in the Feishu console.
- USER_MANUAL_CN: Updated event subscription and troubleshooting steps to remove feishu-test references.

---

## 0.4.5 (2026-02-27)

### Changes

- **Agent identity**: Reworked system prompt to reflect all capabilities — schema inspection, query execution, EXPLAIN, subagent delegation, and (when read_only=false) data modification, DDL, transactions. Capabilities list is now dynamic based on read_only and enable_subagent.
- **ContextBuilder**: Added read_only and enable_subagent parameters; identity guidelines adapt to available tools.

---

## 0.4.4 (2026-02-27)

### Fixes

- **MySQL/OceanBase UTF-8 decode error**: Improved handling of `'utf-8' codec can't decode byte ... unexpected end of data`. On `UnicodeDecodeError`, connection is closed, a short delay is applied before reconnect, and retry uses a fresh connection.
- **MySQL long SQL**: Set `max_allowed_packet=67108864` (64MB) on connect to support bulk UPDATE with large Chinese text.
- **MySQL connection cleanup**: Added `_close_conn()` for consistent connection teardown on errors; prevents reusing corrupted connections.

### Changes

- USER_MANUAL, USER_MANUAL_CN: Updated version references from 0.3.x to 0.4.x.

---

## 0.4.3 (2026-02-27)

### Features

- **`queryclaw feishu-test`**: New CLI command to test Feishu WebSocket connection without running the full serve stack.

### Changes

- USER_MANUAL_CN: Added "serve 收不到消息" troubleshooting (WebSocket connection check, event subscription save order, im.message.receive_v1).
- USER_MANUAL_CN: Clarified event subscription steps: add `im.message.receive_v1` in "添加事件" and save while connection is live.

---

## 0.4.2 (2026-02-27)

### Changes

- USER_MANUAL: Added detailed Feishu "add bot" steps (group + private chat), private chat troubleshooting, `im:message.p2p_chat` permission.
- Feishu channel: Added debug logging (`[Feishu]` prefix) to trace message flow when private chat has no reply.

---

## 0.4.1 (2026-02-27)

### Fixes

- **Feishu WebSocket event loop**: Fixed "This event loop is already running" when running `queryclaw serve`. The lark-oapi WebSocket client now uses a dedicated event loop in its thread instead of the main thread's loop.

### Changes

- USER_MANUAL: Added Feishu channel setup guide (EN/CN).
- DESIGN_CHANNEL_CONFIRMATION: Technical design for interactive confirmation in channel mode.

---

## 0.4.0 (2026-02-26)

### Features

- **Phase 4 Multi-Channel Output**: Message bus + bidirectional channels (Feishu, DingTalk).
- **`queryclaw serve`**: Run the agent in channel mode; receive questions from Feishu/DingTalk and reply in-app.
- **Optional dependencies**: `pip install queryclaw[feishu]` and `pip install queryclaw[dingtalk]`.
- **Channel safety**: Destructive operations are rejected in channel mode when `require_confirmation=True`.

### Changes

- Phase 4 plan docs: [PLAN_PHASE4_CHANNELS.md](docs/PLAN_PHASE4_CHANNELS.md).
- README, USER_MANUAL, PLAN_ARCHITECTURE updated for multi-channel.

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
