"""Debug FTS5 storage - detailed."""
import sys
import os
import tempfile
import sqlite3

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

# Direct DB check
db_path = os.path.join(temp_dir, "test", "episodic_memories.db")
print(f"\nDirect DB check ({db_path}):")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check FTS5 table structure
print("\n  FTS5 table info:")
cursor.execute("PRAGMA table_info(episodic_memories_fts)")
for row in cursor.fetchall():
    print(f"    {row}")

# Check data in FTS5
print("\n  FTS5 indexed content:")
cursor.execute("SELECT rowid, * FROM episodic_memories_fts LIMIT 5")
for row in cursor.fetchall():
    print(f"    {row}")

# Test different MATCH queries
print("\n  Testing MATCH queries:")

# Query 1: Simple word
try:
    cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content MATCH ?", ('Python',))
    results = cursor.fetchall()
    print(f"    MATCH 'Python': {len(results)} results, rowids={results}")
except Exception as e:
    print(f"    MATCH 'Python' error: {e}")

# Query 2: Chinese word
try:
    cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content MATCH ?", ('用户',))
    results = cursor.fetchall()
    print(f"    MATCH '用户': {len(results)} results, rowids={results}")
except Exception as e:
    print(f"    MATCH '用户' error: {e}")

# Query 3: Number
try:
    cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content MATCH ?", ('5',))
    results = cursor.fetchall()
    print(f"    MATCH '5': {len(results)} results, rowids={results}")
except Exception as e:
    print(f"    MATCH '5' error: {e}")

# Query 4: Check if FTS5 is working at all
try:
    cursor.execute("SELECT * FROM episodic_memories_fts LIMIT 1")
    row = cursor.fetchone()
    print(f"\n  Sample FTS5 row: {row}")
except Exception as e:
    print(f"    Error: {e}")

# Check main table
cursor.execute("SELECT rowid, id, content FROM episodic_memories LIMIT 3")
print("\n  Main table sample:")
for row in cursor.fetchall():
    print(f"    {row}")

conn.close()

# Cleanup
import shutil
shutil.rmtree(temp_dir)
print(f"\nCleaned up temp directory")
