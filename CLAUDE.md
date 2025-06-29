# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StoryCraft Agent is an autonomous AI-powered story writing system that generates complete, multi-chapter stories following the hero's journey structure. It uses LangGraph for orchestration, SQLite database for state and memory management, and supports multiple LLM providers.

## Recent Refactoring (December 2024)

The codebase underwent a major reorganization from a flat structure (`storyteller_lib/*.py`) to a hierarchical, Pythonic structure:

```
storyteller_lib/
├── __init__.py
├── api/              # Public API interface
├── analysis/         # Story analysis tools
├── audiobook/        # SSML and TTS generation
├── core/             # Core components (config, models, logger)
├── generation/       # Content generation modules
│   ├── creative/     # Brainstorming and creative tools
│   ├── scene/        # Scene generation and management
│   └── story/        # Story-level components (arcs, narrative)
├── persistence/      # Database and storage
├── prompts/          # Template rendering and optimization
├── universe/         # World and character building
├── utils/            # Utility functions
└── workflow/         # LangGraph workflow nodes
```

### Key Changes from Refactoring

1. **Module Organization**: All modules now follow Python package conventions with proper hierarchy
2. **Import Updates**: All imports updated from `storyteller_lib.module` to `storyteller_lib.category.module`
3. **Fixed Issues During Refactoring**:
   - Widespread indentation errors from automated import updates (now fixed)
   - Missing `plan_chapters` function copied from old codebase
   - `PlotThreadRegistry.register_thread` → `PlotThreadRegistry.add_thread`
   - Database storage of story outline now properly implemented
   - Template paths updated to use absolute package paths

## Common Development Commands

### Development Setup
```bash
# Using Nix development environment
nix develop
```

## Architecture and Patterns

### Graph-Based Workflow
The system uses LangGraph's native edge system (not router-based) with conditional edges that evaluate state to determine flow. Key patterns:

1. **State Management**: Uses TypedDict classes for structured state with immutable updates
2. **Conditional Edges**: Each edge evaluates current state to determine next node
3. **No Recursion**: Explicit state transitions prevent recursion issues

### Core Components (Updated Paths)

1. **Graph Construction** (`storyteller_lib/graph.py`): Defines the LangGraph workflow with nodes and conditional edges
2. **State Models** (`storyteller_lib/core/models.py`): TypedDict definitions for StoryState, CharacterProfile, ChapterState, SceneState
3. **Memory Management** (`storyteller_lib/persistence/memory.py`): SQLite-based memory storage and retrieval
4. **Configuration** (`storyteller_lib/core/config.py`): LLM setup and provider management
5. **Database Integration** (`storyteller_lib/persistence/database.py`): Database manager for state persistence

### Story Generation Pipeline

The workflow follows this sequence:
1. Initialize → Brainstorm → Outline → Worldbuilding → Characters → Chapters → Scenes → Compilation

Each stage uses specific modules (with updated paths):
- **Initialization** (`workflow/nodes/initialization.py`): Sets up state and author style
- **Creative Brainstorming** (`generation/creative/brainstorming.py`): Generates and evaluates ideas
- **Plot Management** (`generation/story/plot_threads.py`): Tracks narrative threads with PlotThreadRegistry
- **Scene Generation** (`workflow/nodes/scenes.py`): Combines brainstorming, writing, reflection, and revision
- **Consistency** (`analysis/consistency.py`): Continuity checking and issue resolution
- **Outline Generation** (`workflow/nodes/outline.py`): Story outline and chapter planning

### Important Design Decisions

1. **Plot Thread Tracking**: Active management system that influences scene generation, not passive tracking
2. **Character Knowledge**: Explicit tracking of what each character knows at any point
3. **Memory Anchors**: Critical story elements stored in database for consistency
4. **Modular Design**: Each aspect of story generation is a separate module with clear interfaces
5. **Progress Tracking**: Real-time updates throughout generation process
6. **State Handling**: Always happens in LangGraph, in the state object
7. **Storage**: The storage happens in the db manager, but not the state handling

### Development Principles

- Never implement redundant code, neither for backward compatibility nor for not removing existing functionality
- If dependencies are missing make sure the dependencies are installed, never try to implement workarounds
- **Never mention claude when creating commit messages**

### Dependency Management

- For python dependencies use poetry, the pyproject.toml and "nix develop install" to actually install them

### Testing Approach

No formal test suite currently exists. Testing is done through running the story generator with different parameters and validating output quality.

## Key Files and Their Purposes (Updated Paths)

- `run_storyteller.py`: Main entry point with CLI argument parsing
- `storyteller_lib/graph.py`: LangGraph workflow definition
- `storyteller_lib/core/models.py`: All state type definitions
- `storyteller_lib/workflow/nodes/scenes.py`: Core scene generation logic
- `storyteller_lib/generation/story/plot_threads.py`: Plot thread tracking system
- `storyteller_lib/analysis/consistency.py`: Continuity management
- `storyteller_lib/api/storyteller.py`: Main API interface for story generation
- `storyteller_lib/prompts/renderer.py`: Template rendering system
- `storyteller_lib/prompts/templates/`: Jinja2 templates for all prompts

## Memories and Known Issues

- Gemini's structured output has a problem with nested dictionaries - it's returning them as JSON strings instead of properly parsed objects.
- NEVER USE JSON parsing, ALWAYs use structured output.
- Always use `nix develop =c python` when starting python scripts
- You can directly look into the database in ~/.storyteller/story_database.db
- Use this command to run the storyteller for testing to reuse llm caching: `nix develop -c python run_storyteller.py --genre sci-fi --tone adventurous`
- Never evaluate texts based on keywords, since they are not reliable. Use LLM based evaluations instead.
- NEVER share state in LangGraph and the database. Never invent your own state management.
- We do not need any migrations. All data is temporary per run.
- NEVER IMPLEMENT A FALLBACK FOR UNSTRUCTURED GENERATION
- Never truncate texts, rather generate a summary using the llm
- Make sure you provide the LLM well structured prompts with a clear intent and properly structured information. Do not just put JSON dumps into the prompt.
- Create each template in english (base language) and german
- Every time you mention claude in a commit message i will kill a small kitten.
- Never use user provided examples in the code. They are licensed.
- To debug the last run look in  ~/.storyteller/logs/story_progress.log
- To debug the database look in ~/.storyteller/story_database.db
- Never implement a fallback for structured output. Fail if the structured output did not work.
- Never use nested dictionaries in structured output.
- Never run the storyteller on your own, it takes hours
- Never add generated markdown files to git.
- never simply add all files (git add -A)
- After refactoring: all Python files have been moved to subdirectories, update imports accordingly
- The `plan_chapters` function was missing and has been added to `workflow/nodes/outline.py`
- Story outline must be stored in database using `db_manager.update_global_story()` after generation
- Character relationships require two-pass saving: first save all characters, then update relationships
- Do not write about every change and fix into the claude.md
- For indentation errors: first try to fix them using black
- You can analyze data database in /home/johann/.storyteller/story_database.db