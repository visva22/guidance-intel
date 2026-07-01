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


def test_parses_read_tool_to_skill_file(tmp_path):
    """Test that Read tool calls to skill files are tracked."""
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type": "assistant", "timestamp": "2026-06-01T10:00:00Z", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": ".agents/skills/unity-codegen/SKILL.md"}}]}}\n'
    )
    events = parse_transcripts([str(transcript)])

    assert len(events) == 1
    assert events[0].kind == "skill"
    assert events[0].name == "unity-codegen"
    assert events[0].metadata is not None
    assert events[0].metadata["manual_reference"] is True
    assert events[0].metadata["file_path"] == ".agents/skills/unity-codegen/SKILL.md"


def test_parses_read_tool_to_agents_md(tmp_path):
    """Test that Read tool calls to AGENTS.md are tracked."""
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type": "assistant", "timestamp": "2026-06-01T10:00:00Z", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "AGENTS.md"}}]}}\n'
    )
    events = parse_transcripts([str(transcript)])

    assert len(events) == 1
    assert events[0].kind == "agent"
    assert events[0].name == "AGENTS"
    assert events[0].metadata["manual_reference"] is True


def test_read_tool_with_offset_limit(tmp_path):
    """Test that Read tool offset/limit are captured."""
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type": "assistant", "timestamp": "2026-06-01T10:00:00Z", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": ".claude/skills/test/SKILL.md", "offset": 10, "limit": 50}}]}}\n'
    )
    events = parse_transcripts([str(transcript)])

    assert len(events) == 1
    assert events[0].metadata["offset"] == 10
    assert events[0].metadata["limit"] == 50


def test_read_tool_ignores_non_guidance_files(tmp_path):
    """Test that Read tool calls to non-guidance files are ignored."""
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "src/main.py"}}]}}\n'
    )
    events = parse_transcripts([str(transcript)])

    assert len(events) == 0  # Non-guidance file ignored


def test_read_tool_prompts_directory(tmp_path):
    """Test Read tool tracking for prompts/ directory."""
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "prompts/code-review.md"}}]}}\n'
    )
    events = parse_transcripts([str(transcript)])

    assert len(events) == 1
    assert events[0].kind == "skill"
    assert events[0].name == "code-review"


def test_read_tool_workflows_directory(tmp_path):
    """Test Read tool tracking for workflows/ directory."""
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": ".claude/workflows/feature-dev.yaml"}}]}}\n'
    )
    events = parse_transcripts([str(transcript)])

    assert len(events) == 1
    assert events[0].kind == "workflow"
    assert events[0].name == "feature-dev"
