# Design: read_skill Tool

> [中文版](DESIGN_READ_SKILL_TOOL_CN.md)

## Goal

Enable the agent to load Skill workflow instructions on demand via a `read_skill` tool, instead of the broken "read with read_file" instruction. The agent calls `read_skill(skill_name)` when the user's request matches a skill's purpose, then follows the loaded instructions.

---

## Overview

| Aspect | Design |
|--------|--------|
| **Tool name** | `read_skill` |
| **Parameter** | `skill_name: str` — directory name (e.g. `test_data_factory`, `data_analysis`) |
| **Returns** | Full SKILL.md content (frontmatter stripped) |
| **Security** | Only allows skill names from `SkillsLoader.list_skills()`; no arbitrary file paths |
| **Registration** | Always registered (skills are read-only, no safety policy dependency) |

---

## 1. Tool Implementation

### 1.1 New File: `queryclaw/tools/read_skill.py`

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

**Note:** Uses `SkillsLoader._strip_frontmatter` (static method) to remove YAML frontmatter from the returned content.

### 1.2 Dynamic enum

Skill names come from `list_skills()` at tool init. If the registry is built before workspace is set, built-in skills only. If workspace has skills, they are included. The `parameters` are built once at init — if skills change at runtime, the enum would be stale. For typical use (fixed builtin + workspace at startup), this is acceptable.

**Fallback:** If `list_skills()` returns empty (e.g. misconfigured path), use a minimal enum like `["data_analysis"]` to avoid schema validation failure.

---

## 2. System Prompt Changes

### 2.1 Update `build_skills_summary()` in `agent/skills.py`

**Before:**
```python
lines.append(f"  - {s['name']}: {desc} (read with read_file: {s['path']})")
```

**After:**
```python
lines.append(f"  - {s['name']}: {desc} — call read_skill(skill_name='{s['name']}') to load instructions when relevant")
```

### 2.2 Update `_get_identity()` in `agent/context.py`

**Before:**
```
- Use the Skills below for domain-specific workflows (data analysis, schema docs, AI column, test data, etc.).
```

**After:**
```
- When the user's request matches a skill's purpose (e.g. generate test data, analyze data, document schema), call read_skill first to load the workflow instructions, then follow them.
```

### 2.3 Skills section header

Keep the section as "Available skills" with the updated per-skill lines. Optionally add a one-line intro:

```
# Skills

Call read_skill(skill_name='<name>') to load full workflow instructions when the user's request matches a skill.

Available skills:
  - test_data_factory: Generate semantically realistic test data... — call read_skill(skill_name='test_data_factory') when relevant
  - data_analysis: ...
  ...
```

---

## 3. AgentLoop Integration

### 3.1 Register ReadSkillTool

In `agent/loop.py`, `_register_default_tools()`:

```python
# Add after SchemaInspectTool (or at start — read_skill has no DB/safety deps)
self.tools.register(ReadSkillTool(self.skills))
```

**Placement:** Register early so the agent sees it in the tool list. No dependency on `allows_write()`.

### 3.2 Import

```python
from queryclaw.tools.read_skill import ReadSkillTool
```

---

## 4. Security

| Concern | Mitigation |
|--------|------------|
| Arbitrary file read | Only accept `skill_name` from `list_skills()`. Tool resolves to `skills/<name>/SKILL.md` internally. |
| Path traversal | `skill_name` is validated against enum; no path concatenation from user input. |
| Workspace escape | `SkillsLoader` only reads from `builtin_skills` and `workspace_skills`; no user-specified paths. |

---

## 5. File Layout

```
queryclaw/
├── tools/
│   ├── read_skill.py    # NEW
│   ├── schema.py
│   ├── query.py
│   └── ...
├── agent/
│   ├── context.py       # Update _get_identity() guideline
│   ├── skills.py        # Update build_skills_summary()
│   └── loop.py          # Register ReadSkillTool
```

---

## 6. Tests

### 6.1 Unit: ReadSkillTool

- `test_read_skill_loads_content`: Call `execute(skill_name="data_analysis")`, assert content contains expected substring.
- `test_read_skill_not_found`: Call `execute(skill_name="nonexistent")`, assert error message.
- `test_read_skill_strips_frontmatter`: Skill with frontmatter returns body only.
- `test_read_skill_parameters_enum`: `parameters["properties"]["skill_name"]["enum"]` contains built-in skill names.

### 6.2 Integration: System prompt

- Assert `build_system_prompt()` output contains "read_skill" and no "read_file".
- Assert skill list uses "call read_skill(skill_name='...')" format.

### 6.3 Integration: Agent behavior (optional)

- User: "Generate 50 test users with orders"
- Expect: Agent calls `read_skill(skill_name="test_data_factory")` before or during execution, then follows the workflow.

---

## 7. Migration from FIX_SKILLS_INJECTION

This design **replaces** the full-injection approach in `FIX_SKILLS_INJECTION.md`:

- No `load_skills_for_context()` in system prompt.
- `build_skills_summary()` is updated, not replaced.
- New tool `read_skill` provides on-demand loading.

---

## 8. Optional Enhancements

| Enhancement | Description |
|-------------|-------------|
| **Cache in conversation** | Once a skill is read, the agent has it in message history. No need to re-read unless context is truncated. |
| **read_skill result formatting** | Optionally wrap in markdown block or add "--- Skill: X ---" header for clarity. |
| **Config: disable read_skill** | `config.agent.enable_read_skill: bool = True` to omit the tool if desired. |

---

## 9. Effort Estimate

| Task | Effort |
|------|--------|
| Implement ReadSkillTool | ~20 min |
| Update build_skills_summary | ~10 min |
| Update context identity/guidelines | ~5 min |
| Register in AgentLoop | ~5 min |
| Unit tests | ~20 min |
| Integration test | ~15 min |

**Total:** ~1.5 hours.
