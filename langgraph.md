# LangGraph - Agent Orchestration Framework

LangGraph is a low-level orchestration framework for building controllable, reliable, and extensible LLM agents. It enables developers to create complex agent workflows with customizable architectures, long-term memory, and human-in-the-loop capabilities.

## Installation

```bash
pip install -U langgraph
```

## Integration with Database

LangGraph integrates with SQLite database for persistent state and memory management:

- **Persistent State Storage**: LangGraph's state management integrates with SQLite for reliable data persistence
- **Memory Management**: Custom memory manager handles key-value storage for story elements
- **State Tracking**: Database tracks story configuration, chapters, scenes, characters, and world elements
- **Progress Monitoring**: Real-time progress updates stored and retrieved from database
- **Consistency Checking**: Database queries ensure narrative consistency across chapters

In storytelling applications:
- Character profiles are stored in dedicated tables and updated throughout generation
- Continuity is maintained by tracking plot threads and revelations in the database
- World elements are persisted for consistent reference across all scenes
- Author style guidance is stored for consistent application throughout generation
- Previous creative decisions are tracked to inform future content development

## Key Features

- **State Management**: Define structured state for your agents with custom reducers to control how state updates are merged
- **Graph-based Architecture**: Organize your agent logic into a graph with nodes and edges for flexible control flow
- **Persistence & Checkpointing**: Save and resume agent execution state for long-running workflows
- **Human-in-the-Loop**: Pause execution for human review and intervention at critical points
- **Time Travel**: Rewind agent execution to explore alternative paths and fix mistakes
- **First-class Streaming**: Stream both tokens and intermediate steps for real-time visibility
- **Multi-agent Support**: Build systems with multiple agents collaborating on complex tasks
- **Built-in Safety**: Automatic infinite loop prevention with configurable recursion limits

## Core Concepts

### StateGraph

The `StateGraph` is the foundation of LangGraph applications. It defines:

1. A **state schema** that specifies the structure of your application state
2. **Nodes** that represent functions or components that process the state
3. **Edges** that define the flow between nodes
4. **Conditional edges** that route execution based on state values

### Nodes and Edges

In LangGraph, the fundamental principle is: "Nodes do the work. Edges tell what to do next."

#### Nodes
- Process and transform state
- Return updates to the state
- Can be any Python function that takes and returns state

#### Edge Types
1. **Normal Edges**: Direct transitions from one node to another
   ```python
   graph_builder.add_edge("node_a", "node_b") 
   ```

2. **Conditional Edges**: Dynamic routing based on state
   ```python
   # Define a routing function that returns the next node name
   def route(state):
       if state["condition"]:
           return "node_b"
       else:
           return "node_c"
   
   # Add conditional edge
   graph_builder.add_conditional_edges("node_a", route, {"node_b": "node_b", "node_c": "node_c"})
   ```

3. **Entry Point Edges**: Define the starting node(s)
   ```python
   graph_builder.add_edge(START, "initial_node")
   ```

4. **Terminal Edges**: Define when the graph should stop
   ```python
   graph_builder.add_edge("final_node", END)
   ```

### Infinite Loop Prevention

LangGraph has built-in protection against infinite loops:

- Default recursion limit is 25 steps
- Can be configured at runtime
- When the limit is reached, LangGraph raises a `GraphRecursionError`

```python
# Set custom recursion limit
result = graph.invoke(inputs, config={"recursion_limit": 50})
```

## Best Practices from Refactoring Experience

### 1. Avoid Custom Routers

**Don't implement your own routing logic:**
- **Problem**: Custom routing logic creates a parallel state management system that competes with LangGraph's built-in mechanisms.
- **Solution**: Use LangGraph's native conditional edges with clear, focused condition functions.

```python
# ❌ BAD: Monolithic router function that checks everything
def route_next_step(state):
    if state.get("last_node") == "review_continuity" and state.get("phase") == "needs_resolution":
        return "resolve_continuity_issues"
    elif ...:
        # Many more conditions...

# ✅ GOOD: Separate, focused condition functions
def needs_continuity_resolution(state):
    return state.get("continuity_phase") == "needs_resolution"

graph_builder.add_conditional_edges(
    "review_continuity",
    needs_continuity_resolution,
    {
        True: "resolve_continuity_issues",
        False: "advance_to_next_scene_or_chapter"
    }
)
```

### 2. State Management Principles

- **Avoid parallel state tracking systems**: Don't create separate flags/variables outside LangGraph's state system.
- **Follow immutable state pattern**: Make copies of nested structures when updating them.
- **Return only changed values**: Node functions should only return keys that changed.
- **Keep conditional logic in edge functions**: Move flow control decisions to edge functions, not node functions.

