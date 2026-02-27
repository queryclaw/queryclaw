# Fix Plan: Skills Content Injection

> [中文版](zh/FIX_SKILLS_INJECTION.md)

## Problem Summary

The agent cannot use Skills because:

1. **`build_skills_summary()`** tells the agent to "read with read_file: {path}" — but there is no `read_file` tool.
2. **`load_skills_for_context()`** exists and can inject full skill content, but is **never called**.
3. The agent only sees a list of skill names and descriptions, not the actual workflow instructions.

**Result:** The agent falls back to manual tool usage (e.g. raw `data_modify` for test data) instead of following the structured workflows in Skills like `test_data_factory`.

---

## Fix Strategy

**Inject full skill content into the system prompt** instead of the misleading "read with read_file" summary.

- Skills are markdown docs (~13KB total for 6 built-in skills) — acceptable for system prompt.
- No new tools or APIs required.
- `load_skills_for_context()` already exists; we just need to call it.

---

## Implementation Plan

### Phase 1: Core Fix (Required)

| Step | File | Change |
|------|------|--------|
| 1.1 | `agent/context.py` | In `build_system_prompt()`, replace `build_skills_summary()` with `load_skills_for_context(all_skill_names)` to inject full content. |
| 1.2 | `agent/skills.py` | Update `build_skills_summary()` or add `build_skills_content()` that returns full content. Alternatively, keep `build_skills_summary()` for other uses but add a clear `get_full_skills_content()` used by ContextBuilder. |
| 1.3 | `agent/context.py` | Update the Skills section header/guidance: "The following skills describe workflows. Follow them when the user's request matches the skill's purpose." |

### Phase 2: Cleanup & Robustness

| Step | File | Change |
|------|------|--------|
| 2.1 | `agent/skills.py` | Remove or correct the misleading "read with read_file" text from `build_skills_summary()` if it remains used elsewhere; otherwise deprecate it. |
| 2.2 | Tests | Add/update `test_skills.py` and `test_agent.py` to assert that skill content (e.g. "test_data_factory", "schema_inspect") appears in the system prompt when ContextBuilder builds it. |
| 2.3 | Docs | Update USER_MANUAL / SELF_EVOLUTION_ANALYSIS to clarify that skills are injected into the system prompt, not read via a tool. |

### Phase 3: Optional Enhancements

| Step | Description |
|------|-------------|
| 3.1 | **Skill selection**: If prompt length becomes an issue, add optional filtering: only inject skills whose description/keywords match the user message (requires intent heuristics). |
| 3.2 | **Config knob**: `config.agent.inject_skills: "all" | "summary" | "none"` — "all" = full content (default), "summary" = names only (current broken behavior), "none" = omit skills section. |

---

## Detailed Code Changes

### 1. `agent/context.py`

**Before:**
```python
skills_summary = self._skills.build_skills_summary()
if skills_summary:
    parts.append(f"# Skills\n\n{skills_summary}")
```

**After:**
```python
all_skill_names = [s["name"] for s in self._skills.list_skills()]
skills_content = self._skills.load_skills_for_context(all_skill_names)
if skills_content:
    parts.append(f"# Skills\n\nThese workflows guide you for specific tasks. Follow the relevant skill when the user's request matches its purpose.\n\n{skills_content}")
```

### 2. `agent/skills.py`

- **Option A:** Leave `build_skills_summary()` as-is for any future "summary only" use cases (e.g. `channels status`), but ensure ContextBuilder does not use it for the main prompt.
- **Option B:** Add `build_full_skills_content() -> str` that calls `load_skills_for_context(list_skills_names)` and use that in ContextBuilder. Keeps separation of concerns.

Recommendation: **Option A** — ContextBuilder directly calls `load_skills_for_context()`. No new method needed.

### 3. Identity guideline (context.py line 144)

**Before:**
```
- Use the Skills below for domain-specific workflows (data analysis, schema docs, AI column, test data, etc.).
```

**After:**
```
- The Skills section below contains full workflow instructions. Follow the relevant skill (e.g. test_data_factory for generating test data, data_analysis for analytics) when the user's request matches.
```

---

## Token / Length Considerations

- 6 skills × ~2KB avg ≈ 12–14KB ≈ 3–4K tokens.
- Typical system prompt: identity (~0.5K) + schema (variable, often 1–5K) + skills (~3–4K) + guidelines (~0.2K) ≈ 5–10K tokens total.
- Models with 128K+ context can handle this. If needed later, Phase 3.1 (skill selection) or 3.2 (config) can reduce size.

---

## Verification

1. **Unit test:** `ContextBuilder.build_system_prompt()` output contains substring from `test_data_factory` SKILL.md (e.g. "Determine Insertion Order" or "data_modify").
2. **Integration test:** User asks "Generate 50 test users with orders" — agent should follow test_data_factory workflow (schema inspect → dependency order → batch insert) rather than ad-hoc INSERTs.
3. **Regression:** Existing tests (test_skills, test_agent) still pass.

---

## Effort Estimate

| Phase | Effort |
|-------|--------|
| Phase 1 | ~30 min |
| Phase 2 | ~30 min |
| Phase 3 | Optional, ~1–2 hrs if needed |

**Total (Phase 1+2):** ~1 hour.
