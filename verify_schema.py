#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Quick verification of database schema for v0.2"""

import sqlite3
import os

# Database path
DB_PATH = 'data/claude_clone.db'

# Change to web-interface directory if needed
if not os.path.exists(DB_PATH):
    if os.path.exists('web-interface'):
        os.chdir('web-interface')
    elif os.path.exists('../web-interface'):
        os.chdir('../web-interface')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 60)
print("Database Schema Verification")
print("=" * 60)

# Check conversations table
cursor.execute("PRAGMA table_info(conversations)")
conv_columns = cursor.fetchall()
print("\nConversations table columns:")
for col in conv_columns:
    print(f"  - {col[1]:20} {col[2]:15} {'NOT NULL' if col[3] else 'NULL'}")
    if col[1] == 'total_tokens':
        print("    ✓ total_tokens column found!")

# Check project_knowledge table
cursor.execute("PRAGMA table_info(project_knowledge)")
pk_columns = cursor.fetchall()
print("\nProject_knowledge table columns:")
for col in pk_columns:
    print(f"  - {col[1]:20} {col[2]:15} {'NOT NULL' if col[3] else 'NULL'}")
    if col[1] == 'token_count':
        print("    ✓ token_count column found!")

# Check token_cache table
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='token_cache'")
if cursor.fetchone():
    print("\n✓ token_cache table exists")

# Check user_permissions table
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_permissions'")
if cursor.fetchone():
    print("✓ user_permissions table exists")

print("\n" + "=" * 60)
print("Schema verification complete!")
print("=" * 60)

conn.close()