# Story Generation Flow

This document describes the complete story generation workflow as implemented in the StoryCraft Agent using LangGraph.

## Overview

The story generation follows a linear workflow with conditional branches for scene quality control. The system uses a state-based approach where each node reads from and updates a shared state dictionary.

## Graph Structure

### Main Flow Sequence

```
START
  ↓
initialize_state
  ↓
brainstorm_story_concepts
  ↓
generate_story_outline
  ↓
generate_worldbuilding
  ↓
generate_characters
  ↓
plan_chapters
  ↓
write_scene ←─────────────────┐
  ↓                           │
reflect_on_scene              │
  ↓                           │
[Conditional Routing]         │
  ├─→ apply_minor_corrections │
  ├─→ revise_scene_if_needed  │
  └─→ (continue)              │
  ↓                           │
update_world_elements         │
  ↓                           │
update_character_profiles     │
  ↓                           │
generate_summaries            │
  ↓                           │
advance_to_next_scene_or_chapter
  ↓                           │
[Story Complete Check]        │
  ├─→ (continue) ─────────────┘
  └─→ (complete)
       ↓
compile_final_story
  ↓
END
```

## Node Descriptions

### 1. **initialize_state**
- Sets up initial story state
- Loads configuration (genre, tone, language)
- Initializes database connection
- Prepares author style analysis

### 2. **brainstorm_story_concepts**
- Generates creative story ideas based on initial parameters
- Evaluates and selects the best concept
- Creates initial story premise

### 3. **generate_story_outline**
- Creates the overall story structure
- Defines major plot points following hero's journey
- Establishes story arc and pacing

### 4. **generate_worldbuilding**
- Develops the story world and setting
- Creates consistent world rules and elements
- Establishes atmosphere and environment

### 5. **generate_characters**
- Creates main and supporting characters
- Defines character profiles, motivations, and relationships
- Establishes character arcs

### 6. **plan_chapters**
- Breaks down the story into chapters (minimum 8)
- Plans scenes for each chapter
- Defines plot progressions and character development per scene

### 7. **write_scene**
- Generates book-level writing instructions
- Creates scene-specific instructions
- Writes the actual scene content
- Stores scene in database

### 8. **reflect_on_scene**
- Analyzes scene quality across 4 key metrics:
  - Overall quality (1-10)
  - Plot advancement
  - Character consistency
  - Prose engagement
- Identifies critical issues (requiring full revision)
- Identifies minor issues (suitable for targeted correction)
- Sets flags: `needs_revision` and `needs_minor_corrections`

### 9. **Conditional Routing** (`check_correction_type`)
Routes based on reflection results:
- **"revise"**: If critical issues exist → `revise_scene_if_needed`
- **"minor_corrections"**: If only minor issues exist → `apply_minor_corrections`
- **"continue"**: If no issues → `update_world_elements`

### 10. **apply_minor_corrections** (New)
- Applies surgical corrections for minor issues
- Uses the `correct_scene` function
- Preserves scene integrity while fixing specific problems
- Does not trigger full rewrite

### 11. **revise_scene_if_needed**
- Performs complete scene revision for critical issues
- Single-pass revision focused on specific problems
- Rewrites scene while maintaining requirements

### 12. **update_world_elements**
- Extracts new world information from the scene
- Updates world database
- Maintains consistency across story

### 13. **update_character_profiles**
- Updates character states and knowledge
- Tracks character development
- Maintains character consistency

### 14. **generate_summaries**
- Creates scene summary
- Updates chapter summary
- Maintains running story summary

### 15. **advance_to_next_scene_or_chapter**
- Moves to next scene or chapter
- Updates progress tracking
- Checks if story is complete

### 16. **Story Complete Check** (`is_story_complete`)
Determines if story generation should continue:
- **"continue"**: More scenes to write → back to `write_scene`
- **"complete"**: All scenes written → `compile_final_story`

### 17. **compile_final_story**
- Assembles all chapters and scenes
- Creates final story document
- Performs final formatting

## Key Features

### Quality Control System
The workflow implements a three-tier quality control system:

1. **No Issues**: Scene passes reflection → continues to updates
2. **Minor Issues**: Small problems → targeted corrections via `correct_scene`
3. **Critical Issues**: Major problems → full revision

### Database Integration
- All scenes stored in SQLite database
- Tracks world elements, characters, and plot progressions
- Maintains consistency throughout generation

### Progress Tracking
- Real-time progress updates via `@track_progress` decorator
- Chapter and scene tracking
- Completion status monitoring

### Language Support
- Multi-language support (English, German, Spanish, French, etc.)
- Language-specific templates for all prompts
- Consistent style across languages

## State Management

The `StoryState` TypedDict maintains:
- Current chapter and scene numbers
- Story configuration (genre, tone, language)
- Generated content (outline, characters, world)
- Book and scene-level instructions
- Reflection results and correction flags
- Progress indicators

## Conditional Logic

### Scene Correction Routing
```python
def check_correction_type(state: StoryState) -> str:
    if state.get("needs_revision", False):
        return "revise"  # Critical issues
    if state.get("needs_minor_corrections", False):
        return "minor_corrections"  # Minor issues
    return "continue"  # No issues
```

### Story Completion Check
```python
def is_story_complete(state: StoryState) -> str:
    if state.get("completed", False):
        return "complete"
    if len(chapters) < 8:
        return "continue"
    # Check if all planned scenes are written
    for chapter in chapters:
        for scene in chapter["scenes"]:
            if not scene.get("db_stored", False):
                return "continue"
    return "complete"
```

## Error Handling

- Database operations wrapped in try-except blocks
- Graceful degradation if minor corrections fail
- Logging at each step for debugging
- State preservation across node failures

## Configuration

Key configuration options:
- `genre`: Story genre (fantasy, sci-fi, mystery, etc.)
- `tone`: Writing tone (adventurous, dark, humorous, etc.)
- `language`: Output language
- `llm_provider`: AI model provider
- `llm_model`: Specific model to use

## Recent Enhancements

### Minor Corrections Integration (Latest)
- Added distinction between critical and minor issues
- New `apply_minor_corrections` node for targeted fixes
- Enhanced reflection to categorize issue severity
- Improved overall story quality without excessive revisions

### Intelligent Scene Writing
- Context-aware scene generation
- Book-level and scene-level instruction synthesis
- "What happened until now" summaries for continuity

## Usage

The workflow is initiated through:
```python
from storyteller_lib import generate_story

result = generate_story(
    initial_premise="Your story idea",
    genre="fantasy",
    tone="adventurous",
    language="english"
)
```

The system then automatically progresses through all nodes, generating a complete multi-chapter story with consistent characters, world-building, and plot development.