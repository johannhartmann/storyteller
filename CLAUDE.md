# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StoryCraft Agent is an autonomous AI-powered story writing system that generates complete, multi-chapter stories following the hero's journey structure. It uses LangGraph for orchestration, LangMem for memory management, and supports multiple LLM providers.

## Common Development Commands

### Running the Story Generator
```bash
# Basic usage
python run_storyteller.py --genre fantasy --tone epic --output my_story.md

# With author style emulation
python run_storyteller.py --genre mystery --tone dark --author "Edgar Allan Poe"

# Generate in different languages (12 supported)
python run_storyteller.py --genre fantasy --tone epic --language spanish

# With custom story idea
python run_storyteller.py --idea "A detective story set in a zoo" --tone mysterious

# Using different LLM providers
python run_storyteller.py --genre fantasy --tone epic --model-provider openai
python run_storyteller.py --genre mystery --tone dark --model-provider anthropic
```

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Using Nix development environment
nix develop

# Create .env file with API keys
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
DEFAULT_MODEL_PROVIDER=gemini
```

## Architecture and Patterns

### Graph-Based Workflow
The system uses LangGraph's native edge system (not router-based) with conditional edges that evaluate state to determine flow. Key patterns:

1. **State Management**: Uses TypedDict classes for structured state with immutable updates
2. **Conditional Edges**: Each edge evaluates current state to determine next node
3. **No Recursion**: Explicit state transitions prevent recursion issues

### Core Components

1. **Graph Construction** (`storyteller_lib/graph.py`): Defines the LangGraph workflow with nodes and conditional edges
2. **State Models** (`storyteller_lib/models.py`): TypedDict definitions for StoryState, CharacterProfile, ChapterState, SceneState
3. **Memory Management** (`storyteller_lib/memory_adapter.py`): LangMem integration with SQLite persistence
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
3. **Memory Anchors**: Critical story elements stored in LangMem for consistency
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