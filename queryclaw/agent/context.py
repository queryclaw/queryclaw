"""Context builder for assembling agent prompts."""

from __future__ import annotations

import platform
from datetime import datetime
from typing import Any

from queryclaw.db.base import SQLAdapter
from queryclaw.agent.skills import SkillsLoader


class ContextBuilder:
    """Builds the context (system prompt + messages) for the agent.

    Unlike nanobot's general-purpose context, this version injects database
    schema information so the LLM always knows the available tables and columns.
    """

    def __init__(
        self,
        db: SQLAdapter,
        skills: SkillsLoader | None = None,
        read_only: bool = True,
        enable_subagent: bool = True,
    ) -> None:
        self._db = db
        self._skills = skills or SkillsLoader()
        self._schema_cache: str | None = None
        self._read_only = read_only
        self._enable_subagent = enable_subagent

    async def build_system_prompt(self) -> str:
        """Build the full system prompt with identity, schema, and skills."""
        parts = [self._get_identity()]

        schema_summary = await self._get_schema_summary()
        if schema_summary:
            parts.append(f"# Database Schema\n\n{schema_summary}")

        skills_summary = self._skills.build_skills_summary()
        if skills_summary:
            parts.append(f"# Skills\n\n{skills_summary}")

        parts.append(self._get_guidelines())

        return "\n\n---\n\n".join(parts)

    async def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
    ) -> list[dict[str, Any]]:
        """Build the complete message list for an LLM call."""
        system_prompt = await self.build_system_prompt()
        return [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": current_message},
        ]

    async def _get_schema_summary(self) -> str:
        """Get a compact table-name-only summary of the database schema.

        Only table names and row counts are included to save tokens.
        The LLM should call `schema_inspect` to get column details when needed.
        Internal tables (prefixed with `_queryclaw`) are excluded.
        """
        if self._schema_cache is not None:
            return self._schema_cache

        try:
            tables = await self._db.get_tables()
        except Exception:
            return ""

        if not tables:
            self._schema_cache = "Database is empty (no tables)."
            return self._schema_cache

        user_tables = [t for t in tables if not t.name.startswith("_queryclaw")]

        lines = [
            f"Database type: {self._db.db_type}",
            f"Tables ({len(user_tables)}):",
        ]

        for table in user_tables:
            rows_str = f" ({table.row_count} rows)" if table.row_count is not None else ""
            lines.append(f"  - {table.name}{rows_str}")

        lines.append("")
        lines.append("Use `schema_inspect` to get column details for any table before writing queries.")

        self._schema_cache = "\n".join(lines)
        return self._schema_cache

    def invalidate_schema_cache(self) -> None:
        """Force a refresh of the schema cache on next prompt build."""
        self._schema_cache = None

    def _get_identity(self) -> str:
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        db_type = self._db.db_type

        # --- Tools ---
        tools = [
            "`schema_inspect` — list tables, columns, indexes, foreign keys, row counts",
            "`query_execute` — run SELECT queries, returns up to N rows",
            "`explain_plan` — run EXPLAIN on a query and return the execution plan",
            "`read_skill` — load a SKILL.md workflow by name (see Skills section)",
        ]
        if self._enable_subagent:
            tools.append("`spawn_subagent` — delegate a subtask to an independent agent with its own context")
        if not self._read_only:
            tools.extend([
                "`data_modify` — run INSERT / UPDATE / DELETE; includes SQL validation, dry-run, before/after snapshot, and audit logging",
                "`ddl_execute` — run CREATE / ALTER / DROP; destructive operations require user confirmation",
                "`transaction` — BEGIN / COMMIT / ROLLBACK for multi-statement atomic operations",
            ])

        # --- Safety notes ---
        if self._read_only:
            safety = "You are in **read-only** mode. Only SELECT queries are allowed."
        else:
            safety = (
                "Write operations go through a multi-layer safety pipeline:\n"
                "  1. SQL AST validation (blocked patterns, table allow-list)\n"
                "  2. Dry-run simulation\n"
                "  3. Human confirmation for destructive operations\n"
                "  4. Transaction wrapping\n"
                "  5. Full audit with before/after data snapshots"
            )

        return f"""# QueryClaw — AI Database Agent

You are **QueryClaw**, an AI-native database agent. You help users explore, query, and manage their database through natural language conversation.

You are connected to a **{db_type}** database. Use the tools below to interact with it — never guess table or column names; always verify with `schema_inspect` first.

## Available Tools

{chr(10).join(f"- {t}" for t in tools)}

## Safety

{safety}

## Runtime

- Platform: {runtime}
- Current time: {now}
- Database type: {db_type}"""

    @staticmethod
    def _get_guidelines() -> str:
        return """# Interaction Guidelines

- Answer in the **same language** as the user's question.
- Be concise; format small result sets as markdown tables, summarize large ones.
- **Always call `schema_inspect`** before writing queries if unsure about table or column names.
- `query_execute` only accepts SELECT (including WITH...SELECT) — use `data_modify` or `ddl_execute` for other statements.
- If a query fails, analyze the error and suggest a fix.
- For multi-step tasks, briefly explain your plan before starting.
- When a request matches a skill, **call `read_skill` first** — do not replicate workflows from memory.
- **Never fabricate data** — only report what the database actually returns.
- When modifying data, confirm the scope (which rows, how many) before executing."""
