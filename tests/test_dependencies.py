from guidance_intel.dependencies import analyze_dependencies
from guidance_intel.models import TranscriptEvent


def _skill(name, uuid, session="s1", parent=None):
    return TranscriptEvent(kind="skill", name=name, session_id=session, uuid=uuid, parent_uuid=parent)


def _agent(name, uuid, session="s1", parent=None):
    return TranscriptEvent(kind="agent", name=name, session_id=session, uuid=uuid, parent_uuid=parent)


def _read(file_path, uuid, session="s1", parent=None, sidechain=False):
    return TranscriptEvent(
        kind="skill", name="x", session_id=session, uuid=uuid, parent_uuid=parent,
        is_sidechain=sidechain,
        metadata={"file_path": file_path, "manual_reference": True},
    )


def test_attributes_child_reads_to_invocation(tmp_path):
    inv = _skill("graphify", "i1")
    r = _read("other/file.md", "r1", parent="i1")
    reports = analyze_dependencies([], [inv, r], str(tmp_path))
    assert len(reports) == 1
    rep = reports[0]
    assert rep.artifact_name == "graphify"
    assert rep.avg_extra_reads == 1.0
    assert any(d.file_path == "other/file.md" for d in rep.dependencies)


def test_same_line_read_counts_as_primary(tmp_path):
    # Skill invocation and its own SKILL.md read share one uuid (batched message).
    src = tmp_path / "skill.md"
    src.write_text("# graphify\ncontent here for tokens\n")
    inv = _skill("graphify", "i1")
    same = _read("skill.md", "i1", parent="u1")  # same uuid as invocation
    reports = analyze_dependencies([], [inv, same], str(tmp_path),
                                   artifact_source={"graphify": "skill.md"})
    rep = reports[0]
    assert rep.primary_tokens > 0
    assert rep.avg_extra_reads == 0.0  # primary read is not "extra"


def test_sidechain_read_attributed_to_agent(tmp_path):
    agent = _agent("Explore", "a1")
    r = _read(".claude/skills/graphify/SKILL.md", "r1", parent="a1", sidechain=True)
    reports = analyze_dependencies([], [agent, r], str(tmp_path))
    rep = next(r for r in reports if r.artifact_name == "Explore")
    dep = rep.dependencies[0]
    assert dep.via_sidechain is True


def test_global_skill_leak_detected(tmp_path):
    inv = _skill("arson", "i1")
    r = _read("/Users/x/.claude/skills/graphify/SKILL.md", "r1", parent="i1")
    reports = analyze_dependencies([], [inv, r], str(tmp_path),
                                   artifact_source={"arson": "skills/arson/SKILL.md"})
    dep = reports[0].dependencies[0]
    assert dep.leak_level == "global"


def test_declared_dependency_not_a_leak(tmp_path):
    src = tmp_path / "arson.md"
    src.write_text("See build-commands.md for details.\n")
    inv = _skill("arson", "i1")
    r = _read("build-commands.md", "r1", parent="i1")
    reports = analyze_dependencies([], [inv, r], str(tmp_path),
                                   artifact_source={"arson": "arson.md"})
    dep = reports[0].dependencies[0]
    assert dep.in_closure is True
    assert dep.leak_level == "none"


def test_cross_reference_leak(tmp_path):
    inv = _skill("arson", "i1")
    r = _read(".claude/skills/unity-codegen/build.md", "r1", parent="i1")
    reports = analyze_dependencies([], [inv, r], str(tmp_path),
                                   artifact_source={"arson": ".claude/skills/arson/SKILL.md"})
    dep = reports[0].dependencies[0]
    assert dep.leak_level == "cross-reference"


def test_cooccurrence_fraction(tmp_path):
    # graphify invoked in 2 sessions; file X read in 1 of them → 0.5
    events = [
        _skill("graphify", "i1", session="s1"),
        _read("X.md", "r1", session="s1", parent="i1"),
        _skill("graphify", "i2", session="s2"),
    ]
    reports = analyze_dependencies([], events, str(tmp_path))
    rep = next(r for r in reports if r.artifact_name == "graphify")
    assert rep.cooccurrence.get("X.md") == 0.5


def test_no_causal_fields_falls_back_to_cooccurrence(tmp_path):
    events = [
        TranscriptEvent(kind="skill", name="graphify", session_id="s1"),
        TranscriptEvent(kind="skill", name="x", session_id="s1",
                        metadata={"file_path": "Y.md", "manual_reference": True}),
    ]
    reports = analyze_dependencies([], events, str(tmp_path))
    rep = next(r for r in reports if r.artifact_name == "graphify")
    assert rep.attribution_method == "co-occurrence"
