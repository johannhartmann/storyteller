# LangGraph - Agent Orchestration Framework

LangGraph is a low-level orchestration framework for building controllable, reliable, and extensible LLM agents. It enables developers to create complex agent workflows with customizable architectures, long-term memory, and human-in-the-loop capabilities.

## Installation

```bash
pip install -U langgraph
```

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

### Example: Basic Chatbot

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_anthropic import ChatAnthropic

# Define state schema
class State(TypedDict):
    messages: Annotated[list, add_messages]

# Create graph with state schema
graph_builder = StateGraph(State)

# Define LLM node
llm = ChatAnthropic(model="claude-3-5-sonnet-20240620")

def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

# Add node to graph
graph_builder.add_node("chatbot", chatbot)

# Define edges
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)

# Compile graph
graph = graph_builder.compile()

# Use the graph
response = graph.invoke({
    "messages": [{"role": "user", "content": "Hello, world!"}]
})
```

### Adding Tools

LangGraph integrates with LangChain's tool system to enable agents to use external functions:

```python
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import ToolNode, tools_condition

# Define tool
search_tool = TavilySearchResults(max_results=2)
tools = [search_tool]

# Bind tools to LLM
llm_with_tools = llm.bind_tools(tools)

def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

# Add tool node
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

# Add conditional edge based on tool calls
graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)

# Connect tool back to chatbot
graph_builder.add_edge("tools", "chatbot")
```

### Persistence with Checkpointing

LangGraph supports persistence through checkpointers:

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)

# Thread-based state management
config = {"configurable": {"thread_id": "thread-123"}}
graph.invoke({"messages": [{"role": "user", "content": "Hello"}]}, config)
```

### Human-in-the-Loop

Interrupt graph execution for human review:

```python
from langgraph.types import Command, interrupt
from langchain_core.tools import tool

@tool
def human_assistance(query: str) -> str:
    """Request assistance from a human."""
    human_response = interrupt({"query": query})
    return human_response["data"]

# Resume execution with command
human_command = Command(resume={"data": "Human response here"})
graph.invoke(human_command, config)
```

### Time Travel

Rewind graph execution to explore alternative paths:

```python
# Get state history
for state in graph.get_state_history(config):
    print(f"State ID: {state.config['configurable']['checkpoint_id']}")

# Resume from specific checkpoint
checkpoint_id = "1efd43e3-0c1f-6c4e-8006-891877d65740"
checkpoint_config = {"configurable": {
    "thread_id": "thread-123", 
    "checkpoint_id": checkpoint_id
}}
graph.invoke(None, checkpoint_config)
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