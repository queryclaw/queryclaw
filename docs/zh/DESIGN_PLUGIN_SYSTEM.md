# QueryClaw 插件系统 — 设计文档

> [English](../DESIGN_PLUGIN_SYSTEM.md)

**状态**：设计 / 规划中  
**阶段**：Phase 5（生态集成）  
**更新日期**：2026-02-27

---

## 1. 概述

插件系统允许第三方代码在不修改 QueryClaw 核心的前提下扩展能力。插件可扩展：

- **数据库适配器** — 支持新数据库类型（MongoDB、Redis、ClickHouse 等）
- **工具** — 新的 Agent 能力（自定义查询、集成、工作流）
- **Skills** — 新的 SKILL.md 工作流（从插件路径加载）
- **通道** — 新的通信渠道（Telegram、Slack、Discord 等）
- **LLM 提供者** — 自定义提供者逻辑（如本地模型封装）
- **安全钩子** — 自定义校验、限流、审计扩展

---

## 2. 设计目标

| 目标 | 说明 |
|------|------|
| **可发现性** | 通过 Python entry points 或配置自动发现插件 |
| **隔离性** | 插件错误不导致核心崩溃；可选沙箱 |
| **版本兼容** | 插件声明 QueryClaw 版本兼容范围 |
| **配置驱动** | 通过 `config.json` 启用/禁用和配置插件 |
| **最小接口** | 清晰、稳定的插件 API；内部实现可变更 |

---

## 3. 插件类型与扩展点

### 3.1 数据库适配器插件

**扩展点**：`queryclaw.db.adapters`

**接口**：实现 `DatabaseAdapter`（或 SQL 库的 `SQLAdapter`）

**示例**：
```python
# my_plugin/db_clickhouse.py
from queryclaw.db.base import SQLAdapter, QueryResult

class ClickHouseAdapter(SQLAdapter):
    @property
    def db_type(self) -> str:
        return "clickhouse"
    # ... 实现 connect, execute, get_tables 等
```

**注册**（通过 entry point）：
```toml
# pyproject.toml
[project.entry-points."queryclaw.db.adapters"]
clickhouse = "my_plugin.db_clickhouse:ClickHouseAdapter"
```

**配置**：
```json
{
  "database": {
    "type": "clickhouse",
    "host": "localhost",
    "port": 9000
  }
}
```

---

### 3.2 工具插件

**扩展点**：`queryclaw.tools`

**接口**：实现 `Tool` 基类（name、description、parameters、execute）

**示例**：
```python
# my_plugin/tools/export_csv.py
from queryclaw.tools.base import Tool

class ExportCSVTool(Tool):
    @property
    def name(self) -> str:
        return "export_csv"
    @property
    def description(self) -> str:
        return "将查询结果导出为 CSV 文件。"
    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"sql": {...}, "path": {...}}}
    async def execute(self, sql: str, path: str, **kwargs) -> str:
        # ...
```

**注册**：
```toml
[project.entry-points."queryclaw.tools"]
export_csv = "my_plugin.tools.export_csv:ExportCSVTool"
```

**工具工厂**：工具可能需要注入 `db`、`policy`、`audit`。插件系统可支持：
- **类注册**：插件注册类；QueryClaw 实例化时注入依赖
- **工厂注册**：插件注册工厂 `(db, policy, ...) -> Tool`

---

### 3.3 Skill 插件

**扩展点**：`queryclaw.skills.paths`

**接口**：包含 `SKILL.md` 的目录路径（格式与内置 Skill 相同）

**示例**：
```
my_plugin/
  skills/
    custom_export/
      SKILL.md
    data_quality_report/
      SKILL.md
```

**注册**：
```toml
[project.entry-points."queryclaw.skills.paths"]
my_plugin = "my_plugin.skills"
```

或通过配置：
```json
{
  "skills": {
    "extra_paths": ["/path/to/my/skills", "my_plugin.skills"]
  }
}
```

**SkillsLoader** 在加载时合并内置路径与插件路径。

---

### 3.4 通道插件

**扩展点**：`queryclaw.channels`

**接口**：实现 `Channel` 接口（connect、send、receive、disconnect）

**示例**：
```python
# my_plugin/channels/telegram.py
from queryclaw.channels.base import Channel

class TelegramChannel(Channel):
    ...
```

**注册**：
```toml
[project.entry-points."queryclaw.channels"]
telegram = "my_plugin.channels.telegram:TelegramChannel"
```

**配置**：
```json
{
  "serve": {
    "channel": "telegram",
    "telegram": {
      "bot_token": "...",
      "allowed_chat_ids": [...]
    }
  }
}
```

---

### 3.5 LLM 提供者插件

**扩展点**：`queryclaw.providers`

**接口**：实现 `LLMProvider`（chat、get_default_model）

**用途**：自定义 API 封装、本地模型服务、A/B 测试层等。

---

### 3.6 安全钩子插件

**扩展点**：`queryclaw.safety.hooks`

**接口**：在安全流水线特定节点调用的回调

**示例钩子**：
- `before_validate(sql, context)` → 返回修改后的 SQL 或抛出以阻止
- `after_audit(entry, result)` → 自定义日志、指标
- `rate_limit(operation, session)` → 按会话限流

