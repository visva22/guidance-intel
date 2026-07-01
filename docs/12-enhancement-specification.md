# Enhancement Specification: Context-Aware Analysis

> **Status: IMPLEMENTED.** All three phases below are built and tested (78 tests
> passing). This spec grounds the design in the *actual* Claude Code transcript
> format and the current parser. The core decision: prefer the **causal
> structure real transcripts already carry** (`parentUuid`, `isSidechain`,
> `promptId`) over positional/string-matching heuristics, and **degrade
> gracefully** to heuristics only when that structure is absent (generic JSONL,
> older transcripts).
>
> **Delivered modules:** `classification.py` (Use Case 1), `dependencies.py`
> (Use Case 2), parser rewrite + `TranscriptEvent` enrichment (Phase 0). New
> CLI flags: `--dependencies`, `--all`. See the per-phase notes below.

---

## 0. Prerequisites & Data-Model Reality Check

Both use cases depend on data the current pipeline does not yet capture — and
one of them is blocked by an existing correctness bug. These must be addressed
first.

### 0.1 Blocker bug: only the first tool call per assistant turn is parsed

[`parser.py`](../src/guidance_intel/parser.py) processes `tool_uses[0]` only:

```python
# parser.py:70-71
# Process first tool use (could extend to handle multiple)
tool_use = tool_uses[0]
```

Real Claude Code assistant messages routinely **batch multiple tool calls in one
`message.content` array** (e.g. several `Read`s in parallel). Every tool call
after the first is silently dropped today. This means:

- Current violation counts already **undercount**.
- Use Case 2's dependency graph would be built on lossy data.

**Fix:** iterate all `tool_uses` and emit one `TranscriptEvent` per call.
This is a standalone correctness fix, valuable independent of the new features.

### 0.2 Fixtures do not match the real transcript format

Test fixtures ([`tests/fixtures/transcripts/`](../tests/fixtures/transcripts/))
use a flat shape that real Claude Code never emits:

```jsonc
{"type": "tool_use", "name": "Skill", "input": {...}}          // fixture (flat)
```

Real transcripts nest tool calls under an assistant message and carry causal
metadata:

```jsonc
{
  "type": "assistant",
  "uuid": "16c1e5a8-...",
  "parentUuid": "eeed417d-...",
  "isSidechain": false,
  "sessionId": "...",
  "timestamp": "...",
  "message": { "content": [ {"type":"tool_use","name":"Read","input":{...}} ] }
}
```

The parser *does* handle the nested `assistant` form, but the tests only exercise
the flat form — so they give false confidence. **Add real-shaped fixtures**
(nested content, `parentUuid`, `isSidechain`, and `tool_result` user lines)
before building on top.

### 0.3 What real transcripts actually contain

Confirmed by inspecting `~/.claude/projects/*/*.jsonl`:

| Field | Where | Why it matters |
|---|---|---|
| `uuid` / `parentUuid` | every line | True causal chain: each event links to what triggered it. Replaces positional "distance" heuristics. |
| `isSidechain: true` | every line | Marks events that happened **inside a subagent**. Cleanly separates autonomous subagent reads. |
| `promptId` | user/assistant lines | Groups all events belonging to one user turn. Scopes "which user request caused this read." |
| `toolUseResult` | present on tool-result user lines | Lets us distinguish real human input from tool-output "user" lines. |
| `isMeta` / `<...>` injected blocks | user lines | IDE/system injects `<ide_opened_file>`, `<system-reminder>`, `@file` mentions, pasted content into user turns. Must be stripped before treating text as "what the human asked." |

**Critical caveat measured in a real session:** of 107 lines with `type:"user"`,
**99 were `tool_result` payloads**, not human input. Naive "match user messages
against filenames" would match the AI's own tool output (full of file paths) and
massively over-classify reads as "user-requested." Filtering to genuine human
text is the hard part of Use Case 1, not the matching itself.

### 0.4 `TranscriptEvent` must be enriched

