# Exclusion Patterns: Detecting AI Usage of Non-AI Files

## Problem

Projects often contain `.md` files that are **NOT for AI consumption**:
- Test plans (e.g., `TEST_PLAN.md`)
- Meeting notes
- Project documentation
- Historical records (e.g., `VALIDATION_REPORT.md`)
- Architecture decision records (ADRs)

When AI reads these files, it:
1. **Wastes tokens** on irrelevant content
2. **Violates project conventions** (files explicitly marked as not for AI)
3. **Reduces context space** for actual guidance

## Solution: Exclusion Tracking

### 1. Mark Files as Excluded

**Option A: Frontmatter in file** (Recommended)
```markdown
---
ai-exclude: true
reason: "Test documentation, not AI guidance"
---

# Test Plan

This is for human testers...
```

**Option B: `.aiignore` file in project root**
```
# Files not for AI consumption
TEST_PLAN.md
VALIDATION_REPORT.md
docs/meeting-notes/
**/ADR-*.md
```

**Option C: `.claude/exclusions.yaml`**
```yaml
excluded_files:
  - pattern: "TEST_PLAN.md"
    reason: "Test documentation"
  - pattern: "**/VALIDATION_*.md"
    reason: "Historical validation reports"
  - pattern: "docs/meetings/"
    reason: "Meeting notes"
```

### 2. Track Violations

When AI reads an excluded file:
```python
violation = {
    "file_path": ".agents/skills/arson-tests-generation/TEST_PLAN.md",
    "exclusion_reason": "Test documentation, not AI guidance",
    "session_id": "session-001",
    "timestamp": "2026-06-15T14:00:00Z",
    "token_estimate": 8290,
}
```

### 3. Violation Report

```bash
gi coverage --violations
```

Output:
```
Guidance Coverage Report
========================
...

⚠️  EXCLUSION VIOLATIONS
========================

Files marked as excluded but read by AI:

❌ TEST_PLAN.md
  Location: .agents/skills/arson-tests-generation/TEST_PLAN.md
  Exclusion reason: Test documentation, not AI guidance
  Times accessed: 32
  Token waste: ~8,290 tokens/access
  Total waste: ~265,280 tokens
  Sessions: session-001, session-003, session-007, ...
  
  💡 Recommendation: 
    - Move to docs/testing/ outside .agents/ directory
    - Or add to .aiignore
    - Or remove ai-exclude marker if AI should use it

❌ VALIDATION_REPORT.md
  Location: .agents/skills/arson-tests-generation/VALIDATION_REPORT.md
  Exclusion reason: Historical validation records
  Times accessed: 3
  Token waste: ~2,259 tokens/access
  Total waste: ~6,777 tokens

Total Exclusion Violations: 2 files
Total Token Waste: ~272,057 tokens
Affected Sessions: 17/54
```

### 4. Auto-Detection

Even without explicit exclusions, detect likely documentation files:
```python
# Patterns that suggest documentation (not guidance)
DOC_PATTERNS = [
    r"TEST[_-]PLAN\.md$",
    r"VALIDATION[_-]REPORT\.md$", 
    r"MEETING[_-]NOTES\.md$",
    r"ADR[_-]\d+",  # Architecture Decision Records
    r"CHANGELOG\.md$",
    r"CONTRIBUTING\.md$",
]
```

Report as "potential violations" (warnings, not errors).

## Implementation

### Models
```python
@dataclass
class ExclusionPattern:
    pattern: str  # glob or regex
    reason: str
    source: str  # "frontmatter" | "aiignore" | "config"

@dataclass
class ExclusionViolation:
    file_path: str
    exclusion_reason: str
    access_count: int
    sessions: list[str]
    token_estimate: int
    total_token_waste: int
```

### Discovery
```python
def discover_exclusions(repo_path: str) -> list[ExclusionPattern]:
    """Find all exclusion patterns from various sources."""
    exclusions = []
    
    # Check .aiignore
    aiignore = Path(repo_path) / ".aiignore"
    if aiignore.exists():
        exclusions.extend(_parse_aiignore(aiignore))
    
    # Check .claude/exclusions.yaml
    config = Path(repo_path) / ".claude" / "exclusions.yaml"
    if config.exists():
        exclusions.extend(_parse_exclusions_config(config))
    
    # Check frontmatter in all .md files
    exclusions.extend(_scan_frontmatter_exclusions(repo_path))
    
    return exclusions
```

