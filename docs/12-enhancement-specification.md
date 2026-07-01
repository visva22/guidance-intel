# Enhancement Specification: Context-Aware Analysis

## Use Case 1: User-Requested vs Autonomous Reads

### Problem Statement

**Current Behavior:**
```
User: "Read TEST_PLAN.md and execute scenario A1"
AI: *reads TEST_PLAN.md*
Tool Report: ❌ VIOLATION (FALSE POSITIVE)

User: "Generate tests for Friends package"
AI: *autonomously reads TEST_PLAN.md*
Tool Report: ❌ VIOLATION (TRUE POSITIVE)
```

**Cannot distinguish between these scenarios.**

### Requirements

1. **Detect user intent** - Did user explicitly request the file read?
2. **Confidence scoring** - How certain are we about user intent?
3. **Filter false positives** - Only report high-confidence violations
4. **Show both** - Allow users to see all accesses + confidence level

### Solution Options

#### Option A: User Message Correlation (Heuristic)

**Approach:** Correlate user messages with subsequent Read tool calls.

```python
def is_user_requested(read_event, user_messages):
    """
    Check if user explicitly requested this file read.
    """
    file_name = Path(read_event.file_path).name.lower()
    
    for user_msg in user_messages:
        msg_lower = user_msg.content.lower()
        
        # Pattern 1: Exact filename mention
        if file_name in msg_lower:
            return True, "high", "User mentioned exact filename"
        
        # Pattern 2: File pattern + action verb
        base_name = file_name.replace('.md', '').replace('_', ' ')
        if base_name in msg_lower and any(verb in msg_lower for verb in ['read', 'check', 'review', 'look at']):
            return True, "high", "User mentioned file pattern + action verb"
        
        # Pattern 3: Related keywords
        if 'test plan' in msg_lower and 'TEST_PLAN' in read_event.file_path:
            return True, "medium", "User mentioned related concept"
    
    return False, "high", "No user mention found"
```

**Confidence Levels:**
- **High confidence violation**: No user mention, deeply nested file
- **Medium confidence**: Ambiguous (user mentioned "tests" but not specific file)
- **Low confidence/Not violation**: User explicitly mentioned file

**Pros:**
- ✅ Catches obvious cases (exact filename)
- ✅ Handles variations (TEST_PLAN vs "test plan")
- ✅ No breaking changes (add confidence field)

**Cons:**
- ⚠️ Heuristic-based (may have edge cases)
- ⚠️ Requires parsing user messages
- ⚠️ Complex content (attachments) may be missed

#### Option B: Conversation Distance Analysis

**Approach:** Measure "distance" between user message and Read call.

```python
def calculate_confidence(read_event, events, event_index):
    """
    More recent user message mentioning file = more likely user-requested.
    """
    # Find previous user messages
    user_messages = []
    for i in range(event_index - 1, max(0, event_index - 10), -1):
        if events[i].kind == "user_message":
            user_messages.append((event_index - i, events[i]))
    
    for distance, user_msg in user_messages:
        if file_mentioned_in_message(user_msg, read_event.file_path):
            if distance <= 2:  # Within 2 events
                return "user_requested", "high"
            elif distance <= 5:
                return "user_requested", "medium"
    
    return "autonomous", "high"
```

**Pros:**
- ✅ Accounts for conversation flow
- ✅ Recency matters (closer = more likely related)

**Cons:**
- ⚠️ Arbitrary distance thresholds
- ⚠️ Complex multi-turn conversations may confuse it

#### Option C: Pattern-Based Classification

**Approach:** Use multiple signals to classify.

```python
class ViolationClassifier:
    def classify(self, read_event, context):
        score = 0
        reasons = []
        
        # Signal 1: User mention (strongest)
        if self.user_mentioned_file(context.user_messages, read_event.file_path):
            score += 50
            reasons.append("User mentioned file")
        
        # Signal 2: First read in session (more likely autonomous)
        if self.is_first_read(read_event, context.prior_reads):
            score -= 20
            reasons.append("First read of this file")
        
        # Signal 3: Multiple reads (pattern suggests autonomous)
        if context.read_count > 5:
            score -= 10
            reasons.append(f"File read {context.read_count} times")
        
        # Signal 4: Read with offset/limit (targeted = likely user-requested)
        if read_event.metadata.get('offset') is not None:
            score += 15
            reasons.append("Targeted read with line range")
        
        # Classify
        if score >= 30:
            return "user_requested", "high", reasons
        elif score >= 10:
            return "user_requested", "medium", reasons
        elif score >= -10:
            return "uncertain", "low", reasons
        else:
            return "autonomous", "high", reasons
```

**Pros:**
- ✅ Multi-signal approach (more robust)
- ✅ Explainable (reasons list)
- ✅ Tunable (adjust weights)

