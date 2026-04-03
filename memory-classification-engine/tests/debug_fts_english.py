"""Debug FTS5 - test English content."""
import sqlite3
import tempfile
import os
import shutil

# Create temp directory
temp_dir = tempfile.mkdtemp()
db_path = os.path.join(temp_dir, 'test.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create standalone FTS5 table
cursor.execute('CREATE VIRTUAL TABLE fts_test USING fts5(content)')

# Insert English content
test_contents = [
    'hello world python',
    'python programming',
    'user likes python',
    'java and python',
    'coding in python'
]

for content in test_contents:
    cursor.execute("INSERT INTO fts_test (content) VALUES (?)", (content,))

conn.commit()

print("FTS table content:")
cursor.execute("SELECT rowid, * FROM fts_test")
for row in cursor.fetchall():
    print(f"  {row}")

print("\nMATCH 'python':")
cursor.execute("SELECT rowid FROM fts_test WHERE content MATCH 'python'")
print(f"  Results: {cursor.fetchall()}")

print("\nMATCH 'hello':")
cursor.execute("SELECT rowid FROM fts_test WHERE content MATCH 'hello'")
print(f"  Results: {cursor.fetchall()}")

# Now test Chinese content
print("\n\n--- Testing Chinese content ---")
cursor.execute('CREATE VIRTUAL TABLE fts_chinese USING fts5(content)')

chinese_contents = [
    '用户喜欢使用Python',
    'Python编程语言',
    '使用Python编写代码',
]

for content in chinese_contents:
    cursor.execute("INSERT INTO fts_chinese (content) VALUES (?)", (content,))

conn.commit()

print("\nChinese FTS table content:")
cursor.execute("SELECT rowid, * FROM fts_chinese")
for row in cursor.fetchall():
    print(f"  {row}")

print("\nMATCH 'Python' (Chinese table):")
cursor.execute("SELECT rowid FROM fts_chinese WHERE content MATCH 'Python'")
print(f"  Results: {cursor.fetchall()}")

print("\nMATCH '用户' (Chinese table):")
cursor.execute("SELECT rowid FROM fts_chinese WHERE content MATCH '用户'")
print(f"  Results: {cursor.fetchall()}")

conn.close()
shutil.rmtree(temp_dir)
print("\nCleaned up")
