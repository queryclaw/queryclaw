# 供其他 Agent 使用的设计 — v2（重新思考）

> [English](DESIGN_AGENT_CONSUMABILITY_V2.md)

## 核心张力：谁来思考？

QueryClaw 是一个 **Agent** —— 它有自己的 LLM、自己的 ReACT 循环、自己的推理能力。当另一个 Agent 想使用它时，根本性的问题是：

**谁来负责思考？**

这不只是 API 设计问题，它决定了整个架构。存在三种本质不同的使用模式，每种需要不同的架构表面：

| 模式 | 谁来推理？ | QueryClaw 提供什么 | 类比 |
|------|-----------|-------------------|------|
| **A. 智能工具** | 调用方的 LLM | 数据库操作 + 安全护栏 | 一把扳手 |
| **B. 专家 Agent** | QueryClaw 自己的 LLM | 端到端的完整回答 | 一位顾问 |
| **C. 知识源** | 调用方的 LLM | 领域专业知识（文本形式） | 一本教科书 |

大多数「如何让 X 被其他 Agent 使用」的分析会直接跳到「加 MCP 服务」或「加 HTTP API」，而不去问调用方到底需要哪种模式。答案是：**三种都需要，且架构必须将它们干净地分离。**

---

## 模式 A：智能工具（不需要内部 LLM）

**含义：** 调用方已有自己的 LLM 和 ReACT 循环。它只需要数据库操作 —— 查 schema、跑 SELECT、看 EXPLAIN —— 作为可调用的工具。QueryClaw 充当 **带安全护栏的数据库抽象层**，不是一个 Agent。

**为什么这最重要：** 这是目前最常见的集成模式。当 Cursor、Claude Desktop 或自定义编排 Agent 想要「数据库能力」时，它要的是把 `schema_inspect` 和 `query_execute` 加到*自己的*工具列表里，而不是委托给一个有独立 LLM 的另一个 Agent。

**当前架构已具备的：**

- `SchemaInspectTool`、`QueryExecuteTool`、`ExplainPlanTool` —— 干净、独立，已实现 `Tool` ABC 与 JSON Schema 参数。
- `SQLAdapter` 与 `AdapterRegistry` —— 数据库无关的抽象。
- `QueryExecuteTool._check_readonly()` 中的只读安全检查。

**缺失的：**

1. **无法在不构建完整 `AgentLoop` 的情况下使用这些工具。**  
   当前路径：CLI → Config → Provider → Adapter → AgentLoop → tools。  
   需要的路径：Adapter → tools，直接可用。工具应当在*不需要 LLM provider* 的情况下即可使用。

2. **暴露单个工具的 MCP 服务。**  
   一个把每个 `Tool` 映射为 MCP tool 的 MCP 服务。调用方的 LLM 在自己的工具列表里看到它们。不涉及内部 LLM。

3. **结构化输出。**  
   工具目前返回格式化的文本字符串（`to_text()`）。另一个 Agent 的 LLM 能解析，但 JSON 模式更可靠：
   ```json
   {"columns": ["id", "name"], "rows": [[1, "Alice"], [2, "Bob"]], "row_count": 2}
   ```

**设计原则：** 工具层必须 **可独立实例化** —— 只给它一个数据库连接，就能得到可调用的工具。不需要 LLM、不需要配置文件、不需要 Agent 循环。

---

## 模式 B：专家 Agent（需要内部 LLM）

**含义：** 调用方有一个复杂问题（「这条查询为什么慢？该加什么索引？」），想把整个调查委托给 QueryClaw。QueryClaw 用自己的 LLM + ReACT 循环 + Skills 进行多步推理，返回完整答案。

**适用场景：**

- 问题需要多步推理（查 schema → 跑查询 → explain → 分析 → 建议）。
- 调用方的上下文里没有数据库领域知识。
- 调用方想从专家那里获取「第二意见」。

**「双 LLM」问题：**

