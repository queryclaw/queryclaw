# Token 优化

> 实施版本：v0.5.4 – v0.5.6（2026-02-28）

## 背景

优化前，每次 LLM 调用的系统提示词中包含全部 32 张表的完整列定义（约 3000 tokens），SKILL.md 全文在 agent loop 后续迭代中反复发送（约 1000 tokens），冗长的 assistant 回复在对话历史中不断累积，交互指引存在重复子节。一个典型的多轮对话消耗约 35,000 tokens，其中约 60% 为冗余内容。

## 变更总览

| 版本 | 变更内容 | 预估节省 |
|------|---------|---------|
| v0.5.4 | Schema 精简 + 过滤内部表 + 交互指引精简 | ~3,300 tokens/轮 |
| v0.5.5 | Agent Loop 消息压缩 + 记忆截断 + SELECT 约束提示 | ~6,000+ tokens/会话 |
| v0.5.6 | 强制 `schema_inspect`，防止列名猜测 | 避免错误迭代浪费 |

## 详细变更

### 1. Schema 精简（v0.5.4）

**文件**：`queryclaw/agent/context.py` — `_get_schema_summary()`

优化前：

```
## maintenance_records (4 rows)
  - id: int(11) [PK] NOT NULL
  - vehicle_id: int(11) NOT NULL
  - maintenance_type: enum(...) NOT NULL
  - title: varchar(200)
  - description: text
  - cost: decimal(10,2)
  - scheduled_date: date
  ... （32 张表全部列出）
```

优化后：

```
Tables (31):
  - alert_rules (5 rows)
  - drivers (8 rows)
  - maintenance_records (4 rows)
  ...

Column details are NOT listed above. You MUST call `schema_inspect` before writing any query.
```

关键决策：
- 仅保留表名和行数；列详情通过 `schema_inspect` 按需获取。
- 以 `_queryclaw` 为前缀的内部表（如 `_queryclaw_audit_log`）从摘要中排除。
- 对于 32 张表的数据库，每次 LLM 调用节省约 2,800 tokens。

### 2. 过滤内部表（v0.5.4）

**文件**：`queryclaw/agent/context.py` — `_get_schema_summary()`

```python
user_tables = [t for t in tables if not t.name.startswith("_queryclaw")]
```

防止 LLM 看到或操作内部审计表。节省约 150 tokens，同时避免对内部表的误操作。

### 3. 交互指引精简（v0.5.4）

**文件**：`queryclaw/agent/context.py` — `_get_guidelines()`

优化前：4 个子节（Response Style、Workflow、Skills、Integrity）— 约 500 tokens。

优化后：9 条精炼准则 — 约 180 tokens。去除了与 Skills 模块重复的子节。

### 4. Agent Loop 消息压缩（v0.5.5）

**文件**：`queryclaw/agent/loop.py` — `_compact_messages()`

在多迭代 agent loop 中，旧消息不断累积（tool 结果、assistant 回复）。每次 LLM 调用前，`_compact_messages()` 生成一个 token 高效的副本：

| 消息类型 | 阈值 | 截断方式 |
|---------|------|---------|
| Tool 结果（如 `read_skill` 返回的 SKILL.md） | > 500 字符 | 保留前 300 字符 + `[... truncated ...]` |
| Assistant 文本回复 | > 300 字符 | 保留前 200 字符 + `[... truncated ...]` |
| System prompt | — | 始终完整保留 |
| 最近 6 条消息 | — | 始终完整保留 |

常量定义：

```python
_COMPACT_KEEP_TAIL = 6    # 保留最近 N 条消息不截断
_COMPACT_TOOL_MAX  = 500  # Tool 结果超过此长度则截断
_COMPACT_ASST_MAX  = 300  # Assistant 文本超过此长度则截断
```

原始 `messages` 列表保持不变（用于追加新 tool 结果），仅压缩副本发送给 LLM。

### 5. 记忆截断（v0.5.5）

**文件**：`queryclaw/agent/memory.py` — `MemoryStore.add()`

存入对话记忆（跨轮历史）的 assistant 回复超过 800 字符时截断为 600 字符：

```python
_MEMORY_ASST_MAX = 800

if role == "assistant" and len(content) > _MEMORY_ASST_MAX:
    content = content[:600] + "\n\n[... response truncated ...]"
```

防止冗长的 assistant 回复（如详细分析报告）在后续轮次中膨胀 prompt。

### 6. SELECT 约束提示（v0.5.5）

**文件**：`queryclaw/skills/data_detective/SKILL.md`

在最容易出错的技能中添加明确约束：

```markdown
> **Constraint**: `query_execute` only accepts `SELECT` (including `WITH ... SELECT`).
> Do not use `CREATE TEMPORARY TABLE`, `SET`, or any non-SELECT statement with it.
> For derived computations, use subqueries or CTEs.
```

**文件**：`queryclaw/agent/context.py` — `_get_guidelines()`

在交互指引中新增规则：

```
- `query_execute` only accepts SELECT (including WITH...SELECT) — use `data_modify` or `ddl_execute` for other statements.
```

### 7. 强制 schema_inspect（v0.5.6）

**文件**：`queryclaw/agent/context.py`

Schema 精简后，LLM 偶尔猜测列名（如将 `scheduled_date` 猜为 `maintenance_date`）。在三个位置将指令从建议性改为强制性：

| 位置 | 措辞 |
|------|------|
| Identity 段 | "column details are **NOT provided**. You **MUST** call `schema_inspect`...Never guess column names." |
| Schema 段尾 | "Column details are **NOT** listed above. You **MUST** call `schema_inspect` before writing any query." |
| Guidelines | "**MUST** call `schema_inspect`...column names are not in the prompt; guessing will fail." |

## 权衡

| 收益 | 代价 |
|------|------|
| 每会话 token 消耗减少约 60% | LLM 在查询新表前需额外调用一次 `schema_inspect` |
| LLM 响应更快（输入量更少） | LLM 偶尔忽略指令猜测列名（已由 v0.5.6 缓解） |
| API 成本降低 | 首次涉及新表时工具调用略增 |
| 降低 LLM 操作内部表的风险 | 无 |

## 参数调优

截断阈值通过模块级常量配置：

| 常量 | 文件 | 默认值 | 用途 |
|------|------|-------|------|
| `_COMPACT_KEEP_TAIL` | `loop.py` | 6 | Agent loop 中保留最近 N 条消息不截断 |
| `_COMPACT_TOOL_MAX` | `loop.py` | 500 | Tool 结果截断阈值 |
| `_COMPACT_ASST_MAX` | `loop.py` | 300 | Assistant 文本截断阈值 |
| `_MEMORY_ASST_MAX` | `memory.py` | 800 | 对话记忆中 assistant 回复截断阈值 |

对于表数量很少（< 5 张）的数据库，schema 精简带来的节省较小，可考虑恢复完整列定义（回退 `_get_schema_summary()`）。
