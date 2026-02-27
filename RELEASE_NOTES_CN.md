# QueryClaw 版本说明

> [English](RELEASE_NOTES.md)

---

## 0.3.4 (2026-02-27)

### 修复

- **MySQL LIKE `%` 转义**：执行无参数原始 SQL 时，字面量 `%`（如 `LIKE '%关键词%'`）现会转义为 `%%`，避免 aiomysql 驱动报「not enough arguments for format string」错误。
- **MySQL UTF-8 连接**：新增 `use_unicode=True` 与 `init_command="SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci"`，减少处理中文等多字节字符时的 `UnicodeDecodeError: unexpected end of data`。

---

## 0.3.3 (2026-02-27)

### 修复

- **确认拒绝**：用户拒绝确认提示（y/N → N）时，工具返回结果会明确告知 LLM 不要重试同一操作，避免重复弹出确认。

---

## 0.3.2 (2026-02-27)

### 修复

- **审计表 MySQL 兼容**：
  - 移除 `TEXT` 列的 `DEFAULT`（MySQL 5.7+ 严格模式下 TEXT/BLOB 不支持 DEFAULT）。
  - 将 `timestamp` 列重命名为 `logged_at`，避免 MySQL 保留字冲突。
  - 若已有损坏的审计表，请先执行 `DROP TABLE IF EXISTS _queryclaw_audit_log` 再使用写操作。

---

## 0.3.1 (2026-02-27)

### 修复

- **MySQL 自动重连**：连接断开时（如 DDL 错误或网络问题后）自动检测并重连，连接参数会保存以供重连。
- **DataModifyTool**：错误后 `rollback()` 失败时，强制关闭适配器，以便下次使用时自动重连。
- **DDLExecuteTool / DataModifyTool**：审计日志写入包裹在 try-except 中，避免审计失败掩盖真实错误。

---

## 0.3.0 (2026-02-27)

### 功能

- **写入工具**：`data_modify`（INSERT/UPDATE/DELETE）、`ddl_execute`（CREATE/ALTER/DROP）、`transaction`（BEGIN/COMMIT/ROLLBACK）。
- **人机确认**：破坏性操作（DROP、高影响更新）需人工确认。
- **写入技能**：AI 列、测试数据工厂。
- **事务支持**：所有数据库适配器（MySQL、SQLite、PostgreSQL）支持显式事务。

---

## 0.2.0 (2026-02)

### 功能

- **PostgreSQL 适配器**：通过 asyncpg 支持异步。
- **安全层**：策略引擎、SQL AST 校验器（sqlglot）、试跑引擎、审计日志。
- **子代理系统**：`spawn_subagent` 工具用于委派任务。
- **只读技能**：Schema 文档生成、查询翻译器、数据侦探。
- **SafetyConfig**：可在 `config.json` 中配置安全策略。

---

## 0.1.2 (2026-02)

### 修复

- **Moonshot（Kimi）**：在启用「思考」时，为 assistant 消息中的 tool_call 增加 `reasoning_content`，修复 API 报错。

---

## 0.1.1 (2026-02)

### 变更

- 将 Phase 1 计划归档至 docs。
- 新增用户手册（中英文）。
- 新增端到端验证脚本。

---

## 0.1.0 (2026-02)

### 首次发布

- **Phase 1 MVP**：只读数据库 Agent。
- **数据库**：MySQL、SQLite。
- **工具**：`schema_inspect`、`query_execute`、`explain_plan`。
- **LLM**：LiteLLM 集成（OpenRouter、Anthropic、OpenAI、DeepSeek、Gemini 等）。
- **CLI**：`onboard`、`chat`（交互或单轮）。
- **技能**：数据分析（内置）。
- **配置**：基于 Pydantic 的 JSON 配置。
