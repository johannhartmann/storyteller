# StoryCraft Agent – Autonomous Story-Writing with Dynamic Memory, State & Progress Tracking

**Overview:**  
StoryCraft Agent is an autonomous AI agent designed to write engaging, multi-chapter stories based on the hero's journey using LangGraph for orchestration and SQLite database for state and memory management. It generates an overall storyline, divides it into chapters with multiple scenes each, and manages evolving characters with detailed profiles. The agent continuously reflects on and revises content to ensure quality and consistency while providing detailed progress tracking throughout the generation process. The implementation includes robust error handling and safety mechanisms to prevent infinite recursion and gracefully manage edge cases.

---

## Core Features

1. **Hero's Journey Integration:**  
   - The agent dynamically generates all phases of the hero's journey (e.g., Call to Adventure, Meeting the Mentor, Trials, Ordeal, Reward, Return) as high-level plot milestones.

2. **Autonomous Storyline Generation:**  
   - It creates a granular, overall storyline that is subdivided into multiple chapters and scenes without any manual intervention.

3. **Multi-Character Management:**  
   - Supports flexible, evolving roles for several characters.  
   - Tracks each character's backstory, evolution, relationships, and both secret and revealed knowledge.

4. **Iterative Self-Reflection & Revision:**  
   - Each chapter and scene undergoes a self-reflection process that evaluates style, tone, continuity, and consistency with the overall storyline and character arcs.  
   - The agent autonomously revises content based on its own feedback loops.

5. **Continuity & Reader Engagement:**  
   - The agent flags inconsistencies (e.g., conflicting character information or plot holes) and automatically fixes them.  
   - It tracks what information has been revealed to the reader and what remains hidden, controlling the timing of key plot revelations to sustain suspense.

6. **Creative Brainstorming:**
   - Generates multiple creative ideas for story concepts, world-building elements, and scene components
   - Evaluates generated ideas against criteria like originality, coherence, and impact
   - Incorporates the most promising ideas into the narrative

7. **Author Style Emulation:**
   - Analyzes and mimics the writing style of specified authors
   - Customizes scene generation to match the author's typical sentence structure, description style, and thematic elements

8. **Real-time Progress Tracking:**
   - Uses decorator pattern to track progress of each node execution
   - Provides detailed status updates showing the current state of story generation
   - Calculates and reports percentage completion for chapters and scenes

9. **Error Handling & Safety Mechanisms:**
   - Prevents infinite recursion with circuit breakers in the router logic
   - Includes robust validation to handle edge cases and unexpected states
   - Gracefully terminates execution if inconsistent state is detected

10. **Memory & State Management:**
   - **Overall Story Memory:** Stores the global plot outline, hero's journey phases, and thematic elements.  
   - **Chapter Memory:** Maintains detailed outlines, scene breakdowns, and reflection notes for each chapter.  
   - **Scene Memory:** Holds the detailed content and self-reflection feedback for each scene.  
   - **Character Memory:** Records individual character profiles, including evolution, known facts, secret details, and relationship changes.  
   - **Revelation Log:** Tracks which critical facts have been revealed to the reader versus those kept in reserve.
   
   **State Structuring Implementation:**

   - **Comprehensive State Schema:**  
     Using TypedDict classes for structured state management:

     ```python
     class CharacterProfile(TypedDict):
         name: str
         role: str
         backstory: str
         evolution: List[str]
         known_facts: List[str]
         secret_facts: List[str]
         revealed_facts: List[str]
         relationships: Dict[str, str]

     class SceneState(TypedDict):
         content: str
         reflection_notes: List[str]

     class ChapterState(TypedDict):
         title: str
         outline: str
         scenes: Dict[str, SceneState]
         reflection_notes: List[str]

     class StoryState(TypedDict):
         messages: Annotated[List[Union[HumanMessage, AIMessage]], add_messages]
         genre: str
         tone: str
         author: str
         author_style_guidance: str
         global_story: str
         chapters: Dict[str, ChapterState]
         characters: Dict[str, CharacterProfile]
         revelations: Dict[str, List[str]]
         creative_elements: Dict[str, Dict]
         current_chapter: str
         current_scene: str
         completed: bool
         last_node: str
     ```
   
   - **Integrated Memory Operations:**  
     Using SQLite database for memory management:
     - **Story Memory:** For storing story outlines, character profiles, and scene elements.
     - **Procedural Memory:** For tracking the creative process and revision history.
     
   - **Progress Tracking:**
     Using function decorators to monitor execution progress:
     ```python
     @track_progress
     def node_function(state: StoryState) -> Dict:
         # Node implementation
         return updated_state
     ```

