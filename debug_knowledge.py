#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Debug script for knowledge search and token counting"""

import sys
import os
import sqlite3

# Add web-interface to path if needed
if os.path.exists('web-interface'):
    os.chdir('web-interface')
elif os.path.exists('../web-interface'):
    os.chdir('../web-interface')

# Import the token service
sys.path.insert(0, '.')
from services.token_service import get_token_service, TokenEstimationError

def test_token_service():
    """Test if token service is working"""
    print("=" * 60)
    print("Testing Token Service")
    print("=" * 60)

    try:
        token_service = get_token_service()

        # Test with sample text
        test_text = "This is a test sentence to verify token counting works."
        result = token_service.estimate_text_tokens(test_text)

        print(f"✓ Token service initialized successfully")
        print(f"  Test text: '{test_text}'")
        print(f"  Estimated tokens: {result['token_count']}")
        print(f"  Cached: {result.get('cached', False)}")

        return True

    except Exception as e:
        print(f"✗ Token service failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_database_content():
    """Check what's in the database"""
    print("\n" + "=" * 60)
    print("Database Content Check")
    print("=" * 60)

    conn = sqlite3.connect('data/claude_clone.db')
    cursor = conn.cursor()

    # Check project_knowledge table
    cursor.execute("""
        SELECT COUNT(*),
               COUNT(token_count),
               SUM(CASE WHEN token_count IS NOT NULL AND token_count > 0 THEN 1 ELSE 0 END),
               MIN(token_count),
               MAX(token_count)
        FROM project_knowledge
    """)
    total, with_token, with_positive_tokens, min_tokens, max_tokens = cursor.fetchone()

    print(f"Project Knowledge Table:")
    print(f"  Total records: {total}")
    print(f"  Records with token_count field: {with_token}")
    print(f"  Records with positive tokens: {with_positive_tokens}")
    print(f"  Min tokens: {min_tokens}")
    print(f"  Max tokens: {max_tokens}")

    # Get sample of records
    cursor.execute("""
        SELECT file_path, token_count
        FROM project_knowledge
        LIMIT 5
    """)

    print("\nSample records:")
    for path, tokens in cursor.fetchall():
        print(f"  - {path}: {tokens} tokens")

    conn.close()

def test_api_search():
    """Test the knowledge search API directly"""
    print("\n" + "=" * 60)
    print("Testing Knowledge Search API")
    print("=" * 60)

    import requests

    # Login first
    session = requests.Session()
    login_response = session.post('http://127.0.0.1:5001/api/auth/login', json={
        'username': 'user',
        'password': 'password'
    })

    if login_response.status_code != 200:
        print("✗ Failed to login")
        return

    print("✓ Logged in successfully")

    # Search for knowledge
    search_response = session.post('http://127.0.0.1:5001/api/knowledge/search', json={
        'vault': 'private',
        'query': '',
        'category': 'all'
    })

    if search_response.status_code == 200:
        results = search_response.json()
        print(f"✓ Search returned {len(results)} results")

        # Check token counts
        with_tokens = sum(1 for r in results if r.get('token_count') and r['token_count'] > 0)
        added = sum(1 for r in results if r.get('is_added'))

        print(f"  Files with token counts: {with_tokens}/{len(results)}")
        print(f"  Files marked as added: {added}/{len(results)}")

        # Show first 3 results
        print("\nFirst 3 results:")
        for item in results[:3]:
            print(f"  - {item['name']}")
            print(f"    Path: {item['path']}")
            print(f"    Tokens: {item.get('token_count', 'None')}")
            print(f"    Added: {item.get('is_added', False)}")
    else:
        print(f"✗ Search failed with status {search_response.status_code}")
        print(f"  Error: {search_response.text[:200]}")

def main():
    print("Claude AI Web Interface - Knowledge Debug Tool")
    print("=" * 60)

    # Run tests
    token_ok = test_token_service()
    check_database_content()

    # Only test API if Flask is running
    try:
        test_api_search()
    except requests.exceptions.ConnectionError:
        print("\nNote: Flask app not running, skipping API test")
        print("Start it with: SERVER_PORT=5001 python3.11 app.py")

    print("\n" + "=" * 60)
    print("Debug Complete")
    print("=" * 60)

    if not token_ok:
        print("\n⚠️  Token service is not working properly!")
        print("This is likely causing the token count issues.")

if __name__ == "__main__":
    import requests
    main()