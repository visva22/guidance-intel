import json

from guidance_intel.models import CoverageReport, UsageRecord
from guidance_intel.reporter import report_json, report_markdown


def _make_report():
    return CoverageReport(
        repo_path="/test/repo",
        analyzed_at="2026-06-30T14:00:00Z",
        sessions_analyzed=3,
        total_artifacts=4,
        used_artifacts=3,
        dead_artifacts=["dead-skill"],
        coverage_percent=75.0,
        usage=[
            UsageRecord(artifact_name="graphify", artifact_kind="skill", total_count=5, session_count=3, sessions_total=3),
            UsageRecord(artifact_name="Explore", artifact_kind="agent", total_count=3, session_count=2, sessions_total=3),
            UsageRecord(artifact_name="code-review", artifact_kind="skill", total_count=2, session_count=2, sessions_total=3),
            UsageRecord(artifact_name="dead-skill", artifact_kind="skill", total_count=0, session_count=0, sessions_total=3),
        ],
    )


def test_json_output_valid():
    output = report_json(_make_report())
    data = json.loads(output)
    assert isinstance(data, dict)


def test_json_contains_score():
    output = report_json(_make_report())
    data = json.loads(output)
    assert data["coverage_percent"] == 75.0
    assert data["total_artifacts"] == 4
    assert data["used_artifacts"] == 3


def test_json_contains_usage():
    output = report_json(_make_report())
    data = json.loads(output)
    assert len(data["usage"]) == 4
    assert data["usage"][0]["artifact_name"] == "graphify"


def test_markdown_has_sections():
    output = report_markdown(_make_report())
    assert "# Guidance Coverage Report" in output
    assert "## Dead Guidance" in output
    assert "## Usage Details" in output


def test_markdown_lists_dead():
    output = report_markdown(_make_report())
    assert "dead-skill" in output


def test_markdown_has_table():
    output = report_markdown(_make_report())
    assert "| graphify |" in output
    assert "| Artifact |" in output
