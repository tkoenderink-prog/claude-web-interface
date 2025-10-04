#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Migration script for v0.3.0 - RUN THIS FIRST"""

import sqlite3
from datetime import datetime
from pathlib import Path

def migrate_database():
    db_path = Path(__file__).parent.parent / 'data' / 'claude_clone.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")

        # Create conversation_modes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_modes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                icon VARCHAR(50) DEFAULT '💬',
                is_default BOOLEAN DEFAULT FALSE,
                is_deleted BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create mode_configuration table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mode_configuration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode_id INTEGER NOT NULL,
                model VARCHAR(50) DEFAULT 'claude-3-5-sonnet-20241022',
                temperature FLOAT DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 4096,
                system_prompt TEXT,
                system_prompt_tokens INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mode_id) REFERENCES conversation_modes(id)
            )
        """)

        # Create mode_knowledge_files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mode_knowledge_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                vault VARCHAR(50) DEFAULT 'private',
                tokens INTEGER DEFAULT 0,
                auto_include BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mode_id) REFERENCES conversation_modes(id)
            )
        """)

        # Add columns to conversations table
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'mode_id' not in columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN mode_id INTEGER")
        if 'auto_title' not in columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN auto_title VARCHAR(255)")
        if 'exported_at' not in columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN exported_at TIMESTAMP")

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mode_conversation ON conversations(mode_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mode_config ON mode_configuration(mode_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mode_knowledge ON mode_knowledge_files(mode_id)")

        # Insert default "General" mode
        cursor.execute("""
            INSERT OR IGNORE INTO conversation_modes (name, description, icon, is_default)
            VALUES ('General', 'General purpose assistant', '💬', TRUE)
        """)

        # Get the General mode ID
        cursor.execute("SELECT id FROM conversation_modes WHERE name = 'General'")
        general_mode_id = cursor.fetchone()[0]

        # Insert configuration for General mode
        cursor.execute("""
            INSERT OR IGNORE INTO mode_configuration (mode_id, model, system_prompt, system_prompt_tokens)
            VALUES (?, 'claude-3-5-sonnet-20241022', 'You are a helpful assistant.', 5)
        """, (general_mode_id,))

        # Update existing conversations to use General mode
        cursor.execute("UPDATE conversations SET mode_id = ? WHERE mode_id IS NULL", (general_mode_id,))

        # Commit transaction
        cursor.execute("COMMIT")
        print("✅ Database migration completed successfully")

    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
