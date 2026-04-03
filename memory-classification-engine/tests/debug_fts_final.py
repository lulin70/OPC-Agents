"""Debug FTS5 - final investigation."""
import sqlite3
import tempfile
import os
import shutil

# Create temp directory
temp_dir = tempfile.mkdtemp()
db_path = os.path.join(temp_dir, 'test.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create main table
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

# Create FTS5 external content table (same as tier3_fts.py)
cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS episodic_memories_fts USING fts5(
        content,
        content_rowid=rowid,
        content=episodic_memories
    )
''')

# Create triggers
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

# Insert test data
for i in range(5):
    cursor.execute('''
        INSERT INTO episodic_memories (id, type, content, created_at, updated_at, last_accessed, confidence, source, status)
        VALUES (?, ?, ?, '2024-01-01', '2024-01-01', '2024-01-01', 0.9, 'test', 'active')
    ''', (f'mem_{i}', 'user_preference', f'用户喜欢使用Python编写{i}号项目'))

conn.commit()

# Check data
cursor.execute("SELECT rowid, id, content FROM episodic_memories")
print("Main table:")
for row in cursor.fetchall():
    print(f"  {row}")

cursor.execute("SELECT rowid, * FROM episodic_memories_fts")
print("\nFTS table:")
for row in cursor.fetchall():
    print(f"  {row}")

# Test MATCH
print("\nMATCH 'Python':")
cursor.execute("SELECT rowid FROM episodic_memories_fts WHERE content MATCH 'Python'")
print(f"  Results: {cursor.fetchall()}")

# Test JOIN query (same as tier3_fts.py)
print("\nJOIN query:")
cursor.execute('''
    SELECT em.*, rank
    FROM episodic_memories em
    JOIN episodic_memories_fts fts ON em.rowid = fts.rowid
    WHERE em.status = 'active' AND episodic_memories_fts MATCH 'Python'
    ORDER BY rank ASC, em.confidence DESC
    LIMIT 10
''')
results = cursor.fetchall()
print(f"  Results: {len(results)} rows")
for row in results:
    print(f"    {row}")

# Test without content option
print("\n\n--- Testing without content option ---")
cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS fts_standalone USING fts5(content)
''')

for i in range(5):
    cursor.execute("INSERT INTO fts_standalone (content) VALUES (?)",
                   (f'用户喜欢使用Python编写{i}号项目',))

conn.commit()

print("\nStandalone FTS table:")
cursor.execute("SELECT rowid, * FROM fts_standalone")
for row in cursor.fetchall():
    print(f"  {row}")

print("\nStandalone MATCH 'Python':")
cursor.execute("SELECT rowid FROM fts_standalone WHERE content MATCH 'Python'")
print(f"  Results: {cursor.fetchall()}")

conn.close()
shutil.rmtree(temp_dir)
print("\nCleaned up")
