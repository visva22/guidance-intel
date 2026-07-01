from guidance_intel.counter import compute_coverage
from guidance_intel.models import Artifact, TranscriptEvent


def _make_artifacts():
    return [
        Artifact(name="graphify", kind="skill", source_path="skills/graphify", triggers=["graphify", "/graphify"]),
        Artifact(name="code-review", kind="skill", source_path="skills/code-review", triggers=["code-review", "/code-review"]),
        Artifact(name="dead-skill", kind="skill", source_path="skills/dead-skill", triggers=["dead-skill", "/dead-skill"]),
        Artifact(name="Explore", kind="agent", source_path="AGENTS.md", triggers=["Explore", "explore"]),
    ]


def _make_events():
    return [
        TranscriptEvent(kind="skill", name="graphify", session_id="s1", timestamp="2026-06-01T10:00:00Z"),
        TranscriptEvent(kind="skill", name="graphify", session_id="s2", timestamp="2026-06-02T10:00:00Z"),
        TranscriptEvent(kind="skill", name="code-review", session_id="s2", timestamp="2026-06-02T11:00:00Z"),
        TranscriptEvent(kind="agent", name="Explore", session_id="s1", timestamp="2026-06-01T10:01:00Z"),
    ]


def test_counts_skill_invocations():
    report = compute_coverage(_make_artifacts(), _make_events(), "/repo")
    graphify = next(r for r in report.usage if r.artifact_name == "graphify")
    assert graphify.total_count == 2


def test_counts_across_sessions():
    report = compute_coverage(_make_artifacts(), _make_events(), "/repo")
    graphify = next(r for r in report.usage if r.artifact_name == "graphify")
    assert graphify.session_count == 2


def test_identifies_dead_artifacts():
    report = compute_coverage(_make_artifacts(), _make_events(), "/repo")
    assert "dead-skill" in report.dead_artifacts


def test_coverage_percentage():
    report = compute_coverage(_make_artifacts(), _make_events(), "/repo")
    # 3 out of 4 artifacts used = 75%
    assert report.coverage_percent == 75.0


def test_no_events_all_dead():
    report = compute_coverage(_make_artifacts(), [], "/repo")
    assert report.coverage_percent == 0.0
    assert len(report.dead_artifacts) == 4


def test_all_used_full_coverage():
    artifacts = [
        Artifact(name="graphify", kind="skill", source_path="x", triggers=["graphify"]),
    ]
    events = [
        TranscriptEvent(kind="skill", name="graphify", session_id="s1"),
    ]
    report = compute_coverage(artifacts, events, "/repo")
    assert report.coverage_percent == 100.0


def test_first_and_last_seen():
    report = compute_coverage(_make_artifacts(), _make_events(), "/repo")
    graphify = next(r for r in report.usage if r.artifact_name == "graphify")
    assert graphify.first_seen == "2026-06-01T10:00:00Z"
    assert graphify.last_seen == "2026-06-02T10:00:00Z"
