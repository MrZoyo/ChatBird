import json
from contextlib import contextmanager
from pathlib import Path


SAFE = """---
name: public-research
description: Research public sources
---

# Public research

Use web_search for current facts.
"""

UPDATED = SAFE.replace("current facts", "recent public facts")


@contextmanager
def _public_background(tmp_path, monkeypatch, decision):
    import tools.public_skill_policy as policy
    import tools.skill_manager_tool as manager
    from tools.skill_provenance import (
        BACKGROUND_REVIEW,
        reset_current_write_origin,
        set_current_write_origin,
    )

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(manager, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(manager, "get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr("agent.skill_utils.get_all_skills_dirs", lambda: [skills_dir])
    monkeypatch.setattr(policy, "_manifest_path", lambda: tmp_path / "approvals.json")
    monkeypatch.setattr(policy, "is_public_discord_context", lambda: True)
    review_token = policy.set_public_skill_reviewer(lambda *_: decision)
    origin_token = set_current_write_origin(BACKGROUND_REVIEW)
    try:
        yield skills_dir, policy, manager
    finally:
        reset_current_write_origin(origin_token)
        policy.reset_public_skill_reviewer(review_token)


def _install(skills_dir: Path, content: str = SAFE) -> Path:
    skill_dir = skills_dir / "public-research"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


def test_rejected_edit_preserves_old_approved_version(tmp_path, monkeypatch):
    from tools.public_skill_policy import ReviewDecision

    with _public_background(
        tmp_path, monkeypatch, ReviewDecision(False, "review rejected", "reviewer")
    ) as (skills_dir, policy, manager):
        skill_dir = _install(skills_dir)
        assert policy.record_public_approval(
            skill_dir, "public-research", reviewer="initial", reason="safe"
        )
        result = json.loads(
            manager.skill_manage("edit", "public-research", content=UPDATED)
        )
        assert result["success"] is False
        assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == SAFE
        assert policy.is_skill_publicly_approved(skill_dir, "public-research")


def test_approved_edit_replaces_and_rebinds_public_version(tmp_path, monkeypatch):
    from tools.public_skill_policy import ReviewDecision

    with _public_background(
        tmp_path, monkeypatch, ReviewDecision(True, "safe", "reviewer")
    ) as (skills_dir, policy, manager):
        skill_dir = _install(skills_dir)
        assert policy.record_public_approval(
            skill_dir, "public-research", reviewer="initial", reason="safe"
        )
        result = json.loads(
            manager.skill_manage("edit", "public-research", content=UPDATED)
        )
        assert result["success"] is True
        assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == UPDATED
        assert policy.is_skill_publicly_approved(skill_dir, "public-research")


def test_public_background_cannot_mutate_unapproved_or_delete(tmp_path, monkeypatch):
    from tools.public_skill_policy import ReviewDecision

    with _public_background(
        tmp_path, monkeypatch, ReviewDecision(True, "safe", "reviewer")
    ) as (skills_dir, _policy, manager):
        skill_dir = _install(skills_dir)
        edited = json.loads(
            manager.skill_manage("edit", "public-research", content=UPDATED)
        )
        deleted = json.loads(manager.skill_manage("delete", "public-research"))
        assert edited["success"] is False
        assert "not available" in edited["error"]
        assert deleted["success"] is False
        assert "cannot delete" in deleted["error"]
        assert (skill_dir / "SKILL.md").exists()


def test_new_public_skill_requires_approval_and_matching_name(tmp_path, monkeypatch):
    from tools.public_skill_policy import ReviewDecision

    with _public_background(
        tmp_path, monkeypatch, ReviewDecision(False, "review rejected", "reviewer")
    ) as (skills_dir, _policy, manager):
        rejected = json.loads(
            manager.skill_manage("create", "public-research", content=SAFE)
        )
        assert rejected["success"] is False
        assert not (skills_dir / "public-research").exists()

    with _public_background(
        tmp_path, monkeypatch, ReviewDecision(True, "safe", "reviewer")
    ) as (skills_dir, policy, manager):
        mismatched = json.loads(
            manager.skill_manage("create", "different-name", content=SAFE)
        )
        assert mismatched["success"] is False
        approved = json.loads(
            manager.skill_manage("create", "public-research", content=SAFE)
        )
        skill_dir = skills_dir / "public-research"
        assert approved["success"] is True
        assert policy.is_skill_publicly_approved(skill_dir, "public-research")


def test_public_policy_error_rejects_update_without_touching_skill(tmp_path, monkeypatch):
    from tools.public_skill_policy import ReviewDecision

    with _public_background(
        tmp_path, monkeypatch, ReviewDecision(True, "safe", "reviewer")
    ) as (skills_dir, policy, manager):
        skill_dir = _install(skills_dir)
        assert policy.record_public_approval(
            skill_dir, "public-research", reviewer="initial", reason="safe"
        )
        monkeypatch.setattr(
            policy,
            "is_skill_publicly_approved",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("broken manifest")),
        )

        result = json.loads(
            manager.skill_manage("edit", "public-research", content=UPDATED)
        )
        assert result["success"] is False
        assert result["public_review"] == "rejected"
        assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == SAFE


def test_public_policy_error_rejects_delete_without_touching_skill(tmp_path, monkeypatch):
    from tools.public_skill_policy import ReviewDecision

    with _public_background(
        tmp_path, monkeypatch, ReviewDecision(True, "safe", "reviewer")
    ) as (skills_dir, _policy, manager):
        skill_dir = _install(skills_dir)
        monkeypatch.setattr(
            manager,
            "_is_background_discord_origin",
            lambda: True,
        )
        import builtins

        real_import = builtins.__import__

        def broken_policy_import(name, *args, **kwargs):
            if name == "tools.public_skill_policy":
                raise ImportError("broken policy")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", broken_policy_import)
        result = json.loads(manager.skill_manage("delete", "public-research"))
        assert result["success"] is False
        assert "deletion was rejected" in result["error"]
        assert skill_dir.exists()
