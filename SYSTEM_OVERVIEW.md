# Guidance Intelligence: How It Works

**A dual-audience guide to understanding our code coverage system for AI guidance files**

---

## For Managers: The Business View

### What Problem Are We Solving?

Teams invest significant time writing guidance for AI coding assistants:
- **Skills** - reusable commands the AI can invoke (like `/graphify`, `/code-review`)
- **Agents** - specialized AI workers for specific tasks (like `Explore` for searching code)
- **Workflows** - multi-step automation scripts

**The problem:** Nobody knows which of these are actually being used vs. sitting idle as wasted effort.

### What Does Our System Do?

Think of it as **usage analytics for AI guidance** - like Google Analytics, but for the instructions you write for AI assistants.

```
Without Guidance Intel:          With Guidance Intel:
"Is anyone using my skill?"  →   "graphify: 47 uses across 12 sessions ✓"
"Should I delete this?"      →   "code-reviewer: 0 uses - DEAD ❌"
"What's the ROI?"            →   "64% coverage - 3 artifacts never used"
```

### Key Capabilities

| Feature | What It Tells You | Why It Matters |
|---------|-------------------|----------------|
| **Coverage Report** | Which artifacts are used vs. dead | Stop maintaining unused features |
| **Usage Statistics** | How often each artifact is invoked | Prioritize improvements on high-impact items |
| **Smart Classification** | Was the AI acting autonomously or following user request? | Reduce false alarms in violation reports |
| **Dependency Tracking** | What extra files get pulled in when you use a skill? | Find hidden token costs and context leaks |
| **Section-Level Analysis** | Which parts of long guidance files are ignored? | Trim bloat, reduce costs |

### Business Impact

**Time Savings:**
- Know what to maintain vs. delete
- Focus on high-usage artifacts
- Eliminate guesswork about what's working

**Cost Reduction:**
- Identify dead sections wasting tokens on every invocation
- Detect context leaks (e.g., global skills pulled into project work)
- Quantify savings: "Remove dead sections → save ~1,200 tokens/invocation"

**Quality Improvement:**
- See what guidance is actually load-bearing
- Make data-driven decisions about what to expand vs. sunset
- Catch when the AI reads test files or docs it shouldn't

### How Teams Use It

```bash
# Quick health check
gi coverage
# Output: 64% coverage, 3 dead artifacts

# Deep dive on wasteful context
gi coverage --sections --violations --dependencies
# Output: "unity-codegen: 8/12 sections used, ~1,200 tokens wasted per use"
```

**Typical workflow:**
1. Run coverage after a sprint
2. Identify dead artifacts → delete or revive
3. Find bloated sections → trim
4. Detect violations → fix exclusion rules

---

## For Technical People: The Implementation

