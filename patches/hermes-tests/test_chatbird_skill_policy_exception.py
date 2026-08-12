from agent.prompt_builder import (
    build_skills_system_prompt,
    clear_skills_system_prompt_cache,
)


def test_trusted_policy_can_bypass_unavailable_skill_tools(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    skill_dir = tmp_path / "skills" / "research" / "web-research"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: web-research\ndescription: Research current facts\n---\n"
    )
    clear_skills_system_prompt_cache(clear_snapshot=True)

    result = build_skills_system_prompt()

    assert "platform-injected trusted access policy" in result
    assert "proceed directly with the tools that policy allows" in result
