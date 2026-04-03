"""Debug FTS5 storage - check tokenizer."""
import sys
import os
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine.storage.tier3_fts import Tier3StorageFTS
from memory_classification_engine.utils.helpers import generate_memory_id

temp_dir = tempfile.mkdtemp()

# Create storage to initialize DB
storage = Tier3StorageFTS(os.path.join(temp_dir, 'test'))

# Insert test memories
for i in range(3):
    memory = {
        'id': generate_memory_id(),
        'type': 'user_preference',
        'content': f'用户喜欢使用Python编写{i}号项目',
        'confidence': 0.9,
        'source': 'test'
    }
    storage.store_memory(memory)

# Direct DB check
db_path = os.path.join(temp_dir, 'test', 'episodic_memories.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check FTS5 table info
print("FTS5 table info:")
cursor.execute("PRAGMA table_info(episodic_memories_fts)")
for row in cursor.fetchall():
    print(f"  {row}")

# Check FTS5 schema
print("\nFTS5 schema:")
cursor.execute("SELECT sql FROM sqlite_master WHERE name='episodic_memories_fts'")
print(f"  {cursor.fetchone()}")

# Try to see what tokenizer is being used
print("\nTrying to query FTS5 with different patterns:")

# Test 1: Simple word
print("\n1. MATCH 'Python':")
try:
    cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content MATCH 'Python'")
    print(f"   Results: {cursor.fetchall()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: Chinese word
print("\n2. MATCH '用户':")
try:
    cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content MATCH '用户'")
    print(f"   Results: {cursor.fetchall()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Using = instead of MATCH
print("\n3. Direct comparison (not FTS):")
cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content LIKE '%Python%'")
print(f"   Results: {cursor.fetchall()}")

# Test 4: Check if FTS5 index is populated
print("\n4. FTS5 index size:")
cursor.execute("SELECT COUNT(*) FROM episodic_memories_fts")
print(f"   Count: {cursor.fetchone()[0]}")

# Test 5: Try rebuilding index
print("\n5. Rebuilding FTS5 index...")
try:
    cursor.execute("INSERT INTO episodic_memories_fts(episodic_memories_fts) VALUES ('rebuild')")
    conn.commit()
    print("   Rebuild completed")
    
    # Test again
    cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content MATCH 'Python'")
    print(f"   After rebuild - MATCH 'Python': {cursor.fetchall()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 6: Create a new standalone FTS5 table without unicode61
print("\n6. Creating standalone FTS5 table:")
try:
    cursor.execute('''
        CREATE VIRTUAL TABLE test_standalone USING fts5(content)
    ''')
    cursor.execute("INSERT INTO test_standalone (content) VALUES ('用户喜欢使用Python')")
    cursor.execute("SELECT rowid FROM test_standalone WHERE content MATCH 'Python'")
    print(f"   Standalone MATCH 'Python': {cursor.fetchall()}")
except Exception as e:
    print(f"   Error: {e}")

conn.close()

import shutil
shutil.rmtree(temp_dir)
print("\nCleaned up")