**Cons:**
- ⚠️ Complex to maintain
- ⚠️ Requires tuning/validation

---

## Use Case 2: Skill Dependency Tracking (Context Leakage Detection)

### Problem Statement

**Current Behavior:**
```
User invokes: arson-tests-generation skill
AI reads:
  - arson-tests-generation/SKILL.md ✓ (expected)
  - unity-codegen/SKILL.md ✗ (why?)
  - graphify SKILL ✗ (global skill leak!)
  
User doesn't know: Which extra files are being pulled in?
```

**Token waste from unnecessary context loading.**

### Requirements

1. **Track context per invocation** - What was read during each skill/agent/workflow execution?
2. **Show dependencies** - "When you use X, AI also reads Y, Z"
3. **Detect leakage** - Global skills being read when not needed
4. **Quantify impact** - Token cost of extra context

### Solution Options

#### Option A: Session-Scoped Dependency Graph

**Approach:** Build dependency graph per guidance invocation.

```python
class DependencyTracker:
    def analyze_dependencies(self, events):
        """
        Group Read events by the artifact that triggered them.
        """
        dependencies = {}
        
        current_context = None
        for event in events:
            # Mark when a skill/agent is invoked
            if event.kind in ["skill", "agent", "workflow"]:
                current_context = event.name
                dependencies[current_context] = {
                    "primary": event.name,
                    "reads": [],
                    "token_cost": 0,
                }
            
            # Track subsequent Read calls
            elif event.kind == "user_message":
                # Reset context on user message (new request)
                current_context = None
            
            elif event.metadata and event.metadata.get("manual_reference"):
                if current_context:
                    file_path = event.metadata["file_path"]
                    dependencies[current_context]["reads"].append(file_path)
                    dependencies[current_context]["token_cost"] += estimate_file_tokens(file_path)
        
        return dependencies
```

**Report:**
```
Dependency Analysis
===================

When "arson-tests-generation" is invoked:
  ✓ Reads: .agents/skills/arson-tests-generation/SKILL.md (~2,100 tokens) [Expected]
  ⚠️ Also reads: .agents/skills/unity-codegen/references/build-commands.md (~850 tokens) [Why?]
  ❌ Also reads: ~/.claude/skills/graphify/SKILL.md (~1,200 tokens) [Global leak!]
  
  Total context: ~4,150 tokens (51% overhead from unexpected reads)
  
  💡 Recommendation:
    - Review why unity-codegen is being read
    - Global skills are leaking into context
```

**Pros:**
- ✅ Clear cause-effect relationship
- ✅ Quantifies overhead per invocation
- ✅ Detects global skill leakage

**Cons:**
- ⚠️ Context boundary detection is heuristic
- ⚠️ Async agents may confuse boundaries

#### Option B: Co-occurrence Analysis

**Approach:** Statistical analysis of which files are read together.

```python
def analyze_cooccurrence(events, sessions):
    """
    Find which files are frequently read together.
    """
    cooccurrence = defaultdict(lambda: defaultdict(int))
    
    for session in sessions:
        session_events = [e for e in events if e.session_id == session]
        
        # Find all skills invoked
        invoked = [e.name for e in session_events if e.kind == "skill"]
        
        # Find all files read
        reads = [e.metadata["file_path"] for e in session_events 
                if e.metadata and e.metadata.get("manual_reference")]
        
        # Record co-occurrences
        for skill in invoked:
            for file_path in reads:
                cooccurrence[skill][file_path] += 1
    
    return cooccurrence
```

**Report:**
```
Co-occurrence Analysis (across 54 sessions)
===========================================

arson-tests-generation (96 invocations):
  Always reads (96/96):
    ✓ .agents/skills/arson-tests-generation/SKILL.md
  
  Frequently reads (45/96 - 47%):
    ⚠️ .agents/skills/unity-codegen/references/build-commands.md
       (Why does test generation need Unity build commands?)
  
  Occasionally reads (5/96 - 5%):
    ❌ ~/.claude/skills/graphify/SKILL.md
       (Global skill leaking into context)
```

**Pros:**
- ✅ Statistical confidence (patterns across sessions)
- ✅ Shows frequency (always/frequently/occasionally)
- ✅ No heuristics for context boundaries

**Cons:**
- ⚠️ Doesn't show causation (just correlation)
- ⚠️ Requires many sessions for confidence

#### Option C: Temporal Windowing

**Approach:** Group Read calls within time window of invocation.

