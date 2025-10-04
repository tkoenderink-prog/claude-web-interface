#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test API endpoints after v0.2 migration"""

import requests
import json

BASE_URL = 'http://127.0.0.1:5001'

def test_endpoints():
    """Test critical API endpoints"""

    print("=" * 60)
    print("Testing API Endpoints after Migration")
    print("=" * 60)

    # Create a session for cookie persistence
    session = requests.Session()

    # 1. Test login
    print("\n1. Testing login endpoint...")
    response = session.post(f'{BASE_URL}/api/auth/login', json={
        'username': 'user',
        'password': 'password'
    })
    if response.status_code == 200:
        print("   ✓ Login successful")
    else:
        print(f"   ✗ Login failed: {response.status_code}")
        return False

    # 2. Test conversations endpoint
    print("\n2. Testing conversations endpoint...")
    response = session.get(f'{BASE_URL}/api/conversations')
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Conversations endpoint working (found {len(data.get('conversations', []))} conversations)")
    else:
        print(f"   ✗ Conversations endpoint failed: {response.status_code}")
        print(f"   Error: {response.text[:200]}")

    # 3. Test knowledge structure
    print("\n3. Testing knowledge structure endpoint...")
    response = session.get(f'{BASE_URL}/api/knowledge/structure?vault=private')
    if response.status_code == 200:
        data = response.json()
        total_files = sum(len(cat.get('files', [])) for cat in data.get('categories', []))
        print(f"   ✓ Knowledge structure working (found {total_files} files)")
    else:
        print(f"   ✗ Knowledge structure failed: {response.status_code}")

    # 4. Test knowledge search
    print("\n4. Testing knowledge search endpoint...")
    response = session.post(f'{BASE_URL}/api/knowledge/search', json={
        'vault': 'private',
        'search': 'test',
        'category': 'all'
    })
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Knowledge search working (found {len(data.get('results', []))} results)")
    else:
        print(f"   ✗ Knowledge search failed: {response.status_code}")
        if response.status_code == 500:
            print(f"   Error: {response.text[:200]}")

    # 5. Test permissions endpoint
    print("\n5. Testing permissions endpoint...")
    response = session.get(f'{BASE_URL}/api/permissions')
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Permissions endpoint working")
        print(f"     - Read files: {data.get('read_files', False)}")
        print(f"     - Write files: {data.get('write_files', False)}")
        print(f"     - Bash: {data.get('bash', False)}")
    else:
        print(f"   ✗ Permissions endpoint failed: {response.status_code}")

    print("\n" + "=" * 60)
    print("API endpoint tests complete!")
    print("=" * 60)

    return True

if __name__ == "__main__":
    import sys
    import time

    print("Note: Make sure Flask app is running on port 5001")
    print("If not running, start it with:")
    print("  SERVER_PORT=5001 /opt/homebrew/opt/python@3.11/bin/python3.11 app.py")
    print("")

    # Give user time to read the message
    time.sleep(2)

    try:
        success = test_endpoints()
        sys.exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to Flask app at http://127.0.0.1:5001")
        print("   Please make sure the Flask app is running!")
        sys.exit(1)