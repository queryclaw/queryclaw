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
        enum = skill_names if skill_names else ["data_analysis"]
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "enum": enum,
                    "description": "Skill name (directory name, e.g. test_data_factory, data_analysis).",
                },
            },
            "required": ["skill_name"],
        }

    async def execute(self, skill_name: str, **kwargs: Any) -> str:
        content = self._skills.load_skill(skill_name)
        if not content:
            return f"Error: Skill '{skill_name}' not found."
        return SkillsLoader._strip_frontmatter(content)