```python
# ❌ BAD: Tracking internal state with custom flags
def review_continuity(state):
    review_flags = state.get("review_flags", {})
    review_flags[f"reviewed_chapter_{state['chapter']}"] = True
    return {"review_flags": review_flags, ...}

# ✅ GOOD: Let state content determine flow
def review_continuity(state):
    # Logic that analyzes content and updates appropriate state
    return {
        "continuity_phase": "needs_resolution" if issues_found else "complete",
        "revelations": updated_revelations
    }
```

### 3. Explicit Flow Control

- **Create clear, linear paths**: Design your graph with straightforward primary flows.
- **Name conditional branches clearly**: Use descriptive names for condition functions.
- **Avoid circular dependencies**: Ensure nodes don't create loops unless explicitly designed.
- **Set appropriate recursion limits**: For complex workflows, configure higher recursion limits.

```python
# Clear flow from one stage to the next
graph_builder.add_edge("reflect_on_scene", "revise_scene_if_needed")
graph_builder.add_edge("revise_scene_if_needed", "update_character_profiles")

# Explicit branching based on clear conditions
graph_builder.add_conditional_edges(
    "update_character_profiles",
    is_chapter_complete,
    {
        True: "review_continuity",
        False: "advance_to_next_scene_or_chapter"
    }
)
```

### 4. Debugging and Error Handling

- **Log state transitions**: Print key state values during transitions for debugging.
- **Add safety checks in condition functions**: Ensure required state values exist.
- **Create graceful fallbacks**: Add default return paths in condition functions.
- **Track flow with explicit phase variables**: Use dedicated state fields to track workflow phase.

```python
def is_chapter_complete(state):
    # Safety checks
    current_chapter = state.get("current_chapter", "")
    if not current_chapter or current_chapter not in state.get("chapters", {}):
        return False
    
    # Actual condition logic
    chapter = state["chapters"][current_chapter]
    for scene in chapter.get("scenes", {}).values():
        if not scene.get("content") or not scene.get("reflection_notes"):
            return False
    return True
```

### Example: Before and After Refactoring

#### Before (Custom Router):
```python
def route_next_step(state):
    router_count = state.get("router_count", 0) + 1
    state["router_count"] = router_count
    
    # Check many conditions to determine next node
    if should_review_continuity(state):
        return "review_continuity"
    elif should_resolve_continuity(state):
        return "resolve_continuity_issues"
    # Many more conditions...

# Add router to all nodes
for node in all_nodes:
    graph_builder.add_conditional_edges(node, route_next_step, {...})
```

#### After (Native Edges):
```python
# Specific condition for character profiles processing
graph_builder.add_conditional_edges(
    "update_character_profiles",
    is_chapter_complete,
    {
        True: "review_continuity",
        False: "advance_to_next_scene_or_chapter"
    }
)

# Specific condition for continuity review processing  
graph_builder.add_conditional_edges(
    "review_continuity",
    needs_continuity_resolution,
    {
        True: "resolve_continuity_issues",
        False: "advance_to_next_scene_or_chapter"
    }
)
```

## State Reducers

State reducers are a critical component of LangGraph that define how node outputs get merged into the graph state. When a node returns a partial state update, reducers control how those values are combined with the existing state.

### How State Reducers Work

By default, LangGraph uses simple overriding behavior - the new value completely replaces the old value for a given state key. However, you can define custom reducers using Python's `Annotated` type:

```python
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    # Use add operator to append lists
    messages: Annotated[list, add]
    # Default behavior: directly replace value
    current_step: int
```

### Common Reducer Patterns

1. **Message Append**: Use `add_messages` for chat history
   ```python
   from langgraph.graph.message import add_messages
   
   class State(TypedDict):
       messages: Annotated[list[Message], add_messages]
   ```

2. **Custom Reducer Logic**: Define any function that takes two values
   ```python
   def merge_dicts(left, right):
       result = left.copy()
       result.update(right)
       return result
       
   class State(TypedDict):
       metadata: Annotated[dict, merge_dicts]
   ```

### Partial State Updates

Nodes in LangGraph return partial state updates, not the full state. The state manager:

1. Extracts the current state
2. Applies node functions to get partial updates
3. Uses reducers to merge these updates into the full state

For example, this node only updates one key:
```python
def update_step(state: State) -> dict:
    # Only returning the step, not the full state
    return {"current_step": state["current_step"] + 1}
```

### Avoiding Common Pitfalls

1. **Missing State Keys**: When a node doesn't return a key, that part of the state remains unchanged
2. **Reducer Compatibility**: Ensure reducer functions are compatible with your data types
3. **Immutability**: Reducers should not modify inputs in-place, always return new objects
4. **Typing Consistency**: Maintain consistent types between annotated state and reducer returns

