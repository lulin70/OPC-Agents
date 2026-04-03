"""Debug FTS5 storage insertion."""
import sys
import os
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine.storage.tier3_fts import Tier3StorageFTS
from memory_classification_engine.utils.helpers import generate_memory_id

temp_dir = tempfile.mkdtemp()
print(f"Temp directory: {temp_dir}")

# Create storage
storage_path = os.path.join(temp_dir, 'test')
storage = Tier3StorageFTS(storage_path)

# Insert 10 memories and track results
print("\nInserting 10 test memories...")
success_count = 0
for i in range(10):
    memory = {
        'id': generate_memory_id(),
        'type': 'user_preference',
        'content': f'用户喜欢使用Python编写{i}号项目',
        'confidence': 0.9,
        'source': 'test'
    }
    result = storage.store_memory(memory)
    if result:
        success_count += 1
    print(f"  Memory {i}: stored={result}")

print(f"\nTotal successful: {success_count}/10")

# Check stats
print("\nStorage stats:")
stats = storage.get_stats()
print(f"  Total memories: {stats['total_memories']}")
print(f"  Active memories: {stats['active_memories']}")
print(f"  FTS indexed: {stats['fts_indexed']}")

# Direct DB check
db_path = os.path.join(storage_path, 'episodic_memories.db')
print(f"\nDirect DB check ({db_path}):")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM episodic_memories")
print(f"  episodic_memories count: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM episodic_memories_fts")
print(f"  episodic_memories_fts count: {cursor.fetchone()[0]}")

cursor.execute("SELECT rowid, id, content FROM episodic_memories LIMIT 3")
print("\n  Sample episodic_memories rows:")
for row in cursor.fetchall():
    print(f"    {row}")

conn.close()

import shutil
shutil.rmtree(temp_dir)
print("\nCleaned up")
