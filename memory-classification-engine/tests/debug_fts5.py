"""Debug FTS5 storage - final check."""
import sys
import os
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine.storage.tier3_fts import Tier3StorageFTS
from memory_classification_engine.utils.helpers import generate_memory_id

temp_dir = tempfile.mkdtemp()
storage = Tier3StorageFTS(os.path.join(temp_dir, 'test'))

# Insert test memories
print("Inserting 5 test memories...")
for i in range(5):
    memory = {
        'id': generate_memory_id(),
        'type': 'user_preference',
        'content': f'用户喜欢使用Python编写{i}号项目',
        'confidence': 0.9,
        'source': 'test'
    }
    result = storage.store_memory(memory)
    print(f"  Memory {i}: stored={result}")

# Direct DB check
db_path = os.path.join(temp_dir, 'test', 'episodic_memories.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('\nMain table content:')
cursor.execute('SELECT rowid, id, content FROM episodic_memories')
for row in cursor.fetchall():
    print(f'  {row}')

print('\nFTS table content:')
cursor.execute('SELECT rowid, * FROM episodic_memories_fts')
for row in cursor.fetchall():
    print(f'  {row}')

print("\nMATCH 'Python':")
cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content MATCH 'Python'")
results = cursor.fetchall()
print(f'  Results: {results}')

print("\nMATCH '*ython' (prefix search):")
cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content MATCH '*ython'")
results = cursor.fetchall()
print(f'  Results: {results}')

conn.close()

# Test storage retrieve
print("\nStorage retrieve (no query):")
all_mems = storage.retrieve_memories(limit=3)
print(f"  Count: {len(all_mems)}")

print("\nStorage retrieve (query='Python'):")
search_results = storage.retrieve_memories(query='Python', limit=3)
print(f"  Count: {len(search_results)}")

import shutil
shutil.rmtree(temp_dir)
print("\nCleaned up")
