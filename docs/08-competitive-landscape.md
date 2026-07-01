# Competitive Landscape

## Summary

No existing tool evaluates whether AI coding agents follow your specific repository
guidance in actual sessions. Adjacent tools exist in five categories — each solves a
different problem.

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│   "Are my instructions       "Do my instructions     "Was the     │
│    well-written?"             change behavior?"       agent        │
│                                                      following    │
│   agnix, skilldoctor,        cceval, AgentProbe,     them?"       │
│   claude-md-lint             agents-md-evals                      │
│                                                      guidance-    │
│   ──── LINTERS ────          ── A/B TESTERS ──      intel (US)   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Category 1: Instruction File Linters & Validators

These tools check whether your guidance artifacts are *structurally valid and
well-written*. They never look at agent behavior.

### agnix (303 stars)
- **GitHub**: github.com/agent-sh/agnix
- **What it does**: Linter and LSP for CLAUDE.md, AGENTS.md, SKILL.md. Validates
  structure, offers IDE autofix suggestions.
- **How it differs from us**: Evaluates the *quality of the document*. Does not
  check whether the agent *followed* it. Analogous to a spell-checker vs. a
  comprehension test.

### skilldoctor (studiomeyer-io)
- **GitHub**: github.com/studiomeyer-io/skilldoctor
- **What it does**: Linter + security scanner for skill files. Produces A-F grades.
  SARIF output for CI.
- **How it differs from us**: Grades the *artifact itself* for security risks and
  structure. Does not analyze agent sessions.

### claude-md-lint (yuziri-open)
- **GitHub**: github.com/yuziri-open/claude-md-lint
- **What it does**: Validates CLAUDE.md and SKILL.md structure.
- **How it differs from us**: Syntax checking only. No behavioral analysis.

### MDA (610 stars)
- **GitHub**: github.com/sno-ai/mda
- **What it does**: Markdown-based spec format for agent documents. Compiles to
  SKILL.md, AGENTS.md, CLAUDE.md with schema validation and dependency graphs.
- **How it differs from us**: An authoring and compilation tool. Helps *write*
  guidance, doesn't measure if it's *used*.

---

## Category 2: A/B Testing & Effectiveness Benchmarks

These tools test whether instructions *matter at all* — do they change agent behavior
compared to a baseline? They don't check compliance with specific rules.

### cceval (johnlindquist)
- **GitHub**: github.com/johnlindquist/cceval
- **What it does**: Runs Claude Code with/without CLAUDE.md against task suites.
  Measures behavioral differences (file reading, permission seeking, verification).
  Found that 4-line instructions beat verbose ones.
- **How it differs from us**: Answers "does this instruction change behavior?" not
  "did the agent follow it correctly in this session?" Requires running new
  experiments, can't analyze past sessions.

### agents-md-evals (vltansky, archived)
- **GitHub**: github.com/vltansky/agents-md-evals
- **What it does**: A/B isolation testing. Physically removes instruction files,
  runs agent, compares results. Measures which rules are redundant.
  Found: 25/26 assertions passed identically with and without a 755-line file.
- **How it differs from us**: Tests *discrimination* (does the rule matter?), not
  *compliance* (was the rule followed?). Destructive test methodology — can't
  analyze existing sessions.

### AgentProbe (sergeyklay)
- **GitHub**: github.com/sergeyklay/agentprobe
- **What it does**: Statistical benchmarking. Isolated git worktrees per run.
  Cohen's d effect sizes, 95% CI. Tests hypotheses like "does CLAUDE.md help?"
- **How it differs from us**: Academic rigor for measuring *impact*, not
  *compliance*. Requires controlled experiments, not post-hoc analysis.

---

## Category 3: Runtime Guardrails & Policy Enforcement

These tools *block* bad behavior in real-time. They don't evaluate or score — they
prevent. They also require their own policy definitions, separate from your existing
guidance.

