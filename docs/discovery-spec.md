# Unified Discovery Implementation Summary

## What Changed

Replaced the hardcoded, Claude-specific discovery logic with a **unified, pattern-based system** that automatically discovers artifacts from **all AI coding assistants** using industry-standard directory conventions.

## Key Improvements

### 1. **Zero Configuration**
- No provider selection needed
- No configuration files
- Just works out of the box

### 2. **Multi-Tool Support**
Automatically discovers artifacts from:
- **Claude Code** (`.claude/`)
- **GitHub Copilot** (`.github/copilot/`)
- **Cursor AI** (`.cursor/`)
- **Continue.dev** (`.continue/`)
- **Aider** (`.aider/`)
- **LangChain** (`.langchain/`)
- **CrewAI** (`.crewai/`)
- **Generic convention** (`.agents/`)
- **No-dot generic** (`skills/`, `agents/`, `prompts/`, etc.)

### 3. **Extended Artifact Types**
Now discovers **13 artifact types** instead of just 4:

| Type | Directories |
|------|-------------|
| `skill` | `.claude/skills/`, `.agents/skills/`, `skills/`, `prompts/` |
| `agent` | `AGENTS.md`, `.claude/agents/`, `.agents/`, `agents/` |
| `workflow` | `.claude/workflows/`, `.agents/workflows/`, `workflows/`, `tools/` |
| `instruction` | `CLAUDE.md`, `INSTRUCTIONS.md`, `.github/copilot/instructions.md` |
| `command` | `commands/`, `.agents/commands/` |
| `template` | `templates/`, `.agents/templates/` |
| `config` | `.claude/settings.json`, `.cursor/config.json`, etc. |
| `tool` | `tools/`, `.agents/tools/` |
| `context` | `context/`, `.agents/context/` |
| `persona` | `personas/`, `.agents/personas/` |
| `example` | `examples/`, `.github/copilot/examples/` |
| `prompt` | `prompts/`, `.agents/prompts/` |
| `memory` | `.claude/memory/`, `.agents/memory/` |

### 4. **Industry-Standard Conventions**

Three tiers of directory patterns, checked in order:

1. **Vendor-specific** (highest priority)
   - `.claude/` → Claude Code
   - `.cursor/` → Cursor AI
   - `.github/copilot/` → GitHub Copilot
   - `.aider/` → Aider
   - `.continue/` → Continue.dev

2. **Generic dotfolder** (medium priority)
   - `.agents/` → **The standard generic convention**

3. **No-dot generic** (lowest priority)
   - `skills/`, `agents/`, `workflows/`, `prompts/`, etc.

### 5. **100% Backward Compatible**
- Existing code using `from guidance_intel.discovery import discover_artifacts` works unchanged
- Same function signatures
- Same return types
- All tests pass

## Architecture

### Before
```
discovery.py (446 lines)
├── _discover_skills()      # Hardcoded Claude + .agents patterns
├── _discover_agents()      # Hardcoded Claude + .agents patterns
├── _discover_workflows()   # Hardcoded Claude + .agents patterns
└── _discover_instructions() # Hardcoded Claude patterns
```

### After
```
discovery_unified.py (600 lines)
├── DISCOVERY_PATTERNS      # Data-driven pattern definitions
│   ├── skill: 9 patterns across all tools
│   ├── agent: 6 patterns across all tools
│   ├── workflow: 12 patterns across all tools
│   └── ... 10 more artifact types
├── discover_artifacts()    # Generic pattern matcher
└── discover_transcripts()  # Multi-platform transcript discovery

discovery.py (15 lines)
└── Re-exports from discovery_unified (backward compatibility)
```

## Code Reduction

- **Discovery logic**: 446 lines → 600 lines (+154 for 9 more artifact types + 5 more platforms)
- **Per-artifact overhead**: Went from ~100 lines/type to ~8 lines/type (pattern definition)
- **Extensibility**: Add new patterns by appending to `DISCOVERY_PATTERNS` dict

## How It Works

