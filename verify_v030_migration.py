#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Verify v0.3.0 database migration was successful"""

import sqlite3
from pathlib import Path

def verify_migration():
    db_path = Path(__file__).parent / 'data' / 'claude_clone.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 60)
    print("VERIFYING V0.3.0 DATABASE MIGRATION")
    print("=" * 60)

    # Check for new tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    print("\n📋 ALL TABLES IN DATABASE:")
    for table in tables:
        print(f"  ✓ {table}")

    # Verify new tables exist
    required_tables = ['conversation_modes', 'mode_configuration', 'mode_knowledge_files']
    print("\n🔍 CHECKING NEW TABLES:")
    for table in required_tables:
        if table in tables:
            print(f"  ✅ {table} - EXISTS")
        else:
            print(f"  ❌ {table} - MISSING")

    # Check conversations table columns
    print("\n📊 CONVERSATIONS TABLE COLUMNS:")
    cursor.execute("PRAGMA table_info(conversations)")
    conv_columns = [(col[1], col[2]) for col in cursor.fetchall()]
    for col_name, col_type in conv_columns:
        print(f"  • {col_name} ({col_type})")

    # Verify new columns exist
    required_columns = ['mode_id', 'auto_title', 'exported_at']
    print("\n🔍 CHECKING NEW COLUMNS IN CONVERSATIONS:")
    conv_column_names = [col[0] for col in conv_columns]
    for col in required_columns:
        if col in conv_column_names:
            print(f"  ✅ {col} - EXISTS")
        else:
            print(f"  ❌ {col} - MISSING")

    # Check indexes
    print("\n🔗 INDEXES:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    indexes = [row[0] for row in cursor.fetchall()]
    required_indexes = ['idx_mode_conversation', 'idx_mode_config', 'idx_mode_knowledge']
    for idx in required_indexes:
        if idx in indexes:
            print(f"  ✅ {idx} - EXISTS")
        else:
            print(f"  ❌ {idx} - MISSING")

    # Check default mode
    print("\n🎯 DEFAULT MODE:")
    cursor.execute("SELECT id, name, description, icon, is_default FROM conversation_modes WHERE is_default = TRUE")
    default_mode = cursor.fetchone()
    if default_mode:
        print(f"  ✅ Default mode exists:")
        print(f"     ID: {default_mode[0]}")
        print(f"     Name: {default_mode[1]}")
        print(f"     Description: {default_mode[2]}")
        print(f"     Icon: {default_mode[3]}")
    else:
        print("  ❌ No default mode found")

    # Check mode configuration
    print("\n⚙️  MODE CONFIGURATION:")
    cursor.execute("""
        SELECT mc.id, cm.name, mc.model, mc.temperature, mc.max_tokens, mc.system_prompt_tokens
        FROM mode_configuration mc
        JOIN conversation_modes cm ON mc.mode_id = cm.id
    """)
    configs = cursor.fetchall()
    if configs:
        for config in configs:
            print(f"  ✅ Configuration for '{config[1]}':")
            print(f"     Model: {config[2]}")
            print(f"     Temperature: {config[3]}")
            print(f"     Max Tokens: {config[4]}")
            print(f"     System Prompt Tokens: {config[5]}")
    else:
        print("  ❌ No mode configurations found")

    # Check how many conversations were updated
    print("\n💬 CONVERSATIONS WITH MODES:")
    cursor.execute("SELECT COUNT(*) FROM conversations WHERE mode_id IS NOT NULL")
    conv_with_mode = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM conversations")
    total_convs = cursor.fetchone()[0]
    print(f"  Total conversations: {total_convs}")
    print(f"  Conversations with mode: {conv_with_mode}")
    if total_convs > 0 and conv_with_mode == total_convs:
        print("  ✅ All conversations have a mode assigned")
    elif total_convs > 0:
        print(f"  ⚠️  {total_convs - conv_with_mode} conversations missing mode assignment")
    else:
        print("  ℹ️  No conversations in database yet")

    conn.close()

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    verify_migration()
