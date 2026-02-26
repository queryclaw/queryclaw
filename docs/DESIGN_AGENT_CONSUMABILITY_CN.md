# 供其他 Agent 使用的设计要点

> [English](DESIGN_AGENT_CONSUMABILITY.md)

本文说明要让 **其他 Agent**（如 Cursor、Claude Desktop、编排类 Agent 或自定义 ReACT 循环）能够发现、调用并与 QueryClaw 组合使用，需要在哪些方面做设计。与现有路线图（如 Phase 4 的 MCP）衔接，并给出可落地的设计维度。

---

## 当前状态

| 维度 | 现状 | 对其他 Agent 的影响 |
|------|------|----------------------|
| **入口** | 仅 CLI（`queryclaw chat`、`onboard`） | 其他 Agent 只能通过子进程 + 解析 stdout 使用，无法进程内或 HTTP 调用。 |
| **配置** | 单文件 `~/.queryclaw/config.json` | 每个进程一套 DB + LLM 配置；无法按请求/会话覆盖。 |
| **输出** | 控制台 Markdown/文本 | 无结构化 JSON，难以被工具型调用方消费。 |
| **会话** | 单个 `AgentLoop` 内内存历史 | 无 session_id、无「无状态单轮」API，难以多路复用。 |
| **发现** | 无 | 其他 Agent 无法用标准方式询问「QueryClaw 能做什么」。 |

因此目前其他 Agent 只能通过跑 CLI 并解析输出使用 QueryClaw，既脆弱又难以组合。

---

## 1. 程序化 API（库模式）

**目标：** 其他 Python Agent（或服务）能把 QueryClaw 当库调用，而无需起子进程。

**设计要点：**

- **单轮 API：**  
  `async def chat(config: Config, message: str, *, session_id: str | None = None) -> ChatResult`  
  - 入参：配置（及可选的已构造好的 DB/LLM）、一条用户消息。  
  - 返回结构化 `ChatResult`：`content: str`、`tools_used: list[str]`，可选 `session_id` 以延续会话。

- **配置 / DB 注入：**  
  - 调用方传入 `Config`（或只覆盖 `database` / `providers` / `agent`），同一进程可服务多租户或多库。  
  - 可选：`create_agent_loop(provider, db, **agent_opts)`，便于完全自定义（如自定义工具、技能目录）。

- **与 CLI 解耦：**  
  - 将「加载配置 → 创建 provider → 创建 adapter → 创建 AgentLoop → chat」抽到独立模块（如 `queryclaw.api` 或 `queryclaw.runner`），CLI 与程序化调用共用同一路径。

**产出：**

- 在 `queryclaw.api`（或等价包）中提供公开 API：`chat()`，可选 `create_agent_loop()` 与 `ChatResult` 数据类。  
- 文档与最小示例：「在另一个 Python Agent 中使用 QueryClaw」。

---

## 2. MCP 服务（标准工具暴露）

**目标：** 以 MCP 标准暴露 QueryClaw，使任意 MCP 客户端（Cursor、Claude Desktop 等）能列出并调用其能力为工具。

**设计要点：**

- **MCP 服务进程：**  
  - 新入口，如 `queryclaw serve-mcp` 或 `queryclaw mcp`，启动 MCP 服务（stdio 或 SSE）。  
  - 实现 `tools/list` 与 `tools/call`。  
  - 每个 **工具** 对应 QueryClaw 的一项能力。

- **两种暴露方式（可择一或并存）：**
  - **A. 暴露底层工具：** 将现有工具一一映射为 MCP 工具：`schema_inspect`、`query_execute`、`explain_plan`。调用方自行驱动 ReACT 循环（自己调 LLM、链式调这些工具）。  
  - **B. 暴露一个高层工具：** 一个 MCP 工具，如 `queryclaw_ask(question: str, database_config?: object)`。QueryClaw 内部跑完整 ReACT 循环并返回最终答案，适合「用自然语言问数据库」的简单集成。

- **MCP 配置：**  
  - 默认读取 `~/.queryclaw/config.json` 作为 DB + LLM 配置。  
  - 可选：在协议允许下支持按请求覆盖 `database`（多库场景），或固定若干命名配置。

**产出：**

- MCP 服务实现（至少 stdio 传输）。  
- 工具 schema（名称、描述、参数）与当前工具和/或 `queryclaw_ask` 一致。  
- 简短文档：「通过 MCP 将 Cursor / Claude Desktop 连接到 QueryClaw」。

---

## 3. 工具结果的结构化输出

**目标：** 当 QueryClaw 作为「工具」被其他 Agent 调用时，返回结果应可被机器解析（如表数据为 JSON，而非仅 Markdown）。

**设计要点：**

- **工具返回形态：**  
  - 当前各工具返回字符串。增加可选 **结构化** 模式：如 `QueryResult` 以 JSON `{ "columns": [...], "rows": [...], "summary": "..." }`，`SchemaInspect` 以 `{ "tables": [...] }` 等。  
  - 实现方式：全局选项 `structured_output: bool`，或单独提供「程序化」版工具返回 JSON。

- **Chat 结果：**  
  - 程序化 `ChatResult` 可包含 `structured_artifacts: list[dict]`（如最后一次查询结果、最后一次 schema 片段），便于调用方直接使用，无需解析 Markdown。

