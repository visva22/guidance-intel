from __future__ import annotations

import json

from rich.console import Console

from .models import CoverageReport, UsageRecord


def report_terminal(report: CoverageReport) -> None:
    console = Console()

    console.print()
    console.print("[bold]Guidance Coverage Report[/bold]")
    console.print("=" * 40)
    console.print()

    by_kind: dict[str, list[UsageRecord]] = {}
    for record in report.usage:
        by_kind.setdefault(record.artifact_kind, []).append(record)

    for kind in ["skill", "agent", "workflow", "instruction"]:
        records = by_kind.get(kind, [])
        if not records:
            continue

        console.print(f"[bold]{kind.title()}s[/bold] ({len(records)} total)")

        max_count = max((r.total_count for r in records), default=1) or 1

        for record in records:
            bar = _usage_bar(record.total_count, max_count)
            label = _usage_label(record)
            dead_marker = "  [red](DEAD)[/red]" if record.total_count == 0 else ""
            console.print(f"  {record.artifact_name:<20} {bar} {record.total_count:>4} invocations  {label}{dead_marker}")

        console.print()

    console.print(f"[bold]Overall Coverage:[/bold] {report.coverage_percent}% ({report.used_artifacts}/{report.total_artifacts} artifacts used)")
    console.print(f"[bold]Sessions Analyzed:[/bold] {report.sessions_analyzed}")

    if report.dead_artifacts:
        console.print(f"[bold red]Dead Guidance:[/bold red] {len(report.dead_artifacts)} artifacts never triggered")
        for name in report.dead_artifacts:
            console.print(f"  [red]✗[/red] {name}")

    console.print()


def report_json(report: CoverageReport) -> str:
    data = {
        "repo_path": report.repo_path,
        "analyzed_at": report.analyzed_at,
        "sessions_analyzed": report.sessions_analyzed,
        "total_artifacts": report.total_artifacts,
        "used_artifacts": report.used_artifacts,
        "dead_artifacts": report.dead_artifacts,
        "coverage_percent": report.coverage_percent,
        "usage": [
            {
                "artifact_name": r.artifact_name,
                "artifact_kind": r.artifact_kind,
                "total_count": r.total_count,
                "session_count": r.session_count,
                "sessions_total": r.sessions_total,
                "first_seen": r.first_seen,
                "last_seen": r.last_seen,
            }
            for r in report.usage
        ],
    }
    return json.dumps(data, indent=2)


def report_markdown(report: CoverageReport) -> str:
    lines = []
    lines.append("# Guidance Coverage Report")
    lines.append("")
    lines.append(f"**Coverage:** {report.coverage_percent}% ({report.used_artifacts}/{report.total_artifacts} artifacts used)")
    lines.append(f"**Sessions Analyzed:** {report.sessions_analyzed}")
    lines.append(f"**Analyzed At:** {report.analyzed_at}")
    lines.append("")

    if report.dead_artifacts:
        lines.append(f"## Dead Guidance ({len(report.dead_artifacts)} artifacts)")
        lines.append("")
        for name in report.dead_artifacts:
            lines.append(f"- ~~{name}~~ — never triggered")
        lines.append("")

    lines.append("## Usage Details")
    lines.append("")
    lines.append("| Artifact | Kind | Invocations | Sessions Used | Status |")
    lines.append("|----------|------|-------------|---------------|--------|")

    for record in report.usage:
        status = "DEAD" if record.total_count == 0 else "active"
        lines.append(
            f"| {record.artifact_name} | {record.artifact_kind} | "
            f"{record.total_count} | {record.session_count}/{record.sessions_total} | {status} |"
        )

    lines.append("")
    return "\n".join(lines)


def _usage_bar(count: int, max_count: int, width: int = 10) -> str:
    if max_count == 0:
        filled = 0
    else:
        filled = round(count / max_count * width)
    return "[green]" + "█" * filled + "░" * (width - filled) + "[/green]"


def _usage_label(record: UsageRecord) -> str:
    if record.total_count == 0:
        return ""
    ratio = record.session_count / record.sessions_total if record.sessions_total > 0 else 0
    if ratio > 0.7:
        return "[green](high)[/green]"
    elif ratio > 0.3:
        return "[yellow](moderate)[/yellow]"
    else:
        return "[dim](low)[/dim]"
