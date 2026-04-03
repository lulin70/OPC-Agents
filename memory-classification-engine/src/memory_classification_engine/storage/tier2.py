import os
import json
from typing import Dict, List, Optional, Any
from memory_classification_engine.storage.base import BaseStorage
from memory_classification_engine.utils.helpers import format_memory
from memory_classification_engine.utils.logger import logger
from memory_classification_engine.utils.encryption import encryption_manager

class Tier2Storage(BaseStorage):
    """Storage for procedural memory (tier 2)."""
    
    def __init__(self, storage_path: str = "./data/tier2"):
        """Initialize tier 2 storage.
        
        Args:
            storage_path: Path to store tier 2 memory files.
        """
        super().__init__(storage_path)
        
        # File paths
        self.preferences_file = os.path.join(self.storage_path, "user_preferences.json")
        self.corrections_file = os.path.join(self.storage_path, "corrections.json")
        
        # Load existing data
        self.preferences = self._load_file(self.preferences_file)
        self.corrections = self._load_file(self.corrections_file)
    
    def _load_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Load data from file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            The loaded data as a list of dictionaries.
        """
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}", exc_info=True)
        return []
    
    def _save_file(self, file_path: str, data: List[Dict[str, Any]]):
        """Save data to file.
        
        Args:
            file_path: Path to the file.
            data: The data to save.
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving file {file_path}: {e}", exc_info=True)
    
    def store_memory(self, memory: Dict[str, Any]) -> bool:
        """Store a memory in tier 2.
        
        Args:
            memory: The memory to store.
            
        Returns:
            True if the memory was stored successfully, False otherwise.
        """
        try:
            memory_type = memory.get('type')
            
            # Prepare memory using base class method
            memory = self._prepare_memory(memory)
            
            # Store based on memory type
            if memory_type == 'user_preference':
                # Encrypt memory content
                if 'content' in memory:
                    memory['content'] = encryption_manager.encrypt(memory['content'])
                self.preferences.append(memory)
                self._save_file(self.preferences_file, self.preferences)
            elif memory_type == 'correction':
                # Encrypt memory content
                if 'content' in memory:
                    memory['content'] = encryption_manager.encrypt(memory['content'])
                self.corrections.append(memory)
                self._save_file(self.corrections_file, self.corrections)
            else:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error storing memory: {e}", exc_info=True)
            return False
    
    def retrieve_memories(self, query: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve memories from tier 2.
        
        Args:
            query: Optional query string to filter memories.
            limit: Maximum number of memories to return.
            
        Returns:
            A list of matching memories.
        """
        all_memories = []
        all_memories.extend(self.preferences)
        all_memories.extend(self.corrections)
        
        # Filter by query if provided
        if query:
            filtered_memories = []
            for memory in all_memories:
                # Decrypt content before filtering
                content = memory.get('content', '')
                try:
                    if content.startswith('gAAAAA'):
                        content = encryption_manager.decrypt(content)
                except Exception as e:
                    logger.error(f"Error decrypting memory: {e}", exc_info=True)
                
                if query.lower() in content.lower():
                    # Store decrypted content in the memory object for return
                    memory['content'] = content
                    filtered_memories.append(memory)
            all_memories = filtered_memories
        else:
            # Decrypt all memories when no query is provided
            for memory in all_memories:
                content = memory.get('content', '')
                try:
                    if content.startswith('gAAAAA'):
                        memory['content'] = encryption_manager.decrypt(content)
                except Exception as e:
                    logger.error(f"Error decrypting memory: {e}", exc_info=True)
        
        # Ensure memory_type field is present
        for memory in all_memories:
            memory = self._ensure_memory_type(memory)
        
        # Sort by last accessed time (most recent first)
        all_memories.sort(key=lambda x: x.get('last_accessed', ''), reverse=True)
        
        # Limit the result
        return all_memories[:limit]
    
    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a memory in tier 2.
        
        Args:
            memory_id: The ID of the memory to update.
            updates: The updates to apply.
            
        Returns:
            True if the memory was updated successfully, False otherwise.
        """
        try:
            # Check preferences
            for i, memory in enumerate(self.preferences):
                if memory.get('id') == memory_id:
                    # Encrypt content if it's being updated
                    if 'content' in updates:
                        updates['content'] = encryption_manager.encrypt(updates['content'])
                    memory.update(updates)
                    memory['updated_at'] = get_current_time()
                    self._save_file(self.preferences_file, self.preferences)
                    return True
            
            # Check corrections
            for i, memory in enumerate(self.corrections):
                if memory.get('id') == memory_id:
                    # Encrypt content if it's being updated
                    if 'content' in updates:
                        updates['content'] = encryption_manager.encrypt(updates['content'])
                    memory.update(updates)
                    memory['updated_at'] = get_current_time()
                    self._save_file(self.corrections_file, self.corrections)
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error updating memory: {e}", exc_info=True)
            return False
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory from tier 2.
        
        Args:
            memory_id: The ID of the memory to delete.
            
        Returns:
            True if the memory was deleted successfully, False otherwise.
        """
        try:
            # Check preferences
            for i, memory in enumerate(self.preferences):
                if memory.get('id') == memory_id:
                    del self.preferences[i]
                    self._save_file(self.preferences_file, self.preferences)
                    return True
            
            # Check corrections
            for i, memory in enumerate(self.corrections):
                if memory.get('id') == memory_id:
                    del self.corrections[i]
                    self._save_file(self.corrections_file, self.corrections)
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error deleting memory: {e}", exc_info=True)
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tier 2 storage.
        
        Returns:
            A dictionary with statistics.
        """
        return {
            'total_preferences': len(self.preferences),
            'total_corrections': len(self.corrections),
            'total_memories': len(self.preferences) + len(self.corrections)
        }
