"""
StoryCraft Agent - Configuration and setup.
"""

import os
from dotenv import load_dotenv

from langchain_anthropic import ChatAnthropic
from langgraph.store.memory import InMemoryStore
from langmem import create_manage_memory_tool, create_search_memory_tool, create_memory_manager, create_prompt_optimizer

# Load environment variables
load_dotenv()

# Initialize LLM
llm = ChatAnthropic(model="claude-3-7-sonnet-20250219", temperature=0.7)

# Initialize a single memory store instance for both LangMem tools and StateGraph checkpointing
store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": "openai:text-embedding-3-small",
    }
) 

# Define the memory namespace consistently
MEMORY_NAMESPACE = ("storyteller",)

# Create memory tools with explicit store parameter
manage_memory_tool = create_manage_memory_tool(namespace=MEMORY_NAMESPACE, store=store)
search_memory_tool = create_search_memory_tool(namespace=MEMORY_NAMESPACE, store=store)

# Create memory manager for background processing
memory_manager = create_memory_manager(
    "anthropic:claude-3-7-sonnet-20250219",
    instructions="Extract key narrative elements, character developments, plot points, and thematic elements from the story content.",
    enable_inserts=True
)

# Create prompt optimizer
prompt_optimizer = create_prompt_optimizer(
    "anthropic:claude-3-7-sonnet-20250219",
    kind="metaprompt",
    config={"max_reflection_steps": 3}
)