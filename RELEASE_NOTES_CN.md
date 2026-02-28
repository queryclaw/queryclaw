# QueryClaw 版本说明

> [English](RELEASE_NOTES.md)

---

## 0.5.11 (2026-02-28)

### 功能

- **定时任务（Cron + Heartbeat）**：支持按固定时间（`at HH:MM`、`every Nm/Nh`、`cron 5-field`）或周期健康检查执行 prompt。结果可广播到飞书/钉钉群或回退到日志。
- **APScheduler 集成**：Cron 使用 `AsyncIOScheduler`；Heartbeat 使用间隔循环。

### 文档

- **用户手册**：Cron、Heartbeat 配置，调度格式，输出路由。
- **设计文档**：[DESIGN_SCHEDULER.md](docs/zh/DESIGN_SCHEDULER.md)（中英双语）。

---

## 0.5.10 (2026-02-28)

### 安全

- **始终拦截密码相关 SQL**：`ALTER USER`、`SET PASSWORD`、`CREATE USER`、`IDENTIFIED BY`、`GRANT` 现已在 validator 中**始终**拦截，不受用户 `blocked_patterns` 配置覆盖。即使配置覆盖默认值，也能防止密码修改类攻击。

---

## 0.5.9 (2026-02-26)

### 功能

- **外网访问**：配置中 `external_access.enabled` 为 true 时，可选启用 `web_fetch`、`api_call` 工具。可抓取网页、调用 REST API、用外部数据丰富数据库记录。
- **SSRF 防护**：`ExternalAccessPolicy` 拦截 localhost、私有 IP、`file://`、`ftp://`。超时与响应大小限制。

### 文档

- **README**：更新工具数量、外网访问说明、路线图。
- **用户手册**：新增 `external_access` 配置项、`web_fetch` 与 `api_call` 工具说明。

---

## 0.5.8 (2026-02-28)

### 安全

- **隐私脱敏**：禁止泄露数据库密码、本机 IP 及凭证。工具结果、错误信息和 Agent 回复在到达用户或 LLM 前均会脱敏。
- **禁止 SQL**：默认拦截 `ALTER USER`、`SET PASSWORD`、`CREATE USER`、`IDENTIFIED BY`、`GRANT`，防止修改密码。
- **敏感列**：查询结果中 `password`、`pwd`、`secret`、`api_key` 等列的值会被替换为 `[REDACTED]`。

### 文档

- **外网访问设计**：新增 [DESIGN_EXTERNAL_ACCESS.md](docs/DESIGN_EXTERNAL_ACCESS.md)（中英双语），用于 web_fetch/api_call 工具设计（v0.5.9 已实现）。

---

## 0.5.7 (2026-02-28)

### 功能

- **钉钉群聊支持**：钉钉通道现自动识别会话类型（`conversationType`），群聊使用 `/v1.0/robot/groupMessages/send`，单聊使用 `/v1.0/robot/oToMessages/batchSend`。修复在群聊场景下的 `chatbotId.notAllow.sendOTO` 错误。

---

## 0.5.6 (2026-02-28)

### 优化

- **强化 schema_inspect 约束**：系统提示词现明确声明列详情未在 prompt 中提供，LLM 在编写任何查询或 DDL 前必须调用 `schema_inspect`。防止 v0.5.4 schema 精简后出现的列名猜测错误。

---

## 0.5.5 (2026-02-28)

### 优化

- **Agent Loop 消息压缩**：旧的 tool result（如 `read_skill` 返回的 SKILL.md 全文）在后续 LLM 迭代中自动截断，避免每轮重复发送约 1000 tokens 的内容。
- **历史回复截断**：过长的 assistant 回复（>800 字符）在存入对话记忆时自动截断，减少未来 prompt 的 token 消耗。
- **SELECT 约束提示**：在交互指引和 `data_detective` 技能中添加 `query_execute` 仅支持 SELECT 的明确提示，减少因无效 SQL 导致的浪费轮次。