---

## 4. 发现与加载

### 4.1 Entry Points（主要方式）

使用 `importlib.metadata.entry_points()`（Python 3.10+）发现插件：

```python
def load_plugins():
    eps = entry_points(group="queryclaw.db.adapters")
    for ep in eps:
        adapter_cls = ep.load()
        AdapterRegistry.register(ep.name, adapter_cls)
```

### 4.2 配置覆盖

`config.json` 可显式启用/禁用插件：

```json
{
  "plugins": {
    "enabled": ["clickhouse", "export_csv", "telegram"],
    "disabled": ["experimental_feature"],
    "paths": ["/opt/queryclaw-plugins"]
  }
}
```

### 4.3 加载顺序

1. 内置组件（始终加载）
2. Entry point 插件（来自已安装包）
3. 路径插件（来自 `plugins.paths`）
4. 配置可禁用上述任意项

---

## 5. 生命周期

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   发现      │ ──► │   校验       │ ──► │   加载      │
│  (entry pts)│     │  (版本、依赖) │     │  (注册到    │
│             │     │              │     │   Registry) │
└─────────────┘     └──────────────┘     └─────────────┘
                                 │
                                 ▼
                    ┌──────────────┐     ┌─────────────┐
                    │   激活       │ ──► │   卸载      │
                    │  (serve/     │     │  (可选)     │
                    │   chat 启动) │     │             │
                    └──────────────┘     └─────────────┘
```

**校验**：检查插件元数据中的 `queryclaw_version`（如 `>=0.5.0,<0.7`）。

---

## 6. 插件元数据

每个插件包可声明：

```toml
# pyproject.toml
[project]
name = "queryclaw-clickhouse"
version = "0.1.0"
dependencies = ["queryclaw>=0.5.0,<0.7"]

[project.entry-points."queryclaw.db.adapters"]
clickhouse = "queryclaw_clickhouse:ClickHouseAdapter"
```

可选元数据（如 `queryclaw_plugin.json`）：

```json
{
  "id": "queryclaw-clickhouse",
  "name": "ClickHouse 适配器",
  "description": "连接 QueryClaw 与 ClickHouse",
  "queryclaw_version": ">=0.5.0,<0.7",
  "author": "...",
  "license": "MIT"
}
```

---

## 7. 安全与沙箱

| 关注点 | 方案 |
|--------|------|
| **恶意插件** | 插件与主进程同进程；信任模型：仅从可信源安装（PyPI、内网）。默认无沙箱。 |
| **插件异常** | 用 try/except 包裹插件执行；记录并继续。可选：N 次失败后禁用插件。 |
| **资源限制** | 可选：单次工具执行超时；内存限制（进阶）。 |
| **敏感数据** | 插件仅接收 QueryClaw 传入的 db、config。除非插件显式读取，否则不暴露原始 env。 |

**未来**：对不可信插件的可选沙箱（如子进程、受限执行）— 不在首版设计中。

---

## 8. 实现阶段

### Phase 5a：适配器与工具插件（MVP）

- 新增 `PluginLoader` 发现 entry points
- 扩展 `AdapterRegistry` 接受插件注册的适配器
- 扩展 `ToolRegistry` 接受插件注册的工具（含工厂支持）
- 配置：`plugins.enabled`、`plugins.disabled`
- CLI：`queryclaw plugins list` 列出已加载插件

### Phase 5b：Skill 与通道插件

- 扩展 `SkillsLoader` 包含插件 Skill 路径
- 通道 Registry + 插件通道加载
- 配置：`serve.channel` 可为插件名

### Phase 5c：提供者与安全钩子

- 提供者插件支持
- 安全钩子接口与调用点
- 插件作者文档

---

## 9. 示例：完整插件包

```
queryclaw-clickhouse/
├── pyproject.toml
├── src/
│   └── queryclaw_clickhouse/
│       ├── __init__.py
│       ├── adapter.py      # ClickHouseAdapter
│       └── queryclaw_plugin.json
└── README.md
```

**pyproject.toml**：
```toml
[project]
name = "queryclaw-clickhouse"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["queryclaw>=0.5.0", "clickhouse-connect"]

[project.entry-points."queryclaw.db.adapters"]
clickhouse = "queryclaw_clickhouse.adapter:ClickHouseAdapter"
```

**使用**：
```bash
pip install queryclaw queryclaw-clickhouse
# config.json: database.type = "clickhouse"
```

---

## 10. 与替代方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Entry points** | 标准、可发现、无需配置即可发现 | 需安装包 |
| **MCP 服务** | 独立进程、语言无关 | 较重；独立协议 |
| **仅配置路径** | 简单、无代码 | 需手动管理路径 |
| **插件市场** | 集中发现 | 需配套基础设施 |

**建议**：先以 entry points 支持适配器和工具；Skill 用配置路径补充。MCP 后续可作为：1）将 QueryClaw 暴露为工具供其他 Agent 使用；2）将外部工具作为插件消费。

---

## 11. 参考

- [Python Packaging](https://packaging.python.org/) — entry points
- [importlib.metadata.entry_points](https://docs.python.org/3/library/importlib.metadata.html#entry-points)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — 未来工具集成
