# Scene Creation Process in StoryCraft Agent

This document provides a detailed explanation of the scene creation process in the StoryCraft Agent storytelling system.

## Overview

The scene creation process is a sophisticated multi-phase workflow that ensures high-quality, varied, and coherent narrative generation. It involves planning, writing, reflection, and revision phases, all orchestrated through a graph-based workflow system.

## Phase 1: Scene Planning (During Chapter Planning)

### Location
- **File**: `storyteller_lib/outline.py`
- **Function**: `plan_chapters()`

### Process
During chapter planning, each scene is specified with detailed requirements using the `SceneSpec` model:

```python
class SceneSpec(BaseModel):
    description: str  # Brief description of what happens
    scene_type: str  # action, dialogue, exploration, revelation, character_moment, transition, conflict, resolution
    plot_progressions: List[str]  # Key plot points that MUST happen
    character_learns: List[str]  # What characters learn (format: "CharacterName: knowledge item")
    required_characters: List[str]  # Characters who must appear
    forbidden_repetitions: List[str]  # Plot points that must NOT be repeated
    dramatic_purpose: str  # setup, rising_action, climax, falling_action, resolution
    tension_level: int  # 1-10 scale
    ends_with: str  # cliffhanger, resolution, soft_transition, hard_break
    connects_to_next: str  # How this scene connects narratively to the next
```

### Key Features
- Structured planning ensures each scene has clear purpose
- Plot progression tracking prevents repetition
- Character knowledge is explicitly planned
- Dramatic structure is maintained throughout

## Phase 2: Scene Writing

### Location
- **File**: `storyteller_lib/scene_writer.py`
- **Function**: `write_scene()`

### Sub-phases

#### 2.1 Context Gathering
The system gathers extensive context before writing:

1. **Database Context** (`_prepare_database_context()`)
   - Previous scene endings
   - Active plot threads
   - Character emotional states
   - Continuation requirements

2. **Previous Scenes Summary** (`_generate_previous_scenes_summary()`)
   - Key events from previous chapters
   - Recent scenes in current chapter
   - Story events and character knowledge updates

3. **Character Context**
   - Character profiles from database
   - Current emotional states
   - Personality traits and motivations
   - Character arcs and development stages

4. **World Elements**
   - Geography, history, culture
   - Magic/technology systems
   - Social structures
   - Current world state

#### 2.2 Intelligent Entity Analysis
The system uses `entity_relevance.py` to:
- Analyze which characters are relevant to the current scene
- Filter world elements based on scene requirements
- Limit context to prevent prompt bloat
- Ensure all necessary entities are included

#### 2.3 Scene Variety Analysis
Using `scene_variety.py`, the system:
- Analyzes previous 10 scenes for patterns
- Determines required scene type (action, dialogue, etc.)
- Sets emotional tone requirements
- Identifies overused elements to avoid

#### 2.4 Creative Brainstorming
Integrated brainstorming phase (`creative_tools.py`):
- Generates 3 creative approaches for the scene
- Considers plot threads and character dynamics
- Evaluates approaches for genre appropriateness
- Selects best approach for implementation

#### 2.5 Intelligent Repetition Analysis
Using `intelligent_repetition.py`:
- Analyzes recent scenes for repetitive patterns
- Distinguishes intentional vs unintentional repetition
- Provides variation guidance
- Considers genre and author style

#### 2.6 Structural Analysis
The system analyzes scene structures to:
- Identify opening patterns (in medias res, descriptive, dialogue, etc.)
- Track narrative techniques
- Ensure structural variety
- Generate guidance for unique approaches

#### 2.7 Prompt Generation
Using Jinja2 templates:
- Assembles all context and guidance
- Formats according to language requirements
- Includes all specifications and constraints
- Optimizes prompt size while maintaining context

#### 2.8 Content Generation
The LLM generates scene content with:
- All context and requirements
- Variety and repetition guidance
- Character consistency requirements
- Plot progression specifications

### Database Operations
After generation:
- Scene content stored in database
- Scene metadata updated
- Plot progressions tracked
- Character knowledge recorded
- Story events logged

## Phase 3: Scene Reflection

### Location
- **File**: `storyteller_lib/scene_reflection.py`
- **Function**: `reflect_on_scene()`

### Structured Analysis
Using the `SceneReflection` model:

