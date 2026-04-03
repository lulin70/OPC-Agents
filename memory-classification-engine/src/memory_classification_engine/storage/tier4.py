import os
import sqlite3
from typing import Dict, List, Optional, Any
from memory_classification_engine.utils.helpers import get_current_time
from memory_classification_engine.utils.logger import logger

class Tier4Storage:
    """Storage for semantic memory (tier 4)."""
    
    def __init__(self, storage_path: str = "./data/tier4"):
        """Initialize tier 4 storage.
        
        Args:
            storage_path: Path to store tier 4 memory database.
        """
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)
        
        # Database path
        self.db_path = os.path.join(self.storage_path, "semantic_memories.db")
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create semantic entities table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS semantic_entities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # Create semantic relationships table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS semantic_relationships (
                    id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    context TEXT,
                    FOREIGN KEY (subject_id) REFERENCES semantic_entities(id),
                    FOREIGN KEY (object_id) REFERENCES semantic_entities(id)
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_entity_type ON semantic_entities (type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_relationship_subject ON semantic_relationships (subject_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_relationship_object ON semantic_relationships (object_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_relationship_predicate ON semantic_relationships (predicate)')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing database: {e}", exc_info=True)
    
    def store_memory(self, memory: Dict[str, Any]) -> bool:
        """Store a memory in tier 4.
        
        Args:
            memory: The memory to store.
            
        Returns:
            True if the memory was stored successfully, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            current_time = get_current_time()
            
            # Store fact declaration
            if memory.get('type') == 'fact_declaration':
                # Extract entities from content
                subject, predicate, obj = self._extract_entities(memory.get('content', ''))
                
                # Create subject entity
                subject_id = self._get_or_create_entity(cursor, subject, "person", current_time)
                
                # Create object entity
                object_id = self._get_or_create_entity(cursor, obj, "fact", current_time)
                
                # Create relationship
                relationship_id = memory.get('id')
                cursor.execute('''
                    INSERT INTO semantic_relationships 
                    (id, subject_id, predicate, object_id, created_at, updated_at, confidence, source, context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    relationship_id,
                    subject_id,
                    predicate or "declares",
                    object_id,
                    current_time,
                    current_time,
                    memory.get('confidence', 1.0),
                    memory.get('source', 'user'),
                    memory.get('context')
                ))
            
            # Store relationship information
            elif memory.get('type') == 'relationship':
                # Extract entities from content
                subject, predicate, obj = self._extract_entities(memory.get('content', ''))
                
                # Create subject entity
                subject_id = self._get_or_create_entity(cursor, subject, "entity", current_time)
                
                # Create object entity
                object_id = self._get_or_create_entity(cursor, obj, "entity", current_time)
                
                # Create relationship
                relationship_id = memory.get('id')
                cursor.execute('''
                    INSERT INTO semantic_relationships 
                    (id, subject_id, predicate, object_id, created_at, updated_at, confidence, source, context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    relationship_id,
                    subject_id,
                    predicate or "related_to",
                    object_id,
                    current_time,
                    current_time,
                    memory.get('confidence', 1.0),
                    memory.get('source', 'user'),
                    memory.get('context')
                ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error storing memory: {e}", exc_info=True)
            return False
    
    def _extract_entities(self, content: str) -> tuple:
        """Extract entities from content.
        
        Args:
            content: The content to extract entities from.
            
        Returns:
            A tuple of (subject, predicate, object).
        """
        # Simple entity extraction based on common patterns
        # In a real implementation, this would use NLP techniques
        
        # Default values
        subject = "User"
        predicate = "declares"
        obj = content
        
        # Look for common relationship patterns
        patterns = [
            (r'(.*)是(.*)', '是'),
            (r'(.*)有(.*)', '有'),
            (r'(.*)在(.*)', '在'),
            (r'(.*)位于(.*)', '位于'),
            (r'(.*)属于(.*)', '属于'),
            (r'(.*)负责(.*)', '负责'),
            (r'(.*)管理(.*)', '管理'),
            (r'(.*)领导(.*)', '领导'),
            (r'(.*)汇报给(.*)', '汇报给'),
            (r'(.*)合作(.*)', '合作'),
        ]
        
        import re
        for pattern, pred in patterns:
            match = re.match(pattern, content)
            if match:
                subject = match.group(1).strip()
                predicate = pred
                obj = match.group(2).strip()
                break
        
        return subject, predicate, obj
    
    def _get_or_create_entity(self, cursor, name: str, entity_type: str, current_time: str) -> str:
        """Get or create an entity.
        
        Args:
            cursor: Database cursor.
            name: Entity name.
            entity_type: Entity type.
            current_time: Current time.
            
        Returns:
            Entity ID.
        """
        # Check if entity already exists
        cursor.execute('''
            SELECT id FROM semantic_entities 
            WHERE name = ? AND type = ?
        ''', (name, entity_type))
        
        result = cursor.fetchone()
        if result:
            return result[0]
        
        # Create new entity
        import hashlib
        entity_id = f"entity_{hashlib.md5((name + entity_type + current_time).encode()).hexdigest()[:16]}"
        cursor.execute('''
            INSERT INTO semantic_entities 
            (id, name, type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            entity_id,
            name,
            entity_type,
            current_time,
            current_time
        ))
        
        return entity_id
    
    def retrieve_memories(self, query: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve memories from tier 4.
        
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
                # Search for query in relationships
                cursor.execute('''
                    SELECT sr.*, se1.name as subject_name, se2.name as object_name 
                    FROM semantic_relationships sr
                    JOIN semantic_entities se1 ON sr.subject_id = se1.id
                    JOIN semantic_entities se2 ON sr.object_id = se2.id
                    WHERE sr.context LIKE ? OR se1.name LIKE ? OR se2.name LIKE ?
                    ORDER BY sr.created_at DESC
                    LIMIT ?
                ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))
            else:
                # Get all relationships
                cursor.execute('''
                    SELECT sr.*, se1.name as subject_name, se2.name as object_name 
                    FROM semantic_relationships sr
                    JOIN semantic_entities se1 ON sr.subject_id = se1.id
                    JOIN semantic_entities se2 ON sr.object_id = se2.id
                    ORDER BY sr.created_at DESC
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert rows to dictionaries
            memories = []
            for row in rows:
                memory_type = 'relationship' if row['predicate'] != 'declares' else 'fact_declaration'
                memory = {
                    'id': row['id'],
                    'type': memory_type,
                    'memory_type': memory_type,
                    'content': f"{row['subject_name']} {row['predicate']} {row['object_name']}",
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'confidence': row['confidence'],
                    'source': row['source'],
                    'context': row['context']
                }
                memories.append(memory)
            
            return memories
        except Exception as e:
            logger.error(f"Error retrieving memories: {e}", exc_info=True)
            return []
    
    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a memory in tier 4.
        
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
                if key in ['confidence', 'context', 'source']:
                    set_clause.append(f"{key} = ?")
                    params.append(value)
            
            # Always update the updated_at timestamp
            set_clause.append("updated_at = ?")
            params.append(get_current_time())
            
            # Add memory_id to params
            params.append(memory_id)
            
            # Execute update
            cursor.execute(f'''
                UPDATE semantic_relationships 
                SET {', '.join(set_clause)} 
                WHERE id = ?
            ''', params)
            
            conn.commit()
            conn.close()
            
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating memory: {e}", exc_info=True)
            return False
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory from tier 4.
        
        Args:
            memory_id: The ID of the memory to delete.
            
        Returns:
            True if the memory was deleted successfully, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete the relationship
            cursor.execute('DELETE FROM semantic_relationships WHERE id = ?', (memory_id,))
            
            conn.commit()
            conn.close()
            
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting memory: {e}", exc_info=True)
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tier 4 storage.
        
        Returns:
            A dictionary with statistics.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get total entities
            cursor.execute('SELECT COUNT(*) FROM semantic_entities')
            total_entities = cursor.fetchone()[0]
            
            # Get total relationships
            cursor.execute('SELECT COUNT(*) FROM semantic_relationships')
            total_relationships = cursor.fetchone()[0]
            
            # Get entity types
            cursor.execute('SELECT type, COUNT(*) FROM semantic_entities GROUP BY type')
            entity_types = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get relationship predicates
            cursor.execute('SELECT predicate, COUNT(*) FROM semantic_relationships GROUP BY predicate')
            predicates = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'total_entities': total_entities,
                'total_relationships': total_relationships,
                'entity_types': entity_types,
                'predicates': predicates
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}", exc_info=True)
            return {
                'total_entities': 0,
                'total_relationships': 0,
                'entity_types': {},
                'predicates': {}
            }
