# QueryClaw 版本说明

> [English](RELEASE_NOTES.md)

---

## 0.4.6 (2026-02-27)

### 变更

- **移除 `queryclaw feishu-test`**：该 CLI 命令已删除。请在飞书开放平台保存事件订阅前，先运行 `queryclaw serve` 建立连接。
- USER_MANUAL_CN：更新事件订阅与排查步骤，移除 feishu-test 相关说明。

---

## 0.4.5 (2026-02-27)

### 变更

- **Agent identity**：重写 system prompt，完整反映能力 — 结构查看、查询执行、EXPLAIN、子代理委派，以及（read_only=false 时）数据修改、DDL、事务。能力列表根据 read_only 和 enable_subagent 动态生成。
- **ContextBuilder**：新增 read_only、enable_subagent 参数；identity 规则随可用工具自适应。

---

## 0.4.4 (2026-02-27)

### 修复

- **MySQL/OceanBase UTF-8 解码错误**：改进对 `'utf-8' codec can't decode byte ... unexpected end of data` 的处理。发生 `UnicodeDecodeError` 时关闭连接、短暂延迟后重连，重试使用新连接。
- **MySQL 长 SQL**：连接时设置 `max_allowed_packet=67108864`（64MB），支持含大量中文的 bulk UPDATE。
- **MySQL 连接清理**：新增 `_close_conn()`，错误时统一关闭连接，避免复用损坏连接。

### 变更

- USER_MANUAL、USER_MANUAL_CN：版本引用从 0.3.x 更新为 0.4.x。

---

## 0.4.3 (2026-02-27)

### 功能

- **`queryclaw feishu-test`**：新增 CLI 命令，用于单独测试飞书 WebSocket 连接，无需启动完整 serve。

### 变更

- USER_MANUAL_CN：新增「serve 端收不到消息」排查（WebSocket 连接检查、事件订阅保存顺序、im.message.receive_v1）。
- USER_MANUAL_CN：明确事件订阅步骤：在「添加事件」中勾选 `im.message.receive_v1`，并在连接在线时保存。

---

## 0.4.2 (2026-02-27)

### 变更

- USER_MANUAL：补充飞书「添加机器人」步骤（群聊 + 私聊）、私聊无回复排查、`im:message.p2p_chat` 权限说明。
- 飞书通道：增加调试日志（`[Feishu]` 前缀），便于排查私聊无回复问题。

---

## 0.4.1 (2026-02-27)

### 修复

- **飞书 WebSocket 事件循环**：修复 `queryclaw serve` 运行时「This event loop is already running」错误。lark-oapi WebSocket 客户端现使用其线程内独立的事件循环，而非主线程的 loop。

### 变更

- USER_MANUAL：新增飞书通道对接指南（中英文）。
- DESIGN_CHANNEL_CONFIRMATION：通道模式交互式确认的技术方案。

---

## 0.4.0 (2026-02-26)

### 功能

- **阶段四多通道输出**：消息总线 + 双向通道（飞书、钉钉）。
- **`queryclaw serve`**：通道模式下运行 Agent；在飞书/钉钉中接收提问并回复。
- **可选依赖**：`pip install queryclaw[feishu]` 与 `pip install queryclaw[dingtalk]`。
- **通道安全**：通道模式下，当 `require_confirmation=True` 时拒绝破坏性操作。

### 变更

- 阶段四计划文档：[PLAN_PHASE4_CHANNELS_CN.md](docs/PLAN_PHASE4_CHANNELS_CN.md)。
- README、USER_MANUAL、PLAN_ARCHITECTURE 已更新以支持多通道。

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
