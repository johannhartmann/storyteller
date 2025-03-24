"""
StoryCraft Agent - Memory Adapter.

This module provides an adapter between LangMem's memory tools and LangGraph's SqliteSaver.
"""

import gc
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.runnables import RunnableConfig


class MemoryStoreAdapter:
    """
    Adapter class that wraps SqliteSaver to provide the interface expected by LangMem tools.
    
    LangMem tools expect a store with methods like put(key, value) and get(key),
    while SqliteSaver uses a different API with methods like put(config, checkpoint, metadata, new_versions).
    This adapter bridges the gap between these two interfaces.
    """
    
    def __init__(self, store: SqliteSaver, namespace: Tuple[str, ...] = ("default",)):
        """
        Initialize the adapter with a SqliteSaver instance.
        
        Args:
            store: The SqliteSaver instance to wrap
            namespace: The default namespace to use for memory operations
        """
        self.store = store
        self.namespace = namespace
        self.thread_id = "memory"  # Default thread ID for memory operations
    
    def _get_config(self, namespace: Optional[Tuple[str, ...]] = None) -> RunnableConfig:
        """
        Create a config object for the SqliteSaver.
        
        Args:
            namespace: Optional namespace to use instead of the default
            
        Returns:
            A RunnableConfig object
        """
        ns = namespace or self.namespace
        ns_str = ".".join(ns)
        return {
            "configurable": {
                "thread_id": self.thread_id,
                "checkpoint_ns": ns_str,
            }
        }
    
    def _create_checkpoint(self, key: str, value: Any) -> Dict[str, Any]:
        """
        Create a checkpoint object for the SqliteSaver.
        
        Args:
            key: The key for the memory item
            value: The value to store
            
        Returns:
            A checkpoint object
        """
        return {
            "id": str(uuid.uuid4()),
            "ts": "2023-01-01T00:00:00Z",  # Placeholder timestamp
            "data": {
                "key": key,
                "value": value
            }
        }
    
    def put(self, *args, **kwargs) -> None:
        """
        Store a value in memory.
        
        This method is flexible to handle different calling patterns:
        - put(key, value, namespace=None)
        - put(key=key, value=value, namespace=None)
        
        Args:
            key: The key to store the value under
            value: The value to store
            namespace: Optional namespace to use instead of the default
        """
        # Extract arguments based on how they're passed
        key = None
        value = None
        namespace = None
        
        # Handle positional arguments
        if args:
            if len(args) >= 1:
                key = args[0]
            if len(args) >= 2:
                value = args[1]
            if len(args) >= 3:
                namespace = args[2]
        
        # Override with keyword arguments if provided
        if 'key' in kwargs:
            key = kwargs['key']
        if 'value' in kwargs:
            value = kwargs['value']
        if 'namespace' in kwargs:
            namespace = kwargs['namespace']
        
        if key is None:
            raise ValueError("Key must be provided")
        if value is None:
            raise ValueError("Value must be provided")
        
        try:
            config = self._get_config(namespace)
            checkpoint = self._create_checkpoint(key, value)
            metadata = {"source": "memory_adapter", "key": key}
            new_versions = {}
            
            self.store.put(config, checkpoint, metadata, new_versions)
        finally:
            # Clear references to large objects
            checkpoint = None
            metadata = None
            new_versions = None
            gc.collect()  # Force garbage collection after put operation
    
    def get(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Retrieve a value from memory.
        
        This method is flexible to handle different calling patterns:
        - get(key, namespace=None)
        - get(key=key, namespace=None)
        
        This implementation uses batching to reduce memory usage when searching
        through many checkpoints.
        
        Args:
            key: The key to retrieve
            namespace: Optional namespace to use instead of the default
            
        Returns:
            The stored value, or None if not found
        """
        # Extract arguments based on how they're passed
        key = None
        namespace = None
        
        # Handle positional arguments
        if args:
            if len(args) >= 1:
                key = args[0]
            if len(args) >= 2:
                namespace = args[1]
        
        # Override with keyword arguments if provided
        if 'key' in kwargs:
            key = kwargs['key']
        if 'namespace' in kwargs:
            namespace = kwargs['namespace']
        
        if key is None:
            raise ValueError("Key must be provided")
            
        config = self._get_config(namespace)
        
        # Process checkpoints in batches to reduce memory usage
        batch_size = 5  # Reduced from 10 to lower memory footprint
        current_batch = 0
        
        try:
            while True:
                # Get a batch of checkpoints - SqliteSaver doesn't support offset parameter
                batch_config = config.copy()
                
                # Use limit parameter only (no offset)
                batch = list(self.store.list(batch_config, limit=batch_size))
                
                # If no more checkpoints, we're done
                if not batch:
                    break
                
                # Skip checkpoints we've already processed
                start_idx = current_batch * batch_size
                if start_idx >= len(batch):
                    break
                    
                # Search for the key in this batch
                for checkpoint_tuple in batch:
                    checkpoint = checkpoint_tuple[1]  # The actual checkpoint data
                    if "data" in checkpoint and checkpoint["data"].get("key") == key:
                        result = {
                            "key": key,
                            "value": checkpoint["data"].get("value"),
                            "metadata": checkpoint_tuple[2]  # The metadata
                        }
                        # Clear references before collection
                        checkpoint_tuple = None
                        checkpoint = None
                        batch = None
                        gc.collect()  # Force garbage collection
                        return result
                
                # Move to the next batch
                current_batch += 1
                
                # Clear batch reference before collection
                batch = None
                gc.collect()  # Force garbage collection after processing each batch
        finally:
            # Ensure cleanup happens even if exceptions occur
            batch = None
            gc.collect()
        
        return None
    
    def delete(self, *args, **kwargs) -> None:
        """
        Delete a value from memory.
        
        This method is flexible to handle different calling patterns:
        - delete(key, namespace=None)
        - delete(key=key, namespace=None)
        
        Note: SqliteSaver doesn't support direct deletion, so we overwrite with None.
        
        Args:
            key: The key to delete
            namespace: Optional namespace to use instead of the default
        """
        # Extract arguments based on how they're passed
        key = None
        namespace = None
        
        # Handle positional arguments
        if args:
            if len(args) >= 1:
                key = args[0]
            if len(args) >= 2:
                namespace = args[1]
        
        # Override with keyword arguments if provided
        if 'key' in kwargs:
            key = kwargs['key']
        if 'namespace' in kwargs:
            namespace = kwargs['namespace']
        
        if key is None:
            raise ValueError("Key must be provided")
            
        self.put(key=key, value=None, namespace=namespace)
    
    def list(self, namespace: Optional[Tuple[str, ...]] = None) -> List[str]:
        """
        List all keys in a namespace.
        
        This method uses batching to reduce memory usage when listing many keys.
        
        Args:
            namespace: Optional namespace to use instead of the default
            
        Returns:
            A list of keys
        """
        config = self._get_config(namespace)
        keys = []
        
        # Process checkpoints in batches to reduce memory usage
        batch_size = 5  # Reduced from 10 to lower memory footprint
        current_batch = 0
        
        try:
            while True:
                # Get a batch of checkpoints - SqliteSaver doesn't support offset parameter
                # Instead, we'll use a different approach to paginate through results
                batch_config = config.copy()
                
                # Use limit parameter only (no offset)
                batch = list(self.store.list(batch_config, limit=batch_size))
                
                # If no more checkpoints, we're done
                if not batch:
                    break
                
                # Skip checkpoints we've already processed
                start_idx = current_batch * batch_size
                if start_idx >= len(batch):
                    break
                
                # Process this batch
                for checkpoint_tuple in batch:
                    checkpoint = checkpoint_tuple[1]  # The actual checkpoint data
                    if "data" in checkpoint and "key" in checkpoint["data"]:
                        keys.append(checkpoint["data"]["key"])
                    
                    # Clear individual checkpoint references
                    checkpoint_tuple = None
                    checkpoint = None
                
                # Move to the next batch
                current_batch += 1
                
                # Clear batch reference before collection
                batch = None
                gc.collect()  # Force garbage collection after processing each batch
        finally:
            # Ensure cleanup happens even if exceptions occur
            batch = None
            gc.collect()
        
        return keys
        
    def search(self, namespace: Optional[Tuple[str, ...]] = None, query: str = "", filter: Optional[Dict] = None, limit: int = 10, offset: int = 0) -> List[Any]:
        """
        Search for values in memory based on a query.
        
        This implementation returns all values where the key contains the query string
        or where the value contains the query string.
        
        Args:
            namespace: Optional namespace to use instead of the default
            query: The query string to search for
            filter: Optional filter criteria (not used in this implementation)
            limit: Maximum number of results to return
            offset: Number of results to skip
            
        Returns:
            A list of matching items
        """
        config = self._get_config(namespace)
        results = []
        
        # Process checkpoints in batches to reduce memory usage
        batch_size = 5  # Reduced from 10 to lower memory footprint
        current_batch = 0
        
        try:
            while True and len(results) < limit + offset:
                # Get a batch of checkpoints - SqliteSaver doesn't support offset parameter
                batch_config = config.copy()
                
                # Use limit parameter only (no offset)
                batch = list(self.store.list(batch_config, limit=batch_size))
                
                # If no more checkpoints, we're done
                if not batch:
                    break
                
                # Skip checkpoints we've already processed
                start_idx = current_batch * batch_size
                if start_idx >= len(batch):
                    break
                
                # Process this batch
                for checkpoint_tuple in batch:
                    checkpoint = checkpoint_tuple[1]  # The actual checkpoint data
                    if "data" in checkpoint and "key" in checkpoint["data"]:
                        key = checkpoint["data"]["key"]
                        value = checkpoint["data"].get("value")
                        
                        # Check if query is in key or value
                        key_match = query.lower() in key.lower() if key else False
                        value_match = False
                        
                        # Check if query is in value (if value is a string or has a string representation)
                        if value is not None:
                            if isinstance(value, str):
                                value_match = query.lower() in value.lower()
                            elif isinstance(value, dict) and "content" in value and isinstance(value["content"], str):
                                value_match = query.lower() in value["content"].lower()
                            elif hasattr(value, "__str__"):
                                value_match = query.lower() in str(value).lower()
                        
                        # If query is empty or there's a match, add to results
                        if query == "" or key_match or value_match:
                            # Create an item that mimics the expected format
                            item = type('Item', (), {
                                'namespace': namespace or self.namespace,
                                'key': key,
                                'value': value,
                                'dict': lambda self=None, key=key, value=value, namespace=namespace or self.namespace:
                                    {'namespace': namespace or self.namespace, 'key': key, 'value': value}
                            })
                            results.append(item)
                    
                    # Clear individual checkpoint references
                    checkpoint_tuple = None
                    checkpoint = None
                
                # Move to the next batch
                current_batch += 1
                
                # Clear batch reference before collection
                batch = None
                gc.collect()  # Force garbage collection after processing each batch
        finally:
            # Ensure cleanup happens even if exceptions occur
            batch = None
            gc.collect()
        
        # Apply offset and limit
        return results[offset:offset + limit]