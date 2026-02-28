# Token Optimization

> Implemented in v0.5.4 – v0.5.6 (2026-02-28)

## Background

Before optimization, each LLM call included the full column definitions for all 32 tables in the system prompt (~3000 tokens), the complete SKILL.md content was repeated on every subsequent agent loop iteration (~1000 tokens), verbose assistant responses accumulated in conversation history, and interaction guidelines contained redundant subsections. A typical multi-turn conversation consumed ~35,000 tokens, of which ~60% was redundant.

## Changes Overview

| Version | Change | Estimated Savings |
|---------|--------|-------------------|
| v0.5.4 | Schema compaction + internal table filter + guidelines compaction | ~3,300 tokens/iteration |
| v0.5.5 | Agent loop message compaction + memory truncation + SELECT constraint hints | ~6,000+ tokens/session |
| v0.5.6 | Enforce `schema_inspect` before any query (prevent column-name guessing) | Avoids wasted error iterations |

## Detailed Changes

### 1. Schema Compaction (v0.5.4)

**File**: `queryclaw/agent/context.py` — `_get_schema_summary()`

Before:

```
## maintenance_records (4 rows)
  - id: int(11) [PK] NOT NULL
  - vehicle_id: int(11) NOT NULL
  - maintenance_type: enum(...) NOT NULL
  - title: varchar(200)
  - description: text
  - cost: decimal(10,2)
  - scheduled_date: date
  ... (repeated for all 32 tables)
```

After:

```
Tables (31):
  - alert_rules (5 rows)
  - drivers (8 rows)
  - maintenance_records (4 rows)
  ...

Column details are NOT listed above. You MUST call `schema_inspect` before writing any query.
```

Key decisions:
- Only table names and row counts are included; column details are discovered on demand via `schema_inspect`.
- Internal tables prefixed with `_queryclaw` (e.g. `_queryclaw_audit_log`) are excluded from the summary.
- Saves ~2,800 tokens per LLM call for a 32-table database.

### 2. Internal Table Filtering (v0.5.4)

**File**: `queryclaw/agent/context.py` — `_get_schema_summary()`

```python
user_tables = [t for t in tables if not t.name.startswith("_queryclaw")]
```

Prevents the LLM from seeing or interacting with internal audit tables. Saves ~150 tokens and avoids accidental operations on internal tables.

### 3. Guidelines Compaction (v0.5.4)

**File**: `queryclaw/agent/context.py` — `_get_guidelines()`

Before: 4 subsections (Response Style, Workflow, Skills, Integrity) — ~500 tokens.

After: 9 flat bullet points — ~180 tokens. The redundant Skills subsection was merged since skills are already listed in the dedicated Skills section of the system prompt.

### 4. Agent Loop Message Compaction (v0.5.5)

**File**: `queryclaw/agent/loop.py` — `_compact_messages()`

During a multi-iteration agent loop, old messages accumulate (tool results, assistant responses). Before each LLM call, `_compact_messages()` creates a token-efficient copy:

| Message type | Threshold | Truncation |
|---|---|---|
| Tool results (e.g. SKILL.md from `read_skill`) | > 500 chars | Keep first 300 chars + `[... truncated ...]` |
| Assistant text responses | > 300 chars | Keep first 200 chars + `[... truncated ...]` |
| System prompt | — | Always kept intact |
| Last 6 messages | — | Always kept intact |

Constants:

```python
_COMPACT_KEEP_TAIL = 6    # keep last N messages intact
_COMPACT_TOOL_MAX  = 500  # truncate tool results above this
_COMPACT_ASST_MAX  = 300  # truncate assistant text above this
```

The original `messages` list is preserved for appending new tool results; only the compacted copy is sent to the LLM.

### 5. Memory Truncation (v0.5.5)

**File**: `queryclaw/agent/memory.py` — `MemoryStore.add()`

When storing assistant responses in conversation memory (for cross-turn history), messages exceeding 800 characters are truncated to 600 characters:

```python
_MEMORY_ASST_MAX = 800

if role == "assistant" and len(content) > _MEMORY_ASST_MAX:
    content = content[:600] + "\n\n[... response truncated ...]"
```

This prevents verbose assistant responses (e.g. detailed analysis reports) from bloating future prompts across conversation turns.

### 6. SELECT Constraint Hints (v0.5.5)

**File**: `queryclaw/skills/data_detective/SKILL.md`

Added explicit constraint to the most error-prone skill:

```markdown
> **Constraint**: `query_execute` only accepts `SELECT` (including `WITH ... SELECT`).
> Do not use `CREATE TEMPORARY TABLE`, `SET`, or any non-SELECT statement with it.
> For derived computations, use subqueries or CTEs.
```

**File**: `queryclaw/agent/context.py` — `_get_guidelines()`

Added rule in interaction guidelines:

```
- `query_execute` only accepts SELECT (including WITH...SELECT) — use `data_modify` or `ddl_execute` for other statements.
```

### 7. Enforce schema_inspect (v0.5.6)

**File**: `queryclaw/agent/context.py`

After schema compaction, the LLM occasionally guessed column names (e.g. `maintenance_date` instead of `scheduled_date`). Strengthened the instruction from advisory to mandatory in three locations:

| Location | Wording |
|---|---|
| Identity section | "column details are **NOT provided**. You **MUST** call `schema_inspect`...Never guess column names." |
| Schema section footer | "Column details are **NOT** listed above. You **MUST** call `schema_inspect` before writing any query." |
| Guidelines | "**MUST** call `schema_inspect`...column names are not in the prompt; guessing will fail." |

## Trade-offs

| Benefit | Cost |
|---|---|
| ~60% token reduction per session | LLM needs 1 extra `schema_inspect` call per table before querying |
| Faster LLM response (less input to process) | Occasional column-name guessing if LLM ignores instruction (mitigated by v0.5.6) |
| Lower API cost | Slightly more tool calls in first iteration of a new topic |
| Reduced risk of LLM touching internal tables | None |

## Tuning

The truncation thresholds can be adjusted via module-level constants:

| Constant | File | Default | Purpose |
|---|---|---|---|
| `_COMPACT_KEEP_TAIL` | `loop.py` | 6 | Number of recent messages kept intact in agent loop |
| `_COMPACT_TOOL_MAX` | `loop.py` | 500 | Max tool result length before truncation |
| `_COMPACT_ASST_MAX` | `loop.py` | 300 | Max assistant text length before truncation |
| `_MEMORY_ASST_MAX` | `memory.py` | 800 | Max assistant response length in conversation memory |

For databases with very few tables (< 5), the schema compaction savings are minimal and full column definitions could be re-enabled if desired (by reverting `_get_schema_summary()`).