```python
class SceneReflection(BaseModel):
    overall_quality: int  # 1-10
    plot_advancement: int  # 1-10
    character_development: int  # 1-10
    dialogue_quality: int  # 1-10
    description_quality: int  # 1-10
    pacing: int  # 1-10
    emotional_impact: int  # 1-10
    consistency: int  # 1-10
    engagement: int  # 1-10
    
    issues: List[ReflectionIssue]  # Specific problems found
    continuity_concerns: List[str]  # Continuity issues
    revision_needed: bool
    revision_priority: str  # high, medium, low, none
    specific_revision_guidance: str
```

### Analysis Components

1. **Quality Metrics**
   - Nine different aspects scored 1-10
   - Overall quality assessment
   - Specific issue identification

2. **Issue Tracking**
   ```python
   class ReflectionIssue(BaseModel):
       issue_type: str  # pacing, character, dialogue, description, plot, consistency
       description: str
       severity: int  # 1-10
       suggested_fix: str
   ```

3. **Continuity Checking**
   - Character consistency
   - World consistency
   - Plot thread continuity
   - Timeline coherence

4. **Technical Analysis**
   - POV consistency
   - Tense consistency
   - Show vs tell balance
   - Genre appropriateness

## Phase 4: Scene Revision

### Location
- **File**: `storyteller_lib/scene_revision.py`
- **Function**: `revise_scene_if_needed()`

### Revision Triggers
Revision occurs when:
- Overall quality < 7
- Any aspect score < 6
- High-severity issues present
- Continuity concerns exist
- Revision priority is "high" or "medium"

### Revision Process

1. **Context-Aware Revision**
   - Original scene content
   - Reflection analysis results
   - Chapter context
   - Previous revisions (if any)

2. **Targeted Improvements**
   - Specific issue resolution
   - Maintains what works well
   - Preserves plot progressions
   - Enhances weak areas

3. **Validation**
   - Re-reflection after revision
   - Continuity re-check
   - Quality verification

## Advanced Features

### Plot Thread Management
- **Registry**: `PlotThreadRegistry` class tracks all threads
- **States**: introduced, developed, resolved, abandoned
- **Integration**: Threads influence scene requirements
- **Resolution**: Major threads must resolve by story end

### Character Knowledge Management
- **Tracking**: What each character knows at any point
- **Visibility**: public, secret, revealed knowledge
- **Validation**: Prevents impossible knowledge
- **Updates**: Tracked per scene

### Scene Progression Tracking
- **Patterns**: Tracks narrative patterns
- **Variety**: Enforces structural variety
- **Events**: Logs all major story events
- **Analysis**: Identifies overused elements

### Multi-Language Support
- **Templates**: 12 languages supported
- **Localization**: Cultural considerations
- **Consistency**: Language-specific validation
- **Quality**: Native-like output

## Workflow Orchestration

### Graph-Based Flow
Using LangGraph, the workflow:
1. Executes scene writing node
2. Performs reflection check
3. Conditionally triggers revision
4. Updates world and characters
5. Checks continuity
6. Advances to next scene

### State Management
- Planning data in state
- Content in database
- Metadata tracked
- Progress logged

### Error Handling
- Graceful degradation
- Partial recovery
- Progress preservation
- Quality maintenance

## Best Practices

1. **Context Management**
   - Balance comprehensive context with prompt limits
   - Use relevance filtering
   - Maintain consistency

2. **Quality Assurance**
   - Multiple validation passes
   - Structured reflection
   - Targeted revision

3. **Variety and Freshness**
   - Active pattern tracking
   - Enforced variety
   - Creative brainstorming

4. **Coherence**
   - Plot thread tracking
   - Character knowledge management
   - Continuity checking

## Technical Implementation Details

### Database Schema
- `scenes` table: content and metadata
- `story_events` table: major events
- `character_knowledge` table: knowledge tracking
- `plot_thread_developments` table: thread progress

### Template System
- Jinja2 templates
- Language-specific versions
- Consistent formatting
- Modular design

### Performance Optimizations
- Prompt size optimization
- Batch database operations
- Efficient context filtering
- Smart caching strategies

## Conclusion

The scene creation process in StoryCraft Agent represents a sophisticated approach to automated storytelling, combining planning, creativity, analysis, and revision to produce high-quality narrative content. The system's modular design, comprehensive tracking, and intelligent features ensure coherent, varied, and engaging story generation.