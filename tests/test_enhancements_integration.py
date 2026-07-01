"""End-to-end tests for the context-aware enhancements against real-shaped fixtures."""
import glob

from guidance_intel.counter import compute_coverage
from guidance_intel.discovery import discover_artifacts
from guidance_intel.parser import parse_transcripts
from guidance_intel.reporter import report_json
import json


def _run(repo_path, real_transcripts_path, **kwargs):
    artifacts = discover_artifacts(repo_path)
    paths = sorted(glob.glob(f"{real_transcripts_path}/*.jsonl"))
    events = parse_transcripts(paths)
    return compute_coverage(artifacts, events, repo_path, **kwargs)


def test_violation_classified_with_mixed_accesses(repo_path, real_transcripts_path):
    report = _run(repo_path, real_transcripts_path, check_violations=True)
    tp = next(v for v in report.exclusion_violations if v.file_path.endswith("TEST_PLAN.md"))
    # Read once on user request ("Read docs/TEST_PLAN.md...") and once autonomously.
    assert tp.access_count == 2
    assert tp.user_requested_count == 1
    assert tp.autonomous_count == 1
    # Headline prefers the autonomous (true-positive) access.
    assert tp.classification == "autonomous"
    assert tp.detection_method == "causal"


def test_dependencies_attribute_sidechain(repo_path, real_transcripts_path):
    report = _run(repo_path, real_transcripts_path, include_dependencies=True)
    explore = next(d for d in report.dependency_reports if d.artifact_name == "Explore")
    dep = next(d for d in explore.dependencies if d.file_path.endswith("graphify/SKILL.md"))
    assert dep.via_sidechain is True


def test_json_includes_classification_and_dependencies(repo_path, real_transcripts_path):
    report = _run(repo_path, real_transcripts_path, check_violations=True, include_dependencies=True)
    data = json.loads(report_json(report))
    assert "exclusion_violations" in data
    assert "classification" in data["exclusion_violations"][0]
    assert "dependencies" in data
    assert data["dependencies"][0]["attribution_method"] == "causal"


def test_backward_compat_flat_fixtures(repo_path, transcripts_path):
    """Old flat fixtures (no causal fields) still parse and count."""
    report = _run(repo_path, transcripts_path)
    assert report.sessions_analyzed == 3
