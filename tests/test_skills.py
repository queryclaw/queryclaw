"""Tests for skills loader."""

import pytest

from queryclaw.agent.skills import SkillsLoader


@pytest.fixture
def workspace_with_skills(tmp_path):
    """Create a workspace with custom skills."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Custom skill
    custom_skill = skills_dir / "my_skill"
    custom_skill.mkdir()
    (custom_skill / "SKILL.md").write_text(
        '---\ndescription: "My custom skill"\n---\n# My Skill\n\nDo something useful.\n'
    )

    # Another skill without frontmatter
    bare_skill = skills_dir / "bare_skill"
    bare_skill.mkdir()
    (bare_skill / "SKILL.md").write_text("# Bare Skill\n\nNo frontmatter.\n")

    return tmp_path


class TestSkillsLoader:
    def test_list_builtin_skills(self):
        loader = SkillsLoader()
        skills = loader.list_skills()
        names = [s["name"] for s in skills]
        assert "data_analysis" in names

    def test_load_builtin_skill(self):
        loader = SkillsLoader()
        content = loader.load_skill("data_analysis")
        assert content is not None
        assert "Data Analysis" in content

    def test_load_nonexistent_skill(self):
        loader = SkillsLoader()
        assert loader.load_skill("nonexistent") is None

    def test_list_workspace_skills(self, workspace_with_skills):
        loader = SkillsLoader(workspace=workspace_with_skills)
        skills = loader.list_skills()
        names = [s["name"] for s in skills]
        assert "my_skill" in names
        assert "bare_skill" in names
        assert "data_analysis" in names

    def test_workspace_skill_overrides_builtin(self, tmp_path):
        skills_dir = tmp_path / "skills" / "data_analysis"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            '---\ndescription: "Overridden"\n---\n# Overridden\n'
        )

        loader = SkillsLoader(workspace=tmp_path)
        content = loader.load_skill("data_analysis")
        assert "Overridden" in content

        skills = loader.list_skills()
        da = next(s for s in skills if s["name"] == "data_analysis")
        assert da["source"] == "workspace"

    def test_get_skill_metadata(self, workspace_with_skills):
        loader = SkillsLoader(workspace=workspace_with_skills)
        meta = loader.get_skill_metadata("my_skill")
        assert meta is not None
        assert meta["description"] == "My custom skill"

    def test_get_skill_metadata_no_frontmatter(self, workspace_with_skills):
        loader = SkillsLoader(workspace=workspace_with_skills)
        meta = loader.get_skill_metadata("bare_skill")
        assert meta is None

    def test_load_skills_for_context(self):
        loader = SkillsLoader()
        context = loader.load_skills_for_context(["data_analysis"])
        assert "Skill: data_analysis" in context
        assert "Data Analysis" in context
        # Frontmatter should be stripped
        assert "---" not in context

    def test_load_skills_for_context_empty(self):
        loader = SkillsLoader()
        assert loader.load_skills_for_context([]) == ""
        assert loader.load_skills_for_context(["nonexistent"]) == ""

    def test_build_skills_summary(self):
        loader = SkillsLoader()
        summary = loader.build_skills_summary()
        assert "data_analysis" in summary
        assert "read_skill" in summary
        assert "read_file" not in summary

    def test_strip_frontmatter(self):
        content = "---\nkey: value\n---\n# Title\nBody"
        assert SkillsLoader._strip_frontmatter(content) == "# Title\nBody"

    def test_strip_frontmatter_no_frontmatter(self):
        content = "# Title\nBody"
        assert SkillsLoader._strip_frontmatter(content) == "# Title\nBody"

    def test_skill_source_labels(self):
        loader = SkillsLoader()
        skills = loader.list_skills()
        for s in skills:
            assert s["source"] in ("workspace", "builtin")
