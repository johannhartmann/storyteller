# StoryCraft Agent Code Usage Summary

## Overview
This document summarizes which parts of the storyteller_lib codebase are actively used versus legacy/unused code.

## Active Code (Currently Used)

### Core Workflow
- **Entry Point**: `run_storyteller.py` → uses "simplified" workflow (v2 is now default)
- **Main Orchestration**: 
  - `storyteller.py` - `generate_story_simplified()` is the main function
  - `graph.py` - `create_simplified_graph()` builds the LangGraph workflow
  - `database_integration.py` - Central database management

### Active Workflow Nodes
- `initialization.py` - Story initialization
- `creative_tools.py` - Brainstorming and idea generation
- `outline.py` - Story outline creation
- `worldbuilding.py` - World building
- `character_creation.py` - Character profiles
- `progression.py` - Chapter and scene progression
- `summary_node.py` - Chapter summaries
- `scenes.py` - Scene orchestration (brainstorm, write, reflect, revise)

### Scene Generation Pipeline (Active)
- `scene_writer.py` - `write_scene_simplified()`
- `scene_reflection.py` - `reflect_scene_simplified()`
- `scene_revision.py` - `revise_scene_simplified()`
- `instruction_synthesis.py` - Intelligent instruction creation
- `scene_context_builder.py` - Comprehensive context building

### Supporting Modules (Active)
- `config.py`, `config_models.py` - Configuration management
- `constants.py` - System constants
- `exceptions.py` - Custom exceptions
- `logger.py` - Logging utilities
- `memory_manager.py` - Memory storage/retrieval
- `models.py` - State type definitions
- `progress_manager.py` - Progress tracking
- `story_progress_logger.py` - Story generation logging

### Analysis & Enhancement (Active)
- `character_arcs.py` - Character arc tracking
- `character_knowledge_manager.py` - Knowledge tracking
- `consistency.py` - Continuity checking
- `dialogue.py` - Dialogue enhancement
- `dramatic_arc.py` - Tension tracking
- `entity_relevance.py` - Entity management
- `exposition.py` - Exposition detection
- `intelligent_repetition.py` - Repetition analysis
- `pacing.py` - Pacing analysis
- `plot_threads.py` - Plot thread tracking
- `repetition.py` - Repetition detection
- `scene_helpers.py` - Scene utilities
- `scene_variety.py` - Variety checking
- `story_context.py` - Context management
- `transitions.py` - Scene transitions

## Legacy/Unused Code

### Completely Unused Modules
- `story_analysis.py` - 8 major analysis functions, never imported
- `prompt_optimization.py` - 7 optimization functions, never used
- `scene_progression.py` - Most functions unused (13+ functions)
- `prompt_templates.py` - Template loading system unused

### Test Files (Broken/Outdated)
- `test_v2_workflow.py` - References non-existent `storyteller_v2` module
- `test_v2_german.py` - References non-existent `storyteller_v2` module
- `test.py` - Basic tests, not part of any suite
- `test_chapter_generation.py` - Standalone test
- `test_writing_style.py` - Standalone test

### Utility/Debug Files (Not Core)
- `dependency_graph.py` - Analysis script
- `debug_revision.py` - Debug utility
- `extract_current_story.py` - Story extraction
- `extract_story.py` - Another extraction script

### Backup Files
- `storyteller.py.backup_20250620_100353`
- `run_storyteller.py.backup_20250620_100353`

### Template System (Unused)
- **184 template files** in `templates/` directory
- Template system exists but `get_prompt_template()` is never called
- Code uses inline prompts instead (24 instances)

### Deprecated Templates
- `story_outline.jinja2.deprecated` (base and German)

### Non-existent Referenced Files
- `migrate_to_v2.py` - Listed in directory but doesn't exist
- Various v2 modules listed but not found:
  - `graph_v2.py`
  - `scenes_v2.py`
  - `scene_reflection_v2.py`
  - `scene_revision_v2.py`
  - `scene_writer_v2.py`
  - `storyteller_v2.py`

## Key Observations

1. **V2 Migration Complete**: The v2 functionality has been merged into main files. The "simplified" workflow is actually the v2 implementation.

2. **Template System Abandoned**: Despite 184 template files, the code uses inline prompts. Only the `synthesize_scene_instructions` templates appear to be actively used.

3. **Significant Dead Code**: Multiple complete modules are unused, suggesting incomplete refactoring or abandoned features.

4. **Test Infrastructure Missing**: Test files exist but aren't part of any test suite, and some reference non-existent modules.

5. **Clean Architecture**: The active code follows a clear pattern with good separation of concerns, but is surrounded by legacy code.

## Recommendations

1. **Remove unused modules**: `story_analysis.py`, `prompt_optimization.py`, etc.
2. **Fix or remove broken tests**: Especially v2 test files
3. **Clean up template system**: Either use it or remove unused templates
4. **Remove backup files**: They're captured in git history
5. **Update directory structure**: Remove references to non-existent files
6. **Consider consolidating**: Some modules have overlapping functionality