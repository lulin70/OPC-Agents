import os
import sqlite3
from typing import Dict, List, Optional, Any
from memory_classification_engine.storage.base import BaseStorage
from memory_classification_engine.utils.helpers import get_current_time
from memory_classification_engine.utils.logger import logger
from memory_classification_engine.utils.cache import MemoryCache
from memory_classification_engine.utils.exceptions import (
    MemoryNotFoundError,
    FTS5Error
)

class Tier3StorageFTS(BaseStorage):
    """Storage for episodic memory (tier 3) with FTS5 full-text search support."""

    def __init__(self, storage_path: str = "./data/tier3", enable_cache: bool = True, cache_size: int = 1000):
        """Initialize tier 3 storage with FTS support.

        Args:
            storage_path: Path to store tier 3 memory database.
            enable_cache: Whether to enable memory caching.
            cache_size: Maximum number of items in cache.
        """
        super().__init__(storage_path)

        # Database path
        self.db_path = os.path.join(self.storage_path, "episodic_memories.db")

        # Initialize cache
        self._cache_enabled = enable_cache
        if enable_cache:
            self._cache = MemoryCache(max_size=cache_size)
            logger.info(f"Memory cache enabled with size={cache_size}")
        else:
            self._cache = None

        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize the database with FTS5 support."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if FTS5 is available
            cursor.execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')")
            fts5_available = cursor.fetchone()[0]
            
            if not fts5_available:
                logger.warning("FTS5 extension is not available. Using fallback search.")
            
            # Create episodic memories table with INTEGER PRIMARY KEY for FTS5 compatibility
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL,
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
            
            # Create FTS5 virtual table for full-text search (external content table)
            # Using unicode61 tokenizer for better Unicode support (including Chinese)
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS episodic_memories_fts USING fts5(
                    content,
                    content_rowid=rowid,
                    content=episodic_memories,
                    tokenize='unicode61'
                )
            ''')

            # Create triggers to keep FTS index in sync
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS episodic_memories_ai AFTER INSERT ON episodic_memories BEGIN
                    INSERT INTO episodic_memories_fts(rowid, content) VALUES (new.rowid, new.content);
                END
            ''')

            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS episodic_memories_ad AFTER DELETE ON episodic_memories BEGIN
                    INSERT INTO episodic_memories_fts(episodic_memories_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
                END
            ''')

            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS episodic_memories_au AFTER UPDATE ON episodic_memories BEGIN
                    INSERT INTO episodic_memories_fts(episodic_memories_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
                    INSERT INTO episodic_memories_fts(rowid, content) VALUES (new.rowid, new.content);
                END
            ''')

            # Populate FTS index with existing data (if any)
            cursor.execute('''
                INSERT OR IGNORE INTO episodic_memories_fts(rowid, content)
                SELECT rowid, content FROM episodic_memories WHERE status = 'active'
            ''')
            
            # Create index on type and status
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_type_status ON episodic_memories (type, status)')
            
            # Create index on last_accessed
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_accessed ON episodic_memories (last_accessed)')
            
            # Create index on confidence for ranking
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_confidence ON episodic_memories (confidence)')
            
            conn.commit()
            conn.close()
            
            logger.info("Tier3StorageFTS initialized successfully with FTS5 support")
        except Exception as e:
            logger.error(f"Error initializing database: {e}", exc_info=True)
    
    def store_memory(self, memory: Dict[str, Any]) -> bool:
        """Store a memory in tier 3 with FTS support.

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
        """Retrieve memories from tier 3 using FTS5 full-text search with Chinese fallback.

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
                # Check if query contains Chinese characters
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in query)

                if has_chinese:
                    # Use LIKE search for Chinese content (FTS5 doesn't handle CJK well)
                    cursor.execute('''
                        SELECT * FROM episodic_memories
                        WHERE status = 'active' AND content LIKE ?
                        ORDER BY confidence DESC, last_accessed DESC
                        LIMIT ?
                    ''', (f'%{query}%', limit))
                else:
                    # Use FTS5 for English/ASCII content
                    cursor.execute('''
                        SELECT em.*, rank
                        FROM episodic_memories em
                        JOIN episodic_memories_fts fts ON em.rowid = fts.rowid
                        WHERE em.status = 'active' AND episodic_memories_fts MATCH ?
                        ORDER BY rank ASC, em.confidence DESC
                        LIMIT ?
                    ''', (query, limit))
            else:
                # Get all active memories ordered by confidence and last_accessed
                cursor.execute('''
                    SELECT * FROM episodic_memories
                    WHERE status = 'active'
                    ORDER BY confidence DESC, last_accessed DESC
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
            # Fallback to basic search if FTS fails
            return self._fallback_retrieve(query, limit)

    def _fallback_retrieve(self, query: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Fallback retrieval using basic LIKE search.
        
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
                # Search for query in content using LIKE
                cursor.execute('''
                    SELECT * FROM episodic_memories 
                    WHERE status = 'active' AND content LIKE ? 
                    ORDER BY confidence DESC, last_accessed DESC 
                    LIMIT ?
                ''', (f'%{query}%', limit))
            else:
                # Get all active memories
                cursor.execute('''
                    SELECT * FROM episodic_memories 
                    WHERE status = 'active' 
                    ORDER BY confidence DESC, last_accessed DESC 
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
            logger.error(f"Error in fallback retrieval: {e}", exc_info=True)
            return []
    
    def search_with_highlight(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories with highlighted matches.
        
        Args:
            query: Query string to search for.
            limit: Maximum number of memories to return.
            
        Returns:
            A list of matching memories with highlighted content.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Use FTS5 with highlight
            cursor.execute('''
                SELECT em.*, 
                       highlight(episodic_memories_fts, 0, '<mark>', '</mark>') as highlighted_content,
                       rank
                FROM episodic_memories em
                JOIN episodic_memories_fts fts ON em.rowid = fts.rowid
                WHERE em.status = 'active' AND episodic_memories_fts MATCH ?
                ORDER BY rank ASC, em.confidence DESC
                LIMIT ?
            ''', (query, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert rows to dictionaries
            memories = []
            for row in rows:
                memory = dict(row)
                # Ensure memory_type field is present
                if 'type' in memory and 'memory_type' not in memory:
                    memory['memory_type'] = memory['type']
                memories.append(memory)
            
            return memories
        except Exception as e:
            logger.error(f"Error searching with highlight: {e}", exc_info=True)
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
            
            # Get FTS index stats
            try:
                cursor.execute("SELECT COUNT(*) FROM episodic_memories_fts")
                fts_count = cursor.fetchone()[0]
            except:
                fts_count = 0
            
            conn.close()
            
            return {
                'total_memories': total,
                'active_memories': active,
                'memory_types': types,
                'fts_indexed': fts_count
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}", exc_info=True)
            return {
                'total_memories': 0,
                'active_memories': 0,
                'memory_types': {},
                'fts_indexed': 0
            }
    
    def rebuild_fts_index(self) -> bool:
        """Rebuild the FTS index.
        
        Returns:
            True if the index was rebuilt successfully, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Rebuild FTS index
            cursor.execute("INSERT INTO episodic_memories_fts(episodic_memories_fts) VALUES ('rebuild')")

            conn.commit()
            conn.close()

            logger.info("FTS index rebuilt successfully")
            return True
        except Exception as e:
            logger.error(f"Error rebuilding FTS index: {e}", exc_info=True)
            return False

    def warmup_cache(self, limit: int = 100) -> int:
        """Warm up cache with frequently accessed memories.

        This method preloads the most frequently accessed memories into cache
        to improve query performance.

        Args:
            limit: Maximum number of memories to preload.

        Returns:
            Number of memories cached.
        """
        if not self._cache_enabled or self._cache is None:
            logger.warning("Cache is not enabled, skipping warmup")
            return 0

        def fetch_recent_memories(limit: int) -> List[Dict]:
            """Fetch recently accessed memories."""
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM episodic_memories
                    WHERE status = 'active'
                    ORDER BY access_count DESC, last_accessed DESC
                    LIMIT ?
                ''', (limit,))

                rows = cursor.fetchall()
                conn.close()

                memories = []
                for row in rows:
                    memory = dict(row)
                    if 'type' in memory and 'memory_type' not in memory:
                        memory['memory_type'] = memory['type']
                    memories.append(memory)

                return memories
            except Exception as e:
                logger.error(f"Error fetching memories for warmup: {e}")
                return []

        return self._cache.warmup(fetch_recent_memories, limit=limit)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        if not self._cache_enabled or self._cache is None:
            return {'enabled': False}

        stats = self._cache.get_stats()
        stats['enabled'] = True
        return stats

    def invalidate_cache(self, memory_id: str = None) -> bool:
        """Invalidate cache entries.

        Args:
            memory_id: Specific memory ID to invalidate, or None to clear all.

        Returns:
            True if operation succeeded.
        """
        if not self._cache_enabled or self._cache is None:
            return False

        if memory_id:
            return self._cache.invalidate_memory(memory_id)
        else:
            self._cache.clear()
            return True
