# QueryClaw 用户手册

**版本 0.1.x** — 只读数据库 Agent（Phase 1 MVP）

本文介绍如何安装、配置和使用 QueryClaw，通过自然语言与数据库对话。

---

## 目录

1. [什么是 QueryClaw？](#什么是-queryclaw)
2. [环境要求](#环境要求)
3. [安装](#安装)
4. [快速开始](#快速开始)
5. [配置说明](#配置说明)
6. [命令参考](#命令参考)
7. [对话模式](#对话模式)
8. [内置工具](#内置工具)
9. [技能](#技能)
10. [常见问题](#常见问题)

---

## 什么是 QueryClaw？

QueryClaw 是一个 **AI 原生数据库 Agent**，可以用自然语言向数据库提问。Agent 使用 **ReACT 循环**（推理 + 行动）：查看表结构、执行只读 SQL、查看执行计划，均通过自然语言完成。

**当前版本（Phase 1）** 支持：

- **数据库：** SQLite、MySQL  
- **LLM 提供方：** OpenRouter、Anthropic、OpenAI、DeepSeek、Gemini、DashScope、Moonshot（通过 [LiteLLM](https://github.com/BerriAI/litellm)）  
- **工具：** 结构查看、只读查询执行、EXPLAIN 计划  
- **CLI：** `onboard`（创建配置）、`chat`（交互或单轮对话）

---

## 环境要求

- **Python** 3.10 或更高  
- **网络** 可访问你的数据库及所选 LLM 的 API  
- 至少一个支持的 LLM 提供方的 **API Key**

---

## 安装

```bash
pip install queryclaw
```

安装指定版本：

```bash
pip install queryclaw==0.1.1
```

验证：

```bash
queryclaw --version
```

---

## 快速开始

1. **创建配置**

   ```bash
   queryclaw onboard
   ```

   会在 `~/.queryclaw/config.json` 生成默认配置。

2. **编辑配置**

   打开 `~/.queryclaw/config.json`，设置：

   - **数据库：** SQLite 时将 `database.type` 设为 `"sqlite"`，`database.database` 设为 `.db` 文件路径；MySQL 时设置 `type`、`host`、`port`、`database`、`user`、`password`。
   - **LLM：** 在 `providers` 下至少为一个提供方设置 `api_key`（如 `providers.anthropic.api_key` 或 `providers.openrouter.api_key`）。

3. **开始对话**

   单次提问：

   ```bash
   queryclaw chat -m "这个数据库里有哪些表？"
   ```

   交互式对话：

   ```bash
   queryclaw chat
   ```

   输入问题即可；输入 `exit` 或 `quit` 结束会话。

---

## 配置说明

配置为 **JSON** 格式，默认路径为 `~/.queryclaw/config.json`。可使用 `--config` / `-c` 指定其他文件。

### 配置结构

| 节点       | 说明 |
|------------|------|
| `database` | 要连接的数据库（SQLite/MySQL）的连接信息。 |
| `providers`| 各 LLM 提供方的 API Key 及可选 base URL。 |
| `agent`    | 模型名、迭代次数、温度、最大 token 等。 |

### 数据库 (database)

| 字段       | 类型   | 默认值       | 说明 |
|------------|--------|--------------|------|
| `type`     | string | `"sqlite"`   | `"sqlite"` 或 `"mysql"`。 |
| `host`     | string | `"localhost"`| 主机（MySQL）。 |
| `port`     | int    | `3306`       | 端口（MySQL）。 |
| `database` | string | `""`         | 数据库名（MySQL）或 SQLite 文件路径（如 `"/path/to/app.db"`）。 |
| `user`     | string | `""`         | 用户名（MySQL）。 |
| `password` | string | `""`         | 密码（MySQL）。 |

**SQLite 示例：**

```json
"database": {
  "type": "sqlite",
  "database": "/path/to/mydb.db"
}
```

**MySQL 示例：**

```json
"database": {
  "type": "mysql",
  "host": "localhost",
  "port": 3306,
  "database": "mydb",
  "user": "myuser",
  "password": "mypass"
}
```

### 提供方 (providers)

至少为一个提供方设置 `api_key`。可选：`api_base`、`extra_headers`。

| 提供方     | 配置键               | 说明 |
|------------|----------------------|------|
| OpenRouter | `providers.openrouter` | 通过统一 API 使用多种模型；如需可设 `api_base` 为 `https://openrouter.ai/api/v1`。 |
| Anthropic  | `providers.anthropic` | Claude 系列（如 `anthropic/claude-sonnet-4-5`）。 |
| OpenAI     | `providers.openai`    | GPT 系列。 |
| DeepSeek   | `providers.deepseek`  | DeepSeek 模型。 |
| Gemini     | `providers.gemini`    | Google Gemini。 |
| DashScope  | `providers.dashscope` | 阿里云百炼。 |
| Moonshot   | `providers.moonshot`  | 月之暗面（Kimi）。 |

**示例（Anthropic）：**

```json
"providers": {
  "anthropic": {
    "api_key": "sk-ant-...",
    "api_base": "",
    "extra_headers": {}
  }
}
```

**示例（OpenRouter）：**

```json
"providers": {
  "openrouter": {
    "api_key": "sk-or-...",
    "api_base": "https://openrouter.ai/api/v1",
    "extra_headers": {}
  }
}
```

Agent 会根据 **模型名** 自动选择提供方（如 `openrouter/...`、`anthropic/...`）。也可通过 `agent.provider` 强制指定（见下）。

### Agent (agent)

| 字段             | 类型   | 默认值                           | 说明 |
|------------------|--------|----------------------------------|------|
| `model`          | string | `"anthropic/claude-sonnet-4-5"` | 模型标识（如 `openrouter/meta-llama/llama-3.1-70b`、`anthropic/claude-sonnet-4-5`）。 |
| `provider`       | string | `"auto"`                         | `"auto"`（按模型自动）或提供方名称（如 `openrouter`、`anthropic`）。 |
| `max_iterations` | int    | `30`                             | 每轮最大 ReACT 步数。 |
| `temperature`    | float  | `0.1`                            | LLM 采样温度。 |
| `max_tokens`     | int    | `4096`                           | 单次回复最大 token 数。 |

---

## 命令参考

### 全局选项

- **`--version`**、**`-v`** — 显示版本并退出。

### `queryclaw onboard`

创建或刷新配置文件。

```bash
queryclaw onboard [--config PATH] [--overwrite]
```

| 选项          | 简写 | 说明 |
|---------------|------|------|
| `--config`   | `-c` | 配置文件路径（默认：`~/.queryclaw/config.json`）。 |
| `--overwrite`|      | 用默认配置覆盖已有文件（不指定则只补充缺失字段）。 |

- 不指定 `--overwrite`：若文件已存在，会加载后写回（仅补充缺失字段）。  
- 指定 `--overwrite`：用默认配置覆盖整个文件。

### `queryclaw chat`

启动与数据库 Agent 的对话。

```bash
queryclaw chat [-m 问题] [--config PATH] [--no-markdown]
```

| 选项           | 简写 | 说明 |
|----------------|------|------|
| `--message`   | `-m` | 单次提问内容；省略则进入交互模式。 |
| `--config`    | `-c` | 配置文件路径（默认：`~/.queryclaw/config.json`）。 |
| `--no-markdown`|      | 助手回复以纯文本显示，不渲染 Markdown。 |

**示例：**

```bash
queryclaw chat -m "列出所有表"
queryclaw chat -m "users 表有多少行？"
queryclaw chat
queryclaw chat -c /path/to/config.json
```

---

## 对话模式

- **单轮：** `queryclaw chat -m "你的问题"` — 问一句、答一句后退出。  
- **交互：** `queryclaw chat` — 同一会话内连续多轮提问，会话内会保留对话历史。

**退出交互：** 输入以下之一即可：`exit`、`quit`、`/exit`、`/quit`、`:q`（不区分大小写）。或按 **Ctrl+C**。

默认按 **Markdown** 渲染回复；加 `--no-markdown` 则按纯文本显示。

---

## 内置工具

Agent 在 ReACT 循环中会自动调用以下工具，用户无需直接调用。

| 工具               | 说明 |
|--------------------|------|
| **schema_inspect** | 列出表；查看指定表的列、索引、外键。 |
| **query_execute**  | 执行 **只读** SQL（仅 SELECT），结果行数有限制。 |
| **explain_plan**   | 对给定 SQL 显示执行计划（EXPLAIN）。 |

Phase 1 为 **只读**：不支持 INSERT/UPDATE/DELETE 或 DDL。

---

## 技能

技能用于在特定类型任务上引导 Agent 行为，通过 `SKILL.md` 文件加载（如安装包内的 `queryclaw/skills/` 目录）。

**Phase 1 内置技能：**

- **Data Analysis（数据分析）** — 引导 Agent 查看结构、执行 SELECT、汇总数据并报告规律或异常。

自定义技能可将 `SKILL.md` 放到对应技能目录，格式与路线图见架构与技能文档。

---

## 常见问题

### “No LLM API key configured”（未配置 LLM API Key）

- 在 `~/.queryclaw/config.json` 中至少为某一个 `providers.<名称>.api_key` 填写有效 Key。  
- 修改配置后重新执行 `queryclaw chat`。

### “Failed to load config” / JSON 报错

- 检查 `config.json` 是否为合法 JSON（逗号、引号、无多余逗号）。  
- 可执行 `queryclaw onboard --overwrite` 重新生成默认配置后再编辑。

### 数据库连接失败

- **SQLite：** 确认 `database.database` 为存在的 `.db` 文件完整路径，且当前用户有读权限。  
- **MySQL：** 检查 `host`、`port`、`database`、`user`、`password`；确认 MySQL 允许当前主机连接，且该用户具备 SELECT 及元数据查询权限。

### 用错提供方或模型

- 将 `agent.provider` 设为提供方名称（如 `openrouter`、`anthropic`）可强制使用该 API。  
- 模型字符串需与提供方匹配（如 `openrouter/meta-llama/llama-3.1-70b`、`anthropic/claude-sonnet-4-5`）。

### 版本

- 查看已安装版本：`queryclaw --version`。  
- 升级：`pip install -U queryclaw`。

---

## 相关文档

- [架构与实现计划](PLAN_ARCHITECTURE_CN.md)（[英文](PLAN_ARCHITECTURE.md)）  
- [技能路线图](SKILLS_ROADMAP_CN.md)（[英文](SKILLS_ROADMAP.md)）  
- [Phase 1 计划归档](PLAN_PHASE1_ARCHIVE.md)