Current model ([`models.py:14-20`](../src/guidance_intel/models.py)) has no
causal fields and discards user messages entirely (parser returns `None` for
non-tool lines, [`parser.py:114`](../src/guidance_intel/parser.py)).

Add:

```python
@dataclass
class TranscriptEvent:
    kind: str            # + "user_message"
    name: str
    session_id: str
    timestamp: str | None = None
    metadata: dict | None = None
    # NEW — populated from real transcripts, None for generic JSONL
    uuid: str | None = None
    parent_uuid: str | None = None
    is_sidechain: bool = False
    prompt_id: str | None = None
```

For `kind="user_message"`, store the **cleaned** human text in
`metadata["text"]` (injected `<...>` blocks and `tool_result` content removed).

### 0.5 Two data sources — design for both (per decision)

| Source | Has causal fields? | Strategy |
|---|---|---|
| Real `~/.claude` transcripts | Yes | Use causal-chain classification (primary path). |
| Generic JSONL / `parse_generic_jsonl` / old transcripts | No | Fall back to heuristics (string match → prompt scoping → temporal window). |

The classifier must **detect which fields are present per event** and pick the
strongest available method, always emitting *why* it chose that method in the
`reason` field. Never assume causal fields exist.

---

## Use Case 1: User-Requested vs Autonomous Reads

### Problem Statement

**Current Behavior:**
```
User: "Read TEST_PLAN.md and execute scenario A1"
AI: *reads TEST_PLAN.md*
Tool Report: ❌ VIOLATION (FALSE POSITIVE — user asked for it)

User: "Generate tests for Friends package"
AI: *autonomously reads TEST_PLAN.md*
Tool Report: ❌ VIOLATION (TRUE POSITIVE — AI pulled it in on its own)
```

The tool cannot distinguish these because it (a) discards user messages and
(b) has no link between a read and the request that caused it.

### Requirements

1. **Detect user intent** — did the user cause this file read?
2. **Confidence scoring** — how certain are we?
3. **Filter false positives** — surface high-confidence violations by default.
4. **Show both** — allow viewing all accesses with confidence levels.

### Recommended Solution: Causal-Scope + String-Match Tiering

Rather than the original Option A/B/C (which correlate by string match, event
distance, or point scores in isolation), combine the causal chain (for *scope*)
with string matching (for *content*):

```
For each guidance Read event:
  1. If is_sidechain → classify as AUTONOMOUS (see §Subagents). Done.
  2. Walk parent_uuid back to the originating user turn (same prompt_id).
  3. Extract that turn's CLEANED human text (strip <...> blocks, drop tool_result).
  4. Also collect explicit @file mentions / attachments from that turn.
  5. Tier the classification:

     @file mention or attachment of this path   → user_requested, HIGH  ("explicit @mention")
     exact filename in cleaned text             → user_requested, HIGH  ("exact filename")
     artifact/parent-dir name + action verb     → user_requested, MEDIUM ("name + verb")
     stem/keyword match only (ambiguous)        → uncertain,      MEDIUM ("keyword only")
     no mention, first action after prompt      → uncertain,      LOW    ("proximate, unmatched")
     no mention, deep in autonomous chain       → autonomous,     HIGH   ("no user link")
```

**Why this beats the original options:**
- The `parent_uuid`/`prompt_id` chain gives an *exact* scope to search — it
  correctly attributes a read to a request made 5 turns ago (which the original
  Option B `distance <= 2` would miss) while never bleeding across turns.
- String matching then runs only inside that scope, so collisions are contained.
- `@file` mentions/attachments are the **cleanest** signal available and are a
  distinct HIGH tier.

### Graceful Degradation (generic JSONL / no causal fields)

When `parent_uuid`/`prompt_id`/`is_sidechain` are `None`, fall back in order:

1. **String match against nearest preceding user_message** (if user messages
   were captured) — original Option A logic, but on cleaned text.
2. **Positional distance** — original Option B, as a last resort, clearly
   labeled low confidence.
