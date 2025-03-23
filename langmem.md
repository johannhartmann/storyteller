# LangMem - Memory System for LLM Applications

LangMem helps agents learn and adapt from interactions over time. It provides tools to extract information from conversations, optimize agent behavior, and maintain long-term memory.

## Installation

```bash
pip install -U langmem
```

Configure your environment:
```bash
export ANTHROPIC_API_KEY="sk-..."  # Or another supported LLM provider
```

## Key Features

- **Memory Types**: Support for semantic (facts), episodic (past experiences), and procedural (system behavior) memory
- **Memory Formation**: Both "hot path" (during conversation) and background (between interactions) memory processing
- **Memory Storage**: Flexible namespace-based organization with LangGraph integration
- **Prompt Optimization**: Tools to refine system prompts based on feedback and experience

## Using LangMem with Claude Code

### 1. Creating an Agent with Memory

```python
from langgraph.prebuilt import create_react_agent
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langmem import create_manage_memory_tool, create_search_memory_tool

# Set up storage with sqlite for persistence
db_path = "/path/to/your/memory.db"
memory_conn = sqlite3.connect(db_path, check_same_thread=False)
store = SqliteSaver(memory_conn)

# Create agent with memory capabilities
agent = create_react_agent(
    "anthropic:claude-3-5-sonnet-latest",
    tools=[
        create_manage_memory_tool(namespace=("memories",)),
        create_search_memory_tool(namespace=("memories",)),
    ],
    store=store,
)
```

### 2. Using Memory Tools

```python
# Store a new memory
agent.invoke(
    {"messages": [{"role": "user", "content": "Remember that I prefer dark mode."}]}
)

# Retrieve the stored memory
response = agent.invoke(
    {"messages": [{"role": "user", "content": "What are my lighting preferences?"}]}
)
print(response["messages"][-1].content)
```

### 3. Advanced Memory Management

#### Creating a Memory Manager (Background Processing)

```python
from langmem import create_memory_manager

# Create memory manager
manager = create_memory_manager(
    "anthropic:claude-3-5-sonnet-latest",
    instructions="Extract all noteworthy facts, events, and relationships.",
    enable_inserts=True,
)

# Process a conversation to extract memories
conversation = [
    {"role": "user", "content": "I work at Acme Corp in the ML team"},
    {"role": "assistant", "content": "I'll remember that. What kind of ML work do you do?"},
    {"role": "user", "content": "Mostly NLP and large language models"}
]

memories = manager.invoke({"messages": conversation})
```

#### Optimizing Prompts

```python
from langmem import create_prompt_optimizer

optimizer = create_prompt_optimizer(
    "anthropic:claude-3-5-sonnet-latest",
    kind="metaprompt",
    config={"max_reflection_steps": 3}
)

prompt = "You are a helpful assistant."
trajectory = [
    {"role": "user", "content": "Explain inheritance in Python"},
    {"role": "assistant", "content": "Here's a detailed theoretical explanation..."},
    {"role": "user", "content": "Show me a practical example instead"},
]

optimized = optimizer.invoke({
    "trajectories": [(trajectory, {"user_score": 0})], 
    "prompt": prompt
})
```

## Integration Patterns

LangMem offers two integration approaches:

1. **Core API**: Functional primitives that transform memory state without side effects
   - Memory Managers
   - Prompt Optimizers

2. **Stateful Integration**: Components that integrate with LangGraph's memory store
   - Store Managers
   - Memory Management Tools

## Best Practices

- Choose between profiles (structured data) and collections (flexible data) based on your needs
- Consider using background memory formation for complex processing to avoid response latency
- Use namespaces to organize memories by user, organization, or other hierarchical structures
- Combine semantic search with metadata filtering for precise memory retrieval

## Resources

- [Hot Path Quickstart](https://langchain-ai.github.io/langmem/hot_path_quickstart)
- [Background Quickstart](https://langchain-ai.github.io/langmem/background_quickstart)
- [Core Concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide)
- [API Reference](https://langchain-ai.github.io/langmem/reference)