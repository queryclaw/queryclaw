"""Skills loader for agent capabilities."""

from __future__ import annotations

import re
from pathlib import Path

BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillsLoader:
    """Loader for agent skills.

    Skills are markdown files (SKILL.md) that teach the agent how to use
    specific tools or perform certain tasks. Supports both built-in skills
    (shipped with queryclaw) and workspace skills (user-defined).
    """

    def __init__(self, workspace: Path | None = None, builtin_skills_dir: Path | None = None):
        self.workspace_skills = workspace / "skills" if workspace else None
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR

    def list_skills(self) -> list[dict[str, str]]:
        """List all available skills.

        Returns:
            List of skill info dicts with 'name', 'path', 'source'.
        """
        skills: list[dict[str, str]] = []

        if self.workspace_skills and self.workspace_skills.exists():
            for skill_dir in sorted(self.workspace_skills.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        skills.append({
                            "name": skill_dir.name,
                            "path": str(skill_file),
                            "source": "workspace",
                        })

        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in sorted(self.builtin_skills.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists() and not any(s["name"] == skill_dir.name for s in skills):
                        skills.append({
                            "name": skill_dir.name,
                            "path": str(skill_file),
                            "source": "builtin",
                        })

        return skills

    def load_skill(self, name: str) -> str | None:
        """Load a skill's SKILL.md content by name.

        Args:
            name: Skill name (directory name).

        Returns:
            Skill content or None if not found.
        """
        if self.workspace_skills:
            ws_path = self.workspace_skills / name / "SKILL.md"
            if ws_path.exists():
                return ws_path.read_text(encoding="utf-8")

        if self.builtin_skills:
            builtin_path = self.builtin_skills / name / "SKILL.md"
            if builtin_path.exists():
                return builtin_path.read_text(encoding="utf-8")

        return None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """Load specific skills for inclusion in agent context.

        Args:
            skill_names: List of skill names to load.

        Returns:
            Formatted skills content.
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                parts.append(f"### Skill: {name}\n\n{content}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def build_skills_summary(self) -> str:
        """Build a summary of all skills for the system prompt.

        Returns:
            Formatted skills summary.
        """
        all_skills = self.list_skills()
        if not all_skills:
            return ""

        lines = [
            "Call read_skill(skill_name='<name>') to load full workflow instructions when the user's request matches a skill.",
            "",
            "Available skills:",
        ]
        for s in all_skills:
            desc = self._get_skill_description(s["name"])
            lines.append(f"  - {s['name']}: {desc} — call read_skill(skill_name='{s['name']}') when relevant")
        return "\n".join(lines)

    def get_skill_metadata(self, name: str) -> dict[str, str] | None:
        """Get metadata from a skill's YAML frontmatter.

        Args:
            name: Skill name.

        Returns:
            Metadata dict or None.
        """
        content = self.load_skill(name)
        if not content:
            return None

        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                metadata: dict[str, str] = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip("\"'")
                return metadata
        return None

    def _get_skill_description(self, name: str) -> str:
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content