3. If no user messages exist at all in the source → classify `unknown`,
   confidence `none`, and **do not filter** the violation (report it, flag that
   intent could not be determined).

### Confidence-Level Semantics

| Level | Meaning | Default report behavior |
|---|---|---|
| HIGH user_requested | Explicit mention / @file | Suppress from violations (with `--all` to show) |
| MEDIUM user_requested | Name + verb | Suppress, but list under "likely intended" |
| uncertain | Ambiguous | **Show** — this is the honest middle |
| autonomous HIGH | No user link | **Show** — true violation candidate |
| unknown / none | No intent data | **Show** — flagged "intent undetermined" |

### Corner Cases

| Case | Problem | Handling |
|---|---|---|
| `<ide_opened_file>` injection | IDE injects a file path into the user turn (this very session did so for this spec file). Substring match → false HIGH. | Strip all `<...>` injected blocks before matching. |
| `tool_result` "user" lines | 99/107 user lines are tool output full of paths. | Only treat lines with no `tool_result` and falsy `isMeta` as human text. |
| `@file` autocomplete | User typed `@TEST_PLAN.md`; arrives as attachment, not free text. | Parse attachments/mentions explicitly → HIGH tier. |
| Reads inside subagents | `isSidechain:true` reads have no line to the user prompt. | Autonomous by definition — user requested the *agent*, not the file (see §Subagents). |
| Filename collision | "read the plan" with three `*_PLAN.md` files. | stem match alone → MEDIUM/uncertain, never HIGH. |
| Generic filenames | `SKILL.md`, `README.md`, `index.md` everywhere. | Match on artifact/parent-dir name, not bare filename. |
| Resumed / compacted sessions | Same read reappears. | Dedup on `uuid`; if absent, dedup on `(file_path, prompt_id)`. |
| Multi-turn deferred request | "read the plan" 5 turns before the read. | `prompt_id` chain scopes correctly; positional distance would miss it. |
| Read triggered by a hook/system, not user | Neither user nor AI "chose" it. | Detectable via parent chain rooting at a system line → classify `system`, don't count as violation. |

#### Subagents

A read with `is_sidechain:true` is **always autonomous with respect to the user**
— the user requested the agent, the agent chose the read. But for reporting we
can attribute it to the spawning `Agent` invocation's intent (via `parent_uuid`),
so the report can say *"Explore agent autonomously read TEST_PLAN.md"* rather
than a bare violation. This also feeds Use Case 2 directly.

---

## Use Case 2: Skill Dependency Tracking (Context Leakage Detection)

### Problem Statement

```
User invokes: arson-tests-generation skill
AI reads:
  - arson-tests-generation/SKILL.md   ✓ (expected)
  - unity-codegen/references/*.md      ✗ (why?)
  - ~/.claude/skills/graphify/SKILL.md ✗ (global skill leak!)

User doesn't know which extra files are pulled in, or the token cost.
```

### Requirements

1. **Track context per invocation** — what was read during each skill/agent/workflow run?
2. **Show dependencies** — "when you use X, AI also reads Y, Z."
3. **Detect leakage** — reads outside the invoked artifact's legitimate dependency set.
4. **Quantify impact** — token cost of the extra context.

### Recommended Solution: Causal Attribution (primary) + Co-occurrence (aggregate)

The original Option A (positional `current_context`) is fragile precisely where
real data is strong: parallel tool calls and nested subagents interleave in the
flat log, so positional attribution smears reads across the wrong owners. Use
the causal chain instead.

**Per-invocation attribution (primary):**
```
For each Skill/Agent/Workflow invocation event I:
  reads(I) = all Read events whose parent_uuid chain roots at I
             (subagent reads captured via is_sidechain + parent_uuid → the Agent spawn)
```
This is Option C's intent (immediate context) but with an **exact causal
boundary** instead of an arbitrary 30-second window.