**产出：**

- 各内置工具的可选结构化格式（schema + 示例）。  
- `ChatResult`（或等价）中可选结构化字段，用于最近一次工具输出。

---

## 4. 会话与无状态模式

**目标：** 支持「一问一答」（无状态）和「多轮带记忆」（会话）两种被其他 Agent 调用的方式。

**设计要点：**

- **无状态：**  
  - 单次调用，无 session_id、无历史。每次 `chat()` 独立。适合嵌入到其他 Agent 的单次工具调用中。

- **会话（有状态）：**  
  - 调用方传入 `session_id`。服务端（或进程内存储）按 `session_id` 维护对话历史。  
  - 支持「追问」和跨轮次上下文。  
  - 需要会话存储：进程内（单进程）或 Redis/DB（多进程）。

- **作用域：**  
  - 可选：在配置中引入 `session_id` 或 `tenant_id`，使不同调用方拥有隔离的配置/历史。

**产出：**

- `chat(..., session_id=None)` 的语义文档；单进程下的进程内会话存储。  
- 可选：持久化会话存储（如 Redis），用于 Phase 4 服务化。

---

## 5. 发现与 Schema

**目标：** 其他 Agent 能发现 QueryClaw 能做什么，以及每项能力的参数格式。

**设计要点：**

- **MCP：** `tools/list` 返回工具名、描述和参数 JSON Schema，与当前 `Tool.to_schema()` 对齐即可。  
- **程序化：** 对外提供 `get_tool_definitions() -> list[dict]`（及可选的技能列表），便于 Python 调用方自行组装工具列表或 OpenAPI 片段。  
- **文档：** 一份「能力矩阵」（Markdown 或 JSON）：工具列表、参数、示例输入输出、只读/写说明。

**产出：**

- 公开 API 中的 `get_tool_definitions()`（或等价）。  
- 能力矩阵文档或 schema 文件（如 `docs/capabilities.json`）。

---

## 6. 安全与多租户（作为服务被调用时）

**目标：** 当 QueryClaw 被多个 Agent 或用户调用时，身份、限流与作用域需明确。

**设计要点：**

- **身份：**  
  - 每次请求（或 MCP 连接）可携带可选 `caller_id` 或 `api_key`。写入审计日志，用于限流或配置查找。

- **按调用方配置：**  
  - 可选：将 `caller_id` / `api_key` 映射到专属配置（如该调用方允许访问的 DB、只读/写）。  
  - 默认：单一共享配置（与当前行为一致）。

- **限流与超时：**  
  - 单次请求最大迭代次数、最大 token；可选按调用方限流，防止滥用。

- **只读与写：**  
  - Phase 1 为只读；引入写工具后，对外暴露明确的「read_only」模式，便于将外部 Agent 限制在 SELECT + explain。

**产出：**

- 文档说明：单租户（当前）与可选多租户（配置 + 身份）行为。  
- 实现 MCP 或 HTTP 服务时：可选 `caller_id`、超时与 `read_only` 标志。

---

## 7. 可选：HTTP API

**目标：** 非 Python Agent 或远程调用方在不使用 MCP 或子进程的情况下调用 QueryClaw。

**设计要点：**

- **REST 或 SSE：**  
  - `POST /chat`，body：`{ "message": "...", "session_id": "...", "config_overrides": {} }`，返回 `{ "content": "...", "tools_used": [...], "structured_artifacts": [...] }`。  
  - 可选：若后续支持流式输出，可增加 SSE。

- **鉴权：**  
  - API Key 或 Bearer token；映射到身份与可选配置。

- **范围：**  
  - 可放在 Phase 4；短期多数「其他 Agent」场景可能仅需 MCP + 程序化 API。

**产出：**

- 可选 HTTP 服务（如 FastAPI），提供 `/chat` 及可选 `/tools`（列表）。  
- OpenAPI schema 便于对接。

---

## 8. 总结：需要补足的设计

| 方向 | 需要补足的内容 | 优先级 |
|------|----------------|--------|
| **程序化 API** | `queryclaw.api.chat()`、`ChatResult`、配置注入；可选 `create_agent_loop()` | 高 |
| **MCP 服务** | `queryclaw serve-mcp`；暴露工具（底层和/或 `queryclaw_ask`）；tools/list + call | 高 |
| **结构化输出** | 工具结果与 `ChatResult.structured_artifacts` 的可选 JSON 形态 | 中 |
| **会话** | `chat()` 的 `session_id`、进程内（及后续持久化）会话存储 | 中 |
| **发现** | `get_tool_definitions()`、能力矩阵文档/schema | 中 |
| **安全 / 多租户** | 可选 `caller_id`、按调用方配置、超时、read_only | 多 Agent 共享服务时 |
| **HTTP API** | 可选 REST `/chat` + OpenAPI | Phase 4 / 较低 |

优先落地 **程序化 API** 与 **MCP 服务**，其他 Agent 就能以标准方式发现和调用 QueryClaw；**结构化输出** 与 **会话** 则让组合与多轮对话更可用。安全与 HTTP 可在 QueryClaw 作为共享服务部署时再加强。
