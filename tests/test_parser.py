from guidance_intel.parser import parse_transcripts, parse_generic_jsonl
from pathlib import Path


def test_parses_skill_invocation(transcripts_path):
    paths = [str(Path(transcripts_path) / "session-001.jsonl")]
    events = parse_transcripts(paths)
    skills = [e for e in events if e.kind == "skill"]
    assert len(skills) == 1
    assert skills[0].name == "graphify"


def test_parses_agent_spawn(transcripts_path):
    paths = [str(Path(transcripts_path) / "session-001.jsonl")]
    events = parse_transcripts(paths)
    agents = [e for e in events if e.kind == "agent"]
    assert len(agents) == 1
    assert agents[0].name == "Explore"


def test_parses_workflow(transcripts_path):
    paths = [str(Path(transcripts_path) / "session-002.jsonl")]
    events = parse_transcripts(paths)
    workflows = [e for e in events if e.kind == "workflow"]
    assert len(workflows) == 1
    assert workflows[0].name == "feature-dev"


def test_skips_non_relevant_tools(transcripts_path):
    paths = [str(Path(transcripts_path) / "session-001.jsonl")]
    events = parse_transcripts(paths)
    # Bash and Edit tool_use should not produce events
    assert len(events) == 2  # only Skill + Agent


def test_handles_malformed_lines(tmp_path):
    bad_file = tmp_path / "bad.jsonl"
    bad_file.write_text("not json\n{}\n{\"type\": \"other\"}\n")
    events = parse_transcripts([str(bad_file)])
    assert events == []


def test_extracts_timestamp(transcripts_path):
    paths = [str(Path(transcripts_path) / "session-001.jsonl")]
    events = parse_transcripts(paths)
    assert events[0].timestamp == "2026-06-01T10:00:00Z"


def test_multiple_sessions(transcripts_path):
    paths = [
        str(Path(transcripts_path) / "session-001.jsonl"),
        str(Path(transcripts_path) / "session-002.jsonl"),
    ]
    events = parse_transcripts(paths)
    session_ids = set(e.session_id for e in events)
    assert len(session_ids) == 2


def test_generic_jsonl_format(tmp_path):
    generic_file = tmp_path / "events.jsonl"
    generic_file.write_text(
        '{"kind": "skill", "name": "graphify", "timestamp": "2026-06-01T10:00:00Z"}\n'
        '{"kind": "agent", "name": "Explore"}\n'
    )
    events = parse_generic_jsonl([str(generic_file)])
    assert len(events) == 2
    assert events[0].kind == "skill"
    assert events[1].kind == "agent"