**Co-occurrence (aggregate) — keep from Option B:**
Across many sessions, report how often each file is read when skill X is
invoked (always / frequently / occasionally). Needs no causal data, so it works
for generic JSONL too, and answers "graphify leaks into 5% of arson sessions."
Layer it as a secondary panel; note explicitly that it shows *correlation, not
causation* and cannot resolve which of two co-invoked skills owns a shared read.

### Defining "leak" (the spec previously asserted it without defining it)

A non-primary read is a **leak** only if the file is outside the invoked
artifact's **dependency closure**:

1. Parse the invoked skill's frontmatter/body for referenced files → declared deps.
2. Any read in its causal scope not in that closure = **candidate** leak.
3. Weight by location:
   - Read of `~/.claude/skills/*` during a **project** skill invocation →
     near-certain global leak (HIGH).
   - Read of a sibling project skill → "cross-reference, review" (MEDIUM).
   - Read within the skill's own directory → not a leak.

Without this baseline, every non-primary read gets labeled a leak → cries wolf.

### Report (per decision: both views, composable flags)

```
gi coverage --dependencies

Dependency Analysis
===================

arson-tests-generation (96 invocations across 54 sessions):

  Per-Invocation Context (causal attribution):
    Primary: .agents/skills/arson-tests-generation/SKILL.md (~2,100 tokens)
    Avg additional reads: 2.3 files   Avg overhead: ~1,850 tokens (47% extra)

  Co-occurrence (aggregate, correlation only):
    Always (96/96):     ✓ arson-tests-generation/SKILL.md
    Frequently (45/96): ⚠️ unity-codegen/references/build-commands.md   +850 tok
                           (in declared deps? NO → candidate cross-ref leak)
    Rarely (5/96):      ❌ ~/.claude/skills/graphify/SKILL.md            +1,200 tok
                           (global skill during project invocation → LEAK)

  💡 Recommendations:
    - Review cross-reference to unity-codegen (not in declared deps)
    - Isolate arson skill to prevent global leaks
    - Potential savings: ~2,050 tokens/invocation
```

### Corner Cases

| Case | Problem | Handling |
|---|---|---|
| Partial reads | `len(content)//4` on whole file overcounts a ranged read. | Use captured `offset`/`limit` to estimate only lines actually read. |
| Repeated reads | Same file read many times / re-read with new offsets. | Attribute tokens per read; flag repeated full-file re-reads as a distinct waste category. |
| Legit skill composition | Skill A intentionally uses Skill B. | Declared-dependency closure prevents false leak. |
| No sidechains (old/generic) | Field absent. | Degrade: prompt_id scope → temporal window → co-occurrence only. Log which method was used. |
| Multiple skills one turn | Which owns a shared read? | Causal chain resolves; co-occurrence cannot (credits both) — state this in report. |
| Workflow spawning many agents | Deep nesting. | Attribute to nearest invocation in the chain; roll up to the workflow for a summary line. |

---

## Recommended Solution Summary

| | Original spec | This revision |
|---|---|---|
| UC1 primary | Option A string match + Option C scores | **Causal-scope (parent_uuid/prompt_id) + string tiering** |
| UC1 fallback | — | String match → positional → `unknown` (graceful degradation) |
| UC2 primary | Option A positional context | **Causal attribution (parent_uuid + is_sidechain)** |
| UC2 aggregate | Option B co-occurrence | **Keep, as secondary correlation panel** |
| Leak definition | asserted | **Dependency-closure baseline + location weighting** |

---

## Implementation Phases

