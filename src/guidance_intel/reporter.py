from __future__ import annotations

import json
from pathlib import Path

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

    # Section-level reporting if available
    if report.section_reports:
        _report_sections(console, report)

    # Exclusion violations if available
    if report.exclusion_violations:
        _report_violations(console, report)


def _report_sections(console: Console, report: CoverageReport) -> None:
    """Display section-level coverage details."""
    console.print("\n[bold]Section-Level Coverage[/bold]")
    console.print("=" * 40)
    console.print()

    # Show top artifacts with most token waste
    top_waste = sorted(report.section_reports, key=lambda r: r.token_waste_estimate, reverse=True)[:5]

    for artifact_report in top_waste:
        if artifact_report.token_waste_estimate == 0:
            continue  # Skip if no waste

        console.print(f"[bold]{artifact_report.artifact_name}[/bold] ({artifact_report.artifact_kind})")
        console.print(f"  File: {artifact_report.file_path}")
        console.print(f"  Total invocations: {artifact_report.total_invocations}")
        console.print(f"  Dead sections: {artifact_report.dead_section_count}/{len(artifact_report.sections)}")
        console.print(f"  [yellow]Token waste estimate: ~{artifact_report.token_waste_estimate:,} tokens/invocation[/yellow]")
        console.print()

        # Show sections sorted by usage (dead ones first)
        sorted_sections = sorted(artifact_report.sections, key=lambda s: (not s.is_dead, -s.usage_count))

        for section in sorted_sections[:8]:  # Show top 8 sections
            if section.is_dead:
                status = "[red]DEAD (0%)[/red]"
            elif section.usage_percentage < 25:
                status = f"[yellow]LOW ({section.usage_percentage}%)[/yellow]"
            else:
                status = f"[green]{section.usage_percentage}%[/green]"

            console.print(f"    {section.section_title:<30} {status:>20} (lines {section.line_range}, ~{section.token_estimate} tokens)")

        if len(artifact_report.sections) > 8:
            console.print(f"    ... and {len(artifact_report.sections) - 8} more sections")

        console.print()


def _report_violations(console: Console, report: CoverageReport) -> None:
    """Display exclusion violations."""
    console.print("\n[bold red]⚠️  EXCLUSION VIOLATIONS[/bold red]")
    console.print("=" * 40)
    console.print()

    if not report.exclusion_violations:
        console.print("[green]No violations detected.[/green]")
        return

    total_waste = sum(v.total_token_waste for v in report.exclusion_violations)

    console.print(f"[yellow]Files marked as excluded but read by AI:[/yellow]\n")

    for violation in report.exclusion_violations:
        console.print(f"[red]❌ {Path(violation.file_path).name}[/red]")
        console.print(f"  Location: {violation.file_path}")
        console.print(f"  Reason: {violation.exclusion_reason}")
        console.print(f"  Times accessed: {violation.access_count}")
        console.print(f"  Token waste: ~{violation.token_estimate:,} tokens/access")
        console.print(f"  [yellow]Total waste: ~{violation.total_token_waste:,} tokens[/yellow]")
        console.print(f"  Sessions: {', '.join(violation.sessions[:5])}")
        if len(violation.sessions) > 5:
            console.print(f"            ... and {len(violation.sessions) - 5} more")

        # Recommendation
        console.print(f"\n  💡 [cyan]Recommendation:[/cyan]")
        if "[Auto-detected]" in violation.exclusion_reason:
            console.print(f"     • Add ai-exclude: true to frontmatter if this file shouldn't be read")
            console.print(f"     • Or move to docs/ directory outside guidance paths")
        else:
            console.print(f"     • Move to docs/ directory outside .agents/ or .claude/")
            console.print(f"     • Or remove ai-exclude marker if AI should use this file")
        console.print()

    console.print(f"[bold]Total Exclusion Violations:[/bold] {len(report.exclusion_violations)} files")
    console.print(f"[bold yellow]Total Token Waste:[/bold yellow] ~{total_waste:,} tokens")
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

    # Add section reports if available
    if report.section_reports:
        data["section_coverage"] = [
            {
                "artifact_name": sr.artifact_name,
                "artifact_kind": sr.artifact_kind,
                "file_path": sr.file_path,
                "total_invocations": sr.total_invocations,
                "dead_section_count": sr.dead_section_count,
                "token_waste_estimate": sr.token_waste_estimate,
                "sections": [
                    {
                        "title": s.section_title,
                        "line_range": s.line_range,
                        "usage_count": s.usage_count,
                        "usage_percentage": s.usage_percentage,
                        "token_estimate": s.token_estimate,
                        "is_dead": s.is_dead,
                    }
                    for s in sr.sections
                ],
            }
            for sr in report.section_reports
        ]

    # Add exclusion violations if available
    if report.exclusion_violations:
        data["exclusion_violations"] = [
            {
                "file_path": v.file_path,
                "exclusion_reason": v.exclusion_reason,
                "access_count": v.access_count,
                "sessions": v.sessions,
                "token_estimate": v.token_estimate,
                "total_token_waste": v.total_token_waste,
            }
            for v in report.exclusion_violations
        ]

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
