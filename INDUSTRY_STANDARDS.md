# Industry-Standard Directory Conventions for AI Coding Assistants

Based on analysis of Claude Code, GitHub Copilot, Cursor AI, Aider, Continue.dev, LangChain, CrewAI, and other tools.

## Common Patterns

### 1. Dotfolder Convention
Most AI tools use hidden directories starting with a dot:
- `.claude/`
- `.cursor/`
- `.github/` (for Copilot/Actions)
- `.agents/` (generic convention)
- `.aider/`
- `.continue/`
- `.langchain/`
- `.crewai/`

**Pattern**: `.*/<artifact-type>/`

### 2. Standard Subdirectories

| Artifact Type | Standard Paths |
|---------------|----------------|
| Skills | `skills/`, `*/skills/`, `prompts/` |
| Agents | `agents/`, `*/agents/` |
| Workflows | `workflows/`, `*/workflows/`, `tools/` |
| Instructions | Root-level `.md` files, `*/instructions/` |
| Commands | `commands/`, `*/commands/` |
| Templates | `templates/`, `*/templates/` |
| Config | `*/settings.*`, `*/config.*` |
| Memory | `*/memory/` |
| Context | `context/`, `*/context/` |
| Examples | `examples/`, `*/examples/` |
| Personas | `personas/`, `*/personas/` |

### 3. File Naming Conventions

**Primary Artifact Files:**
- `SKILL.md` - Primary skill definition (when this exists, other .md files in same dir are references)
- `*.agent.md` - Agent definition files
- `AGENTS.md` - Agent registry
- `INSTRUCTIONS.md`, `CLAUDE.md` - Instruction files
- `*.workflow.{yaml,yml}` - Workflow definitions

**Reference/Support Files (should be skipped):**
- `references/` - subdirectory for skill references
- `README.md` - Documentation
- `TEST_PLAN.md` - Test plans
- `CHANGELOG.md` - Change history
- `NOTES.md` - Notes

### 4. Generic Pattern Structure

```
<optional-dotfolder>/<artifact-type>/<optional-subdirs>/<artifact-file>

Examples:
.claude/skills/my-skill/SKILL.md
.agents/skills/my-skill/SKILL.md
.github/skills/my-skill/SKILL.md
skills/my-skill/SKILL.md
```

All match the pattern: `*/skills/*/SKILL.md` or `skills/*/SKILL.md`

## Universal Skip Rules

1. **Skip `references/` subdirectories** - Always ignore
2. **SKILL.md precedence** - If SKILL.md exists, only discover that file
3. **Common doc files** - Skip README.md, CHANGELOG.md, CONTRIBUTING.md, LICENSE.md
4. **Symlinks** - Skip to avoid duplicates
5. **Hidden files** - Skip `.DS_Store`, `*.swp`, etc.

## Extensibility

This structure is **tool-agnostic**:
- New tools can use ANY dotfolder name (`.newtool/`)
- Following standard subdirectories (`skills/`, `agents/`, etc.) ensures auto-discovery
- No code changes needed for new platforms
