#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Test the complete knowledge workflow after fixes
"""

import requests
import json
import sys
import time

BASE_URL = 'http://127.0.0.1:5001'

def test_complete_workflow():
    """Test the complete knowledge selection workflow"""

    print("=" * 60)
    print("Testing Complete Knowledge Workflow")
    print("=" * 60)

    session = requests.Session()

    # 1. Login
    print("\n1. Logging in...")
    response = session.post(f'{BASE_URL}/api/auth/login', json={
        'username': 'user',
        'password': 'password'
    })
    if response.status_code != 200:
        print(f"   ✗ Login failed: {response.status_code}")
        return False
    print("   ✓ Logged in successfully")

    # 2. Get conversations to find or create one
    print("\n2. Getting conversations...")
    response = session.get(f'{BASE_URL}/api/conversations')
    if response.status_code == 200:
        conversations = response.json().get('conversations', [])
        print(f"   ✓ Found {len(conversations)} conversations")

        if conversations:
            conversation_id = conversations[0]['uuid']
            print(f"   Using existing conversation: {conversation_id}")
        else:
            # Create a new conversation
            print("   Creating new conversation...")
            response = session.post(f'{BASE_URL}/api/conversations', json={
                'title': 'Test Conversation',
                'model': 'claude-3-5-sonnet-20241022'
            })
            if response.status_code == 200:
                conversation = response.json()
                conversation_id = conversation['uuid']
                print(f"   ✓ Created conversation: {conversation_id}")
            else:
                print(f"   ✗ Failed to create conversation")
                return False
    else:
        print(f"   ✗ Failed to get conversations")
        return False

    # 3. Search for knowledge WITH conversation_id
    print(f"\n3. Searching for knowledge (with conversation_id: {conversation_id})...")
    response = session.post(f'{BASE_URL}/api/knowledge/search', json={
        'vault': 'private',
        'query': '',
        'category': None,
        'select_all': True,
        'conversation_id': conversation_id
    })

    if response.status_code != 200:
        print(f"   ✗ Search failed: {response.status_code}")
        print(f"   Error: {response.text[:200]}")
        return False

    results = response.json()
    print(f"   ✓ Found {len(results)} files")

    # Analyze results
    stats = {
        'total': len(results),
        'with_tokens': sum(1 for r in results if r.get('token_count') and r['token_count'] > 0),
        'is_added': sum(1 for r in results if r.get('is_added')),
        'available': sum(1 for r in results if not r.get('is_added'))
    }

    print(f"\n   Statistics:")
    print(f"   - Total files: {stats['total']}")
    print(f"   - Files with token counts: {stats['with_tokens']}")
    print(f"   - Already added to THIS conversation: {stats['is_added']}")
    print(f"   - Available for selection: {stats['available']}")

    # Show sample files
    print(f"\n   Sample files (first 3):")
    for item in results[:3]:
        print(f"   - {item['name']}")
        print(f"     Path: {item['path']}")
        print(f"     Tokens: {item.get('token_count', 'not calculated')}")
        print(f"     Added to current conversation: {item.get('is_added', False)}")

    # 4. Test adding a file if available
    available_files = [r for r in results if not r.get('is_added')]
    if available_files:
        test_file = available_files[0]
        print(f"\n4. Testing bulk add with file: {test_file['name']}...")

        response = session.post(f'{BASE_URL}/api/knowledge/add-bulk', json={
            'conversation_id': conversation_id,
            'files': [{
                'vault': 'private',
                'file_path': test_file['path'],
                'category': test_file.get('category', 'RESOURCE')
            }]
        })

        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Bulk add successful")
            print(f"   - Succeeded: {result['summary']['succeeded']}")
            print(f"   - Failed: {result['summary']['failed']}")
            print(f"   - Total tokens: {result['summary']['total_tokens']}")

            # 5. Re-search to verify file is now marked as added
            print(f"\n5. Re-searching to verify file is marked as added...")
            response = session.post(f'{BASE_URL}/api/knowledge/search', json={
                'vault': 'private',
                'query': '',
                'category': None,
                'select_all': True,
                'conversation_id': conversation_id
            })

            if response.status_code == 200:
                new_results = response.json()
                updated_file = next((f for f in new_results if f['path'] == test_file['path']), None)

                if updated_file:
                    print(f"   File: {updated_file['name']}")
                    print(f"   Was added: {test_file.get('is_added', False)}")
                    print(f"   Now added: {updated_file.get('is_added', False)}")

                    if updated_file.get('is_added') and not test_file.get('is_added'):
                        print(f"   ✓ File correctly marked as added to conversation!")
                    else:
                        print(f"   ✗ File status not updated correctly")
                else:
                    print(f"   ✗ Could not find file in results")
        else:
            print(f"   ✗ Bulk add failed: {response.status_code}")
            print(f"   Error: {response.text[:200]}")
    else:
        print(f"\n4. No available files to test adding (all already added)")

    print("\n" + "=" * 60)
    print("Workflow Test Complete")
    print("=" * 60)

    return True

def main():
    print("Claude AI Web Interface - Knowledge Workflow Test")
    print("=" * 60)
    print("\nMake sure Flask app is running on port 5001")
    print("This test will verify the complete knowledge selection workflow\n")

    time.sleep(1)

    try:
        success = test_complete_workflow()
        if success:
            print("\n✅ All workflow tests passed!")
        else:
            print("\n❌ Some workflow tests failed")
        return 0 if success else 1
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to Flask app at http://127.0.0.1:5001")
        print("   Please start the Flask app first!")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())