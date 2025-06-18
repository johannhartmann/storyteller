# StoryCraft Agent - LangGraph Flow Documentation

## Overview
The StoryCraft Agent uses LangGraph to orchestrate a multi-step story generation process. Each node in the graph performs specific tasks, often involving LLM calls, and saves its results to a SQLite database.

## State Management
The `StoryState` contains:
- Configuration: genre, tone, author, language
- Workflow control: current_chapter, current_scene, completed, last_node
- Content (should be in DB only): global_story, characters, world_elements, chapters
- Temporary data: scene_elements, reflection_notes, continuity_issues

## Graph Structure
- Single graph.py file with integrated database operations
- Linear flow for story setup phase (no conditional branching)
- Each node handles its own database saves/loads
- No wrapper functions or state duplication

## Node Flow

## Linear Setup Phase

The story generation begins with a linear sequence of nodes (no branching):

1. **START** → `initialize_state`
2. `initialize_state` → `brainstorm_story_concepts`
3. `brainstorm_story_concepts` → `generate_story_outline`
4. `generate_story_outline` → `generate_worldbuilding`
5. `generate_worldbuilding` → `generate_characters`
6. `generate_characters` → `plan_chapters`
7. `plan_chapters` → `brainstorm_scene_elements` (begins scene loop)

### 1. `initialize_state`
**Purpose**: Set up initial story configuration
- **Input**: User parameters (genre, tone, author, language, initial_idea)
- **LLM Tasks**: 
  - Parse initial idea into structured elements (if provided)
  - Extract setting, characters, plot, themes from the idea
- **Database Operations**: 
  - Create story_config record
  - Initialize story metadata
- **Output**: Initialized state with configuration
- **Next**: Always proceeds to brainstorm_story_concepts

### 2. `brainstorm_story_concepts`
**Purpose**: Generate creative ideas for the story
- **Always runs**: Even with initial idea, to enhance and expand concepts
- **LLM Tasks**:
  - Generate 5 story concept ideas
  - Generate 4 world-building ideas  
  - Generate 3 central conflict ideas
  - Evaluate and rank each idea
- **Output**: creative_elements with recommended concepts
- **Next**: Always proceeds to generate_story_outline

### 3. `generate_story_outline`
**Purpose**: Create the hero's journey structure
- **LLM Tasks**:
  - Generate complete story outline following hero's journey
  - If author specified: analyze author's style first
  - Validate outline matches genre/tone/initial idea
  - Generate plot threads from outline
- **Database Operations**:
  - Save global_story to story_config
  - Create plot_threads records
- **Output**: global_story outline, plot_threads
- **Next**: Always proceeds to generate_worldbuilding

### 4. `generate_worldbuilding`
**Purpose**: Create detailed world elements
- **LLM Tasks**:
  - Extract world categories from outline
  - For each category, generate detailed elements
  - Ensure consistency with genre/setting
- **Database Operations**:
  - Save world_elements to database
- **Output**: world_elements dictionary (marked as stored_in_db)
- **Next**: Always proceeds to generate_characters

### 5. `generate_characters`
**Purpose**: Create detailed character profiles
- **LLM Tasks**:
  - Extract character roles from outline
  - For each major character:
    - Generate backstory, personality, motivations
    - Define character arc type and progression
    - Establish relationships with other characters
- **Database Operations**:
  - Create characters records
  - Save character arcs
- **Output**: characters dictionary with profiles
- **Next**: Always proceeds to plan_chapters

### 6. `plan_chapters`
**Purpose**: Divide story into chapters with scene descriptions
- **LLM Tasks**:
  - Create 8-12 chapter breakdown
  - For each chapter:
    - Write detailed outline (200-300 words)
    - Define 1+ scenes with:
      - Scene description
      - Plot progressions
      - Character learning moments
      - Required characters
      - Dramatic purpose
- **Database Operations**:
  - Create chapters records
  - Create scenes records with descriptions (via save_chapter_outline)
