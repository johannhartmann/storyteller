# StoryCraft - AI Story Generation Agent

This system uses Claude and LangGraph to generate multi-chapter stories with configurable genre, tone, and author style.

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with `ANTHROPIC_API_KEY=your_api_key`

## Usage

### Basic Command

```bash
python run_storyteller.py --genre fantasy --tone epic
```

### With Author Style

```bash
python run_storyteller.py --genre mystery --tone dark --author "Edgar Allan Poe"
```

### All Options

```bash
python run_storyteller.py --genre [GENRE] --tone [TONE] --author [AUTHOR] --output [FILENAME.md]
```

## Simplified Version

For more reliable performance, use the simplified storyteller:

```bash
python run_simple_storyteller.py --genre mystery --tone dark --author "Edgar Allan Poe"
```

## Architecture Overview

StoryCraft uses LangGraph for orchestration and LangMem for memory management:

1. **State Management**: Defines a structured state schema (StoryState) that tracks:
   - Messages
   - Story details (genre, tone, author)
   - Chapters and content
   - Story progression

2. **Graph Nodes**: Functions that process the state:
   - `initialize_state`: Sets up initial parameters
   - `create_story_outline`: Generates title and plot summary
   - `plan_chapters`: Divides the story into chapters
   - `write_current_chapter`: Writes content for each chapter
   - `compile_story`: Assembles final story
   - `router`: Directs flow between nodes

3. **Router Logic**: Determines next step based on current state

4. **Memory Management** (full version only):
   - Stores story elements, character details
   - Tracks revelations and maintains continuity
   - Uses semantic search to retrieve relevant memories

## Common Issues and Solutions

1. **Graph Building Errors**:
   - Ensure router node is added to the graph
   - Router must return a dictionary with routing info
   - Update conditional edges to use correct routing function

2. **Memory Storage Issues**:
   - Pass store parameter explicitly to memory tools
   - Use correct action commands ("create" instead of "upsert")

3. **State Management**:
   - Be consistent with state updates
   - When using custom reducers, ensure correct types
   - **IMPORTANT: Always use LangGraph's immutable state update pattern:**
     - Return a dict with ONLY the keys that changed (not the entire state)
     - Never modify the input state directly
     - For nested structures (lists/dicts), create a new copy of the entire structure
     - Example: To update `state["revelations"]["continuity_issues"]`, first copy `state["revelations"]`, 
       then create a new list for `continuity_issues`, and assign it to the copied revelations dict

## Debug Commands

Test basic LangGraph functionality:

```bash
python test_graph.py
```

## LangGraph Key Concepts

- **StateGraph**: Foundation of LangGraph applications
- **Nodes**: Functions that process state
- **Edges**: Define flow between nodes
- **Conditional Edges**: Route based on state values
- **Checkpointing**: Save/resume execution state
- **Tools Integration**: Use external tools via LangChain

## LangMem Key Concepts

- **Memory Types**: Semantic, episodic, procedural
- **Memory Formation**: Hot path and background processing
- **Storage**: Namespace-based organization
- **Prompt Optimization**: Refine system prompts

## LangChain Structured Output Processing

LangChain provides several approaches for handling structured outputs from language models:

### 1. `.with_structured_output()` Method (Recommended)

The most reliable and modern way to get structured outputs from LLMs:

```python
from langchain_core.pydantic_v1 import BaseModel, Field

class Character(BaseModel):
    name: str = Field(description="The character's full name")
    role: str = Field(description="The character's role in the story")
    backstory: str = Field(description="The character's detailed history")
    
# Apply to a chain or directly to a model
structured_llm = llm.with_structured_output(Character)
result = structured_llm.invoke("Create a character for a fantasy story")
```

Benefits:
- Automatic schema validation
- Clear error handling
- Supports streaming
- Works with Pydantic, TypedDict, or JSON Schema

### 2. Using JSON Output Parser

For cases where more customization is needed:

```python
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

# Create the parser
parser = JsonOutputParser(pydantic_object=Character)

# Create a prompt with format instructions
prompt = PromptTemplate(
    template="Generate a character for a {genre} story.\n{format_instructions}",
    input_variables=["genre"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# Create the chain
chain = prompt | llm | parser

# Run the chain
result = chain.invoke({"genre": "fantasy"})
```

### Best Practices for Storyteller App

1. **Define Clear Schemas**:
   - Use Pydantic models for character profiles, chapters, and other structured data
   - Include field descriptions to guide the LLM

2. **Error Handling**:
   - Always provide fallback options if parsing fails
   - Log parsing errors for debugging

3. **LLM Instructions**:
   - Include format instructions from the parser
   - Be explicit about expected output structure