使用模式 B 时，两个 LLM 在同时运行 —— 调用方的和 QueryClaw 的。这带来实际后果：

| 关注点 | 影响 |
|--------|------|
| **成本** | 双重 LLM 调用（调用方推理该委托什么，然后 QueryClaw 推理数据库问题）。 |
| **延迟** | 调用方需等待 QueryClaw 完成整个多步循环。 |
| **上下文丢失** | 调用方的上下文（对话历史、用户意图、更大的任务）被压缩成一句提问字符串。QueryClaw 不知道全局图景。 |
| **模型不一致** | 调用方可能用 GPT-4o，QueryClaw 用 Claude。不同模型在 SQL 生成上各有所长。 |

**关键设计决策：**

1. **允许调用方注入自己的 LLM Provider。**  
   `queryclaw_ask(question)` 不一定总用 QueryClaw 配置的 LLM，而是允许调用方可选地传入 provider（或 API key + model）。这样：
   - 成本可归因到调用方。
   - 调用方可保证模型一致性。
   - QueryClaw 贡献的是工具、技能和安全 —— 而非它的 LLM。

2. **可观测执行（不仅仅返回最终答案）。**  
   调用方可能想看中间步骤：「QueryClaw 检查了 3 张表、跑了 2 条查询，然后分析了 EXPLAIN 输出」。这对以下场景至关重要：
   - **审计：** 实际执行了什么 SQL？
   - **学习：** 调用方 Agent 可以从 QueryClaw 的方法中学习。
   - **中断：** 「停，那张表搞错了。」
   
   设计：事件流或回调接口：
   ```python
   async for event in queryclaw.chat_stream(question):
       # event.type: "tool_call" | "tool_result" | "thinking" | "final_answer"
   ```

3. **上下文注入（调用方向 QueryClaw 提供上下文）。**  
   调用方可以传入提示，避免 QueryClaw 从零探索：
   ```python
   queryclaw.chat(question, context_hints={
       "relevant_tables": ["orders", "customers"],
       "business_context": "我们在调查 Q4 的营收下降",
   })
   ```
   这避免了多余的 schema 扫描，使内部 Agent 的推理更聚焦。

---

## 模式 C：知识源（不执行任何操作）

**含义：** 调用方只需要 QueryClaw 的领域知识 —— 如何安全地查询数据库、如何分析性能、如何探索数据 —— 注入到自己的上下文中。不需要工具执行，不需要数据库连接。只需要文本形式的专业知识。

**这就是 Skills 现在的本质**，但它们目前只被加载到 QueryClaw 自己的 system prompt 里。它们可以被导出：

1. **作为 MCP 资源：** `queryclaw://skills/data_analysis` 返回技能内容。调用方注入到自己的 system prompt。

2. **作为 schema 摘要服务：** `queryclaw://schema/summary` 返回数据库 schema，格式适合另一个 Agent 的上下文。调用方不需要 `schema_inspect` 作为工具 —— 它只要 schema 作为上下文。

3. **作为 prompt 片段：** QueryClaw 的安全准则、SQL 最佳实践、数据库特定的提示，导出为可复用的文本块。

**为什么这个模式被低估了：** QueryClaw 对调用方 Agent 的最大价值可能不在「跑 SQL」—— 调用方用任何 DB 客户端都能做到。价值在于*知道怎么*推理数据库：该检查什么、什么是陷阱、如何解读 EXPLAIN 输出。这些知识活在 Skills 和 system prompt 里。导出它们成本低、安全、立即可用。

---

## 解耦架构

核心洞察：**QueryClaw 当前的整块流程（CLI → Config → Provider → Adapter → AgentLoop → tools → response）必须解耦为可独立寻址的层次：**

