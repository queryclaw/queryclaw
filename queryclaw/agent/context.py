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
        """Get a text summary of the database schema (cached after first call)."""
        if self._schema_cache is not None:
            return self._schema_cache

        try:
            tables = await self._db.get_tables()
        except Exception:
            return ""

        if not tables:
            self._schema_cache = "Database is empty (no tables)."
            return self._schema_cache

        lines = [
            f"Database type: {self._db.db_type}",
            f"Tables: {len(tables)}",
            "",
        ]

        for table in tables:
            rows_str = f" ({table.row_count} rows)" if table.row_count is not None else ""
            lines.append(f"## {table.name}{rows_str}")
            try:
                columns = await self._db.get_columns(table.name)
                for col in columns:
                    pk = " [PK]" if col.is_primary_key else ""
                    null = "" if col.nullable else " NOT NULL"
                    lines.append(f"  - {col.name}: {col.data_type}{pk}{null}")
            except Exception:
                lines.append("  (unable to read columns)")
            lines.append("")

        self._schema_cache = "\n".join(lines)
        return self._schema_cache

    def invalidate_schema_cache(self) -> None:
        """Force a refresh of the schema cache on next prompt build."""
        self._schema_cache = None

    def _get_identity(self) -> str:
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")

        capabilities = [
            "**Schema inspection** — view tables, columns, indexes, foreign keys",
            "**Query execution** — run SELECT queries and return results",
            "**Performance analysis** — use EXPLAIN to show execution plans",
        ]
        if self._enable_subagent:
            capabilities.append("**Subagent delegation** — spawn_subagent for complex or isolated tasks")
        if not self._read_only:
            capabilities.extend([
                "**Data modification** — INSERT, UPDATE, DELETE via data_modify (with dry-run and audit)",
                "**DDL** — CREATE, ALTER, DROP via ddl_execute (destructive ops may require confirmation)",
                "**Transactions** — BEGIN, COMMIT, ROLLBACK for multi-statement operations",
            ])

        write_note = "" if self._read_only else (
            "\n- Write operations go through dry-run validation and audit logging; "
            "destructive ops may require user confirmation."
        )

        return f"""# QueryClaw — AI Database Agent

You are QueryClaw, an AI-native database agent. You help users explore, query, and understand their database using natural language.
{f"You can also modify data, run DDL, and manage transactions when requested." if not self._read_only else ""}

## Capabilities
{chr(10).join(f"- {c}" for c in capabilities)}

## Runtime
{runtime}
Current time: {now}

## Guidelines
- Use the provided tools to inspect schema, run queries, and analyze execution plans.
- Always inspect the schema before writing queries if you're unsure about table/column names.
- Present results clearly and concisely; summarize large result sets.
- If a query fails, analyze the error and suggest a fix.
- When asked about performance, use explain_plan to show the execution plan.
- When the user's request matches a skill's purpose (e.g. generate test data, analyze data, document schema), call read_skill first to load the workflow instructions, then follow them.
{'- Only execute SELECT queries — you are in read-only mode.' if self._read_only else write_note}"""

    @staticmethod
    def _get_guidelines() -> str:
        return """# Interaction Guidelines

- Answer in the same language as the user's question.
- Be concise but thorough; include relevant SQL and data in your response.
- If you need multiple steps, explain your reasoning briefly before each tool call.
- Do not fabricate data — only report what the database actually returns."""