## Error Handling and Resilience

Building resilient LangGraph applications requires careful error handling and graceful recovery mechanisms. Here are key strategies to ensure your applications remain robust even when errors occur:

### 1. GraphRecursionError Handling

When LangGraph hits its recursion limit, it throws a `GraphRecursionError`. Implement proper handling:

```python
from langgraph.errors import GraphRecursionError

try:
    result = graph.invoke(initial_state, config={"recursion_limit": 100})
except GraphRecursionError as e:
    # Extract the final state from the error
    final_state = e.state
    
    # Log error details
    print(f"Recursion limit reached after {e.iterations} iterations")
    print(f"Last node executed: {e.last_node}")
    
    # Try to recover partial results
    partial_result = extract_partial_results(final_state)
```

### 2. Output Resilience

Always ensure your outputs are saved, even when errors occur:

```python
def save_with_fallback(content, primary_path, fallback_path="output_fallback.txt"):
    """Save content with a fallback mechanism if primary save fails."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(primary_path), exist_ok=True)
        
        # Save to primary location
        with open(primary_path, "w") as f:
            f.write(content)
        return True
    except IOError as e:
        print(f"Error saving to {primary_path}: {str(e)}")
        try:
            # Try fallback location
            with open(fallback_path, "w") as f:
                f.write(content)
            return True
        except IOError:
            print("Critical error: Could not save to fallback location")
            return False
```

### 3. Partial Results Recovery

Implement functions to extract meaningful partial results when the full workflow doesn't complete:

```python
def extract_partial_results(state):
    """Extract whatever useful results are available in the state."""
    results = {}
    
    # Extract key components that might be valuable
    if "completed_items" in state:
        results["completed"] = state["completed_items"]
    
    if "intermediate_outputs" in state:
        results["partial_outputs"] = state["intermediate_outputs"]
        
    # Format a partial result
    return format_partial_result(results)
```

### 4. Checkpoint System

Implement periodic checkpoints to save state during long-running processes:

```python
def process_with_checkpoints(graph, initial_state, checkpoint_dir="./checkpoints"):
    """Run graph with periodic state checkpointing."""
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    # Configure checkpoint callback
    def checkpoint_callback(state, node_name):
        checkpoint_path = f"{checkpoint_dir}/checkpoint_{node_name}.json"
        with open(checkpoint_path, "w") as f:
            json.dump(state, f, indent=2)
    
    # Run with checkpoint callback
    try:
        result = graph.invoke(initial_state, 
                             config={
                                 "recursion_limit": 100,
                                 "callbacks": [checkpoint_callback]
                             })
        return result
    except Exception as e:
        # Recover from latest checkpoint
        return recover_from_checkpoint(checkpoint_dir)
```

### 5. Node-Level Error Handling

Wrap critical node functions with error handling to prevent graph failure:

```python
def safe_node_function(func):
    """Decorator to make node functions resilient to errors."""
    def wrapper(state):
        try:
            return func(state)
        except Exception as e:
            # Log the error
            print(f"Error in node {func.__name__}: {str(e)}")
            
            # Return a safe state update that won't break the graph
            return {
                "errors": state.get("errors", []) + [f"{func.__name__}: {str(e)}"],
                "error_location": func.__name__
            }
    return wrapper

@safe_node_function
def process_data(state):
    # Processing that might fail
    return {"processed_data": process(state["raw_data"])}
```

## Advanced Patterns

### Multi-Agent Systems

LangGraph supports complex multi-agent systems where different agents collaborate:

```python
# Create multiple agent graphs
agent1 = create_agent_graph(...)
agent2 = create_agent_graph(...)

# Create supervisor graph to coordinate
supervisor = create_supervisor_graph([agent1, agent2])
```

### RAG Applications

Build sophisticated retrieval-augmented generation workflows:

```python
# RAG node
def retrieve(state):
    query = state["messages"][-1].content
    results = retriever.get_relevant_documents(query)
    return {"context": results}

# Add to graph
graph_builder.add_node("retrieve", retrieve)
graph_builder.add_edge(START, "retrieve")
graph_builder.add_edge("retrieve", "chatbot")
```

## Deployment Options

1. **LangGraph Platform**: Managed deployment with LangGraph Cloud
2. **Self-hosted**: Deploy as a web service with FastAPI
3. **Serverless**: Deploy as cloud functions

## Resources

- [Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Academy Course](https://academy.langchain.com/courses/intro-to-langgraph)
- [GitHub Repository](https://github.com/langchain-ai/langgraph)
- [JavaScript Version](https://github.com/langchain-ai/langgraphjs)