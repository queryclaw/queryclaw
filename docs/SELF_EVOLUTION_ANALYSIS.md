# Can QueryClaw’s Tools & Skills Support Self-Evolution?

This doc analyzes whether the current **Tools** and **Skills** design can support the project “evolving by itself” (e.g. the agent or the system adding new capabilities over time), and what would be needed.

> [中文版](zh/SELF_EVOLUTION_ANALYSIS.md)

---

## Short Answer

| Dimension | Self-evolution today? | Reason |
|-----------|------------------------|--------|
| **Skills** | **Partially / design-ready** | Declarative, file-based, workspace already supported; missing only a safe “write skill” path for the agent. |
| **Tools** | **No** | Tools are Python code; the agent has no way to define or register new tools at runtime. |

So: **Skills can be made to support self-evolution with a small, well-scoped extension. Tools in their current form cannot**, unless we introduce a separate mechanism (e.g. declarative / DSL-based tools or a safe “add tool” API).

---

## 1. Current Architecture (Recap)

### Tools

- **What they are:** Python classes implementing the `Tool` ABC (`name`, `description`, `parameters`, `execute()`).
- **How they’re used:** Registered in `ToolRegistry` at agent init via `_register_default_tools()` (schema_inspect, query_execute, explain_plan). The agent only **calls** tools; it does not create or register them.
- **Registry API:** `ToolRegistry` already has `register()` / `unregister()` at runtime, but nothing in the agent loop or in any tool exposes this to the LLM.

### Skills

- **What they are:** Markdown files (`SKILL.md`) with optional YAML frontmatter. They describe how to do certain tasks (e.g. “Data Analysis”).
- **How they’re used:** `SkillsLoader` loads from (1) **builtin** `queryclaw/skills/` and (2) **workspace** `workspace/skills/` (if `workspace` is set). Skill names and descriptions are summarized in the system prompt; full content can be loaded for context.
- **No execution:** Skills are text only; they guide the agent’s behavior, they are not executed as code.

---

## 2. Why Skills *Can* Support Self-Evolution

- **Declarative and text-based:** Skills are just markdown. An LLM can generate valid `SKILL.md` content (and frontmatter) without writing code. So “new capability” here is “new text,” which fits LLM outputs.
- **Workspace is already part of the model:** `SkillsLoader(workspace=...)` already supports a second directory (workspace skills). So the “place where new skills live” exists; we only need a way for the agent (or the user) to put files there.
- **No code execution:** Adding a new skill does not require running user/agent-generated code; it only requires writing a file. That keeps the security surface small (file write scoped to a skills dir).
- **Immediate effect:** Once a new `SKILL.md` is on disk under the workspace (or a reloadable builtin path), the next time the system prompt is built, `SkillsLoader` can list and load it. So behavior can evolve without redeploying the app.

**What’s missing today:**  
The agent has **no tool that can create or update files** (e.g. “write this content to `workspace/skills/<name>/SKILL.md`”). So the design is ready, but the “write skill” path is not exposed. Adding a constrained tool (e.g. `create_skill(name, content)`) that only writes under a dedicated skills directory would make Skills self-evolution capable in practice.

---

## 3. Why Tools *Cannot* Self-Evolve (As Currently Designed)

- **Tools are code:** Each tool is a Python class. To “add a new tool” the system would need to either run new code (e.g. dynamically load a new `Tool` implementation) or interpret some non-code definition. The current codebase does neither for agent-generated definitions.
- **No agent-visible “add tool” API:** The agent only sees `get_definitions()` (to call tools) and `execute()`. It has no way to call something like “register_tool(name, description, parameters, handler).” So even if we later had a safe handler (e.g. a DSL), we’d need to expose registration to the agent.
- **Security and correctness:** Letting the agent execute arbitrary generated code as a new tool would require sandboxing, validation, and strong limits. That’s a much larger design than “add one file-write tool” for Skills.

So: **with the current “tools = Python classes only” design, the system cannot self-evolve by adding new tools**, unless we introduce an extra layer (e.g. declarative tools, or a very restricted “add tool” API with a safe interpreter/DSL).

---

## 4. Possible Directions for Self-Evolution

### Skills (minimal change)

- Add a **create_skill** (or **write_skill**) tool:
  - Allowed path: only under `workspace/skills/<name>/SKILL.md` (or a configurable skills dir).
  - Input: skill name + markdown content (and optionally frontmatter).
- Optionally: a **reload_skills** or “refresh context” step so the same session sees the new skill without restart.

Then the agent (or a separate “skill author” flow) can create new skills from natural language; the project “evolves” by accumulating skills on disk.

### Tools (larger design)

- **Option A — Declarative / DSL tools:**  
  Introduce a class of tools that are **defined by data** (e.g. parameterized SQL templates, or a small DSL). The agent (or a separate process) could then “add a tool” by creating a definition (e.g. a JSON/YAML file or a row in a table) that an existing “meta-tool” or engine interprets. New capabilities appear without new Python code.

- **Option B — Agent-visible registration (advanced):**  
  Provide a safe “register_tool” mechanism (e.g. name + schema + reference to a known safe handler type). The agent still cannot upload arbitrary code, but could enable pre-approved “templates” or plugins. This requires careful permission and schema design.

- **Option C — Keep tools code-only, evolve only skills:**  
  All new “capabilities” are expressed as new Skills (workflows that combine existing tools). The set of tools stays fixed and maintained by developers. Self-evolution is limited to Skills.

---

## 5. Summary

| Question | Answer |
|----------|--------|
| Can the **current** Tools + Skills design support self-evolution? | **Skills:** design is ready; in practice we need one safe “write skill” path. **Tools:** no, they are code and the agent cannot add or register new tools. |
| Why can Skills support it? | Declarative, file-based, workspace already in the model, no code execution, prompt-side effect. |
| Why can’t Tools support it today? | Tools are Python code; there is no agent-visible way to define or register new tools, and doing so safely would require new machinery (DSL, safe interpreter, or restricted registration API). |
| Recommended next step for self-evolution | Implement a constrained **create_skill** (or **write_skill**) tool and optionally **reload_skills**, so the project can self-evolve via new Skills; treat Tools as extensible only by code/configuration unless a separate declarative-tool or registration design is added later. |
