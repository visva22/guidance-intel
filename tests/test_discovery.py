from guidance_intel.discovery import discover_artifacts, discover_transcripts


def test_finds_skills(repo_path):
    artifacts = discover_artifacts(repo_path)
    skills = [a for a in artifacts if a.kind == "skill"]
    names = [s.name for s in skills]
    assert "graphify" in names
    assert "code-review" in names
    assert "dead-skill" in names


def test_finds_agents(repo_path):
    artifacts = discover_artifacts(repo_path)
    agents = [a for a in artifacts if a.kind == "agent"]
    names = [a.name for a in agents]
    assert "Explore" in names
    assert "Plan" in names
    assert "code-reviewer" in names


def test_finds_workflows(repo_path):
    artifacts = discover_artifacts(repo_path)
    workflows = [a for a in artifacts if a.kind == "workflow"]
    names = [w.name for w in workflows]
    assert "feature-dev" in names


def test_skill_has_triggers(repo_path):
    artifacts = discover_artifacts(repo_path)
    graphify = next(a for a in artifacts if a.name == "graphify")
    assert "graphify" in graphify.triggers
    assert "/graphify" in graphify.triggers


def test_empty_repo(tmp_path):
    artifacts = discover_artifacts(str(tmp_path))
    assert artifacts == []


def test_finds_transcript_files(repo_path, transcripts_path):
    paths = discover_transcripts(repo_path, transcripts_path)
    assert len(paths) == 3
    assert all(p.endswith(".jsonl") for p in paths)


def test_no_transcripts_without_path(tmp_path):
    paths = discover_transcripts(str(tmp_path), None)
    assert paths == []


def test_excludes_reference_files(repo_path):
    """Reference files in references/ subdirs should not be discovered as skills."""
    artifacts = discover_artifacts(repo_path)
    skill_names = [a.name for a in artifacts if a.kind == "skill"]

    # SKILL.md should be discovered
    assert "test-skill" in skill_names

    # But references/ files should NOT
    assert "build-commands" not in skill_names
    assert "TEST_PLAN" not in skill_names
    assert "VALIDATION_REPORT" not in skill_names
