# Memory System for StoryCraft Agent

StoryCraft Agent uses a custom SQLite-based memory system to maintain state and track story elements throughout the generation process.

## Overview

The memory system replaces the previous LangMem dependency with a simpler, more direct approach using SQLite database for persistent storage of story elements, character information, world details, and generation state.

## Key Components

### 1. Memory Manager (`storyteller_lib/memory_manager.py`)

The MemoryManager class provides a simple key-value store interface:

```python
from storyteller_lib.memory_manager import MemoryManager
from storyteller_lib.database_integration import get_db_manager

# Initialize
db_manager = get_db_manager()
memory_manager = MemoryManager(db_manager)

# Store memory
memory_manager.create_memory("story_theme", "A hero's journey of self-discovery")

# Retrieve memory
theme = memory_manager.get_memory("story_theme")

# Update memory
memory_manager.update_memory("story_theme", "An epic tale of redemption")

# Search memories
results = memory_manager.search_memory("character")
```

### 2. Database Schema

The memory system uses these main tables:

- **memories**: Generic key-value storage with namespace support
- **story_config**: Story configuration and global outline
- **chapters**: Chapter outlines and metadata
- **scenes**: Scene content and reflection notes
- **characters**: Character profiles and development
- **world_elements**: World-building information by category
- **plot_threads**: Narrative thread tracking

### 3. Memory Types in StoryCraft

The system manages several types of memory:

1. **Story Memory**: Overall plot, theme, and structure
2. **Character Memory**: Profiles, relationships, knowledge states
3. **World Memory**: Geography, history, culture, and other world elements
4. **Procedural Memory**: Generation decisions and creative choices
5. **Progress Memory**: Current state and completion status

### 4. Integration with LangGraph

Memory operations are integrated into the LangGraph workflow:

```python
# In LangGraph nodes
def generate_chapter(state: StoryState) -> Dict:
    # Retrieve relevant memories
    characters = memory_manager.get_memory("characters")
    world_elements = memory_manager.get_memory("world_elements")
    
    # Generate content using memories
    chapter_content = generate_with_context(characters, world_elements)
    
    # Store new memories
    memory_manager.create_memory(f"chapter_{num}_outline", chapter_content)
    
    return {"chapters": updated_chapters}
```

### 5. Memory Namespaces

Memories are organized by namespace for better organization:
- `storyteller`: Main story elements
- `characters`: Character-specific memories
- `world`: World-building elements
- `progress`: Generation progress tracking

## Benefits Over LangMem

1. **Simplicity**: Direct database operations without complex abstractions
2. **Performance**: Faster queries and updates with SQL
3. **Transparency**: Easy to inspect and debug stored data
4. **Flexibility**: Custom queries for complex retrieval patterns
5. **No External Dependencies**: Reduces complexity and potential failures

## Usage in Story Generation

The memory system is used throughout the story generation process:

1. **Initialization**: Store genre, tone, author style, and initial idea
2. **Brainstorming**: Save creative elements and selected ideas
3. **Outline Generation**: Store the hero's journey structure
4. **World Building**: Persist geography, history, culture, etc.
5. **Character Creation**: Save profiles, arcs, and relationships
6. **Chapter Planning**: Store chapter outlines and scene breakdowns
7. **Scene Writing**: Track content, revisions, and continuity
8. **Consistency Checking**: Query memories to ensure coherence

## Database Location

The SQLite database is stored at: `~/.storyteller/story_database.db`

You can inspect it directly using SQLite tools:
```bash
sqlite3 ~/.storyteller/story_database.db
.tables
.schema memories
SELECT * FROM memories WHERE namespace = 'storyteller';
```

## Future Enhancements

Potential improvements to the memory system:
- Vector embeddings for semantic search
- Memory consolidation and summarization
- Automatic memory pruning for efficiency
- Cross-story memory sharing for series
- Memory versioning for revision tracking