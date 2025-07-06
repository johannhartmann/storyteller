# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StoryCraft Agent is an autonomous AI-powered story writing system that generates complete, multi-chapter stories following the hero's journey structure. It uses a simple sequential orchestrator (no longer LangGraph), SQLite database for all state management, and supports multiple LLM providers.

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
└── workflow/         # Workflow nodes and orchestrator
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

### Sequential Workflow (LangGraph Removed - January 2025)
The system now uses a simple sequential orchestrator that executes workflow steps in order. All state is stored in the database. Key patterns:

1. **State Management**: All state stored in SQLite database, no in-memory state objects
2. **Sequential Execution**: Steps execute in predefined order without conditional routing
3. **Database-Driven**: All data persistence and retrieval through database manager

### Core Components (Updated Paths)

1. **Orchestrator** (`storyteller_lib/workflow/orchestrator.py`): Simple sequential workflow executor
2. **State Models** (`storyteller_lib/core/models.py`): Pydantic models for data validation (StoryState removed)
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
6. **State Handling**: All state is stored and retrieved from the database
7. **Storage**: Database manager handles all state persistence and retrieval

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
- `storyteller_lib/workflow/orchestrator.py`: Sequential workflow orchestrator
- `storyteller_lib/core/models.py`: All state type definitions
- `storyteller_lib/workflow/nodes/scenes.py`: Core scene generation logic
- `storyteller_lib/generation/story/plot_threads.py`: Plot thread tracking system
- `storyteller_lib/analysis/consistency.py`: Continuity management
- `storyteller_lib/api/storyteller.py`: Main API interface for story generation
- `storyteller_lib/prompts/renderer.py`: Template rendering system
- `storyteller_lib/prompts/templates/`: Jinja2 templates for all prompts

## Memories and Known Issues

- NEVER USE JSON parsing, ALWAYs use structured output.
- Always use `nix develop =c python` when starting python scripts
- Never evaluate texts based on keywords, since they are not reliable. Use LLM based evaluations instead.
- All state is in the database. No separate state management systems.
- We do not need any migrations. All data is temporary per run.
- Never truncate texts, rather generate a summary using the llm
- Make sure you provide the LLM well structured prompts with a clear intent and properly structured information. Do not just put JSON dumps into the prompt.
- Create each template in english (base language) and german
- Every time you mention claude in a commit message i will kill a small kitten.
- Never use user provided examples in the code. They are licensed.
- To debug the last run look in  ~/.storyteller/logs/story_progress.log
- To debug the database look in ~/.storyteller/story_database.db
- Never implement a fallback for structured output. Fail if the structured output did not work.
- Never use nested dictionaries in structured output.
- NEVER START THE STORYTELLER ON YOUR OWN, IT TAKES HOURS
- Never add generated markdown files to git.
- never simply add all files (git add -A)
- Do not write about every change and fix into the claude.md
- For indentation errors: first try to fix them using black
- never add all files in a directory to a commit
- NEVER USE EXAMPLES FROM A RANDOM DEMO BOOK