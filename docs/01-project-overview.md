# Project Overview: Guidance Intelligence

## One-line pitch

**Code coverage, but for your AI guidance files.**

## What It Does

Guidance Intelligence (`guidance-intel`) analyzes real AI coding agent sessions to
measure which of your Skills, Agents, and Workflows are actually being used — and
which are dead weight.

```bash
pip install guidance-intel
cd my-repo
gi coverage
```

Output:
```
Guidance Coverage Report
========================

Skills (4 total)
  graphify          ██████████ 47 invocations  (high usage)
  code-review       ████░░░░░░ 12 invocations  (moderate)
  deep-research     ░░░░░░░░░░  0 invocations  (DEAD - never triggered)
  simplify          █░░░░░░░░░  2 invocations  (low usage)

Agents (3 total)
  Explore           ██████████ 89 spawns
  Plan              ███░░░░░░░  8 spawns
  code-reviewer     ░░░░░░░░░░  0 spawns       (DEAD - never spawned)

Workflows (1 total)
  feature-dev       █████░░░░░ 14 runs

Overall Coverage: 64% (7/11 artifacts actively used)
Dead Guidance: 3 artifacts never triggered across 23 sessions
```

## What It Does NOT Do

- Does not test whether skills *can* work (that's QA — use OpenAI eval-skills for that)
- Does not grade instruction *quality* (that's linting — use agnix for that)
- Does not block bad behavior (that's guardrails — use Invariant/Sponsio for that)
- Does not evaluate model quality
- Does not require configuration or test prompts
- Does not need API keys or cloud services

## Target Users

Teams that maintain AI coding guidance and want answers to:
- "Which of my skills are actually being used?"
- "Is anyone triggering this workflow I spent 3 days writing?"
- "Can I safely delete this agent definition?"
- "Which parts of my guidance are load-bearing vs. cargo cult?"

## How It Differs From Existing Tools

| Tool | What it does | What we do differently |
|------|-------------|----------------------|
| OpenAI eval-skills | QA: "does my skill work?" (synthetic tests) | Analytics: "is my skill used?" (real sessions) |
| cceval / AgentProbe | A/B: "does this instruction change behavior?" | Coverage: "how often is it triggered?" |
| agnix / skilldoctor | Lint: "is my SKILL.md well-structured?" | Usage: "is my SKILL.md actually invoked?" |
| Claude Code Auditor | Grade: "A-F quality score" | Coverage: "used 47 times vs. never" |

**Analogy**: They're the linter and test runner. We're `pytest --cov`.

## MVP Scope

| Feature | Included |
|---------|----------|
| Auto-discover skills, agents, workflows in repo | Yes |
| Parse Claude Code session transcripts | Yes |
| Count invocations per artifact | Yes |
| Identify dead/unused guidance | Yes |
| Usage frequency over time | Yes |
| Terminal coverage report | Yes |
| JSON export for CI integration | Yes |
| Markdown report for sharing | Yes |
| Zero configuration | Yes |
| Generic JSONL input (non-Claude agents) | Yes |
| Line-level instruction coverage | No (future) |
| A/B testing capabilities | No (different tool) |
| Real-time monitoring | No (future) |