### Pattern Definition
```python
DISCOVERY_PATTERNS = {
    "skill": [
        # (glob_pattern, name_strategy, extract_triggers)
        (".claude/skills/*/SKILL.md", "parent_dir", True),
        (".agents/skills/**/SKILL.md", "parent_dir", True),
        ("skills/**/*.md", "stem", False),
        # ... more patterns
    ],
    # ... more artifact types
}
```

### Discovery Process
1. Iterate through all patterns for all artifact types
2. Glob match files in the repo
3. Derive artifact name based on strategy (`stem`, `parent_dir`, or `special:*`)
4. Extract triggers if configured
5. Deduplicate by (kind, name, source_path)
6. Return unified list

### Special Handlers
For cases that need custom parsing:
- `AGENTS.md` → Parse markdown headers to extract agent names
- Instruction files → Custom naming (`copilot-instructions:instructions.md`)
- Config files → Custom naming (`config:settings.json`)

## Adding New Platforms

To add support for a new AI tool, just add patterns:

```python
DISCOVERY_PATTERNS = {
    "skill": [
        # ... existing patterns
        (".newtool/skills/**/*.md", "stem", False),  # ← Add this
    ],
    "instruction": [
        # ... existing patterns
        (".newtool/instructions.md", "special:newtool_instruction", False),  # ← Add this
    ],
}
```

No classes to write. No provider registration. Just data.

## Testing

```bash
# Import test
python -c "from guidance_intel.discovery import discover_artifacts; print('✓')"

# Discovery test
python -c "
from guidance_intel.discovery import discover_artifacts
artifacts = discover_artifacts('.')
print(f'Discovered {len(artifacts)} artifacts')
for a in artifacts:
    print(f'  [{a.kind}] {a.name} - {a.source_path}')
"

# CLI test
python -m guidance_intel.cli discover
```

## Migration Notes

### For Users
- **No changes needed** - existing code works as-is
- **More artifacts discovered** - may see new types in output
- **Multi-tool support** - automatically detects all platforms

### For Contributors
- **Adding patterns** - Edit `DISCOVERY_PATTERNS` in `discovery_unified.py`
- **Adding artifact types** - Add new key to `DISCOVERY_PATTERNS`
- **Custom parsing** - Add handler to `_discover_special()`

## Files

- **`discovery_unified.py`** - New unified discovery implementation
- **`discovery.py`** - Backward-compatible wrapper (re-exports from unified)
- **`discovery_legacy_backup.py`** - Backup of original implementation (reference only)
- **`DESIGN_PROPOSAL.md`** - Original design proposal (provider-based approach, abandoned)
- **`IMPLEMENTATION_SUMMARY.md`** - This file

## What Was Abandoned

Initial design proposed a provider plugin system with:
- `ArtifactProvider` interface
- `ProviderRegistry` for managing providers
- Separate provider classes for each platform
- Configuration files

**Why abandoned**: Over-engineered. The problem is simpler than we thought:
- 95% of discovery is just glob pattern matching
- Different platforms use the same file structures
- No need for runtime provider selection
- Data-driven patterns are easier to maintain than class hierarchies

## Benefits

1. **Simplicity** - One pattern list, not 5+ provider classes
2. **Discoverability** - All patterns in one place
3. **Extensibility** - Add new tools/types by appending to dict
4. **Performance** - Single pass through filesystem
5. **Maintainability** - Pattern definitions are self-documenting
6. **User experience** - Zero configuration, works everywhere

## Future Enhancements

Possible improvements (not implemented):

1. **Configuration override**
   ```yaml
   # .guidance-intel.yaml (optional)
   discovery:
     custom_patterns:
       skill:
         - ".mycompany/skills/**/*.md"
   ```

2. **Exclude patterns**
   ```yaml
   discovery:
     exclude:
       - "**/test/**"
       - "**/examples/**"
   ```

3. **Pattern priority**
   ```python
   DISCOVERY_PATTERNS = {
       "skill": [
           (pattern, name_strategy, extract_triggers, priority),
       ]
   }
   ```

But for now, the simple approach works perfectly.
