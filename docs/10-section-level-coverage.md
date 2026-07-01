# Section-Level Coverage: Deep Guidance Analytics

## Problem

Current tool answers: "Is this SKILL.md file used?"

But teams need: "Which sections of SKILL.md are actually referenced?"

### Why This Matters: Token Efficiency

A 500-line SKILL.md might only use:
- ✅ Purpose section (50 lines) - **always referenced**
- ✅ Common scenarios (100 lines) - **frequently used**
- ❌ Advanced edge cases (150 lines) - **never referenced**
- ❌ Deprecated workflows (200 lines) - **dead weight**

**Result:** 350 lines (70%) wasting tokens in every invocation!

## Proposed Solution: Section-Level Coverage

### Report Format

```bash
gi coverage --sections
```

Output:
```
Skill: unity-codegen (.agents/skills/unity-codegen/SKILL.md)
  Overall usage: 12 invocations across 8 sessions

  Section Coverage:
  ✅ Purpose (lines 1-15)           Used in: 12/12 invocations (100%)
  ✅ Input → Output (lines 17-30)   Used in: 10/12 invocations (83%)
  ✅ Prerequisites (lines 32-45)    Used in: 9/12 invocations (75%)
  ⚠️  Special Cases (lines 60-120)  Used in: 2/12 invocations (17%)  ← LOW USAGE
  ❌ Platform Details (lines 122-180) Used in: 0/12 invocations (0%) ← DEAD SECTION
  
  Token Waste Estimate: ~1,200 tokens/invocation from unused sections
  Recommendation: Consider moving "Platform Details" to separate reference file
```

### Detailed Section Report

```bash
gi sections unity-codegen
```

```
unity-codegen: Section Usage Details
=====================================

## Purpose (lines 1-15) - 100% coverage ✅
  First used: 2026-05-12
  Last used: 2026-06-28
  Referenced in sessions: session-001, session-003, session-007, ...

## Platform Details (lines 122-180) - 0% coverage ❌
  Never referenced across 12 invocations
  Token cost: ~1,200 tokens/invocation
  
  Dead subsections:
    - iOS Build Steps (lines 125-140)
    - Android NDK Setup (lines 142-160)
    - Cross-compilation Guide (lines 162-180)
  
  💡 Recommendation: Move to .agents/skills/unity-codegen/references/platforms.md
     and only load when explicitly needed
```

## How It Works

### 1. Track Read Tool Calls to Guidance Files

When Claude reads a guidance file:
```json
{
  "type": "tool_use",
  "name": "Read",
  "input": {
    "file_path": ".agents/skills/unity-codegen/SKILL.md"
  }
}
```

Track as: **Manual skill reference** (not formal invocation, but usage)

### 2. Analyze Claude's Subsequent Actions

After reading the skill, correlate:
- **What sections were read** (from Read tool `offset`/`limit` params)
- **What actions Claude took** (edits, bash commands, file writes)
- **What Claude referenced** (parse assistant message for section headers mentioned)

### 3. Section Parsing

Parse guidance files into sections:
```python
class Section:
    title: str           # "## Prerequisites"
    start_line: int      # 32
    end_line: int        # 45
    content: str         # Full text
    usage_count: int     # How many times referenced
    sessions_used: set   # Which sessions used it
```

Detect sections by:
- Markdown headers (`##`, `###`)
- YAML frontmatter blocks
- Common patterns (Purpose, Prerequisites, Examples, etc.)

### 4. Reference Detection

When Claude reads a skill file, check if it:
- **Explicitly mentions section titles** in responses
- **Uses examples from specific sections**
- **Follows workflows from specific sections**
- **References line numbers** (e.g., "following line 45...")

### 5. Correlation Algorithm

```python
def correlate_section_usage(skill_read_event, subsequent_events):
    """
    After Claude reads a skill file, analyze what it actually used.
    """
    sections_mentioned = extract_mentioned_sections(subsequent_events)
    actions_taken = extract_actions(subsequent_events)
    
    # Match actions to skill sections
    for section in skill.sections:
        if section.title in sections_mentioned:
            section.usage_count += 1
        elif section_keywords_match(section, actions_taken):
            section.usage_count += 1  # Implicit usage
```

## Implementation Plan

### Phase 1: Track Read Tool Calls (2 hours)
- Extend parser to capture Read tool calls to guidance files
- Track as "manual reference" events
- Update TranscriptEvent model

### Phase 2: Section Parser (3 hours)
- Parse guidance files into sections
- Extract headers, line ranges, content
- Build section index per artifact

### Phase 3: Usage Correlation (4 hours)
- After skill read, analyze next N assistant messages
- Detect section mentions, keyword matches
- Mark sections as "used" or "unused"

### Phase 4: Section Reports (3 hours)
- New command: `gi sections <artifact-name>`
- Update coverage report to show section stats
- Token waste estimates

### Phase 5: Recommendations Engine (2 hours)
- Identify consistently unused sections
- Suggest refactoring (split files, move to references)
- Calculate token savings potential

**Total: ~14 hours (2 days)**

## Benefits

### 1. Token Efficiency
- Identify sections that waste tokens in every invocation
- Quantify potential savings (tokens/invocation)
- Guide refactoring decisions

### 2. Guidance Quality
- See which parts of guidance are actually valuable
- Remove or relocate unused content
- Optimize for real usage patterns

### 3. Maintenance Priorities
- Focus updates on high-usage sections
- Deprecate truly unused content
- Evidence-based guidance evolution

### 4. Closed-Loop Feedback
```
Discover → Measure → Analyze Sections → Optimize → Measure Again
```

## Example Use Case

**Before:**
```
unity-codegen SKILL.md: 500 lines, ~10,000 tokens
Used in 20 sessions, costing ~200k tokens total
```

**After Section Analysis:**
```
Section Coverage Report:
- Core workflow: 100% usage ✅
- Platform specifics: 15% usage ⚠️
- Deprecated v1 API: 0% usage ❌

Token Waste: 3,000 tokens/invocation from unused sections
Potential Savings: 60k tokens across 20 sessions
```

**Action:**
1. Move platform specifics to separate reference file
2. Delete deprecated v1 API section
3. Reduce to 250 lines, ~5,000 tokens

**Result:** 50% token reduction while maintaining actual utility!

## Challenges

### 1. Implicit Usage
Claude might use a section without explicitly mentioning it:
- Solution: Keyword matching, action correlation

### 2. Read Tool Granularity
Read tool might not capture exact sections:
- Solution: Track offset/limit params, estimate sections read

### 3. Multi-File Skills
Skills with references/ subdirectories:
- Solution: Track entire skill tree, report per-file and aggregate

### 4. False Positives
Claude might read but not use a section:
- Solution: Require evidence of usage (mention + action)

## MVP Scope

Start simple:
1. ✅ Track Read tool calls to guidance files
2. ✅ Parse sections from Markdown headers
3. ✅ Mark section as "used" if mentioned in next 3 assistant messages
4. ✅ Report section coverage percentage
5. ❌ Skip advanced correlation (manual review for now)

**Deliverable:** `gi coverage --sections` showing % coverage per section

## Future Enhancements

- **Heatmaps**: Visual representation of section usage
- **Time-based analysis**: Section usage trends over time
- **Cross-reference detection**: Which sections reference each other
- **AI-powered recommendations**: LLM suggests refactoring
- **Integration with editors**: VSCode extension showing coverage inline
