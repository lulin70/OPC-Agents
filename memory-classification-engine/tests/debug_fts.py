"""Debug FTS5 storage."""
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine.storage.tier3_fts import Tier3StorageFTS
from memory_classification_engine.utils.helpers import generate_memory_id

# Create temp directory
temp_dir = tempfile.mkdtemp()
print(f"Temp directory: {temp_dir}")

# Initialize storage
storage = Tier3StorageFTS(os.path.join(temp_dir, "test"))

# Insert test memories
print("\nInserting 10 test memories...")
for i in range(10):
    memory = {
        'id': generate_memory_id(),
        'type': 'user_preference',
        'content': f'用户喜欢使用Python编写{i}号项目',
        'confidence': 0.9,
        'source': 'test'
    }
    result = storage.store_memory(memory)
    print(f"  Memory {i}: stored={result}")

# Check stats
print("\nStorage stats:")
stats = storage.get_stats()
print(f"  Total memories: {stats['total_memories']}")
print(f"  Active memories: {stats['active_memories']}")
print(f"  FTS indexed: {stats['fts_indexed']}")

# Retrieve all memories
print("\nAll memories (limit 5):")
all_memories = storage.retrieve_memories(limit=5)
print(f"  Count: {len(all_memories)}")
for m in all_memories:
    print(f"    - {m['content'][:40]}...")

# Search for Python
print("\nSearch for 'Python':")
results = storage.retrieve_memories(query='Python', limit=5)
print(f"  Count: {len(results)}")
for m in results:
    print(f"    - {m['content'][:40]}...")

# Direct DB check
import sqlite3
db_path = os.path.join(temp_dir, "test", "episodic_memories.db")
print(f"\nDirect DB check ({db_path}):")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM episodic_memories")
print(f"  episodic_memories count: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM episodic_memories_fts")
print(f"  episodic_memories_fts count: {cursor.fetchone()[0]}")

cursor.execute("SELECT * FROM episodic_memories LIMIT 3")
rows = cursor.fetchall()
print(f"\n  Sample episodic_memories rows:")
for row in rows:
    print(f"    rowid={row[0]}, content={row[2][:30]}...")

conn.close()

# Cleanup
import shutil
shutil.rmtree(temp_dir)
print(f"\nCleaned up temp directory")