```
┌─────────────────────────────────────────────────┐
│                    消费表面                       │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ MCP 工具 │  │ 程序 API │  │ CLI（当前）    │  │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘  │
│       │              │               │           │
├───────┴──────────────┴───────────────┴───────────┤
│              编排层（可选，需要 LLM）              │
│  ┌──────────────────────────────────────────┐    │
│  │  AgentLoop (ReACT) — 需要 LLM provider  │    │
│  │  ContextBuilder — 需要 DB + skills       │    │
│  │  MemoryStore — 会话状态                   │    │
│  └──────────────────────────────────────────┘    │
│                    ↕ 可选                         │
├──────────────────────────────────────────────────┤
│              核心层（不需要 LLM）                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │   工具   │  │   安全   │  │    技能      │   │
│  │(schema,  │  │(只读检查 │  │ (SKILL.md)  │   │
│  │ query,   │  │  行限制) │  │             │   │
│  │ explain) │  │          │  │             │   │
│  └────┬─────┘  └──────────┘  └──────────────┘   │
│       │                                          │
├───────┴──────────────────────────────────────────┤
│                   数据库层                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ SQLite   │  │  MySQL   │  │ (PostgreSQL) │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
└──────────────────────────────────────────────────┘
```

**核心层（工具 + 安全 + 技能）不需要任何 LLM 即可使用。** 编排层（AgentLoop）是可选的 —— 你想让 QueryClaw 自己思考时才加。消费表面（MCP、API、CLI）是可替换的入口。

---

## 五个最重要的设计决策

### 1. LLM 归属权：自带 vs. 内置

| 方式 | 优点 | 缺点 |
|------|------|------|
| **BYOLLM**（调用方提供 LLM） | 成本归因清晰、模型一致、调用方控制推理 | 调用方须自行处理 ReACT 循环或传入 provider |
| **内置**（QueryClaw 用自己的 LLM） | API 更简单，调用方只需发送问题 | 双 LLM 运行、上下文丢失、成本不透明 |
| **两者皆可**（默认内置、可选覆盖） | 最大灵活性 | API 表面更大 |

**建议：** 两者都支持。默认内置（模式 B），但允许注入 provider，或在不使用任何 LLM 的情况下直接用工具（模式 A）。这就是 `create_agent_loop(provider=caller_provider)` 与 `tools = get_tools(db_adapter)` 的区分。

### 2. 粒度：工具 vs. Agent vs. 两者都暴露

同时暴露单个工具和 Agent 级的 `ask()`：

- `schema_inspect`、`query_execute`、`explain_plan` —— 给想自己驱动推理的调用方（模式 A）。
- `queryclaw_ask(question)` —— 给想委托的调用方（模式 B）。

不要强制二选一。在 MCP 中：全部列出，调用方自己挑。

### 3. 输出契约：文本 vs. 结构化 vs. 流式

三种模式，按每次调用协商：

| 模式 | 何时 | 格式 |
|------|------|------|
| **文本** | 面向人类，或调用方的 LLM 来解读 | Markdown 字符串（当前方式） |
| **结构化** | 机器对机器，或调用方要做后处理 | 带类型字段的 JSON |
| **流式** | 调用方想看中间步骤或实时进度 | 事件流（tool_call、tool_result、final_answer） |

**对 Agent 消费的最低要求：** 工具支持结构化模式。Agent 级 `ask()` 的流式是强「锦上添花」。

### 4. 上下文共享：避免重复劳动

当另一个 Agent 调用 QueryClaw 时，它往往已经知道一些数据库信息（来自上次调用或自身上下文）。避免重复扫描：

- **Schema 缓存：** 已实现（`_schema_cache`）。让它可在会话间共享。
- **上下文提示：** 允许调用方传入 `relevant_tables`、`business_context`，甚至预构建的 schema 摘要，省去 QueryClaw 重新发现调用方已知的信息。
- **可导出上下文：** 允许调用方*读取* QueryClaw 的上下文（`get_schema_summary()`、`get_skills_summary()`）并注入到自己的 system prompt —— 模式 C。

### 5. 安全作为可分离关注点

安全性（只读检查、行限制、未来：SQL AST 校验、审计日志）应当是 **中间件**，而非硬编码在工具里：