---

## 0.5.4 (2026-02-28)

### 优化

- **Token 优化**：系统提示词中的 Schema 部分改为仅列出表名和行数，不再包含完整列定义（每次 LLM 调用节省约 3000 tokens）。LLM 按需通过 `schema_inspect` 获取列详情。
- **过滤内部表**：`_queryclaw_audit_log` 等内部表不再出现在 Schema 摘要中。
- **精简交互指引**：将 4 个子节合并为 8 条精炼准则，去除与 Skills 模块的重复内容（节省约 350 tokens）。

---

## 0.5.3 (2026-02-28)

### 修复

- **Debug 模式**：`queryclaw chat --debug` 现会完整打印 LLM prompt，不再截断（此前每条消息截断为 800 字符）。系统提示词全文（含完整 Database Schema）现均会输出到日志。

---

## 0.5.2 (2026-02-28)

### 变更

- **系统提示词优化**：完善 Agent 身份与交互指引。身份部分现包含数据库类型、工具列表及说明（schema_inspect、query_execute、explain_plan、read_skill、data_modify、ddl_execute、transaction、spawn_subagent），以及写模式下的安全管线说明。指引拆分为「响应风格」「工作流」「技能」「完整性」，并补充结果格式、必须通过 read_skill 加载技能、修改前确认范围等说明。

---

## 0.5.1 (2026-02-28)

### 功能

- **Chat 调试模式**：`queryclaw chat --debug`（或 `-d`）将每次发送给 LLM 的 prompt 打印到终端，便于调试系统提示、工具调用和对话上下文。

### 变更

- `queryclaw/agent/loop.py`：`_run_agent_loop` 新增 `log_prompt`；`chat(debug=...)` 控制是否打印。
- `queryclaw/cli/commands.py`：`chat` 命令新增 `--debug` / `-d` 选项。

---

## 0.5.0 (2026-02-27)

### 变更

- 版本升级至 0.5.0。

---

## 0.4.12 (2026-02-27)

### 功能

- **审计前后快照**：审计表 `_queryclaw_audit_log` 现会填充 `before_snapshot` 和 `after_snapshot`。UPDATE：before = 修改前行，after = 修改后行。DELETE：before = 被删行，after = 空。INSERT：before = 空，after = 插入值（从 VALUES 解析）。快照为 JSON，最多 100 行、约 50KB。

### 修复

- **SeekDB 审计兼容**：SeekDB（OceanBase）使用 MySQL 协议，此前误用 SQLite DDL/占位符，导致 `AUTOINCREMENT` 语法错误及「not all arguments converted」。现 SeekDB 使用 MySQL 风格 DDL 和 `%s` 占位符。
- **SeekDB dialect 映射**：`data_modify` 与 `ddl_execute` 现把 SeekDB 映射为 MySQL dialect 供 sqlglot 解析。

### 变更

- `queryclaw/safety/snapshot.py`：新增 SnapshotHelper 用于前后行快照采集。
- `queryclaw/safety/audit.py`：将 `seekdb` 按 `mysql` 处理建表与 INSERT。
- `queryclaw/tools/modify.py`：集成 SnapshotHelper；seekdb → mysql dialect 映射。
- `queryclaw/tools/ddl.py`：seekdb → mysql dialect 映射。
- 测试：`test_audit_snapshots_populated` 验证 UPDATE/DELETE/INSERT 快照。

---

## 0.4.11 (2026-02-26)

### 功能

- **SeekDB 适配器**：新增 SeekDB（OceanBase AI 原生搜索数据库）适配器。使用 MySQL 协议，默认端口 2881。支持 VECTOR 类型、l2_distance、cosine_distance、AI_EMBED。
- **SeekDB 向量搜索技能**：新增 `seekdb_vector_search` 技能，用于 SeekDB 中的向量搜索、语义搜索、AI_EMBED 和混合搜索工作流。

### 变更

