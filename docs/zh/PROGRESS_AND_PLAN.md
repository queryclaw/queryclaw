# QueryClaw：项目进展与规划

> [English](../PROGRESS_AND_PLAN.md)

**更新日期**：2026-02-27  
**当前版本**：0.5.0

---

## 1. 项目概述

QueryClaw 是一款 AI 原生数据库 Agent，将数据库实例交由 LLM 控制。用户通过自然语言交互，Agent 通过 ReACT 循环探索 Schema、查询数据、修改记录、执行管理任务，并配有安全防护。

**核心定位**：*OpenClaw : 操作系统 = QueryClaw : 数据库*

---

## 2. 已完成工作（进展汇总）

### 2.1 Phase 1：MVP — 只读 Agent ✅

| 组件 | 状态 | 说明 |
|------|------|------|
| CLI | ✅ | typer + prompt_toolkit，交互式对话 |
| ReACT Agent 循环 | ✅ | Reason → Act → Observe → Repeat |
| LLM 提供者层 | ✅ | LiteLLM，多模型（OpenAI、Anthropic、Gemini、DeepSeek 等） |
| 数据库适配器 | ✅ | MySQL、SQLite |
| 工具 | ✅ | `schema_inspect`、`query_execute`、`explain_plan` |
| 配置系统 | ✅ | `~/.queryclaw/config.json` |
| Skill 加载 | ✅ | 基础 SKILL.md 加载器 |

### 2.2 Phase 2：写操作 + 安全层 ✅

| 组件 | 状态 | 说明 |
|------|------|------|
| 写操作工具 | ✅ | `data_modify`、`ddl_execute`、`transaction` |
| 安全层 | ✅ | 策略引擎、SQL AST 校验（sqlglot）、Dry-Run、审计日志 |
| 人工确认 | ✅ | CLI 提示 + 通道模式（飞书/钉钉）确认/取消 |
| PostgreSQL 适配器 | ✅ | asyncpg |
| 子 Agent 系统 | ✅ | `spawn_subagent` 处理后台长任务 |
| 审计前后快照 | ✅ | `SnapshotHelper` 填充 `before_snapshot`、`after_snapshot` |

### 2.3 Phase 4：多通道输出 ✅

| 组件 | 状态 | 说明 |
|------|------|------|
| 消息总线 | ✅ | 事件驱动、双向 |
| 飞书通道 | ✅ | WebSocket，可选 `queryclaw[feishu]` |
| 钉钉通道 | ✅ | Stream 模式，可选 `queryclaw[dingtalk]` |
| `queryclaw serve` | ✅ | 通道模式运行 Agent |
| 通道确认 | ✅ | 回复「确认」/「取消」执行或中止破坏性操作 |

### 2.4 SeekDB 与向量搜索（Phase 3 部分）✅

| 组件 | 状态 | 说明 |
|------|------|------|
| SeekDB 适配器 | ✅ | 继承 MySQLAdapter，端口 2881，VECTOR、AI_EMBED |
| SeekDB 审计修复 | ✅ | MySQL 风格 DDL 与 `%s` 占位符 |
| SeekDB dialect 映射 | ✅ | seekdb → mysql 供 sqlglot 解析 |
| SeekDB 向量搜索 Skill | ✅ | `seekdb_vector_search` SKILL.md |

### 2.5 已实现 Skills（SKILL.md）

| Skill | 状态 | 阶段 |
|-------|------|------|
| AI Column | ✅ | 2 |
| Test Data Factory | ✅ | 2 |
| Data Detective | ✅ | 2 |
| Schema Documenter | ✅ | 2 |
| Query Translator | ✅ | 2 |
| Data Analysis | ✅ | 2 |
| SeekDB Vector Search | ✅ | 3 |

### 2.6 基础设施与质量

| 项目 | 状态 |
|------|------|
| `read_skill` 工具 | ✅ Agent 按需加载 SKILL.md |
| Skills 打包进 pip | ✅ `package-data` 包含所有 SKILL.md |
| 测试 | ✅ 243+ 用例（安全、工具、Agent、通道等） |
| PyPI | ✅ 已发布（0.5.0） |
| 文档 | ✅ USER_MANUAL、PLAN_ARCHITECTURE、SKILLS_ROADMAP、RELEASE_NOTES（中英） |

---

## 3. 未实现项（差距分析）

### 3.1 Phase 3：高级 Skills + 记忆 + Cron

| 组件 | 状态 | 优先级 |
|------|------|--------|
| **持久化记忆** | ❌ | 高 |
| - Schema 知识（MEMORY.md 风格） | ❌ | |
| - 操作历史（HISTORY.md 风格） | ❌ | |
| - 数据库存储 | ❌ | |
| **Cron 系统** | ❌ | 中 |
| **Heartbeat** | ❌ | 中 |
| **Index Advisor Skill** | ❌ | 中 |
| **Data Healer Skill** | ❌ | 中 |
| **Anomaly Scanner Skill** | ❌ | 中 |
| **Data Masker Skill** | ❌ | 中 |
| **Smart Migrator Skill** | ❌ | 中 |
| **Change Impact Analyzer Skill** | ❌ | 低 |
| **多步规划** | ❌ | 中 |

### 3.2 Phase 5：生态集成

| 组件 | 状态 | 优先级 |
|------|------|--------|
| MCP 服务端模式 | ❌ | 高 |
| 更多通道（Telegram、Slack） | ❌ | 中 |
| MongoDB 适配器 | ❌ | 中 |
| 多数据库连接 | ❌ | 中 |
| Web UI | ❌ | 低 |
| 插件系统 | ❌ | 低 |
| `admin_ops` 工具 | ❌ | 低 |

### 3.3 Phase 5+：向量与 AI 原生数据库