```python
def analyze_temporal_dependencies(events):
    """
    Group reads within 30 seconds of skill invocation.
    """
    dependencies = {}
    
    for i, event in enumerate(events):
        if event.kind in ["skill", "agent", "workflow"]:
            event_time = parse_timestamp(event.timestamp)
            
            # Find reads within next 30 seconds
            related_reads = []
            for j in range(i+1, len(events)):
                next_event = events[j]
                
                # Stop at next user message or skill invocation
                if next_event.kind in ["user_message", "skill", "agent"]:
                    break
                
                if next_event.metadata and next_event.metadata.get("manual_reference"):
                    next_time = parse_timestamp(next_event.timestamp)
                    if next_time and (next_time - event_time).seconds <= 30:
                        related_reads.append(next_event.metadata["file_path"])
            
            dependencies[event.name] = related_reads
    
    return dependencies
```

**Pros:**
- ✅ Time-based (objective boundary)
- ✅ Captures immediate context

**Cons:**
- ⚠️ Arbitrary time window
- ⚠️ Slow agents may exceed window

---

## Recommended Solution

### For Use Case 1 (User-Requested Detection):

**Recommendation: Option A (User Message Correlation) + Option C (Pattern-Based)**

**Hybrid Approach:**
```python
def classify_violation(read_event, events, event_index):
    """Combine heuristics for robust classification."""
    
    # Get preceding user messages
    user_messages = get_preceding_user_messages(events, event_index, limit=3)
    
    # Check for explicit mention
    user_mentioned, mention_confidence, reason = check_user_mention(
        read_event.metadata["file_path"],
        user_messages
    )
    
    # If high-confidence user mention, mark as user-requested
    if user_mentioned and mention_confidence == "high":
        return {
            "classification": "user_requested",
            "confidence": "high",
            "reason": reason
        }
    
    # Otherwise, use multi-signal pattern classifier
    return pattern_classifier.classify(read_event, {
        "user_messages": user_messages,
        "user_mentioned": user_mentioned,
        "mention_confidence": mention_confidence,
        "read_count": count_reads(read_event.metadata["file_path"], events),
        "has_line_range": read_event.metadata.get("offset") is not None,
    })
```

**Benefits:**
- ✅ Strong signal (user mention) takes precedence
- ✅ Fallback to pattern-based for ambiguous cases
- ✅ Explainable (reasons provided)

### For Use Case 2 (Skill Dependency Tracking):

**Recommendation: Option A (Session-Scoped) + Option B (Co-occurrence)**

**Hybrid Approach:**
1. **Session-scoped** for detailed per-invocation analysis
2. **Co-occurrence** for aggregate patterns across many sessions

**Report Structure:**
```
gi coverage --dependencies

Dependency Analysis
===================

arson-tests-generation (96 invocations across 54 sessions):

  Per-Invocation Context:
    Primary: .agents/skills/arson-tests-generation/SKILL.md (~2,100 tokens)
    Average additional reads: 2.3 files
    Average overhead: ~1,850 tokens (47% extra)
  
  Co-occurrence Patterns:
    Always reads (96/96 - 100%):
      ✓ arson-tests-generation/SKILL.md
    
    Frequently reads (45/96 - 47%):
      ⚠️ unity-codegen/references/build-commands.md
         Why: Cross-reference for build commands
         Impact: +850 tokens per invocation
    
    Rarely reads (5/96 - 5%):
      ❌ ~/.claude/skills/graphify/SKILL.md
         Why: Global skill context leak
         Impact: +1,200 tokens when present
  
  💡 Recommendations:
    - Review cross-references to unity-codegen (needed?)
    - Isolate arson skill to prevent global leaks
    - Potential savings: ~2,050 tokens/invocation
```

---

## Implementation Phases

### Phase 1: User-Requested Detection (Priority: HIGH)
1. Extend parser to capture user messages
2. Implement user mention detection
3. Implement pattern-based classifier
4. Add confidence scores to violations
5. Update reporting to show classifications

**Effort:** 4-6 hours  
**Impact:** Eliminates false positives in violation detection

### Phase 2: Dependency Tracking (Priority: MEDIUM)
1. Implement session-scoped dependency tracker
2. Implement co-occurrence analyzer
3. Add --dependencies CLI flag
4. Create dependency report

**Effort:** 6-8 hours  
**Impact:** Reveals hidden token waste from context leakage

---

## Questions for Decision

1. **Use Case 1 Priority**: Should we implement this immediately or defer?
2. **Confidence threshold**: Report only high-confidence violations, or show all with confidence levels?
3. **Use Case 2 Scope**: Session-scoped only, co-occurrence only, or both?
4. **CLI design**: Separate flags (--dependencies, --violations) or combined report?
5. **Performance**: Acceptable to parse all user messages (adds ~20% overhead)?

---

## Success Criteria

### Use Case 1:
- ✅ Correctly identify user-requested reads (>90% accuracy)
- ✅ Reduce false positives by >80%
- ✅ Clear explanations for each classification

### Use Case 2:
- ✅ Show context overhead per skill/agent invocation
- ✅ Detect global skill leakage
- ✅ Quantify potential token savings