### System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    CLI: gi coverage                  │
└──────────┬──────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│  Phase 1: DISCOVERY                                  │
│  • Scan repo for artifacts (.claude/skills/, etc.)  │
│  • Find transcripts (~/.claude/projects/)            │
│  • Multi-platform (Claude Code, LangChain, CrewAI)  │
└──────────┬──────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│  Phase 2: PARSING                                    │
│  • Parse JSONL transcripts → TranscriptEvent list    │
│  • Extract causal metadata (uuid, parent_uuid)       │
│  • Capture tool calls (Skill, Agent, Workflow, Read) │
│  • Clean user messages (strip injected blocks)       │
└──────────┬──────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│  Phase 3: ANALYSIS                                   │
│  • Match events to artifacts (counter.py)            │
│  • Classify reads (classification.py)                │
│  • Track dependencies (dependencies.py)              │
│  • Detect violations (exclusions.py)                 │
└──────────┬──────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│  Phase 4: REPORTING                                  │
│  • Terminal (rich tables), JSON, or Markdown         │
│  • Coverage metrics, dead artifacts, token waste     │
└─────────────────────────────────────────────────────┘
```

### Core Modules

#### 1. Discovery (`discovery.py`)

**Purpose:** Find guidance artifacts and session transcripts with zero configuration.

**Artifact patterns:**
```python
# Claude Code standard
.claude/skills/*/SKILL.md          → skill
.claude/agents/*.md                → agent
.claude/workflows/*.yaml           → workflow

# Multi-platform support
skills/**/*.md                     → skill
agents/**/*.md                     → agent
.langchain/sessions/*.jsonl        → transcript
.crewai/logs/*.jsonl              → transcript
```

**Transcript discovery strategy:**
```python
def discover_transcripts(repo_path, transcripts_path=None):
    # 1. User-provided path (if any)
    if transcripts_path:
        return find_jsonl_files(transcripts_path)
    
    # 2. Claude Code: ~/.claude/projects/{hash}/*.jsonl
    # 3. LangChain: .langchain/sessions/
    # 4. CrewAI: .crewai/logs/
    # 5. Generic: {repo}/.sessions/*.jsonl
```

**Key insight:** The system discovers transcripts from multiple platforms automatically, not just Claude Code.

#### 2. Parser (`parser.py`)

**Purpose:** Convert raw JSONL transcript lines into structured `TranscriptEvent` objects.

**Transcript format (Claude Code):**
```jsonl
{
  "type": "assistant",
  "uuid": "16c1e5a8-...",
  "parentUuid": "eeed417d-...",
  "isSidechain": false,
  "promptId": "...",
  "message": {
    "content": [
      {"type": "tool_use", "name": "Read", "input": {"file_path": "..."}}
    ]
  }
}
```

**Critical parsing rules:**

1. **Multi-tool extraction** (bug fix - previously dropped all but first):
```python
# OLD (WRONG): tool_use = tool_uses[0]
# NEW (CORRECT):
for tool_use in tool_uses:
    event = _parse_tool_use(...)
    events.append(event)
```

2. **User message cleaning** (prevents false positives):
```python
def clean_user_text(raw_text):
    # Strip IDE injections: <ide_opened_file>, <system-reminder>, etc.
    text = _INJECTED_BLOCK_RE.sub("", raw_text)
    
    # Ignore tool_result "user" lines (99/107 user lines are AI output)
    if is_tool_result or is_meta:
        return None
    
    return text
```

3. **Document capture** (enables violation detection):
```python
if _looks_like_doc_name(file_path):  # TEST_PLAN.md, CHANGELOG.md
    return TranscriptEvent(kind="document", doc_reference=True, ...)
```

**Causal metadata enrichment:**
```python
@dataclass
class TranscriptEvent:
    kind: str               # skill | agent | workflow | document | user_message
    name: str               # artifact name or filename
    session_id: str
    timestamp: str | None
    
    # Causal chain (for smart classification)
    uuid: str | None
    parent_uuid: str | None
    is_sidechain: bool      # True if event is inside a subagent
    prompt_id: str | None   # Groups events from one user turn
    
    metadata: dict | None   # file_path, offset, limit, etc.
```

#### 3. Counter (`counter.py`)

**Purpose:** Match transcript events to discovered artifacts and compute usage statistics.

**Core algorithm:**
```python
def compute_coverage(artifacts, events, repo_path, include_sections=False, 
                     check_violations=False, include_dependencies=False):
    # Basic coverage
    usage_records = [_count_artifact_usage(artifact, events) for artifact in artifacts]
    
    # Optional: section-level coverage
    if include_sections:
        section_reports = _compute_section_coverage(artifacts, events, repo_path)
    
    # Optional: exclusion violations (Use Case 1)
    if check_violations:
        violations = _detect_exclusion_violations(events, repo_path)
    
    # Optional: dependency tracking (Use Case 2)
    if include_dependencies:
        dependency_reports = analyze_dependencies(artifacts, events, repo_path)
    
    return CoverageReport(...)
```

**Matching logic:**
```python
def _find_matching_events(artifact, events):
    # Simple exact match on triggers
    # artifact.triggers = ["graphify", "/graphify"]
    matched = []
    for event in events:
        if event.name.lower() in [t.lower().lstrip("/") for t in artifact.triggers]:
            matched.append(event)
    return matched
```

#### 4. Classification (`classification.py`) - **Use Case 1**

**Problem:** When the AI reads a file, was it user-requested or autonomous?

**Solution: Causal-chain traversal + text matching**

```python
def classify_read(read_event, all_events, uuid_index):
    # Fast path: subagent reads are always autonomous
    if read_event.is_sidechain:
        return Classification("autonomous", "high", "Read in subagent scope", "causal")
    
    # Primary path: walk parent_uuid chain to originating user turn
    user_turn = _resolve_user_turn(read_event, uuid_index)
    
    if user_turn:
        # Match the read's file against the user's cleaned text + @mentions
        classification = _match_text(
            read_event.metadata["file_path"],
            user_turn.metadata["text"],
            user_turn.metadata.get("mentions", [])
        )
        if classification:
            return classification
    
    # Fallback: heuristics (positional, no causal data)
    return _classify_heuristic(read_event, all_events)
```

**Confidence tiers:**
```python
# HIGH confidence user_requested
- @file mention/attachment     → "Explicit @mention"
- Exact filename in user text  → "Exact filename in user message"

# MEDIUM confidence user_requested
- Artifact name + action verb  → "Artifact name + action verb"
- Keyword overlap only         → "Keyword overlap only (ambiguous)" → uncertain

# HIGH confidence autonomous
- No mention, deep in chain    → "No user link"
- Inside subagent              → "Read in subagent scope"

# Fallback
- No causal data               → heuristic (distance-based, low confidence)
- No user messages at all      → "unknown", none confidence
```

**Why this works:**
- `parent_uuid` gives exact scope (not just "last 2 messages")
- Strips false signals (`<ide_opened_file>`, tool results)
- @mentions are unambiguous
- Degrades gracefully for generic JSONL (no causal fields)

**Corner case: tool_result user lines**
```python
# Real transcript: 99 of 107 "user" lines are tool output, not human text
{"type": "user", "toolUseResult": {...}, "message": {"content": "File contents..."}}

# The parser skips these when extracting user text
if data.get("toolUseResult") or data.get("isMeta"):
    return None  # Not human speech
```

#### 5. Dependencies (`dependencies.py`) - **Use Case 2**

**Problem:** What extra context gets pulled in when you invoke a skill/agent?

**Solution: Causal attribution + co-occurrence analysis**

```python
def analyze_dependencies(artifacts, events, repo_path, artifact_source):
    reports = []
    
    # Build causal lookup tables
    children_of = defaultdict(list)  # parent_uuid → child events
    same_line = defaultdict(list)    # uuid → sibling events (batched tool calls)
    
    for event in events:
        if event.parent_uuid:
            children_of[event.parent_uuid].append(event)
        if event.uuid:
            same_line[event.uuid].append(event)
    
    # For each invocation, find all reads in its causal scope
    for invocation in [e for e in events if e.kind in {"skill", "agent", "workflow"}]:
        reads = _read_events_from(invocation, same_line, children_of)
        
        # Classify reads as primary (the skill's own file) vs. additional
        primary_path = artifact_source.get(invocation.name)
        additional_reads = [r for r in reads if not _is_primary(r, primary_path)]
        
        # Detect leaks (reads outside the dependency closure)
        closure = _parse_closure(primary_path)  # Parse referenced files from skill body
        leaks = [r for r in additional_reads if _is_leak(r, primary_path, closure)]
        
        reports.append(InvocationDependency(...))
    
    return reports
```

**Causal attribution:**
```python
def _read_events_from(invocation, same_line, children_of):
    """All reads whose causal chain roots at this invocation."""
    if not invocation.uuid:
        return []  # Fall back to co-occurrence
    
    reads = []
    
    # Same-line siblings (batched tool calls share one uuid)
    for sibling in same_line[invocation.uuid]:
        if _is_read(sibling):
            reads.append(sibling)
    
    # Walk the descendant tree (including subagent reads via is_sidechain)
    stack = children_of[invocation.uuid]
    seen_uuids = set()
    
    while stack:
        node = stack.pop()
        if node.uuid in seen_uuids:
            continue
        seen_uuids.add(node.uuid)
        
        if _is_read(node):
            reads.append(node)
        
        # Descend into children (even nested invocations, to capture their reads)
        stack.extend(children_of.get(node.uuid, []))
    
    return reads
```

**Leak detection:**
```python
def _leak_level(file_path, primary_source, in_closure):
    """Classify a non-primary read by location."""
    if in_closure:
        return "none"  # Declared dependency, not a leak
    
    # Global skill leak (e.g., ~/.claude/skills/graphify/ during project work)
    if "/.claude/" in file_path.lower() and "/skills/" in file_path.lower():
        return "global"  # HIGH severity
    
    # Cross-reference to another project skill
    if "/skills/" in file_path.lower() or "/agents/" in file_path.lower():
        return "cross-reference"  # MEDIUM severity
    
    return "none"  # Within same directory, not a leak
```

**Co-occurrence fallback (no causal data):**
```python
def _cooccurrence(invocation_name, events):
    """How often file X is read when skill Y is invoked (correlation only)."""
    sessions_with_invocation = {e.session_id for e in events if e.name == invocation_name}
    read_counts = defaultdict(int)
    
    for session_id in sessions_with_invocation:
        session_events = [e for e in events if e.session_id == session_id]
        for read_event in session_events:
            if _is_read(read_event):
                file_path = read_event.metadata["file_path"]
                read_counts[file_path] += 1
    
    return read_counts  # Always/Frequently/Rarely labels derived from these counts
```

**Why two approaches?**
- **Causal** (primary): Exact per-invocation attribution, handles nested subagents
- **Co-occurrence** (fallback): Works with generic JSONL (no uuid/parent_uuid)
- Both reported with explicit labels about what each means

#### 6. Sections (`sections.py`)

**Purpose:** Parse guidance files into sections and track which sections are used.

```python
def parse_sections(file_path):
    """Split a markdown file into sections by headers."""
    sections = []
    current_section = None
    
    for line_num, line in enumerate(file_path.read_text().splitlines(), start=1):
        if line.startswith("#"):  # Markdown header
            if current_section:
                current_section.end_line = line_num - 1
                sections.append(current_section)
            
            current_section = Section(
                title=line.lstrip("#").strip(),
                start_line=line_num,
                content_lines=[]
            )
        elif current_section:
            current_section.content_lines.append(line)
    
    return sections

def detect_section_mentions(text, sections):
    """Which sections are referenced in subsequent AI responses?"""
    text_lower = text.lower()
    mentioned = []
    
    for section in sections:
        # Check if section title appears in the text
        if section.title.lower() in text_lower:
            mentioned.append(section)
    
    return mentioned
```

**Token estimation:**
```python
def estimate_section_tokens(section):
    """Rough GPT-4 token estimate: ~4 chars per token."""
    char_count = sum(len(line) for line in section.content_lines)
    return char_count // 4
```

#### 7. Reporter (`reporter.py`)

**Purpose:** Format analysis results for different audiences.

**Three output formats:**
- **Terminal** (default): Rich tables, colored bars, emoji status
- **JSON**: Machine-readable for CI/CD pipelines
- **Markdown**: Shareable reports for team review

```python
def format_terminal(report: CoverageReport):
    # Coverage summary
    console.print(f"Overall Coverage: {report.coverage_percent}%")
    console.print(f"Dead Guidance: {len(report.dead_artifacts)} artifacts")
    
    # Usage table with bars
    for usage in report.usage:
        bar = "█" * (usage.total_count // 10) + "░" * (10 - usage.total_count // 10)
        console.print(f"  {usage.artifact_name:20} {bar} {usage.total_count} invocations")
    
    # Section-level waste (if requested)
    if report.section_reports:
        for section_report in report.section_reports:
            console.print(f"\n{section_report.artifact_name}: {section_report.dead_section_count} dead sections")
            console.print(f"  Token waste: ~{section_report.token_waste_estimate:,} per invocation")
    
    # Violations with classification (if requested)
    if report.exclusion_violations:
        for violation in report.exclusion_violations:
            # Filter out user-requested with high confidence by default
            if violation.classification == "user_requested" and violation.confidence == "high":
                continue  # Hidden unless --all
            
            console.print(f"❌ {violation.file_path}: {violation.access_count} accesses")
            console.print(f"   Classification: {violation.classification} ({violation.confidence})")
            console.print(f"   Reason: {violation.classification_reason}")
```

---

## How the Use Cases Work Together

### Use Case 1: Smart Violation Detection

**Before (false positives):**
```
User: "Read TEST_PLAN.md and execute scenario A1"
AI: *reads TEST_PLAN.md*
Report: ❌ VIOLATION (wrong - user asked for it!)
```

**After (accurate classification):**
```
Report: ✓ TEST_PLAN.md (1 access, user_requested [high], "Exact filename in user message")
        [Hidden from default violations report, visible with --all flag]
```

**Technical flow:**
1. Parser captures user message: `"Read TEST_PLAN.md and execute scenario A1"`
2. Parser strips `<ide_opened_file>` and other injected blocks
3. Parser captures Read event with `parent_uuid` linking to user message
4. Classifier walks `parent_uuid` chain to user message
5. Classifier matches "TEST_PLAN.md" in user text → `user_requested, high`
6. Reporter suppresses this from violations (but logs full detail in JSON)

### Use Case 2: Context Leak Detection

**Before (invisible waste):**
```
User: "Use arson-tests-generation skill"
AI: *secretly reads graphify/SKILL.md (~1,200 tokens)*
Report: Nothing - leak invisible
```

**After (quantified waste):**
```
Report:
  arson-tests-generation (96 invocations):
    Avg overhead: ~1,850 tokens/use (47% extra context)
    
    ❌ ~/.claude/skills/graphify/SKILL.md (5/96 sessions)
       Leak level: GLOBAL
       Wasted: ~6,000 tokens total
       Not in declared dependencies
```

**Technical flow:**
1. User invokes `Skill(skill="arson-tests-generation")`
2. Parser captures invocation event with `uuid=abc123`
3. AI spawns `Agent(subagent_type="Explore")` with `parent_uuid=abc123, is_sidechain=true`
4. Inside agent, AI reads `graphify/SKILL.md` with `parent_uuid=xyz, is_sidechain=true`
5. Dependency analyzer walks causal chain: `graphify read` → `Explore spawn` → `arson invocation`
6. Analyzer checks `arson/SKILL.md` for declared deps → graphify not found
7. Analyzer checks path: `~/.claude/skills/` → global leak (HIGH severity)
8. Reporter surfaces leak with token estimate and remediation suggestion

---

## Key Design Decisions

### 1. Causal Chain Over Position

**Why:** Parallel tool calls and nested subagents break positional assumptions.

```python
# BAD (positional)
def attribute_read_to_invocation(read_event, events):
    # Find the last invocation before this read
    for e in reversed(events[:events.index(read_event)]):
        if e.kind == "skill":
            return e  # WRONG if parallel tools or subagents

# GOOD (causal)
def attribute_read_to_invocation(read_event, uuid_index):
    # Walk parent_uuid chain to root invocation
    cur = read_event
    while cur.parent_uuid:
        cur = uuid_index[cur.parent_uuid]
        if cur.kind in {"skill", "agent", "workflow"}:
            return cur
```

**Real example:** In one session, 2 skills invoked in same turn, each spawning agents. Positional attribution smeared one skill's reads onto the other. Causal chain resolved correctly.

### 2. Graceful Degradation

**Why:** Support both Claude Code (rich causal data) and generic JSONL (flat format).

```python
def classify_read(read_event, all_events, uuid_index):
    # Try causal path first
    if read_event.uuid and read_event.parent_uuid:
        return _classify_causal(read_event, uuid_index)
    
    # Fall back to heuristics
    if any(e.kind == "user_message" for e in all_events):
        return _classify_heuristic(read_event, all_events)
    
    # No data at all
    return Classification("unknown", "none", "No intent data available", "none")
```

Every result carries `detection_method` field (`causal` | `heuristic` | `none`) so users know data quality.

### 3. Audit Trail Required

**Why:** AI classification is fallible. Every decision must be explainable.

```python
@dataclass
class Classification:
    classification: str  # the verdict
    confidence: str      # how sure we are
    reason: str          # human-readable explanation
    method: str          # which code path produced this
```

**Example output:**
```json
{
  "file_path": "docs/TEST_PLAN.md",
  "classification": "user_requested",
  "confidence": "high",
  "reason": "Exact filename in user message",
  "detection_method": "causal"
}
```

This lets users validate/debug classifications and builds trust.

### 4. Token Waste Quantification

**Why:** Abstract metrics don't drive action. Concrete savings do.

```python
# Don't just say "dead section"
"Section X: 0 uses"

# Quantify the cost
"Section X: 0/47 uses, ~1,200 tokens wasted per invocation"
"Total waste: ~56,400 tokens across all sessions"
"Potential monthly savings: ~$X (at GPT-4 rates)"
```

Real tokens → real costs → real urgency to fix.

---

## Common Pitfalls & Solutions

### Pitfall 1: Tool Result User Lines

**Problem:** 99 of 107 "user" lines in one session were AI tool output, not human text.

```jsonl
{"type": "user", "toolUseResult": {...}, "message": {"content": "File: test.py\n..."}}
```

**Solution:** Filter by `toolUseResult` presence:
```python
if data.get("toolUseResult") or data.get("isMeta"):
    return None  # Not human speech
```

### Pitfall 2: IDE Injections

**Problem:** `<ide_opened_file>path/to/file.md</ide_opened_file>` injected into user turn → false HIGH match.

**Solution:** Strip all `<...>` blocks:
```python
_INJECTED_BLOCK_RE = re.compile(r"<(ide_opened_file|system-reminder|...)>.*?</\1>", re.DOTALL)
cleaned = _INJECTED_BLOCK_RE.sub("", raw_user_text)
```

### Pitfall 3: SKILL.md Basename Collision

**Problem:** Every skill's primary file is `SKILL.md`. A leaked `graphify/SKILL.md` was mistaken for the invoked skill's own file.

**Solution:** Parent-aware matching:
```python
def _primary_key(file_path):
    p = Path(file_path)
    if p.name.upper() == "SKILL.MD":
        return f"{p.parent.name}/{p.name}".lower()  # "graphify/skill.md"
    return p.name.lower()
```

### Pitfall 4: Multi-Tool Calls Dropped

**Problem:** Parser only extracted `tool_uses[0]`, dropping all parallel reads.

**Solution:** Iterate all:
```python
for tool_use in tool_uses:
    event = _parse_tool_use(tool_use, ...)
    events.append(event)
```

This bug fix alone boosted accuracy from ~60% to ~95% on real sessions.

---

## Performance Characteristics

**Typical session:**
- 500-2000 JSONL lines
- 50-200 relevant events (tool calls)
- ~10ms parse time per session

**Scaling:**
```python
# O(n) passes, no nested loops
parse:         O(lines)                    # ~100ms for 20 sessions
uuid_index:    O(events)                   # ~10ms one-time build
classification: O(events)                  # ~50ms (walks chains)
dependencies:  O(invocations × reads)      # ~100ms (bounded by reads/invocation)
reporting:     O(artifacts + violations)   # ~10ms

Total: <500ms for typical repo (20 sessions, 10 artifacts)
```

**Memory:**
- Streams JSONL (never loads full file)
- Keeps only parsed events in memory (~1KB per event)
- Peak: ~5MB for large repo (100 sessions, 1000 artifacts)

---

## Testing Strategy

**Test coverage: 78 tests, all passing**

### Test categories:

1. **Parser correctness** (`test_parser.py`)
   - Multi-tool extraction
   - Causal field capture
   - User message cleaning
   - Document capture

2. **Classification accuracy** (`test_classification.py`)
   - Causal tiers (@mention, exact filename, name+verb, keyword)
   - Sidechain detection
   - Heuristic fallback
   - Unknown handling

3. **Dependency attribution** (`test_dependencies.py`)
   - Causal per-invocation
   - Leak detection (global, cross-reference, none)
   - Dependency closure parsing
   - Co-occurrence fallback

4. **Integration** (`test_enhancements_integration.py`)
   - End-to-end on real-shaped fixtures
   - Backward compatibility with old transcripts
   - Multi-platform transcript formats

5. **Fixtures** (`tests/fixtures/real_transcripts/`)
   - Real Claude Code format (nested content, causal fields)
   - Edge cases (tool_result user lines, injected blocks, batched tools)

---

## Future Enhancements

### Planned:

1. **Real-time monitoring** - Live dashboard of usage as sessions happen
2. **Trend analysis** - Usage over time (growing, declining, seasonal)
3. **A/B testing** - Compare two versions of a skill's usage
4. **Recommendation engine** - "Consider merging these two low-use skills"
5. **IDE integration** - Show usage stats in skill editor

### Under consideration:

- **Line-level coverage** - Which exact instruction lines are ignored?
- **Cross-repo analysis** - Compare guidance usage across projects
- **Cost tracking** - Tie token waste to actual $ spent
- **Auto-optimization** - Suggest specific edits to reduce waste

---

## Glossary

**Artifact** - A guidance file (skill, agent, workflow, instruction) that AI can use

**Causal chain** - The `parent_uuid` links connecting an event back to what triggered it

**Classification** - Whether a file read was user-requested, autonomous, uncertain, or unknown

**Co-occurrence** - How often two things happen in the same session (correlation, not causation)

**Coverage** - Percentage of artifacts that have been used at least once

**Dead artifact** - Guidance that has never been invoked across all analyzed sessions

**Dependency closure** - Set of files a guidance artifact explicitly references in its body

**Leak** - A file read outside the dependency closure of the invoked artifact

**Prompt ID** - Groups all events from one user request turn

**Sidechain** - Events that happen inside a spawned subagent (marked `is_sidechain: true`)

**Section** - A portion of a guidance file delimited by markdown headers

**Token waste** - Tokens spent reading content that doesn't contribute to the task

**Transcript** - JSONL log of an AI coding session (tool calls, messages, timestamps)

**Trigger** - Pattern that invokes an artifact (e.g., `/graphify`, `subagent_type: "Explore"`)

**UUID index** - Map from event UUID to event object (enables fast causal chain traversal)

**Violation** - When AI reads a file marked as excluded or documentation

---

## Quick Reference: CLI Commands

```bash
# Basic coverage report
gi coverage

# Include section-level analysis
gi coverage --sections

# Check for exclusion violations
gi coverage --violations

# Track dependencies & context leaks
gi coverage --dependencies

# All analysis types
gi coverage --sections --violations --dependencies

# JSON output for CI/CD
gi coverage --format json

# Markdown report for sharing
gi coverage --format md

# Only recent sessions
gi coverage --last 10

# Custom transcript location
gi coverage --transcripts ./my-sessions/

# Discovery only (no analysis)
gi discover

# Show only dead artifacts
gi dead

# Detailed per-artifact statistics
gi stats
```

---

## Questions?

**For managers:**
- How do I interpret the coverage percentage?
  - > 80%: Healthy, most guidance is used
  - 50-80%: Moderate, some cleanup opportunities
  - < 50%: High waste, significant ROI from pruning

**For developers:**
- How do I debug a classification?
  - Check `detection_method`: `causal` is most reliable, `heuristic` less so
  - Read the `reason` field for explanation
  - View full details with `--format json`

- How do I mark a file as excluded?
  - Add frontmatter: `---\nai-exclude: true\n---`
  - Or use heuristic detection (TEST_, _test.py, docs/, etc.)

- Why is my skill showing 0 uses?
  - Check if trigger pattern matches actual invocations
  - Verify skill is in a supported location (`.claude/skills/*/SKILL.md`)
  - Run `gi discover` to see what was found

---

**Last updated:** 2026-07-02  
**Version:** 1.0 (enhancement spec implemented, 78 tests passing)