| 组件 | 状态 | 优先级 |
|------|------|--------|
| pgvector / 向量列支持 | ❌ | 中 |
| 语义 Schema 搜索 | ❌ | 中 |
| 混合查询（SQL + 向量） | ❌ | 中 |
| 向量化记忆 | ❌ | 中 |
| AI Column：Embedding 生成 | ❌ | 中 |

### 3.4 未实现 Skills

| Skill | 优先级 | 阶段 |
|-------|--------|------|
| Index Advisor | 中 | 3 |
| Data Healer | 中 | 3 |
| Anomaly Scanner | 中 | 3 |
| Data Masker | 中 | 3 |
| Smart Migrator | 中 | 3 |
| Change Impact Analyzer | 低 | 3 |
| Capacity Planner | 低 | 5 |
| Compliance Scanner | 低 | 5 |
| Permission Auditor | 低 | 5 |
| API Scaffolding | 低 | 5 |
| Cross-DB Sync Checker | 低 | 5 |

---

## 4. 建议下一步（规划）

### 4.1 短期（0.5.x — 1–2 个月）

**目标**：强化核心价值与生产可用性。

| # | 任务 | 工作量 | 价值 |
|---|------|--------|------|
| 1 | **持久化记忆** | 中 | 高 — Schema 知识 + 操作历史入库，Agent 越用越聪明 |
| 2 | **Index Advisor Skill** | 中 | 高 — 常见 DBA 需求，复用现有 EXPLAIN + Schema 工具 |
| 3 | **MCP 服务端模式** | 中 | 高 — 作为工具供其他 Agent 使用（Cursor、Claude Desktop 等） |
| 4 | **Data Healer Skill** | 中 | 中 — 外键完整性、格式检查、语义脏数据 |
| 5 | **通道体验优化** | 低 | 中 — 更清晰的确认提示、错误信息 |

### 4.2 中期（0.6.x — 2–4 个月）

**目标**：扩展 Skills 与运维能力。

| # | 任务 | 工作量 | 价值 |
|---|------|--------|------|
| 1 | **Cron + Heartbeat** | 中 | 中 — 定时健康检查、主动监控 |
| 2 | **Anomaly Scanner Skill** | 中 | 中 — 分布分析、异常检测 |
| 3 | **Smart Migrator Skill** | 中 | 中 — NL → 迁移脚本、回滚、Dry-Run |
| 4 | **Data Masker Skill** | 中 | 中 — PII 检测、脱敏 |
| 5 | **多步规划** | 高 | 高 — 复杂多表任务 |
| 6 | **Telegram / Slack 通道** | 低 | 中 — 扩大通道覆盖 |

### 4.3 长期（0.7+ — 4+ 个月）

**目标**：生态与向量/AI 原生集成。

| # | 任务 | 工作量 | 价值 |
|---|------|--------|------|
| 1 | **MongoDB 适配器** | 中 | 中 — 文档库支持 |
| 2 | **多数据库连接** | 高 | 中 — 跨库对比/同步 |
| 3 | **pgvector / 向量支持** | 中 | 高 — 语义 Schema 搜索、混合查询 |
| 4 | **向量化记忆** | 中 | 高 — 语义召回 |
| 5 | **Web UI** | 高 | 中 — 更易触达 |
| 6 | **插件系统** | 高 | 中 — 社区扩展 |

---

## 5. 优先级矩阵

```
                    高价值
                         │
    Index Advisor        │  持久化记忆
    Data Healer          │  MCP 服务端
                         │
    ─────────────────────┼─────────────────────
                         │
    Anomaly Scanner      │  Cron/Heartbeat
    Smart Migrator       │  多步规划
    Data Masker          │
                         │
                    低价值
                         
         低工作量 ───────────── 高工作量
```

**建议推进顺序**：
1. 持久化记忆（Agent 智能基础）
2. MCP 服务端（生态触达）
3. Index Advisor（高频 DBA 需求）
4. Data Healer（数据治理）
5. Cron + Heartbeat（运维成熟度）

---

## 6. 风险与依赖

| 风险 | 应对 |
|------|------|
| 记忆设计复杂 | 先用简单 DB 表（schema_facts、operation_log）；语义/向量召回延后到 Phase 5+ |
| MCP 协议变更 | 遵循 MCP 规范；抽象传输层 |
| Skill 质量参差 | 增加 Skill 专项测试；文档化预期工作流 |
| 通道 API 变更 | 飞书/钉钉 SDK 版本；固定可选依赖 |

---

## 7. 版本路线图（暂定）

| 版本 | 重点 | 目标 |
|------|------|------|
| 0.5.x | 稳定性、小修复 | 当前 |
| 0.6.0 | 持久化记忆 + Index Advisor | ~1 个月 |
| 0.6.x | MCP 服务端 + Data Healer | ~2 个月 |
| 0.7.0 | Cron + Heartbeat + Anomaly Scanner | ~3 个月 |
| 0.8.0 | 向量支持、MongoDB | ~4+ 个月 |

---

## 8. 参考文档

- [PLAN_ARCHITECTURE.md](../PLAN_ARCHITECTURE.md) — 完整架构
- [SKILLS_ROADMAP.md](../SKILLS_ROADMAP.md) — Skill 目录与优先级
- [DESIGN_PLUGIN_SYSTEM.md](DESIGN_PLUGIN_SYSTEM.md) — 插件系统设计（适配器、工具、Skills、通道）
- [PLAN_SEEKDB_FORK_SANDBOX.md](PLAN_SEEKDB_FORK_SANDBOX.md) — SeekDB Fork Table 沙箱规划
- [RELEASE_NOTES.md](../../RELEASE_NOTES_CN.md) — 版本历史
- [USER_MANUAL.md](USER_MANUAL.md) — 用户手册