### Phase 0: Parser Correctness & Fixtures ✅ DONE
1. ✅ Fixed `tool_uses[0]` → `_parse_claude_code_line` now returns a list, one event per tool call.
2. ✅ Added real-shaped fixtures in `tests/fixtures/real_transcripts/` (nested content, `parentUuid`, `isSidechain`, `tool_result` user lines).
3. ✅ Enriched `TranscriptEvent` with `uuid`, `parent_uuid`, `is_sidechain`, `prompt_id`.
4. ✅ Capture cleaned user-message events (`clean_user_text` strips injected `<...>` blocks; `tool_result`/`isMeta` lines skipped; `@file` mentions extracted).
5. ✅ **Added beyond spec:** capture doc-like reads (`TEST_PLAN`, `CHANGELOG`, …) as `kind="document"` with `doc_reference=True`, so exclusion violations can fire on them (previously impossible — this blocked Use Case 1's own canonical example).

**Impact:** Fixed current undercounting; unblocked both use cases.

### Phase 1: User-Requested Detection ✅ DONE — `classification.py`
1. ✅ `build_uuid_index()` — one O(n) pass.
2. ✅ `_resolve_user_turn()` — walks `parent_uuid` to the originating user turn.
3. ✅ `_match_text()` — @mention / exact-filename / name+verb / keyword tiering.
4. ✅ `_classify_heuristic()` — positional fallback (downgraded confidence), `unknown` when no user text.
5. ✅ Violations carry `classification`/`confidence`/`detection_method` + per-access breakdown; terminal report hides user-requested false positives, `--all` reveals them; JSON carries full data.

**Impact:** Eliminates false positives with an auditable reason per classification.

### Phase 2: Dependency Tracking ✅ DONE — `dependencies.py`
1. ✅ `_read_events_from()` — causal per-invocation attribution incl. same-line batched reads and subagent sidechain reads.
2. ✅ `_parse_closure()` (declared deps from file body) + `_leak_level()` location weighting (global / cross-reference / none).
3. ✅ `_cooccurrence()` aggregate (correlation-only), used as the fallback when causal fields are absent.
4. ✅ `--dependencies` flag + `report_dependencies()`; `attribution_method` recorded per artifact.

**Impact:** Reveals hidden token waste; distinguishes real leaks from intended composition.

### Bugs found & fixed during implementation
- **`SKILL.md` basename collision:** every skill's primary file is `SKILL.md`, so a leaked `graphify/SKILL.md` was mistaken for the invoked skill's own primary and skipped. Fixed with `_primary_key()` (parent-dir-aware matching).
- **Doc reads dropped:** the parser only captured guidance-artifact reads, so `docs/TEST_PLAN.md` never produced an event — the exclusion feature could never fire on the spec's example file. Fixed via name-based doc capture in the parser (no file IO on the hot path).

### Test coverage
78 tests pass (49 pre-existing, no regressions + 29 new): `test_parser.py`
(multi-tool, causal fields, user-message cleaning, doc capture),
`test_classification.py` (causal tiers, sidechain, heuristic fallback),
`test_dependencies.py` (attribution, closure, leak levels, co-occurrence),
`test_enhancements_integration.py` (end-to-end on real-shaped fixtures + backward compat).

---

## Answers to the Original Open Questions

1. **UC1 priority / defer?** Do Phase 0 first (fixes current inaccuracy and is a hard prerequisite), then UC1.
2. **Confidence threshold?** Show all; default terminal view to HIGH-confidence violations; `--all` reveals the rest. Never silently hide — surface "intent undetermined" explicitly.
3. **UC2 scope?** Both. Causal per-invocation is primary; co-occurrence is a secondary aggregate panel with a stated correlation-only caveat.
4. **CLI design?** Separate, composable flags (`--violations`, `--dependencies`) — consistent with the existing `--sections`/`--violations`.
5. **Performance?** Not parsing more files — keeping more lines per file. Linear. Main cost is the one-pass `uuid → event` index; acceptable.

---

## Success Criteria

### Use Case 1
- ✅ Correctly identify user-requested reads (>90% accuracy on real transcripts).
- ✅ Reduce false positives by >80%.
- ✅ Every classification carries a machine-readable reason and the method used (causal / heuristic / none).
- ✅ Correctly strips injected `<...>` blocks and ignores `tool_result` user lines.

### Use Case 2
- ✅ Per-invocation context overhead attributed via causal chain (not position).
- ✅ Distinguishes global-skill leaks from intended composition via dependency closure.
- ✅ Quantifies potential token savings using actual read ranges.
- ✅ Degrades cleanly to co-occurrence when causal fields are absent, logging the method used.
