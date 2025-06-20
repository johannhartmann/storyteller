# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StoryCraft Agent is an autonomous AI-powered story writing system that generates complete, multi-chapter stories following the hero's journey structure. It uses LangGraph for orchestration, SQLite database for state and memory management, and supports multiple LLM providers.

## Common Development Commands

### Development Setup
```bash
# Using Nix development environment
nix develop


## Architecture and Patterns

### Graph-Based Workflow
The system uses LangGraph's native edge system (not router-based) with conditional edges that evaluate state to determine flow. Key patterns:

1. **State Management**: Uses TypedDict classes for structured state with immutable updates
2. **Conditional Edges**: Each edge evaluates current state to determine next node
3. **No Recursion**: Explicit state transitions prevent recursion issues

### Core Components

1. **Graph Construction** (`storyteller_lib/graph.py`): Defines the LangGraph workflow with nodes and conditional edges
2. **State Models** (`storyteller_lib/models.py`): TypedDict definitions for StoryState, CharacterProfile, ChapterState, SceneState
3. **Memory Management** (`storyteller_lib/memory_manager.py`): SQLite-based memory storage and retrieval
4. **Configuration** (`storyteller_lib/config.py`): LLM setup and provider management

### Story Generation Pipeline

The workflow follows this sequence:
1. Initialize → Brainstorm → Outline → Worldbuilding → Characters → Chapters → Scenes → Compilation

Each stage uses specific modules:
- **Initialization** (`initialization.py`): Sets up state and author style
- **Creative Brainstorming** (`creative_tools.py`): Generates and evaluates ideas
- **Plot Management** (`plot_threads.py`): Tracks narrative threads with PlotThreadRegistry
- **Scene Generation** (`scenes.py`): Combines brainstorming, writing, reflection, and revision
- **Consistency** (`consistency.py`): Continuity checking and issue resolution

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

## Key Files and Their Purposes

- `run_storyteller.py`: Main entry point with CLI argument parsing
- `storyteller_lib/graph.py`: LangGraph workflow definition
- `storyteller_lib/models.py`: All state type definitions
- `storyteller_lib/scenes.py`: Core scene generation logic
- `storyteller_lib/plot_threads.py`: Plot thread tracking system
- `storyteller_lib/consistency.py`: Continuity management

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