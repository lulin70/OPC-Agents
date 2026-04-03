"""Debug FTS5 storage - check FTS5 availability."""
import sqlite3
import tempfile
import os

# Create temp db
temp_dir = tempfile.mkdtemp()
db_path = os.path.join(temp_dir, "test.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check FTS5 availability
cursor.execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')")
fts5_available = cursor.fetchone()[0]
print(f"FTS5 available: {fts5_available}")

if fts5_available:
    # Create test table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_docs (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT
        )
    ''')

    # Create FTS5 table with unicode61
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS test_fts USING fts5(
            content,
            content_rowid=rowid,
            content=test_docs,
            tokenize='unicode61'
        )
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
    print("\nMain table:")
    for row in cursor.fetchall():
        print(f"  {row}")

    cursor.execute("SELECT rowid, * FROM test_fts")
    print("\nFTS table:")
    for row in cursor.fetchall():
        print(f"  {row}")

    # Test MATCH
    print("\nMATCH 'Python':")
    cursor.execute("SELECT rowid FROM test_fts WHERE content MATCH 'Python'")
    for row in cursor.fetchall():
        print(f"  {row}")

    print("\nMATCH '用户':")
    cursor.execute("SELECT rowid FROM test_fts WHERE content MATCH '用户'")
    for row in cursor.fetchall():
        print(f"  {row}")

    # Try different tokenizers
    print("\n\nTesting different tokenizers:")

    # Try porter tokenizer
    try:
        cursor.execute('''
            CREATE VIRTUAL TABLE test_fts_porter USING fts5(
                content,
                tokenize='porter'
            )
        ''')
        cursor.execute("INSERT INTO test_fts_porter (content) VALUES ('Hello world Python')")
        cursor.execute("SELECT rowid FROM test_fts_porter WHERE content MATCH 'Python'")
        results = cursor.fetchall()
        print(f"  Porter tokenizer: {len(results)} results")
    except Exception as e:
        print(f"  Porter tokenizer error: {e}")

conn.close()

# Cleanup
import shutil
shutil.rmtree(temp_dir)
print(f"\nCleaned up")