### Violation Detection
```python
def detect_violations(
    events: list[TranscriptEvent],
    exclusions: list[ExclusionPattern],
    repo_path: str,
) -> list[ExclusionViolation]:
    """Find Read tool calls to excluded files."""
    violations = {}
    
    for event in events:
        if not event.metadata or not event.metadata.get("manual_reference"):
            continue
        
        file_path = event.metadata.get("file_path", "")
        if not file_path:
            continue
        
        # Check if file matches any exclusion pattern
        for exclusion in exclusions:
            if _matches_pattern(file_path, exclusion.pattern):
                key = file_path
                if key not in violations:
                    violations[key] = {
                        "file_path": file_path,
                        "exclusion_reason": exclusion.reason,
                        "sessions": set(),
                        "access_count": 0,
                    }
                
                violations[key]["access_count"] += 1
                violations[key]["sessions"].add(event.session_id)
    
    # Convert to violation objects with token estimates
    result = []
    for v in violations.values():
        file_full_path = Path(repo_path) / v["file_path"]
        token_estimate = estimate_file_tokens(file_full_path)
        
        result.append(ExclusionViolation(
            file_path=v["file_path"],
            exclusion_reason=v["exclusion_reason"],
            access_count=v["access_count"],
            sessions=sorted(v["sessions"]),
            token_estimate=token_estimate,
            total_token_waste=token_estimate * v["access_count"],
        ))
    
    return sorted(result, key=lambda x: x.total_token_waste, reverse=True)
```

## Benefits

1. **Enforces Conventions**: Catch when AI violates project rules
2. **Quantifies Waste**: Show exact token cost of reading wrong files
3. **Guides Cleanup**: Identify misplaced documentation
4. **Validates Organization**: Ensure files are in correct locations

## Use Cases

### Use Case 1: Test Documentation
```markdown
# TEST_PLAN.md
---
ai-exclude: true
reason: "Test scenarios for human QA, not AI guidance"
---
```

**Violation detected**: AI read this 32 times, wasting ~265k tokens
**Action**: Move to `docs/testing/test-plan.md`

### Use Case 2: Historical Records
```yaml
# .claude/exclusions.yaml
excluded_files:
  - pattern: "**/VALIDATION_REPORT.md"
    reason: "Historical validation records, not current guidance"
```

**Violation detected**: AI read this 3 times
**Action**: Archive to `docs/archive/` or remove ai-exclude if needed

### Use Case 3: Meeting Notes
```
# .aiignore
docs/meetings/
NOTES.md
**/minutes-*.md
```

**Violation detected**: AI read meeting notes
**Action**: Move outside `.agents/` directory

## CLI Usage

```bash
# Show violations in coverage report
gi coverage --violations

# Show only violations (no coverage stats)
gi violations

# Check specific file
gi check-exclusion TEST_PLAN.md

# Suggest exclusions based on patterns
gi suggest-exclusions
```

## Future: Auto-Suggest Exclusions

Analyze file content to suggest exclusions:
```python
def suggest_exclusions(file_path: str) -> bool:
    """Suggest if file should be excluded based on content."""
    content = read_file(file_path)
    
    # Heuristics
    if "test plan" in content.lower()[:200]:
        return True
    if re.search(r"scenario \d+", content, re.IGNORECASE):
        return True  # Looks like test scenarios
    if "meeting notes" in content.lower():
        return True
    
    return False
```

Output:
```
💡 Suggested Exclusions

These files look like documentation, not AI guidance:

  📄 TEST_PLAN.md
    Why: Contains "test plan" in header
    Tokens: ~8,290
    Accessed: 32 times
    
  📄 MEETING_NOTES.md
    Why: Contains "meeting notes"
    Tokens: ~1,450
    Accessed: 5 times

Add to .aiignore to prevent AI from reading these files.
```
