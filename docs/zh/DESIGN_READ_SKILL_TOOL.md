# 设计：read_skill 工具

> [English](DESIGN_READ_SKILL_TOOL.md)

## 目标

通过 `read_skill` 工具让 Agent 按需加载 Skill 工作流说明，替代当前无效的「read with read_file」提示。当用户请求与某 Skill 用途匹配时，Agent 调用 `read_skill(skill_name)` 获取完整说明，再按说明执行。

---

## 概述

| 方面 | 设计 |
|------|------|
| **工具名** | `read_skill` |
| **参数** | `skill_name: str` — 目录名（如 `test_data_factory`、`data_analysis`） |
| **返回值** | SKILL.md 完整内容（去除 frontmatter） |
| **安全** | 仅接受 `SkillsLoader.list_skills()` 返回的 skill 名称；不接受任意文件路径 |
| **注册** | 始终注册（Skill 为只读，不依赖安全策略） |

---

## 1. 工具实现

### 1.1 新文件：`queryclaw/tools/read_skill.py`

```python
"""Read skill tool for loading workflow instructions on demand."""

from __future__ import annotations

from typing import Any

from queryclaw.agent.skills import SkillsLoader
from queryclaw.tools.base import Tool


class ReadSkillTool(Tool):
    """Load a skill's full workflow instructions. Call this when the user's request
    matches a skill's purpose (e.g. test data generation, data analysis)."""

    def __init__(self, skills: SkillsLoader) -> None:
        self._skills = skills

    @property
    def name(self) -> str:
        return "read_skill"

    @property
    def description(self) -> str:
        return (
            "Load the full workflow instructions for a skill. Call this when the user "
            "asks for tasks that match a skill (e.g. generate test data → test_data_factory, "
            "analyze data → data_analysis). Returns the skill's SKILL.md content."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        skill_names = [s["name"] for s in self._skills.list_skills()]
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "enum": skill_names if skill_names else ["data_analysis"],
                    "description": "Skill name (directory name, e.g. test_data_factory, data_analysis).",
                },
            },
            "required": ["skill_name"],
        }

    async def execute(self, skill_name: str, **kwargs: Any) -> str:
        content = self._skills.load_skill(skill_name)
        if not content:
            return f"Error: Skill '{skill_name}' not found."
        from queryclaw.agent.skills import SkillsLoader
        return SkillsLoader._strip_frontmatter(content)
```

**说明：** 使用 `SkillsLoader._strip_frontmatter`（静态方法）去除 YAML frontmatter。

### 1.2 动态 enum

`skill_name` 的 enum 在工具初始化时由 `list_skills()` 生成。若在设置 workspace 之前构建，则仅包含内置 Skill；若已设置 workspace，则一并包含。`parameters` 在初始化时确定，之后不再更新。对典型使用（固定内置 + 启动时 workspace）可接受。

**兜底：** 若 `list_skills()` 为空（如路径配置错误），使用最小 enum `["data_analysis"]`，避免 schema 校验失败。

---

## 2. 系统提示变更

### 2.1 更新 `skills.py` 中的 `build_skills_summary()`

**修改前：**
```python
lines.append(f"  - {s['name']}: {desc} (read with read_file: {s['path']})")
```

**修改后：**
```python
lines.append(f"  - {s['name']}: {desc} — call read_skill(skill_name='{s['name']}') to load instructions when relevant")
```

### 2.2 更新 `context.py` 中的 `_get_identity()`

**修改前：**
```
- Use the Skills below for domain-specific workflows (data analysis, schema docs, AI column, test data, etc.).
```

**修改后：**
```
- When the user's request matches a skill's purpose (e.g. generate test data, analyze data, document schema), call read_skill first to load the workflow instructions, then follow them.
```

### 2.3 Skills 区块标题

保留「Available skills」标题，并更新每行说明。可选增加一行引导：

