# QueryClaw

**你的数据库，由 AI 接管。**

> [English](README.md)

[![PyPI](https://img.shields.io/pypi/v/queryclaw)](https://pypi.org/project/queryclaw/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)

<!-- TODO: 将录屏放到 docs/assets/demo.gif（asciinema 或 GIF）后取消下面注释：
![Demo](docs/assets/demo.gif)
-->

**9 工具** | **7 技能** | **4 种数据库** | **243+ 测试用例** | **多 LLM 支持（LiteLLM）**

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

### 对比：传统方式 vs QueryClaw

| | 传统方式 | 使用 QueryClaw |
|---|---|---|
| **查询** | 手写 SQL，猜表名列名 | `"显示收入最高的客户"` — Agent 自动探索 Schema 并生成查询 |
| **修改数据** | 手写 UPDATE，祈祷 WHERE 没写错，无审计 | Agent 校验、试跑、要求确认，自动记录修改前后快照 |
| **生成测试数据** | 写脚本、手动处理外键约束 | `"生成 100 个带订单的测试用户"` — 自动满足 Schema 约束 |
| **诊断慢查询** | 手动 EXPLAIN、查文档、反复调试 | `"这条查询为什么慢？"` — Agent 执行 EXPLAIN、建议索引 |
| **团队协作** | 在群里传 SQL 片段 | 直接在飞书/钉钉里提问，Agent 回复结果 |

### 核心差异

- **自主推理** —— 完整的 ReACT Agent 循环，不是一次性翻译。它会探索 Schema、执行查询、观察结果、跨多个步骤调整策略
- **安全优先的写操作** —— 多层变更防护：策略检查 → SQL AST 校验 → 试跑 → 人工确认 → 事务包裹 → 完整审计（含修改前后快照）
- **多通道** —— 终端使用（`queryclaw chat`），或部署到团队消息平台（`queryclaw serve`），支持飞书/钉钉，含交互式确认
- **可扩展技能** —— 通过 `SKILL.md` 文件添加新能力，无需改代码、无需重新部署。Agent 按需加载技能
- **多数据库** —— MySQL、PostgreSQL、SQLite、SeekDB（OceanBase），干净的适配器接口方便扩展
- **外网访问**（可选）—— 启用后可抓取网页、调用 REST API；SSRF 防护、超时与大小限制保障安全

### 你可以做什么

```
> "显示上季度按收入排序的前 10 名客户"
> "这条查询为什么慢？建议加什么索引"
> "生成 100 个带订单的真实测试用户"
> "找到孤岛记录，修复外键违规"
> "基于产品描述，生成一个一句话摘要列"
> "与订单系统相关的表有哪些？画出关系"
> "抓取 https://example.com/api 的 API 文档并总结接口" *（需启用外网访问）*
```

## 安装

```bash
pip install queryclaw
```

安装 PostgreSQL 支持：

```bash
pip install queryclaw[postgresql]
```

安装飞书通道支持：

```bash
pip install queryclaw[feishu]
```

安装钉钉通道支持：

```bash
pip install queryclaw[dingtalk]
```

安装所有可选功能（PostgreSQL + SQL 校验 + 飞书 + 钉钉）：

```bash
pip install queryclaw[all]
```

## 快速开始

```bash
# 1. 初始化配置
queryclaw onboard

# 2. 编辑配置——设置数据库连接和 LLM API Key
#    配置文件位置：~/.queryclaw/config.json

# 3. 开始和你的数据库聊天
queryclaw chat
```

交互示例：

```
你: 这个数据库有哪些表？
Agent: [调用 schema_inspect] 找到 12 张表，主要的有...

你: 显示按订单总额排序的前 5 名客户
Agent: [调用 query_execute] 查询结果如下...

你: 给 orders.customer_id 加个索引
Agent: ⚠️ 这是一个 DDL 操作，是否继续？[y/N]
```

通道模式（飞书 / 钉钉）：

```bash
queryclaw serve
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
                    │        数据库适配器          │
                    │  MySQL│SQLite│PG│SeekDB   │
                    └─────────────────────────────┘
```

LLM 提供方层基于 [LiteLLM](https://github.com/BerriAI/litellm)，支持 OpenAI、Anthropic、Gemini、DeepSeek 及任意兼容 API。

## 记忆与上下文

QueryClaw 在整个对话过程中维护**会话记忆**——它会追踪你探索过的 Schema、执行过的查询、做过的修改，让你可以基于之前的步骤继续操作，无需重复解释。[审计追踪](#完整审计追踪)同时提供持久的操作历史，可通过标准 SQL 随时查询。

**即将推出**（Phase 3）：持久化数据库原生记忆——Schema 知识、使用模式、语义召回，跨会话持续积累，让 Agent 越用越聪明。

## 完整审计追踪

QueryClaw 的每一个操作都会记录到所管理数据库中的一张专用审计表（`_queryclaw_audit_log`）。它提供：

- **完整血缘**：从自然语言提问 → 生成的 SQL → 执行结果 → 影响的行数
- **前后快照**：数据修改前后的状态以 JSON 格式完整记录
- **时间戳 + 会话追踪**：谁在什么时候、哪次对话中做了什么
- **回滚参考**：如果出了问题，审计日志会告诉你究竟发生了什么、如何撤销

示例：执行 `UPDATE users SET status = 'active' WHERE id = 42` 后，审计日志记录：

```
sql_text:         UPDATE users SET status = 'active' WHERE id = 42
affected_rows:    1
before_snapshot:  [{"id": 42, "status": "inactive", "name": "Alice"}]
after_snapshot:   [{"id": 42, "status": "active", "name": "Alice"}]
```

这不只是日志——这是一份完整的**安全审计记录**，合规团队、DBA 和开发者都可以用标准 SQL 来查询。因为它就存在数据库里，所以始终可用、始终可查，并且享有与你的业务数据相同的 ACID 保障。

## 内置技能

QueryClaw 的真正威力来自技能系统。每个技能教会 Agent 一套领域工作流——无需改代码，只需 `SKILL.md` 文件：

| 技能 | 功能说明 |
|------|---------|
| **AI 列** | 用 LLM 生成列值（摘要、情感分析、翻译、评分） |
| **测试数据工厂** | 生成语义合理的测试数据，自动满足外键约束 |
| **数据侦探** | 沿关联表追踪数据血缘，快速定位 bug 根因 |
| **数据分析** | 统计分析、分布画像、数据质量评估 |
| **Schema 文档生成** | 从命名和采样自动推断业务含义，生成文档 |
| **查询翻译器** | 用自然语言解释复杂 SQL，指出问题，建议优化 |
| **SeekDB 向量搜索** | SeekDB（OceanBase AI 原生库）中的向量搜索、语义搜索、AI_EMBED、混合搜索 |

> 更多技能规划中（索引顾问、数据修复师、异常探测器等）——完整列表与优先级见 [Skills 路线图](docs/zh/SKILLS_ROADMAP.md)。

## 路线图

> 各阶段按需并行开发，编号代表逻辑分组而非严格的依赖顺序。

### 阶段一：MVP —— 只读 Agent *（已完成）*

- 交互式 CLI（typer + prompt_toolkit）
- ReACT Agent 循环
- LLM 提供方层（LiteLLM）
- 数据库适配器：MySQL + SQLite
- 只读工具：`schema_inspect`、`query_execute`、`explain_plan`、`read_skill`
- 配置系统
- 基础技能加载

### 阶段二：写操作与安全 *（已完成）*

- PostgreSQL 适配器（asyncpg）
- SeekDB 适配器（OceanBase AI 原生数据库）
- 安全层：策略引擎、SQL AST 校验器、试跑引擎、审计日志
- DML 操作前后数据快照（before/after snapshot）
- 子代理系统：`spawn_subagent` 工具，用于委派任务
- 写入工具：`data_modify`、`ddl_execute`、`transaction`
- 破坏性操作人机确认流程
- 技能：Schema 文档生成、查询翻译器、数据侦探、数据分析、AI 列、测试数据工厂、SeekDB 向量搜索
- 配置系统新增 `SafetyConfig`

### 阶段三：高级技能与记忆

- 持久记忆（Schema 知识 + 操作历史）
- 定时任务 + 主动唤醒（Heartbeat）
- 技能：索引顾问、数据修复师、异常探测器、智能迁移器
- 复杂任务多步规划
- SeekDB Fork Table 沙箱，安全实验环境

### 阶段四：多通道输出 *（已完成）*

- 消息总线 + 双向通道（飞书、钉钉）
- 外网访问：`web_fetch`、`api_call` 工具（可选，带 SSRF 防护）
- `queryclaw serve` — 通道模式下运行 Agent；在飞书/钉钉中提问并接收回复
- 可选依赖：`queryclaw[feishu]`、`queryclaw[dingtalk]`
- 通道内交互式确认——回复「确认」或「取消」来批准或拒绝破坏性操作

### 阶段五：生态集成

- MCP 服务模式（对外暴露为其他 Agent 的工具）
- 更多通道（Telegram、Slack 等）
- MongoDB 适配器 + 多数据库同时连接
- Web UI
- 自定义工具与适配器插件体系

### 阶段五+：向量与 AI 原生数据库

- **语义 Schema 检索** —— 用向量 embedding 按「意思」搜索表/列，大库下更稳
- **混合查询** —— SQL 条件 + 向量相似度联合查询（pgvector 或侧挂向量库）
- **向量化记忆** —— 跨会话语义召回，Agent 越用越聪明
- **AI 原生库集成** —— 关系型 + 向量 + AI 原生后端统一入口

> 详细架构计划：[docs/zh/PLAN_ARCHITECTURE.md](docs/zh/PLAN_ARCHITECTURE.md)

## 文档

- **[用户手册](docs/zh/USER_MANUAL.md)**（[English](docs/USER_MANUAL.md)）— 安装、配置与使用（当前版本）
- **[版本说明](RELEASE_NOTES_CN.md)**（[English](RELEASE_NOTES.md)）— 版本历史与更新日志
- [架构与实施计划](docs/zh/PLAN_ARCHITECTURE.md)（[English](docs/PLAN_ARCHITECTURE.md)）
- [Skills 路线图](docs/zh/SKILLS_ROADMAP.md)（[English](docs/SKILLS_ROADMAP.md)）
- [自我演进分析（Tools 与 Skills）](docs/zh/SELF_EVOLUTION_ANALYSIS.md)（[English](docs/SELF_EVOLUTION_ANALYSIS.md)）

## 贡献

欢迎贡献！无论是新的数据库适配器、创意技能想法，还是 bug 修复——我们都期待你的 PR。

## 致谢

QueryClaw 的架构深受 AI Agent 领域两个先驱项目的启发：

- **[OpenClaw](https://github.com/openclaw/openclaw)** —— 最早提出让 LLM 完全控制个人电脑的愿景。OpenClaw 证明了自主 AI Agent 可以在复杂环境中安全运行。QueryClaw 将这一理念从操作系统延伸到了数据库。
- **[nanobot](https://github.com/HKUDS/nanobot)** —— 一个极致轻量的个人 AI 助手，以优雅的方式实现了 ReACT 循环、工具注册、技能系统、记忆和多通道架构。QueryClaw 的 Agent 核心、提供方层和技能格式直接参考了 nanobot 的简洁设计。

感谢两个团队不断拓展 AI Agent 的能力边界。

## 协议

Apache 2.0 —— 详见 [LICENSE](LICENSE)。