### Invariant Labs (433 stars)
- **GitHub**: github.com/invariantlabs-ai/invariant
- **What it does**: Rule-based security proxy for AI agents. Intercepts requests,
  evaluates against Python-inspired rules, blocks violations.
- **How it differs from us**: Real-time enforcement, not post-hoc evaluation.
  Requires writing Invariant-specific rules. Doesn't read your CLAUDE.md.

### Sponsio (478 stars)
- **GitHub**: github.com/SponsioLabs/Sponsio
- **What it does**: Deterministic safety contracts using Fuzzy LTL Monitor.
  0.01ms enforcement. 46 pre-built patterns. 95.6% misalignment block rate.
- **How it differs from us**: Runtime blocker. Operates on its own YAML contracts,
  not your existing guidance artifacts. Prevents, doesn't evaluate.

### vectimus (36 stars)
- **GitHub**: github.com/vectimus/vectimus
- **What it does**: Cedar-based policy engine for AI coding agents. Intercepts
  every action, evaluates against deterministic rules.
- **How it differs from us**: Enforcement, not evaluation. Requires writing Cedar
  policies. Doesn't produce compliance reports or suggestions.

### Immunity Agent (213 stars)
- **GitHub**: github.com/PrismorSec/immunity-agent
- **What it does**: Runtime security layer for Claude Code, Cursor, Windsurf.
  Policy engine (0.8ms overhead), supply chain enforcement, secret protection.
- **How it differs from us**: Security-focused enforcement. Could theoretically
  check custom policies, but doesn't auto-discover or evaluate guidance.

### NVIDIA NeMo Guardrails
- **GitHub**: github.com/NVIDIA/NeMo-Guardrails
- **What it does**: Programmable guardrails for LLM conversational systems using
  Colang modeling language.
- **How it differs from us**: Designed for chatbots, not coding agents. Shapes
  dialog flow, doesn't evaluate instruction compliance.

---

## Category 4: Agent Observability Platforms

These platforms trace agent behavior (tool calls, latency, costs) but don't correlate
traces with repository guidance or produce compliance scores.

### LangSmith (LangChain)
- **What it does**: Observability + evaluation + deployment platform. Traces show
  "what your agent did and why." LLM-as-judge evaluators.
- **How it differs from us**: General-purpose evaluation infrastructure. Could be
  configured for compliance checking, but requires building custom evaluators.
  Doesn't auto-discover guidance artifacts.

### Langfuse (open source)
- **What it does**: Open-source LLM engineering platform. Tracing, prompt
  management, evaluations.
- **How it differs from us**: Observability layer. Tracks calls but doesn't map
  them to guidance or score compliance. Requires manual evaluator setup.

### AgentOps
- **What it does**: Agent observability for 400+ LLMs. Time-travel debugging,
  audit logging, cost tracking.
- **How it differs from us**: Operational tracing. Doesn't know about your
  CLAUDE.md or skills.

### Arize
- **What it does**: Trace, eval, learn platform. 1 trillion spans/month.
  Integrates with OpenTelemetry.
- **How it differs from us**: Scale observability. No guidance awareness.

### HoneyHive
- **What it does**: Code evaluators + online evals. Closest to supporting
  instruction compliance among observability tools.
- **How it differs from us**: Flexible enough to *build* compliance checking, but
  doesn't provide it out of the box. No auto-discovery of repo artifacts.

---

## Category 5: Forensic Auditors & Session Analyzers

### agent-audit (scadastrangelove)
- **GitHub**: github.com/scadastrangelove/agent-audit
- **What it does**: Forensic auditor for Claude Code, Codex CLI, OpenClaw sessions.
  Reads session logs. Detects known-bad patterns using 296 bundled rules.
- **How it differs from us**: Uses *generic* bad-pattern rules, not *your repo's
  specific guidance*. Security-focused (exfiltration, injection), not compliance-
  focused. Doesn't correlate with CLAUDE.md or skills.

