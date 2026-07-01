from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from .models import CoverageReport, UsageRecord


def report_terminal(report: CoverageReport, show_all: bool = False) -> None:
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
        _report_violations(console, report, show_all=show_all)


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


def _is_user_requested(v) -> bool:
    """A violation dominated by user-requested reads is a false positive by default."""
    return v.classification == "user_requested"


def _report_violations(console: Console, report: CoverageReport, show_all: bool = False) -> None:
    """Display exclusion violations, filtering user-requested reads by default (Use Case 1)."""
    console.print("\n[bold red]⚠️  EXCLUSION VIOLATIONS[/bold red]")
    console.print("=" * 40)
    console.print()

    all_violations = report.exclusion_violations
    if not all_violations:
        console.print("[green]No violations detected.[/green]")
        return

    if show_all:
        shown = all_violations
    else:
        shown = [v for v in all_violations if not _is_user_requested(v)]

    suppressed = len(all_violations) - len(shown)

    if not shown:
        console.print("[green]No autonomous violations — all excluded-file reads were user-requested.[/green]")
        if suppressed:
            console.print(f"[dim]({suppressed} user-requested read(s) hidden; use --all to show.)[/dim]")
        console.print()
        return

    total_waste = sum(v.total_token_waste for v in shown)
    console.print("[yellow]Files marked as excluded but read by AI:[/yellow]\n")

    for violation in shown:
        console.print(f"[red]❌ {Path(violation.file_path).name}[/red]")
        console.print(f"  Location: {violation.file_path}")
        console.print(f"  Reason: {violation.exclusion_reason}")
        console.print(
            f"  Intent: [bold]{violation.classification}[/bold] "
            f"({violation.confidence} confidence, via {violation.detection_method}) — {violation.classification_reason}"
        )
        # Access breakdown when mixed.
        if violation.access_count > 1 and (violation.user_requested_count or violation.uncertain_count):
            console.print(
                f"    Accesses: {violation.autonomous_count} autonomous, "
                f"{violation.user_requested_count} user-requested, {violation.uncertain_count} uncertain"
            )
        console.print(f"  Times accessed: {violation.access_count}")
        console.print(f"  Token waste: ~{violation.token_estimate:,} tokens/access")
        console.print(f"  [yellow]Total waste: ~{violation.total_token_waste:,} tokens[/yellow]")
        console.print(f"  Sessions: {', '.join(violation.sessions[:5])}")
        if len(violation.sessions) > 5:
            console.print(f"            ... and {len(violation.sessions) - 5} more")

        # Recommendation
        console.print("\n  💡 [cyan]Recommendation:[/cyan]")
        if "[Auto-detected]" in violation.exclusion_reason:
            console.print("     • Add ai-exclude: true to frontmatter if this file shouldn't be read")
            console.print("     • Or move to docs/ directory outside guidance paths")
        else:
            console.print("     • Move to docs/ directory outside .agents/ or .claude/")
            console.print("     • Or remove ai-exclude marker if AI should use this file")
        console.print()

    console.print(f"[bold]Autonomous Violations Shown:[/bold] {len(shown)} files")
    console.print(f"[bold yellow]Total Token Waste:[/bold yellow] ~{total_waste:,} tokens")
    if suppressed and not show_all:
        console.print(f"[dim]{suppressed} user-requested read(s) hidden as false positives; use --all to show.[/dim]")
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
                "classification": v.classification,
                "confidence": v.confidence,
                "classification_reason": v.classification_reason,
                "detection_method": v.detection_method,
                "user_requested_count": v.user_requested_count,
                "autonomous_count": v.autonomous_count,
                "uncertain_count": v.uncertain_count,
            }
            for v in report.exclusion_violations
        ]

    # Add dependency reports if available
    if report.dependency_reports:
        data["dependencies"] = [
            {
                "artifact_name": d.artifact_name,
                "artifact_kind": d.artifact_kind,
                "invocation_count": d.invocation_count,
                "session_count": d.session_count,
                "primary_file": d.primary_file,
                "primary_tokens": d.primary_tokens,
                "avg_extra_reads": d.avg_extra_reads,
                "avg_overhead_tokens": d.avg_overhead_tokens,
                "attribution_method": d.attribution_method,
                "cooccurrence": d.cooccurrence,
                "reads": [
                    {
                        "file_path": r.file_path,
                        "read_count": r.read_count,
                        "token_estimate": r.token_estimate,
                        "in_closure": r.in_closure,
                        "leak_level": r.leak_level,
                        "via_sidechain": r.via_sidechain,
                    }
                    for r in d.dependencies
                ],
            }
            for d in report.dependency_reports
        ]

    return json.dumps(data, indent=2)


def report_dependencies(report: CoverageReport) -> None:
    """Display per-invocation dependency / context-leakage analysis (Use Case 2)."""
    console = Console()
    console.print("\n[bold]Dependency Analysis[/bold]")
    console.print("=" * 40)
    console.print()

    if not report.dependency_reports:
        console.print("[dim]No invocations with tracked reads were found.[/dim]\n")
        return

    for d in report.dependency_reports:
        console.print(
            f"[bold]{d.artifact_name}[/bold] ({d.artifact_kind}) — "
            f"{d.invocation_count} invocation(s) across {d.session_count} session(s)"
        )
        console.print(f"  Attribution: {d.attribution_method}")
        if d.primary_file:
            console.print(f"  Primary: {d.primary_file} (~{d.primary_tokens:,} tokens)")
        console.print(
            f"  Avg additional reads: {d.avg_extra_reads:.1f}   "
            f"Avg overhead: ~{d.avg_overhead_tokens:,} tokens"
        )

        if d.dependencies:
            console.print("  Reads within causal scope:")
            for r in sorted(d.dependencies, key=lambda x: x.token_estimate, reverse=True):
                if r.leak_level == "global":
                    marker = "[red]❌ LEAK (global)[/red]"
                elif r.leak_level == "cross-reference":
                    marker = "[yellow]⚠️  cross-reference[/yellow]"
                elif r.in_closure:
                    marker = "[green]✓ declared[/green]"
                else:
                    marker = "[green]✓[/green]"
                sc = " [dim](via subagent)[/dim]" if r.via_sidechain else ""
                console.print(
                    f"    {marker} {r.file_path} "
                    f"(×{r.read_count}, ~{r.token_estimate:,} tok){sc}"
                )

        if d.cooccurrence:
            console.print("  Co-occurrence across sessions (correlation only):")
            for fp, frac in sorted(d.cooccurrence.items(), key=lambda kv: kv[1], reverse=True):
                console.print(f"    {frac*100:.0f}%  {fp}")
        console.print()


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