```
# Skills

Call read_skill(skill_name='<name>') to load full workflow instructions when the user's request matches a skill.

Available skills:
  - test_data_factory: Generate semantically realistic test data... — call read_skill(skill_name='test_data_factory') when relevant
  - data_analysis: ...
  ...
```

---

## 3. AgentLoop 集成

### 3.1 注册 ReadSkillTool

在 `agent/loop.py` 的 `_register_default_tools()` 中：

```python
# 在 SchemaInspectTool 之后或开头注册 — read_skill 无 DB/安全依赖
self.tools.register(ReadSkillTool(self.skills))
```

**位置：** 尽早注册，使 Agent 可见。不依赖 `allows_write()`。

### 3.2 导入

```python
from queryclaw.tools.read_skill import ReadSkillTool
```

---

## 4. 安全

| 关注点 | 措施 |
|--------|------|
| 任意文件读取 | 仅接受 `list_skills()` 返回的 skill 名称；工具内部解析为 `skills/<name>/SKILL.md`。 |
| 路径遍历 | `skill_name` 通过 enum 校验；不对用户输入做路径拼接。 |
| 工作区逃逸 | `SkillsLoader` 仅从 `builtin_skills` 和 `workspace_skills` 读取；不接收用户指定路径。 |

---

## 5. 文件结构

```
queryclaw/
├── tools/
│   ├── read_skill.py    # 新增
│   ├── schema.py
│   ├── query.py
│   └── ...
├── agent/
│   ├── context.py       # 更新 _get_identity() 引导语
│   ├── skills.py        # 更新 build_skills_summary()
│   └── loop.py          # 注册 ReadSkillTool
```

---

## 6. 测试

### 6.1 单元：ReadSkillTool

- `test_read_skill_loads_content`：调用 `execute(skill_name="data_analysis")`，断言返回内容包含预期子串。
- `test_read_skill_not_found`：调用 `execute(skill_name="nonexistent")`，断言错误信息。
- `test_read_skill_strips_frontmatter`：带 frontmatter 的 Skill 仅返回正文。
- `test_read_skill_parameters_enum`：`parameters["properties"]["skill_name"]["enum"]` 包含内置 Skill 名称。

### 6.2 集成：系统提示

- 断言 `build_system_prompt()` 输出包含 "read_skill" 且不含 "read_file"。
- 断言 Skill 列表使用 "call read_skill(skill_name='...')" 格式。

### 6.3 集成：Agent 行为（可选）

- 用户：「生成 50 个测试用户及其订单」
- 预期：Agent 在执行前或执行中调用 `read_skill(skill_name="test_data_factory")`，并按工作流执行。

---

## 7. 与 FIX_SKILLS_INJECTION 的关系

本设计**替代** `FIX_SKILLS_INJECTION.md` 中的全量注入方案：

- 不在 system prompt 中使用 `load_skills_for_context()`。
- 更新 `build_skills_summary()`，而非替换。
- 通过新工具 `read_skill` 实现按需加载。

---

## 8. 可选增强

| 增强 | 说明 |
|------|------|
| **对话内缓存** | 一旦读取某 Skill，内容会留在消息历史中；除非上下文被截断，无需重复读取。 |
| **read_skill 返回格式** | 可选：用 markdown 块包裹或添加 "--- Skill: X ---" 标题。 |
| **配置：禁用 read_skill** | `config.agent.enable_read_skill: bool = True`，可按需关闭该工具。 |

---

## 9. 工作量估算

| 任务 | 预估 |
|------|------|
| 实现 ReadSkillTool | ~20 分钟 |
| 更新 build_skills_summary | ~10 分钟 |
| 更新 context 身份/引导语 | ~5 分钟 |
| 在 AgentLoop 中注册 | ~5 分钟 |
| 单元测试 | ~20 分钟 |
| 集成测试 | ~15 分钟 |

**合计：** 约 1.5 小时。