### Trajex (chanikkyasaai)
- **GitHub**: github.com/chanikkyasaai/trajex
- **What it does**: Agent behavioral testing and anomaly detection. Captures
  execution traces, detects deviations via rule-based assertions or baseline
  learning. SQLite, zero deps.
- **How it differs from us**: Generic trace anomaly detection. No awareness of
  guidance artifacts. You'd need to manually write assertions that replicate
  what's already in your CLAUDE.md.

---

## Category 6: Instruction Quality Graders

### Claude Code Auditor (ordinary9843)
- **GitHub**: github.com/ordinary9843/claude-code-auditor
- **What it does**: Evaluates Claude Code artifacts against Anthropic best
  practices. A-F grades on a 100-point rubric. Covers CLAUDE.md, skills, agents,
  commands, rules, memory files.
- **How it differs from us**: Measures *writing quality* against best practices.
  "Is your SKILL.md well-structured?" not "Did the agent use graphify when it
  should have?"

---

## What Guidance Intelligence Does Differently

| Capability | Linters | A/B Testers | Guardrails | Observability | Forensic | **Us** |
|------------|---------|-------------|------------|---------------|----------|--------|
| Auto-discovers repo guidance | - | - | - | - | - | **Yes** |
| Reads actual agent sessions | - | - | - | Yes | Yes | **Yes** |
| Maps behavior to YOUR guidance | - | - | - | - | - | **Yes** |
| Scores compliance per-artifact | - | - | - | - | - | **Yes** |
| Detects ordering violations | - | - | Partial | - | - | **Yes** |
| Detects skipped mandatory steps | - | - | Partial | - | - | **Yes** |
| Identifies dead/unused guidance | - | Partial | - | - | - | **Yes** |
| Suggests guidance improvements | - | Partial | - | - | - | **Yes** |
| Zero configuration required | Partial | - | - | - | - | **Yes** |
| Works on past sessions | - | - | - | Yes | Yes | **Yes** |
| Requires custom rules/policies | - | - | Yes | Yes | - | **No** |

---

## Our Position

```
                    ┌─────────────────────────────────┐
                    │     GUIDANCE LIFECYCLE           │
                    │                                  │
  WRITE ──────►  VALIDATE ──────►  ENFORCE ──────►  EVALUATE
                    │                                  │
  (MDA, authoring) │ (agnix,        (Invariant,      │ (guidance-intel)
                    │  skilldoctor)   Sponsio,         │
                    │                 vectimus)        │
                    │                                  │
                    │  "Is it         "Block bad       │  "Was it
                    │   valid?"        behavior"       │   followed?"
                    └─────────────────────────────────┘
```

We occupy the **evaluate** position — the last mile that nobody has built.
All other tools are complementary, not competitive.

---

## Complementary Tool Pairings

| Use With | Why |
|----------|-----|
| agnix | Lint your guidance for structure, then use us to measure if it works |
| cceval / AgentProbe | Test whether instructions matter, then use us to track ongoing compliance |
| Invariant / Sponsio | Enforce critical rules in real-time, use us to audit what slipped through |
| Claude Code Auditor | Grade artifact quality, then use us to see if quality correlates with usage |
| Trajex | Get generic traces, use us to add guidance-aware interpretation |

---

## Why This Gap Exists

1. **Guidance artifacts are new** — CLAUDE.md, SKILL.md became standard only in
   2025-2026. The tooling ecosystem hasn't caught up.

2. **Cross-cutting concern** — requires both repo-parsing AND transcript-parsing.
   Linter authors don't read transcripts. Observability authors don't read CLAUDE.md.

3. **No standard format** — each agent (Claude, Cursor, Copilot) uses different
   file structures. A tool needs to understand all of them.

4. **Post-hoc evaluation is harder than enforcement** — blocking is binary (allow/deny).
   Evaluation requires matching, scoring, and judgment calls.

5. **No commercial incentive yet** — guidance authoring is still early-adopter
   territory. The market for evaluation tooling follows adoption.