- **Output**: chapters structure (minimal in state)
- **Next**: Proceeds to brainstorm_scene_elements for Chapter 1, Scene 1

### 7. Scene Writing Loop

#### 7a. `brainstorm_scene_elements`
**Purpose**: Generate creative approach for current scene
- **Preconditions**: 
  - Retrieves scene description from database
  - Gets previous scenes for context
- **LLM Tasks**:
  - Analyze scene variety (avoid repetition)
  - Suggest scene type and approach
  - Brainstorm 3 different ways to write the scene
  - Consider plot threads and character dynamics
- **Database Operations**:
  - Query scene description from scenes table
  - Query previous scenes for variety analysis
- **Output**: scene_elements with creative approach

#### 7b. `write_scene`
**Purpose**: Write the actual scene content
- **LLM Tasks**:
  - Write 800-1200 word scene
  - Follow scene description from chapter planning
  - Incorporate required plot progressions
  - Include character learning moments
  - Maintain consistent POV and style
- **Database Operations**:
  - Save scene content to scenes table
  - Track plot progressions
  - Record character knowledge updates
- **Output**: current_scene_content

#### 7c. `reflect_on_scene`
**Purpose**: Analyze the written scene
- **LLM Tasks**:
  - Evaluate scene effectiveness
  - Check character consistency
  - Verify plot progressions occurred
  - Identify any issues
- **Output**: reflection_notes

#### 7d. `revise_scene_if_needed`
**Purpose**: Improve scene based on reflection
- **Condition**: Only if reflection found issues
- **LLM Tasks**:
  - Rewrite problematic sections
  - Enhance character moments
  - Clarify plot points
- **Database Operations**:
  - Update scene content if revised
- **Output**: Updated scene content

#### 7e. `update_world_elements`
**Purpose**: Track new world details from scene
- **LLM Tasks**:
  - Extract new locations mentioned
  - Note new world details introduced
  - Check for consistency
- **Database Operations**:
  - Update world_elements table
- **Output**: Updated world tracking

#### 7f. `update_character_profiles`
**Purpose**: Track character development
- **LLM Tasks**:
  - Note character growth/changes
  - Update emotional states
  - Track relationship changes
- **Database Operations**:
  - Update characters table
  - Record character states
- **Output**: Updated character tracking

### 8. `review_continuity` (every 3 scenes)
**Purpose**: Check for consistency issues
- **Condition**: Runs every 3rd scene
- **LLM Tasks**:
  - Analyze recent scenes for contradictions
  - Check timeline consistency
  - Verify character behavior consistency
  - Review world-building consistency
- **Output**: continuity_issues list

### 9. `resolve_continuity_issues`
**Purpose**: Fix any continuity problems
- **Condition**: Only if issues found
- **LLM Tasks**:
  - Generate fixes for each issue
  - Determine which scenes need updates
- **Database Operations**:
  - Update affected scenes
- **Output**: Resolution status

### 10. `advance_to_next_scene_or_chapter`
**Purpose**: Move to next scene/chapter or complete
- **Logic**:
  - If more scenes in chapter: next scene
  - If chapter complete: next chapter, scene 1
  - If all chapters done: mark completed
- **Output**: Updated current_chapter, current_scene

### 11. `compile_final_story`
**Purpose**: Assemble the complete story
- **Database Operations**:
  - Query all chapters and scenes in order
  - Combine into final story document
- **Output**: Complete story file

## Data Flow Issues

### Current Problems:
1. **Scene Descriptions**: Saved during `plan_chapters` but sometimes not found during `brainstorm_scene_elements`
2. **Chapter ID Mapping**: Temporary map in DB manager doesn't persist between nodes
3. **State Bloat**: Full content stored in state instead of just references
4. **Variety Analysis**: Gets incomplete data, shows "unknown" for scene types

### Root Causes:
- Database manager instances don't share state between nodes
- Scene variety analysis runs before scene descriptions are loaded
- Dual data storage (state + database) creates confusion
- No clear separation between workflow data and content data