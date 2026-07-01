import os

import click

from .counter import compute_coverage
from .discovery import discover_artifacts, discover_transcripts
from .parser import parse_generic_jsonl, parse_transcripts
from .reporter import report_json, report_markdown, report_terminal


@click.group()
@click.version_option()
def cli():
    """Guidance Intelligence — code coverage for your AI guidance files."""
    pass


@cli.command()
@click.option("--repo", default=".", help="Path to the repository to analyze.")
@click.option("--transcripts", default=None, help="Path to transcript files or directory.")
@click.option("--format", "fmt", type=click.Choice(["terminal", "json", "md"]), default="terminal")
@click.option("--last", default=None, type=int, help="Analyze only the last N sessions.")
@click.option("--sections", is_flag=True, help="Include section-level coverage analysis (shows token waste).")
@click.option("--violations", is_flag=True, help="Check for exclusion violations (AI reading non-AI files).")
def coverage(repo, transcripts, fmt, last, sections, violations):
    """Analyze guidance coverage across agent sessions."""
    repo = os.path.abspath(repo)

    artifacts = discover_artifacts(repo)
    if not artifacts:
        click.echo("No guidance artifacts found in this repository.")
        click.echo("Looking for: .claude/skills/, AGENTS.md, .claude/workflows/")
        return

    transcript_paths = discover_transcripts(repo, transcripts)
    if not transcript_paths:
        click.echo("No transcripts found.")
        click.echo("Provide transcripts with: gi coverage --transcripts <path>")
        raise SystemExit(1)

    if last:
        transcript_paths = transcript_paths[-last:]

    events = parse_transcripts(transcript_paths)
    if not events and transcripts:
        events = parse_generic_jsonl(transcript_paths)

    report = compute_coverage(artifacts, events, repo, include_sections=sections, check_violations=violations)

    if fmt == "json":
        click.echo(report_json(report))
    elif fmt == "md":
        click.echo(report_markdown(report))
    else:
        report_terminal(report)


@cli.command()
@click.option("--repo", default=".", help="Path to the repository.")
@click.option("--transcripts", default=None, help="Path to transcript files or directory.")
def discover(repo, transcripts):
    """Show discovered guidance artifacts and transcripts."""
    repo = os.path.abspath(repo)

    artifacts = discover_artifacts(repo)
    transcript_paths = discover_transcripts(repo, transcripts)

    click.echo(f"\nRepository: {repo}\n")

    if artifacts:
        click.echo(f"Guidance Artifacts Found: {len(artifacts)}")
        for a in artifacts:
            click.echo(f"  [{a.kind}] {a.name:<20} {a.source_path}")
    else:
        click.echo("No guidance artifacts found.")

    click.echo()

    if transcript_paths:
        click.echo(f"Transcripts Found: {len(transcript_paths)} sessions")
        if len(transcript_paths) <= 5:
            for p in transcript_paths:
                click.echo(f"  {p}")
        else:
            click.echo(f"  {transcript_paths[0]}")
            click.echo(f"  ... ({len(transcript_paths) - 2} more)")
            click.echo(f"  {transcript_paths[-1]}")
    else:
        click.echo("No transcripts found.")

    click.echo()


@cli.command()
@click.option("--repo", default=".", help="Path to the repository.")
@click.option("--transcripts", default=None, help="Path to transcript files or directory.")
def dead(repo, transcripts):
    """Show only unused/dead guidance artifacts."""
    repo = os.path.abspath(repo)

    artifacts = discover_artifacts(repo)
    if not artifacts:
        click.echo("No guidance artifacts found.")
        return

    transcript_paths = discover_transcripts(repo, transcripts)
    if not transcript_paths:
        click.echo("No transcripts found. Cannot determine dead guidance.")
        raise SystemExit(1)

    events = parse_transcripts(transcript_paths)
    if not events and transcripts:
        events = parse_generic_jsonl(transcript_paths)

    report = compute_coverage(artifacts, events, repo)

    if not report.dead_artifacts:
        click.echo("All guidance artifacts are being used!")
    else:
        click.echo(f"\nDead Guidance ({len(report.dead_artifacts)} artifacts never triggered):\n")
        for name in report.dead_artifacts:
            artifact = next((a for a in artifacts if a.name == name), None)
            source = artifact.source_path if artifact else "unknown"
            click.echo(f"  ✗ {name:<20} ({source})")
        click.echo(f"\nConsider removing these or improving their triggers.\n")


@cli.command()
@click.option("--repo", default=".", help="Path to the repository.")
@click.option("--transcripts", default=None, help="Path to transcript files or directory.")
def stats(repo, transcripts):
    """Show detailed usage statistics per artifact."""
    repo = os.path.abspath(repo)

    artifacts = discover_artifacts(repo)
    if not artifacts:
        click.echo("No guidance artifacts found.")
        return

    transcript_paths = discover_transcripts(repo, transcripts)
    if not transcript_paths:
        click.echo("No transcripts found.")
        raise SystemExit(1)

    events = parse_transcripts(transcript_paths)
    if not events and transcripts:
        events = parse_generic_jsonl(transcript_paths)

    report = compute_coverage(artifacts, events, repo)

    click.echo(f"\nDetailed Statistics ({report.sessions_analyzed} sessions analyzed)\n")

    for record in report.usage:
        click.echo(f"  {record.artifact_name} ({record.artifact_kind})")
        click.echo(f"    Total invocations:  {record.total_count}")
        click.echo(f"    Sessions used in:   {record.session_count}/{record.sessions_total}")
        if record.first_seen:
            click.echo(f"    First seen:         {record.first_seen}")
        if record.last_seen:
            click.echo(f"    Last seen:          {record.last_seen}")
        click.echo()
