from guidance_intel.counter import compute_coverage
from guidance_intel.discovery import discover_artifacts, discover_transcripts
from guidance_intel.parser import parse_transcripts
from guidance_intel.reporter import report_json, report_markdown

import json


def test_full_pipeline(repo_path, transcripts_path):
    # Discover
    artifacts = discover_artifacts(repo_path)
    assert len(artifacts) >= 6  # 3 skills + 3 agents + 1 workflow (at minimum)

    # Find transcripts
    transcript_paths = discover_transcripts(repo_path, transcripts_path)
    assert len(transcript_paths) == 3

    # Parse
    events = parse_transcripts(transcript_paths)
    assert len(events) > 0

    # Count
    report = compute_coverage(artifacts, events, repo_path)

    # Verify results
    assert report.sessions_analyzed == 3
    assert report.coverage_percent > 0
    assert "dead-skill" in report.dead_artifacts
    assert "code-reviewer" in report.dead_artifacts

    # Verify graphify was used
    graphify_usage = next(r for r in report.usage if r.artifact_name == "graphify")
    assert graphify_usage.total_count == 2
    assert graphify_usage.session_count == 2

    # Verify Explore was used
    explore_usage = next(r for r in report.usage if r.artifact_name == "Explore")
    assert explore_usage.total_count == 2


def test_json_output_end_to_end(repo_path, transcripts_path):
    artifacts = discover_artifacts(repo_path)
    transcript_paths = discover_transcripts(repo_path, transcripts_path)
    events = parse_transcripts(transcript_paths)
    report = compute_coverage(artifacts, events, repo_path)

    output = report_json(report)
    data = json.loads(output)

    assert "coverage_percent" in data
    assert "dead_artifacts" in data
    assert "usage" in data
    assert data["sessions_analyzed"] == 3


def test_markdown_output_end_to_end(repo_path, transcripts_path):
    artifacts = discover_artifacts(repo_path)
    transcript_paths = discover_transcripts(repo_path, transcripts_path)
    events = parse_transcripts(transcript_paths)
    report = compute_coverage(artifacts, events, repo_path)

    output = report_markdown(report)
    assert "Coverage" in output
    assert "dead-skill" in output