- `queryclaw/db/seekdb.py`：SeekDBAdapter 继承 MySQLAdapter。
- `queryclaw/skills/seekdb_vector_search/SKILL.md`：向量搜索工作流说明。
- `queryclaw/db/registry.py`：注册 `seekdb` 适配器。
- `queryclaw/config/schema.py`：在 DatabaseConfig.type 中新增 `seekdb`。
- README、USER_MANUAL、PLAN_ARCHITECTURE、SKILLS_ROADMAP：更新（中英）以包含 SeekDB。
- 测试：新增 SeekDB 适配器测试（无 SeekDB 实例时跳过集成测试）。

---

## 0.4.10 (2026-02-27)

### 变更

- **USER_MANUAL 精简**：将通道对接（飞书、钉钉）和 Skills 的详细内容移至独立文档。新增 FEISHU_SETUP、DINGTALK_SETUP；Skills 部分现链接至 SKILLS_ROADMAP。
- **通道确认说明**：更新 serve 模式描述 — 破坏性操作现会发起确认提示（回复确认/取消），而非直接拒绝。
- **相关文档**：新增飞书、钉钉对接指南链接。

---

## 0.4.9 (2026-02-27)

### 修复

- **Skills 未包含在 pip 包中**：`queryclaw/skills/` 目录（6 个内置 SKILL.md）在通过 PyPI 安装时未被包含。已添加 `[tool.setuptools.package-data]`，现所有 Skills 均会打包。用户执行 `pip install queryclaw` 后将获得 data_analysis、test_data_factory、ai_column、data_detective、query_translator、schema_documenter。

---

## 0.4.8 (2026-02-26)

### 功能

- **`read_skill` 工具**：Agent 现可按需加载 Skill 工作流说明。当用户请求与某 Skill 匹配（如生成测试数据 → test_data_factory）时，Agent 会先调用 `read_skill(skill_name)` 获取完整 SKILL.md 内容，再按工作流执行。
- **Skills 系统提示修复**：将无效的「read with read_file」提示改为「call read_skill(skill_name='...') when relevant」，Agent 现可正确访问 Skills。

### 变更

- `tools/read_skill.py`：新增 ReadSkillTool；从 SkillsLoader 读取并返回去除 frontmatter 的 SKILL.md 内容。
- `agent/skills.py`：`build_skills_summary()` 现提示调用 read_skill 而非 read_file。
- `agent/context.py`：更新 identity 引导语，指导 Agent 在遵循 Skill 工作流前先调用 read_skill。
- `agent/loop.py`：注册 ReadSkillTool（始终注册，无安全策略依赖）。
- 设计文档：DESIGN_READ_SKILL_TOOL、FIX_SKILLS_INJECTION。

---

## 0.4.7 (2026-02-26)

### 功能

- **通道模式确认流程**：当 `require_confirmation=True` 时，飞书/钉钉中的破坏性操作（INSERT/UPDATE/DELETE/DDL）现会向用户发起确认提示，而非直接拒绝。用户在聊天中回复「确认」或「取消」以执行或中止。
- **ConfirmationStore**：按会话跟踪待确认项；含确认/取消关键词的入站消息会在到达 Agent 前解析并完成对应 Future。
- **测试**：在 `test_bus_channels.py` 中新增 `TestChannelConfirmation`，覆盖拦截、关键词解析及取消逻辑。

### 变更

- `MessageBus`：新增 `register_confirmation`、`cancel_confirmation`；`publish_inbound` 会拦截有待确认会话的确认/取消回复。
- `AgentLoop`：处理消息时设置 `_current_msg`，供通道回调获取会话上下文。
- `cli/commands.py`：`_channel_confirm_callback` 通过 outbound 发送确认提示，并等待用户回复（300 秒超时）。

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

- 阶段四计划文档：[PLAN_PHASE4_CHANNELS_CN.md](docs/zh/PLAN_PHASE4_CHANNELS.md)。
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
