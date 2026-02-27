# QueryClaw

**你的数据库，由 AI 接管。**

> [English](README.md)

[![PyPI](https://img.shields.io/pypi/v/queryclaw)](https://pypi.org/project/queryclaw/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)

---

## QueryClaw 是什么？

**QueryClaw** 是一个 AI 原生数据库 Agent，让你可以把整个数据库实例交给 LLM 驱动的 Agent。想象一下给你的数据库装上一个大脑——它能探索表结构、查询数据、修改记录、诊断性能、甚至用 AI 生成新数据，一切通过自然语言完成。

**这不是又一个 Text-to-SQL 聊天机器人。** QueryClaw 是一个完整的 [ReACT](https://arxiv.org/abs/2210.03629) Agent，能够推理、行动、观察、迭代——它以开发者思考数据的方式工作，同时具备资深 DBA 的深度。

### 灵感来源

[OpenClaw](https://github.com/openclaw/openclaw) 证明了 LLM 可以安全地控制一台个人电脑。**QueryClaw 问：如果把数据库交给它呢？**

| | OpenClaw / nanobot | QueryClaw |
|---|---|---|
| **控制对象** | 操作系统 | 数据库 |
| **交互界面** | Shell、文件系统、浏览器 | SQL、schema、数据 |
| **安全机制** | 沙箱执行 | 事务回滚、试跑、审计 |
| **目标用户** | 通用用户 | 应用开发者与 DBA |

## 为什么选择 QueryClaw？

开发者在数据库上花费了大量时间：写查询、排查数据问题、生成测试数据、审查 schema 设计、分析性能。大多数数据库工具要么太底层（原始 SQL 客户端），要么太受限（拖拽式查询构建器）。

QueryClaw 恰好在中间：**一个既理解你的自然语言意图、又理解数据库语义的智能 Agent**。

### 你可以做什么

```
> "显示上季度按收入排序的前 10 名客户"
> "这条查询为什么慢？建议加什么索引"
> "生成 100 个带订单的真实测试用户"
> "找到孤岛记录，修复外键违规"
> "基于产品描述，生成一个一句话摘要列"
> "与订单系统相关的表有哪些？画出关系"
> "检查有没有明文存储的个人信息"
```

## 架构

QueryClaw 使用 LLM 驱动的 **ReACT（推理 + 行动）循环**，配合模块化的工具与技能系统：

```
                    ┌─────────────────────────┐
                    │      CLI / 通道          │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   AgentLoop (ReACT)      │
                    │  推理 → 行动 → 观察        │
                    │        → 循环             │
                    └──┬──────────┬──────────┬──┘
                       │          │          │
              ┌────────▼────┐ ┌──▼──────┐ ┌▼────────────┐
              │   LLM        │ │  工具   │ │   技能      │
              │  提供方      │ │         │ │ (SKILL.md)  │
              └─────────────┘ └────┬────┘ └──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │          安全层              │
                    │  校验 → 试跑 → 审计           │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │        数据库适配器            │
                    │  MySQL │ SQLite │ PostgreSQL │
                    └─────────────────────────────┘
```

**核心设计：**

- **多数据库**：基于适配器架构，支持 MySQL（首要目标）、SQLite、PostgreSQL，未来可扩展 MongoDB、Redis 等
- **多 LLM**：通过 [LiteLLM](https://github.com/BerriAI/litellm) 统一接入 OpenAI、Anthropic、Gemini、DeepSeek 等任意兼容 API
- **可扩展技能**：通过 `SKILL.md` 文件添加新能力，无需改代码
- **安全优先**：分层安全——策略检查、SQL AST 校验、试跑、事务包裹、人工确认、完整审计日志

## 数据库原生记忆 —— 越用越聪明

与通用 Agent 将记忆存在文件中不同，QueryClaw 把记忆**直接存储在它管理的数据库中**——对结构化数据来说，这是最自然、最可靠的地方。

每一次交互都让 Agent 学到东西：表间关系、列的业务含义、常用查询模式、数据特征。这些知识被持久化并不断积累：

- **Schema 知识**：「`orders` 表的 `status` 列含义是 1=待处理、2=已发货、3=已完成」
- **使用模式**：「这个团队经常按地区查 `daily_sales` 的汇总」
- **操作历史**：「上周二我们在 `users.email` 上加了索引来解决登录慢的问题」

你用 QueryClaw 越多，需要解释的就越少。它像一个在你的系统上工作了多年的资深 DBA 一样记住你的数据库——只不过它永远不会遗忘。

## 完整审计追踪 —— 每一步操作，全部记录

QueryClaw 的每一个操作都会记录到所管理数据库中的一张专用审计表（`_queryclaw_audit_log`）。它提供：

- **完整血缘**：从自然语言提问 → 生成的 SQL → 执行结果 → 影响的行数
- **前后快照**：数据修改前后的状态对比
- **时间戳 + 会话追踪**：谁在什么时候、哪次对话中做了什么
- **回滚参考**：如果出了问题，审计日志会告诉你究竟发生了什么、如何撤销

这不只是日志——这是一份完整的**安全审计记录**，合规团队、DBA 和开发者都可以用标准 SQL 来查询。因为它就存在数据库里，所以始终可用、始终可查，并且享有与你的业务数据相同的 ACID 保障。

## 内置技能

QueryClaw 的真正威力来自技能系统。每个技能教会 Agent 一套领域工作流：

| 技能 | 功能说明 |
|------|---------|
| **AI 列** | 用 LLM 生成列值（摘要、情感分析、翻译、评分） |
| **测试数据工厂** | 生成语义合理的测试数据，自动满足外键约束 |
| **数据侦探** | 沿关联表追踪数据血缘，快速定位 bug 根因 |
| **Schema 文档生成** | 从命名和采样自动推断业务含义，生成文档 |
| **查询翻译器** | 用自然语言解释复杂 SQL，指出问题，建议优化 |
| **索引顾问** | 分析慢查询，建议索引，评估写入影响 |
| **数据修复师** | 发现并修复脏数据——孤岛记录、格式不一致、语义错误 |
| **数据脱敏** | 自动识别 PII 列，生成真实感的脱敏数据 |
| **异常探测器** | 主动发现离群值、分布偏移、可疑模式 |
| **智能迁移器** | 用自然语言描述变更，自动生成迁移脚本与回滚方案 |

> 完整列表与优先级：[docs/SKILLS_ROADMAP_CN.md](docs/SKILLS_ROADMAP_CN.md)

## 路线图

### 阶段一：MVP —— 只读 Agent *（已完成）*

- 交互式 CLI（typer + prompt_toolkit）
- ReACT Agent 循环
- LLM 提供方层（LiteLLM）
- 数据库适配器：MySQL + SQLite
- 只读工具：`schema_inspect`、`query_execute`、`explain_plan`
- 配置系统
- 基础技能加载

### 阶段二：写操作与安全 *（已完成）*

- PostgreSQL 适配器（asyncpg）
- 安全层：策略引擎、SQL AST 校验器、试跑引擎、审计日志
- 子代理系统：`spawn_subagent` 工具，用于委派任务
- 写入工具：`data_modify`、`ddl_execute`、`transaction`
- 破坏性操作人机确认流程
- 只读技能：Schema 文档生成、查询翻译器、数据侦探
- 写操作技能：AI 列、测试数据工厂
- 配置系统新增 `SafetyConfig`

### 阶段三：高级技能与记忆

- 持久记忆（Schema 知识 + 操作历史）
- 定时任务 + 主动唤醒（Heartbeat）
- 技能：索引顾问、数据修复师、异常探测器、智能迁移器
- 复杂任务多步规划

### 阶段四：生态集成

- MCP 服务模式（对外暴露为其他 Agent 的工具）
- 多通道输出（Telegram、Slack、飞书等）
- MongoDB 适配器 + 多数据库同时连接
- Web UI
- 自定义工具与适配器插件体系

### 向量与 AI 原生数据库（阶段四+）

与向量数据库、AI 原生数据库结合，可带来这些新亮点：

| 方向 | 亮点 |
|------|------|
| **向量 + Schema** | 语义 Schema 检索：按「意思」找表/列（如「和用户登录、权限相关的表」），大库下更稳；对 schema + 文档做 RAG。 |
| **向量 + 查询** | 混合查询：SQL 条件 + 向量相似（如「和这条订单描述语义相近的异常订单」）；支持 pgvector 或侧挂向量库。 |
| **向量 + 记忆** | 记忆向量化：用 embedding 存操作与知识；「和上次那个慢查询类似」→ 语义召回历史，越用越聪明。 |
| **向量 + AI 列** | 一键 embedding 列：为某列生成并写入向量，便于同库内做相似搜索、去重、聚类。 |
| **AI 原生库** | 统一入口：简单查数用库自带 NL；复杂多步、试跑/回滚、技能编排用 QueryClaw 的 ReACT + 工具。 |
| **AI 原生库** | 技能层补足：测试数据工厂、数据侦探、AI 列、合规扫描；关系型 + 向量 + AI 原生库统一记忆与审计。 |

> 详细架构计划：[docs/PLAN_ARCHITECTURE_CN.md](docs/PLAN_ARCHITECTURE_CN.md)

## 安装

```bash
pip install queryclaw
```

安装 PostgreSQL 支持：

```bash
pip install queryclaw[postgresql]
```

安装所有可选功能（PostgreSQL + SQL 校验）：

```bash
pip install queryclaw[all]
```

## 文档

- **[用户手册](docs/USER_MANUAL_CN.md)**（[English](docs/USER_MANUAL.md)）— 安装、配置与使用（当前版本）
- [架构与实施计划](docs/PLAN_ARCHITECTURE_CN.md)（[English](docs/PLAN_ARCHITECTURE.md)）
- [AI 列设计文档](docs/DESIGN_AI_COLUMN_CN.md)（[English](docs/DESIGN_AI_COLUMN.md)）
- [Skills 路线图](docs/SKILLS_ROADMAP_CN.md)（[English](docs/SKILLS_ROADMAP.md)）
- [自我演进分析（Tools 与 Skills）](docs/SELF_EVOLUTION_ANALYSIS_CN.md)（[English](docs/SELF_EVOLUTION_ANALYSIS.md)）

## 贡献

欢迎贡献！无论是新的数据库适配器、创意技能想法，还是 bug 修复——我们都期待你的 PR。

## 致谢

QueryClaw 的架构深受 AI Agent 领域两个先驱项目的启发：

- **[OpenClaw](https://github.com/openclaw/openclaw)** —— 最早提出让 LLM 完全控制个人电脑的愿景。OpenClaw 证明了自主 AI Agent 可以在复杂环境中安全运行。QueryClaw 将这一理念从操作系统延伸到了数据库。
- **[nanobot](https://github.com/HKUDS/nanobot)** —— 一个极致轻量的个人 AI 助手，以优雅的方式实现了 ReACT 循环、工具注册、技能系统、记忆和多通道架构。QueryClaw 的 Agent 核心、提供方层和技能格式直接参考了 nanobot 的简洁设计。

感谢两个团队不断拓展 AI Agent 的能力边界。

## 协议

Apache 2.0 —— 详见 [LICENSE](LICENSE)。
