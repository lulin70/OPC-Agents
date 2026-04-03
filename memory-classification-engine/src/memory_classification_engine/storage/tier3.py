import os
import sqlite3
from typing import Dict, List, Optional, Any
from memory_classification_engine.storage.base import BaseStorage
from memory_classification_engine.utils.helpers import get_current_time
from memory_classification_engine.utils.logger import logger
from memory_classification_engine.utils.exceptions import (
    MemoryNotFoundError,
    DatabaseError
)

class Tier3Storage(BaseStorage):
    """Storage for episodic memory (tier 3)."""
    
    def __init__(self, storage_path: str = "./data/tier3"):
        """Initialize tier 3 storage.
        
        Args:
            storage_path: Path to store tier 3 memory database.
        """
        super().__init__(storage_path)
        
        # Database path
        self.db_path = os.path.join(self.storage_path, "episodic_memories.db")
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create episodic memories table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    context TEXT,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            # Create index on type and status
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_type_status ON episodic_memories (type, status)')
            
            # Create index on last_accessed
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_accessed ON episodic_memories (last_accessed)')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing database: {e}", exc_info=True)
    
    def store_memory(self, memory: Dict[str, Any]) -> bool:
        """Store a memory in tier 3.
        
        Args:
            memory: The memory to store.
            
        Returns:
            True if the memory was stored successfully, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Prepare memory using base class method
            memory = self._prepare_memory(memory)
            
            # Insert memory
            cursor.execute('''
                INSERT INTO episodic_memories 
                (id, type, content, created_at, updated_at, last_accessed, access_count, confidence, source, context, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                memory.get('id'),
                memory.get('type'),
                memory.get('content'),
                memory.get('created_at'),
                memory.get('updated_at'),
                memory.get('last_accessed'),
                memory.get('access_count'),
                memory.get('confidence'),
                memory.get('source'),
                memory.get('context'),
                memory.get('status')
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error storing memory: {e}", exc_info=True)
            return False
    
    def retrieve_memories(self, query: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve memories from tier 3.
        
        Args:
            query: Optional query string to filter memories.
            limit: Maximum number of memories to return.
            
        Returns:
            A list of matching memories.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if query:
                # Search for query in content
                cursor.execute('''
                    SELECT * FROM episodic_memories 
                    WHERE status = 'active' AND content LIKE ? 
                    ORDER BY last_accessed DESC 
                    LIMIT ?
                ''', (f'%{query}%', limit))
            else:
                # Get all active memories
                cursor.execute('''
                    SELECT * FROM episodic_memories 
                    WHERE status = 'active' 
                    ORDER BY last_accessed DESC 
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert rows to dictionaries
            memories = []
            for row in rows:
                memory = dict(row)
                # Ensure memory_type field is present
                memory = self._ensure_memory_type(memory)
                memories.append(memory)
            
            return memories
        except Exception as e:
            logger.error(f"Error retrieving memories: {e}", exc_info=True)
            return []
    
    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a memory in tier 3.
        
        Args:
            memory_id: The ID of the memory to update.
            updates: The updates to apply.
            
        Returns:
            True if the memory was updated successfully, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build update query
            set_clause = []
            params = []
            
            for key, value in updates.items():
                set_clause.append(f"{key} = ?")
                params.append(value)
            
            # Always update the updated_at timestamp
            set_clause.append("updated_at = ?")
            params.append(get_current_time())
            
            # Add memory_id to params
            params.append(memory_id)
            
            # Execute update
            cursor.execute(f'''
                UPDATE episodic_memories 
                SET {', '.join(set_clause)} 
                WHERE id = ?
            ''', params)
            
            conn.commit()
            conn.close()
            
            if cursor.rowcount == 0:
                raise MemoryNotFoundError(f"Memory with ID {memory_id} not found")
            return True
        except MemoryNotFoundError:
            raise
        except Exception as e:
            self._handle_error(e, "updating memory")
            return False
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory from tier 3.
        
        Args:
            memory_id: The ID of the memory to delete.
            
        Returns:
            True if the memory was deleted successfully, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Soft delete by setting status to 'deleted'
            cursor.execute('''
                UPDATE episodic_memories 
                SET status = 'deleted', updated_at = ? 
                WHERE id = ?
            ''', (get_current_time(), memory_id))
            
            conn.commit()
            conn.close()
            
            if cursor.rowcount == 0:
                raise MemoryNotFoundError(f"Memory with ID {memory_id} not found")
            return True
        except MemoryNotFoundError:
            raise
        except Exception as e:
            self._handle_error(e, "deleting memory")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tier 3 storage.
        
        Returns:
            A dictionary with statistics.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get total memories
            cursor.execute('SELECT COUNT(*) FROM episodic_memories')
            total = cursor.fetchone()[0]
            
            # Get active memories
            cursor.execute('SELECT COUNT(*) FROM episodic_memories WHERE status = ?', ('active',))
            active = cursor.fetchone()[0]
            
            # Get memory types
            cursor.execute('SELECT type, COUNT(*) FROM episodic_memories WHERE status = ? GROUP BY type', ('active',))
            types = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'total_memories': total,
                'active_memories': active,
                'memory_types': types
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}", exc_info=True)
            return {
                'total_memories': 0,
                'active_memories': 0,
                'memory_types': {}
            }
