#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Database Migration Script for v0.2
Adds missing columns for token counting system
"""

import sqlite3
import os
import sys
from datetime import datetime

# Database path
DB_PATH = 'data/claude_clone.db'
BACKUP_PATH = f'data/claude_clone_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'

def check_column_exists(cursor, table, column):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    return column in columns

def migrate_database():
    """Add missing columns for v0.2 token system"""

    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return False

    # Create backup
    print(f"Creating backup at {BACKUP_PATH}...")
    import shutil
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print("Backup created successfully")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")

        # 1. Add total_tokens column to conversations table
        if not check_column_exists(cursor, 'conversations', 'total_tokens'):
            print("Adding total_tokens column to conversations table...")
            cursor.execute("""
                ALTER TABLE conversations
                ADD COLUMN total_tokens INTEGER DEFAULT 0
            """)
            print("✓ Added total_tokens to conversations")
        else:
            print("✓ total_tokens column already exists in conversations")

        # 2. Add token_count column to project_knowledge table
        if not check_column_exists(cursor, 'project_knowledge', 'token_count'):
            print("Adding token_count column to project_knowledge table...")
            cursor.execute("""
                ALTER TABLE project_knowledge
                ADD COLUMN token_count INTEGER DEFAULT 0
            """)
            print("✓ Added token_count to project_knowledge")
        else:
            print("✓ token_count column already exists in project_knowledge")

        # 3. Check and potentially create other v0.2 tables
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='token_cache'
        """)
        if not cursor.fetchone():
            print("Creating token_cache table...")
            cursor.execute("""
                CREATE TABLE token_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash VARCHAR(64) NOT NULL UNIQUE,
                    token_count INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX idx_token_cache_hash ON token_cache(content_hash)
            """)
            print("✓ Created token_cache table")
        else:
            print("✓ token_cache table already exists")

        # 4. Check for user_permissions table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='user_permissions'
        """)
        if not cursor.fetchone():
            print("Creating user_permissions table...")
            cursor.execute("""
                CREATE TABLE user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    bash BOOLEAN DEFAULT 0,
                    read_files BOOLEAN DEFAULT 1,
                    write_files BOOLEAN DEFAULT 0,
                    create_files BOOLEAN DEFAULT 0,
                    search_web BOOLEAN DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE(user_id)
                )
            """)

            # Insert default permissions for existing users
            cursor.execute("""
                INSERT OR IGNORE INTO user_permissions (user_id, bash, read_files, write_files, create_files, search_web)
                SELECT id, 0, 1, 0, 0, 0 FROM users
            """)
            print("✓ Created user_permissions table and initialized default permissions")
        else:
            print("✓ user_permissions table already exists")

        # 5. Verify all columns exist
        print("\nVerifying database schema...")

        # Check conversations
        cursor.execute("PRAGMA table_info(conversations)")
        conv_columns = {col[1] for col in cursor.fetchall()}
        if 'total_tokens' in conv_columns:
            print("✓ conversations.total_tokens verified")
        else:
            print("✗ ERROR: conversations.total_tokens not found")
            raise Exception("Migration failed: conversations.total_tokens not created")

        # Check project_knowledge
        cursor.execute("PRAGMA table_info(project_knowledge)")
        pk_columns = {col[1] for col in cursor.fetchall()}
        if 'token_count' in pk_columns:
            print("✓ project_knowledge.token_count verified")
        else:
            print("✗ ERROR: project_knowledge.token_count not found")
            raise Exception("Migration failed: project_knowledge.token_count not created")

        # Commit transaction
        cursor.execute("COMMIT")
        print("\n✅ Migration completed successfully!")
        return True

    except Exception as e:
        # Rollback on error
        cursor.execute("ROLLBACK")
        print(f"\n❌ Migration failed: {str(e)}")
        print(f"Database has been rolled back. Backup available at {BACKUP_PATH}")
        return False

    finally:
        conn.close()

def main():
    """Main entry point"""
    print("=" * 60)
    print("Claude AI Web Interface v0.2 Database Migration")
    print("=" * 60)

    # Change to web-interface directory if needed
    if not os.path.exists(DB_PATH):
        if os.path.exists('web-interface'):
            os.chdir('web-interface')
            print("Changed directory to web-interface/")
        elif os.path.exists('../web-interface'):
            os.chdir('../web-interface')
            print("Changed directory to web-interface/")

    success = migrate_database()

    if success:
        print("\nYou can now restart your Flask application!")
        return 0
    else:
        print("\nPlease check the error messages above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())