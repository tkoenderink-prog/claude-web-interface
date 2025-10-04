#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Fix knowledge issues:
1. Update existing records with 0 tokens to have actual token counts
2. Check for issues in the frontend
"""

import sqlite3
import sys
import os

# Add web-interface to path if needed
if os.path.exists('web-interface'):
    os.chdir('web-interface')
elif os.path.exists('../web-interface'):
    os.chdir('../web-interface')

# Import the services
sys.path.insert(0, '.')
from services.token_service import get_token_service
from services.obsidian_service import get_obsidian_service

def update_token_counts():
    """Update token counts for existing knowledge entries"""
    print("=" * 60)
    print("Updating Token Counts for Existing Knowledge")
    print("=" * 60)

    token_service = get_token_service()
    obsidian_service = get_obsidian_service()

    conn = sqlite3.connect('data/claude_clone.db')
    cursor = conn.cursor()

    # Get all project_knowledge records with 0 or NULL token count
    cursor.execute("""
        SELECT id, vault_type, file_path
        FROM project_knowledge
        WHERE token_count IS NULL OR token_count = 0
    """)

    records = cursor.fetchall()
    print(f"Found {len(records)} records to update")

    updated = 0
    failed = 0

    for pk_id, vault_type, file_path in records:
        try:
            # Get the file content
            content = obsidian_service.get_file_content_sync(vault_type, file_path)

            if content:
                # Estimate tokens
                result = token_service.estimate_text_tokens(content)
                token_count = result['token_count']

                # Update database
                cursor.execute("""
                    UPDATE project_knowledge
                    SET token_count = ?
                    WHERE id = ?
                """, (token_count, pk_id))

                updated += 1
                print(f"  ✓ Updated {file_path}: {token_count} tokens")
            else:
                print(f"  ⚠️  No content found for {file_path}")
                failed += 1

        except Exception as e:
            print(f"  ✗ Failed to update {file_path}: {e}")
            failed += 1

    # Commit changes
    conn.commit()
    conn.close()

    print(f"\nSummary:")
    print(f"  Updated: {updated}")
    print(f"  Failed: {failed}")

    return updated > 0

def check_frontend_issues():
    """Check for common frontend issues"""
    print("\n" + "=" * 60)
    print("Checking Frontend Issues")
    print("=" * 60)

    # Check if the app.js file has the correct event listeners
    with open('static/js/app.js', 'r') as f:
        js_content = f.read()

    issues = []

    # Check for Select All functionality
    if 'selectAllKnowledge' not in js_content:
        issues.append("selectAllKnowledge element not referenced")

    if 'this.knowledgeSelector.selectAll()' not in js_content:
        issues.append("selectAll() method not called correctly")

    # Check for token display updates
    if 'updateTokenDisplay' not in js_content:
        issues.append("Token display update logic missing")

    # Check for bulk add button
    if 'bulkAddBtn' not in js_content:
        issues.append("Bulk add button not properly referenced")

    if issues:
        print("Found issues:")
        for issue in issues:
            print(f"  ✗ {issue}")
    else:
        print("  ✓ Frontend code structure looks correct")

    # Check if event listener is properly attached
    if "document.getElementById('selectAllKnowledge').addEventListener" in js_content:
        print("  ✓ Select All event listener is attached")
    else:
        print("  ✗ Select All event listener missing")

    return len(issues) == 0

def main():
    print("Claude AI Web Interface - Knowledge Issues Fixer")
    print("=" * 60)

    # Update token counts in database
    token_update_success = update_token_counts()

    # Check frontend issues
    frontend_ok = check_frontend_issues()

    print("\n" + "=" * 60)
    print("Fix Complete")
    print("=" * 60)

    if token_update_success:
        print("\n✅ Token counts have been updated in the database")
        print("   Restart your Flask app to see the changes")
    else:
        print("\n⚠️  No token counts were updated")

    if not frontend_ok:
        print("\n⚠️  Some frontend issues were detected")
        print("   Check the output above for details")

    return 0 if (token_update_success and frontend_ok) else 1

if __name__ == "__main__":
    sys.exit(main())