#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Fix missing token_count column in file_attachments table"""

import sqlite3
import os
from datetime import datetime

# Database path
DB_PATH = 'data/claude_clone.db'

# Change to web-interface directory if needed
if not os.path.exists(DB_PATH):
    if os.path.exists('web-interface'):
        os.chdir('web-interface')
    elif os.path.exists('../web-interface'):
        os.chdir('../web-interface')

def add_token_count_column():
    """Add token_count column to file_attachments table"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(file_attachments)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'token_count' not in columns:
            print("Adding token_count column to file_attachments table...")
            cursor.execute("""
                ALTER TABLE file_attachments
                ADD COLUMN token_count INTEGER DEFAULT 0
            """)
            conn.commit()
            print("✅ Column added successfully!")
        else:
            print("✅ token_count column already exists")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("Fixing file_attachments table...")
    add_token_count_column()
    print("Done!")