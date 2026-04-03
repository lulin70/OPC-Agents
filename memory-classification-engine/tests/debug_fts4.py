"""Debug FTS5 storage - test external content table."""
import sqlite3
import tempfile
import os

# Create temp db
temp_dir = tempfile.mkdtemp()
db_path = os.path.join(temp_dir, "test.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create main table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS test_docs (
        rowid INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT
    )
''')

# Create FTS5 external content table
# Note: For external content tables, we need triggers to sync data
cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS test_fts USING fts5(
        content,
        content_rowid=rowid,
        content=test_docs
    )
''')

# Create trigger to sync inserts
cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS test_docs_ai AFTER INSERT ON test_docs BEGIN
        INSERT INTO test_fts(rowid, content) VALUES (new.rowid, new.content);
    END
''')

# Insert test data
test_contents = [
    'Hello world Python',
    '用户喜欢使用Python',
    'Python programming',
    '使用Python编写代码'
]

for content in test_contents:
    cursor.execute("INSERT INTO test_docs (content) VALUES (?)", (content,))

# Check data
cursor.execute("SELECT rowid, content FROM test_docs")
print("Main table:")
for row in cursor.fetchall():
    print(f"  {row}")

cursor.execute("SELECT rowid, * FROM test_fts")
print("\nFTS table:")
for row in cursor.fetchall():
    print(f"  {row}")

# Test MATCH
print("\nMATCH 'Python':")
cursor.execute("SELECT rowid FROM test_fts WHERE content MATCH 'Python'")
results = cursor.fetchall()
print(f"  Results: {results}")

print("\nMATCH '用户':")
cursor.execute("SELECT rowid FROM test_fts WHERE content MATCH '用户'")
results = cursor.fetchall()
print(f"  Results: {results}")

# Test without content option (standalone FTS5 table)
print("\n\n--- Testing standalone FTS5 table ---")
cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS test_fts_standalone USING fts5(
        content
    )
''')

for content in test_contents:
    cursor.execute("INSERT INTO test_fts_standalone (content) VALUES (?)", (content,))

cursor.execute("SELECT rowid, * FROM test_fts_standalone")
print("\nStandalone FTS table:")
for row in cursor.fetchall():
    print(f"  {row}")

print("\nMATCH 'Python' (standalone):")
cursor.execute("SELECT rowid FROM test_fts_standalone WHERE content MATCH 'Python'")
results = cursor.fetchall()
print(f"  Results: {results}")

conn.close()

# Cleanup
import shutil
shutil.rmtree(temp_dir)
print(f"\nCleaned up")
