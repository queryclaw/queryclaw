# 修复计划：Skills 内容注入

> [English](FIX_SKILLS_INJECTION.md)

## 问题概述

Agent 无法使用 Skills 的原因：

1. **`build_skills_summary()`** 告诉 Agent「read with read_file: {path}」——但不存在 `read_file` 工具。
2. **`load_skills_for_context()`** 已实现且可注入完整 Skill 内容，但**从未被调用**。
3. Agent 只能看到 Skill 名称和描述列表，看不到实际的工作流说明。

**结果：** Agent 退而使用手动工具调用（如用 `data_modify` 逐条插入测试数据），而不是遵循 `test_data_factory` 等 Skill 中的结构化工作流。

---

## 修复策略

**将完整 Skill 内容注入 system prompt**，替代误导性的「read with read_file」摘要。

- 6 个内置 Skill 合计约 13KB —— 对 system prompt 可接受。
- 无需新增工具或 API。
- `load_skills_for_context()` 已存在，只需调用即可。

---

## 实现计划

### 阶段一：核心修复（必做）

| 步骤 | 文件 | 变更 |
|------|------|------|
| 1.1 | `agent/context.py` | 在 `build_system_prompt()` 中，用 `load_skills_for_context(all_skill_names)` 替代 `build_skills_summary()`，注入完整内容。 |
| 1.2 | `agent/skills.py` | 视需要保留或调整 `build_skills_summary()`；ContextBuilder 改为使用 `load_skills_for_context()`。 |
| 1.3 | `agent/context.py` | 更新 Skills 区块的引导语：「以下 Skills 描述工作流。当用户请求与某 Skill 用途匹配时，请遵循该 Skill。」 |

### 阶段二：清理与健壮性

| 步骤 | 文件 | 变更 |
|------|------|------|
| 2.1 | `agent/skills.py` | 若 `build_skills_summary()` 仍被使用，移除或修正「read with read_file」表述；否则可弃用。 |
| 2.2 | 测试 | 在 `test_skills.py` 或 `test_agent.py` 中增加断言：ContextBuilder 构建的 system prompt 包含 Skill 内容（如 test_data_factory、schema_inspect 等）。 |
| 2.3 | 文档 | 更新 USER_MANUAL、SELF_EVOLUTION_ANALYSIS，说明 Skills 通过 system prompt 注入，而非通过工具读取。 |

### 阶段三：可选增强

| 步骤 | 说明 |
|------|------|
| 3.1 | **Skill 筛选**：若 prompt 过长，可仅注入与用户消息匹配的 Skill（需简单意图匹配）。 |
| 3.2 | **配置项**：`config.agent.inject_skills: "all" | "summary" | "none"` —— "all" 为完整内容（默认），"summary" 仅名称，"none" 不注入。 |

---

## 代码变更详情

### 1. `agent/context.py`

**修改前：**
```python
skills_summary = self._skills.build_skills_summary()
if skills_summary:
    parts.append(f"# Skills\n\n{skills_summary}")
```

**修改后：**
```python
all_skill_names = [s["name"] for s in self._skills.list_skills()]
skills_content = self._skills.load_skills_for_context(all_skill_names)
if skills_content:
    parts.append(f"# Skills\n\nThese workflows guide you for specific tasks. Follow the relevant skill when the user's request matches its purpose.\n\n{skills_content}")
```

### 2. `agent/skills.py`

- **方案 A**：保留 `build_skills_summary()` 供其他场景使用，但 ContextBuilder 不再用它构建主 prompt。
- **方案 B**：新增 `build_full_skills_content()` 封装 `load_skills_for_context()`，由 ContextBuilder 调用。

建议：**方案 A** —— ContextBuilder 直接调用 `load_skills_for_context()`，无需新增方法。

### 3. Identity 引导语（context.py 第 144 行）

**修改前：**
```
- Use the Skills below for domain-specific workflows (data analysis, schema docs, AI column, test data, etc.).
```

**修改后：**
```
- The Skills section below contains full workflow instructions. Follow the relevant skill (e.g. test_data_factory for generating test data, data_analysis for analytics) when the user's request matches.
```

---

## Token / 长度考量

- 6 个 Skill × 约 2KB ≈ 12–14KB ≈ 3–4K tokens。
- 典型 system prompt：identity（~0.5K）+ schema（1–5K）+ skills（~3–4K）+ guidelines（~0.2K）≈ 5–10K tokens。
- 128K+ 上下文的模型可承受。若后续需要，可通过阶段三的 Skill 筛选或配置项缩减。

---

## 验证

1. **单元测试**：`ContextBuilder.build_system_prompt()` 输出包含 `test_data_factory` SKILL.md 的片段（如 "Determine Insertion Order" 或 "data_modify"）。
2. **集成测试**：用户请求「生成 50 个测试用户及其订单」——Agent 应遵循 test_data_factory 工作流（schema 检查 → 依赖顺序 → 批量插入），而非临时拼 INSERT。
3. **回归**：现有 test_skills、test_agent 仍通过。

---

## 工作量估算

| 阶段 | 预估 |
|------|------|
| 阶段一 | ~30 分钟 |
| 阶段二 | ~30 分钟 |
| 阶段三 | 可选，约 1–2 小时 |

**阶段一 + 二合计：** 约 1 小时。