---

## Agent Workflow & Architecture

1. **Initialization:**  
   - Input parameters (genre, tone, author) set the stylistic and thematic guidelines.  
   - The state is initialized with empty structures for all components.

2. **Story Concept Brainstorming:**
   - Generates and evaluates multiple creative story concepts
   - Brainstorms world-building elements and central conflicts
   - Stores creative elements for later use in the story development

3. **Overall Story Generation:**  
   - Generates the full hero's journey outline and stores it in `global_story`.
   - If an author style is specified, analyzes and incorporates that author's writing style.

4. **Character Generation:**  
   - Creates detailed character profiles with interconnected backgrounds.
   - Establishes relationships, motivations, and secrets for each character.

5. **Chapter Planning:**  
   - Divides the story into chapters, each with a title and detailed outline.
   - Structures each chapter to include 2-5 scenes that advance the plot.

6. **Scene Generation & Reflection:**
   - **Brainstorm Scene Elements:** Creates creative elements specific to each scene.
   - **Write Scene:** Generates detailed scene content incorporating creative elements.
   - **Reflect on Scene:** Evaluates scene quality, continuity, and consistency.
   - **Revise if Needed:** Automatically improves scenes that don't meet quality standards.

7. **Character Profile Updates:**  
   - Updates character profiles after each scene with new developments.
   - Ensures consistency in character evolution throughout the story.

8. **Continuity Management:**  
   - Reviews completed chapters for overall continuity and consistency.
   - Flags and resolves inconsistencies in the narrative.

9. **Story Progression:**  
   - Advances through chapters and scenes systematically.
   - Reports detailed progress at each step of the generation process.

10. **Final Compilation:**  
    - Once all chapters and scenes are completed, compiles the final story.
    - Formats the story with proper markdown structure for readability.

11. **Progress Tracking System:**
    - Monitors and reports on each step of the generation process.
    - Provides real-time status updates with timing information.
    - Calculates completion percentages for chapters and scenes.
    - Includes safety mechanisms to prevent infinite loops.

---

## Implementation Details

The agent is implemented using a modular architecture with several key components:

1. **LangGraph for Flow Control:**
   - Utilizes a StateGraph with a central router node
   - Each story generation step is implemented as a separate node
   - Conditional edges determine the flow based on the current state

2. **Node Structure:**
   ```
   START → initialize_state → router
                               ↓
    ┌──────────────────────────┼───────────────────────────────┐
    ↓                          ↓                               ↓
   brainstorm_concepts → generate_outline → generate_characters → plan_chapters
    |                    |                  |                     |
    └────────────────────┴──────────────────┴─────────────────────┘
                                 ↓
                     ┌────────────────────────┐
                     ↓                        ↓
             brainstorm_scene → write_scene → reflect_on_scene → revise_scene
                     |           |             |                   |
                     └───────────┘             └───────────────────┘
                         ↓                               ↓
                update_characters → review_continuity → advance_to_next
                     |                      |                |
                     └──────────────────────┘                ↓
                                                    compile_final_story → END
   ```

3. **Progress Tracking:**
   - Decorators applied to all node functions
   - Real-time reporting of node execution and state changes
   - Detailed progress information customized for each node type

4. **Error Handling:**
   - Built-in recursion limits with safe termination
   - State validation at each step to prevent inconsistencies
   - Graceful error recovery mechanisms

5. **Module Organization:**
   - `initialization.py`: Initial state setup and concept brainstorming
   - `outline.py`: Story outline, character generation, and chapter planning
   - `scenes.py`: Scene creation, reflection, and revision
   - `progression.py`: Character updates, continuity checks, and story advancement
   - `graph.py`: Graph definition, routing logic, and node connections
   - `models.py`: State schema definitions
   - `config.py`: Configuration settings and utilities
   - `creative_tools.py`: Brainstorming and creative element generation

---

## Final Notes

- **Fully Autonomous Operation:**  
  The agent operates completely independently without requiring any manual intervention during the story generation process.

- **Rich Progress Reporting:**
  Provides detailed information about the current state of generation, making it easy to track what the system is doing.

- **Robust Error Handling:**
  Includes safety mechanisms to prevent common issues like infinite recursion and to gracefully handle unexpected states.

- **Database Integration:**
  Uses SQLite database for memory operations, allowing the agent to maintain coherence across a complex narrative structure.

- **Modular, Extendable Design:**
  The modular implementation makes it easy to enhance or modify specific aspects of the story generation process.