```python
safety = SafetyPolicy(read_only=True, max_rows=100, audit=True)
tools = get_tools(db_adapter, safety=safety)
```

不同调用方可拥有不同的安全策略。内部管理员 Agent 可 `read_only=False`；外部 Agent 则 `read_only=True`。这对多租户以及 Phase 2 写操作过渡至关重要。

---

## 具体实施路线

### 第 1 步：解耦核心层（实现模式 A）

- **`queryclaw.api.get_tools(db_adapter, safety=None) -> list[Tool]`** —— 返回工具实例，不需要 LLM。
- **`queryclaw.api.connect(db_type, **kwargs) -> SQLAdapter`** —— 快捷创建已连接的 adapter。
- 每个工具增加可选的 `structured=True` 参数，返回 JSON 而非文本。

仅此一步就能让任何 Python Agent 直接使用 QueryClaw 的数据库工具。

### 第 2 步：MCP 服务（为 MCP 客户端实现模式 A + B）

- `queryclaw serve-mcp`（stdio 传输）。
- 暴露单个工具（模式 A）与 `queryclaw_ask`（模式 B）。
- MCP 资源用于 schema 摘要与技能内容（模式 C）。

### 第 3 步：带 LLM 注入的 Agent 级 API（正确实现模式 B）

- **`queryclaw.api.ask(question, config=None, provider=None, ...) -> ChatResult`**
- 若给了 `provider` 则使用；否则用 config 的 provider。
- `ChatResult` 包含 `content`、`tools_used`、`structured_artifacts`，可选 `events`（中间步骤列表）。

### 第 4 步：可观测执行

- `async for event in queryclaw.api.ask_stream(question, ...):`
- 事件类型：`schema_loaded`、`tool_call`、`tool_result`、`reasoning`、`final_answer`。
- 让调用方 Agent 能审计、学习、中断。

### 第 5 步：安全策略对象

- `SafetyPolicy(read_only=True, max_rows=100, allowed_tables=None, audit=True, require_confirmation=False)`
- 传给工具或 Agent；控制哪些操作允许。
- 不同调用方可拥有不同策略。

---

## 不要做的事（反模式）

| 反模式 | 为什么是错的 |
|--------|-------------|
| **以 HTTP API 作为主要集成方式** | Agent 越来越多用 MCP 或进程内调用；HTTP 增加延迟、序列化和部署复杂度。先做 MCP + 库 API；HTTP 最后。 |
| **始终跑两个 LLM** | 调用方已有 LLM 时，不要强制第二个。直接暴露工具（模式 A）。 |
| **隐藏中间步骤** | 只返回最终答案的「神谕式」API 妨碍审计、学习和调试。始终让执行可观测。 |
| **整块配置** | 所有调用方共享一个 `config.json` 在多 Agent 场景下行不通。配置必须可按调用注入。 |
| **工具依赖 CLI 上下文** | 工具应当是（数据库 + 参数 + 安全策略）的纯函数。不依赖 terminal、prompt_toolkit 或 rich 渲染。 |

---

## 总结

「如何让 QueryClaw 被其他 Agent 使用」实质上是三个问题：

1. **如何在不需要内部 LLM 的情况下暴露数据库工具？**（模式 A —— 解耦核心层）
2. **如何让另一个 Agent 委托复杂问题？**（模式 B —— 可注入 LLM、可观测执行、上下文共享）
3. **如何在不执行操作的情况下共享数据库专业知识？**（模式 C —— 可导出的技能和上下文）

架构原则：**将整块系统解耦为可独立寻址的层次（数据库 → 工具+安全 → 可选 Agent → 消费表面），使每种模式都能被满足，而不拖入不必要的机制。**

最有影响力的第一步是 **第 1 步：解耦核心层** —— 一个 `get_tools(db_adapter)` 函数，返回可用工具，不需要任何 LLM、配置文件或 CLI。其余一切建立在这个基础之上。
