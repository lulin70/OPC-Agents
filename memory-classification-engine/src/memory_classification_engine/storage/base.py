"""Base storage class for memory classification engine."""

import os
import sqlite3
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from memory_classification_engine.utils.helpers import get_current_time
from memory_classification_engine.utils.logger import logger
from memory_classification_engine.utils.exceptions import (
    StorageError,
    MemoryNotFoundError,
    MemoryAlreadyExistsError,
    DatabaseError
)


class BaseStorage(ABC):
    """Abstract base class for all storage implementations."""

    def __init__(self, storage_path: str):
        """Initialize storage.

        Args:
            storage_path: Path to store memory data.
        """
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)

    @abstractmethod
    def store_memory(self, memory: Dict[str, Any]) -> bool:
        """Store a memory.

        Args:
            memory: The memory to store.

        Returns:
            True if the memory was stored successfully, False otherwise.
        """
        pass

    @abstractmethod
    def retrieve_memories(self, query: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve memories.

        Args:
            query: Optional query string to filter memories.
            limit: Maximum number of memories to return.

        Returns:
            A list of matching memories.
        """
        pass

    @abstractmethod
    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a memory.

        Args:
            memory_id: The ID of the memory to update.
            updates: The updates to apply.

        Returns:
            True if the memory was updated successfully, False otherwise.
        """
        pass

    @abstractmethod
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory.

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            True if the memory was deleted successfully, False otherwise.
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the storage.

        Returns:
            A dictionary with statistics.
        """
        pass

    def _prepare_memory(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare memory for storage.

        Adds timestamps and other required fields if not present.

        Args:
            memory: The memory to prepare.

        Returns:
            The prepared memory.
        """
        current_time = get_current_time()

        # Add timestamps if not present
        if 'created_at' not in memory:
            memory['created_at'] = current_time
        memory['updated_at'] = current_time
        memory['last_accessed'] = current_time

        # Add other required fields
        memory['access_count'] = memory.get('access_count', 1)
        memory['status'] = memory.get('status', 'active')

        # Ensure type fields are consistent
        if 'type' in memory and 'memory_type' not in memory:
            memory['memory_type'] = memory['type']
        elif 'memory_type' in memory and 'type' not in memory:
            memory['type'] = memory['memory_type']

        return memory

    def _handle_error(self, error: Exception, operation: str) -> None:
        """Handle storage operation errors.

        Args:
            error: The exception that occurred.
            operation: The operation that failed.

        Raises:
            StorageError: For general storage errors.
            DatabaseError: For database-specific errors.
        """
        logger.error(f"Error {operation}: {error}", exc_info=True)
        
        # Convert to appropriate exception
        if isinstance(error, sqlite3.Error):
            raise DatabaseError(f"Database error during {operation}: {error}") from error
        elif operation == "storing" and "UNIQUE" in str(error):
            raise MemoryAlreadyExistsError(f"Memory already exists: {error}") from error
        else:
            raise StorageError(f"Error {operation}: {error}") from error

    def _ensure_memory_type(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure memory has both type and memory_type fields.

        Args:
            memory: The memory to process.

        Returns:
            The memory with consistent type fields.
        """
        if 'type' in memory and 'memory_type' not in memory:
            memory['memory_type'] = memory['type']
        elif 'memory_type' in memory and 'type' not in memory:
            memory['type'] = memory['memory_type']
        return memory
