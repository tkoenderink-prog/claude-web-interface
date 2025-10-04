#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test script for permission system."""

import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set Flask app before imports
os.environ['FLASK_APP'] = 'app.py'

from app import app, db
from models.models import User, UserPermissions
from services.permission_service import get_permission_manager

def test_database_migration():
    """Test database migration and model creation."""
    print("Testing database migration...")

    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✓ Database tables created successfully")

            # Check if UserPermissions table exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            if 'user_permissions' in tables:
                print("✓ UserPermissions table exists")
            else:
                print("✗ UserPermissions table missing")
                return False

            return True

        except Exception as e:
            print(f"✗ Database migration failed: {e}")
            return False

def test_permission_manager():
    """Test permission manager functionality."""
    print("\nTesting permission manager...")

    with app.app_context():
        try:
            permission_manager = get_permission_manager()

            # Test permission info
            info = permission_manager.get_permission_info()
            print(f"✓ Permission info loaded: {len(info['permissions'])} permissions available")

            # Test default permissions for non-existent user
            perms = permission_manager.get_user_permissions(999)  # Non-existent user
            print(f"✓ Default permissions work: {perms}")

            # Test tool mapping
            tools = permission_manager.get_allowed_tools(999)
            print(f"✓ Tool mapping works: {len(tools)} tools allowed by default")

            # Test forbidden tools are not included
            forbidden_found = any(tool in permission_manager.FORBIDDEN_TOOLS for tool in tools)
            if not forbidden_found:
                print("✓ Forbidden tools correctly excluded")
            else:
                print("✗ Forbidden tools found in allowed list")
                return False

            # Test write permissions are always false
            if not perms.get('writeFiles', True):  # Should be False
                print("✓ Write permissions correctly disabled")
            else:
                print("✗ Write permissions not properly disabled")
                return False

            return True

        except Exception as e:
            print(f"✗ Permission manager test failed: {e}")
            return False

def test_user_permissions_model():
    """Test UserPermissions model with safety checks."""
    print("\nTesting UserPermissions model...")

    with app.app_context():
        try:
            # Get or create test user
            user = User.query.first()
            if not user:
                user = User(username='test_user', email='test@example.com')
                db.session.add(user)
                db.session.commit()
                print("✓ Test user created")

            # Get or create user permissions
            user_perms = UserPermissions.query.filter_by(user_id=user.id).first()

            if not user_perms:
                # Test creating permissions with write=True (should be forced to False)
                user_perms = UserPermissions(
                    user_id=user.id,
                    web_search=True,
                    vault_search=True,
                    read_files=True,
                    write_files=True  # This should be forced to False
                )

                db.session.add(user_perms)
                db.session.commit()

            # Reload and check
            user_perms = UserPermissions.query.filter_by(user_id=user.id).first()

            if not user_perms.write_files:
                print("✓ Write permissions correctly forced to False in model")
            else:
                print("✗ Write permissions not forced to False in model")
                return False

            print(f"✓ User permissions created: {user_perms}")

            return True

        except Exception as e:
            print(f"✗ UserPermissions model test failed: {e}")
            return False

def test_permission_validation():
    """Test permission validation and safety checks."""
    print("\nTesting permission validation...")

    with app.app_context():
        try:
            permission_manager = get_permission_manager()
            user = User.query.first()

            if not user:
                print("✗ No test user found")
                return False

            # Test valid permission update
            success = permission_manager.update_user_permissions(user.id, {
                'webSearch': True,
                'vaultSearch': True,
                'readFiles': True,
                'writeFiles': False
            })

            if success:
                print("✓ Valid permission update successful")
            else:
                print("✗ Valid permission update failed")
                return False

            # Test blocked write permission update
            success = permission_manager.update_user_permissions(user.id, {
                'writeFiles': True  # This should be blocked
            })

            if not success:
                print("✓ Write permission update correctly blocked")
            else:
                print("✗ Write permission update not blocked")
                return False

            # Verify write permissions are still False
            perms = permission_manager.get_user_permissions(user.id)
            if not perms['writeFiles']:
                print("✓ Write permissions remain False after blocked update")
            else:
                print("✗ Write permissions incorrectly set to True")
                return False

            return True

        except Exception as e:
            print(f"✗ Permission validation test failed: {e}")
            return False

def test_tool_mappings():
    """Test tool mappings and tool access."""
    print("\nTesting tool mappings...")

    with app.app_context():
        try:
            permission_manager = get_permission_manager()

            # Test that correct tools are mapped
            mapping = permission_manager.PERMISSION_MAPPING

            # Check that webSearch maps to web tools
            if 'WebSearch' in mapping['webSearch'] and 'WebFetch' in mapping['webSearch']:
                print("✓ Web search tools correctly mapped")
            else:
                print("✗ Web search tools not correctly mapped")
                return False

            # Check that vault search maps to search tools
            if 'Grep' in mapping['vaultSearch'] and 'Glob' in mapping['vaultSearch']:
                print("✓ Vault search tools correctly mapped")
            else:
                print("✗ Vault search tools not correctly mapped")
                return False

            # Check that readFiles maps to Read tool
            if 'Read' in mapping['readFiles']:
                print("✓ Read files tool correctly mapped")
            else:
                print("✗ Read files tool not correctly mapped")
                return False

            # Check that writeFiles mapping is empty
            if not mapping['writeFiles']:
                print("✓ Write files mapping correctly empty")
            else:
                print("✗ Write files mapping not empty")
                return False

            return True

        except Exception as e:
            print(f"✗ Tool mapping test failed: {e}")
            return False

def main():
    """Run all tests."""
    print("🔒 Permission System Test Suite")
    print("=" * 50)

    tests = [
        test_database_migration,
        test_permission_manager,
        test_user_permissions_model,
        test_permission_validation,
        test_tool_mappings
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! Permission system is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)