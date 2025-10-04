#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Comprehensive test suite for Claude AI Web Interface v0.2 - Permission System

Tests the permission management features including:
- Default permission values
- Permission updates via API
- Write permission blocking (CRITICAL SECURITY TEST)
- Tool mapping correctness
- Permission persistence
- UI toggle states
"""

import unittest
import json
from pathlib import Path
from unittest.mock import Mock, patch

# Add the parent directory to the path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db
from models.models import User, UserPermissions
from services.permission_service import PermissionManager


class TestPermissionSystem(unittest.TestCase):
    """Test suite for the Permission Management System in v0.2"""

    def setUp(self):
        """Set up test environment before each test"""
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

        self.app = app
        self.client = app.test_client()

        # Create application context
        self.app_context = app.app_context()
        self.app_context.push()

        # Create all database tables
        db.create_all()

        # Create test user
        self.test_user = User(username='testuser', email='test@example.com')
        db.session.add(self.test_user)
        db.session.commit()

        # Initialize permission manager
        self.permission_manager = PermissionManager()

    def tearDown(self):
        """Clean up after each test"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_client(self):
        """Helper to login the test client"""
        response = self.client.post('/api/auth/login', json={})
        self.assertEqual(response.status_code, 200)
        return response

    def test_default_permission_values(self):
        """Test that default permission values are correctly set"""
        self.login_client()

        # Get permissions for new user
        response = self.client.get('/api/permissions')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('permissions', data)
        self.assertIn('permission_info', data)

        permissions = data['permissions']

        # Check default values
        expected_defaults = {
            'webSearch': False,       # Should be disabled by default
            'vaultSearch': True,      # Should be enabled by default
            'readFiles': True,        # Should be enabled by default
            'writeFiles': False       # CRITICAL: Should ALWAYS be False
        }

        for perm_name, expected_value in expected_defaults.items():
            self.assertIn(perm_name, permissions)
            self.assertEqual(permissions[perm_name], expected_value,
                           f"Default value for {perm_name} should be {expected_value}")

        # Verify permission info structure
        permission_info = data['permission_info']
        self.assertIn('permissions', permission_info)
        self.assertIn('core_tools', permission_info)

        # Check that each permission has tool mappings
        for perm_name in expected_defaults.keys():
            if perm_name in permission_info['permissions']:
                perm_info = permission_info['permissions'][perm_name]
                self.assertIn('tools', perm_info)
                self.assertIn('description', perm_info)
                self.assertIsInstance(perm_info['tools'], list)

    def test_permission_updates_via_api(self):
        """Test updating permissions through the API"""
        self.login_client()

        # Test updating valid permissions
        updates = {
            'webSearch': True,
            'vaultSearch': False,
            'readFiles': False
            # Note: NOT including writeFiles - should never be allowed
        }

        response = self.client.put('/api/permissions', json={
            'permissions': updates
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data['success'])
        self.assertIn('permissions', data)

        updated_permissions = data['permissions']

        # Check that allowed updates were applied
        self.assertEqual(updated_permissions['webSearch'], True)
        self.assertEqual(updated_permissions['vaultSearch'], False)
        self.assertEqual(updated_permissions['readFiles'], False)

        # CRITICAL: writeFiles should remain False
        self.assertEqual(updated_permissions['writeFiles'], False)

        # Verify in database
        user_permissions = UserPermissions.query.filter_by(user_id=self.test_user.id).first()
        if user_permissions:
            self.assertEqual(user_permissions.web_search, True)
            self.assertEqual(user_permissions.vault_search, False)
            self.assertEqual(user_permissions.read_files, False)
            self.assertEqual(user_permissions.write_files, False)

    def test_write_permission_blocking_critical(self):
        """CRITICAL SECURITY TEST: Ensure write permissions cannot be enabled"""
        self.login_client()

        # Attempt 1: Direct attempt to enable write permissions
        response = self.client.put('/api/permissions', json={
            'permissions': {
                'writeFiles': True
            }
        })

        # Should be explicitly blocked
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)
        self.assertIn('Write permissions cannot be enabled', data['error'])

        # Attempt 2: Try to sneak it in with other permissions
        response = self.client.put('/api/permissions', json={
            'permissions': {
                'webSearch': True,
                'writeFiles': True,  # This should be blocked
                'readFiles': True
            }
        })

        # Should still be blocked
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertFalse(data['success'])

        # Attempt 3: Verify current permissions are still safe
        response = self.client.get('/api/permissions')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['permissions']['writeFiles'], False)

        # Attempt 4: Try direct database manipulation
        user_permissions = UserPermissions.query.filter_by(user_id=self.test_user.id).first()
        if not user_permissions:
            user_permissions = UserPermissions(user_id=self.test_user.id)
            db.session.add(user_permissions)

        user_permissions.write_files = True
        db.session.commit()

        # Even if database is manually modified, API should override
        response = self.client.get('/api/permissions')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        # The permission manager should still return False for write_files
        self.assertEqual(data['permissions']['writeFiles'], False)

    def test_tool_mapping_correctness(self):
        """Test that permission-to-tool mappings are correct"""
        self.login_client()

        # Get permission info
        response = self.client.get('/api/permissions/info')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        permission_info = data['info']

        # Verify expected tool mappings
        expected_mappings = {
            'webSearch': ['WebSearch', 'WebFetch'],
            'vaultSearch': ['Grep', 'Glob'],
            'readFiles': ['Read'],
            'writeFiles': ['Write', 'Edit', 'MultiEdit', 'NotebookEdit']
        }

        for perm_name, expected_tools in expected_mappings.items():
            if perm_name in permission_info['permissions']:
                actual_tools = permission_info['permissions'][perm_name]['tools']
                for tool in expected_tools:
                    self.assertIn(tool, actual_tools,
                                f"Tool {tool} should be mapped to permission {perm_name}")

        # Verify core tools are present
        self.assertIn('core_tools', permission_info)
        core_tools = permission_info['core_tools']
        expected_core_tools = ['Bash', 'TodoWrite']

        for tool in expected_core_tools:
            self.assertIn(tool, core_tools,
                        f"Core tool {tool} should always be available")

    def test_get_allowed_tools_endpoint(self):
        """Test the allowed tools endpoint"""
        self.login_client()

        # Test with default permissions
        response = self.client.get('/api/permissions/tools')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data['success'])
        self.assertIn('allowed_tools', data)

        allowed_tools = data['allowed_tools']
        self.assertIsInstance(allowed_tools, list)

        # Should include core tools
        self.assertIn('Bash', allowed_tools)
        self.assertIn('TodoWrite', allowed_tools)

        # Should include read tools (default enabled)
        self.assertIn('Read', allowed_tools)
        self.assertIn('Grep', allowed_tools)
        self.assertIn('Glob', allowed_tools)

        # Should NOT include write tools (default disabled)
        self.assertNotIn('Write', allowed_tools)
        self.assertNotIn('Edit', allowed_tools)
        self.assertNotIn('MultiEdit', allowed_tools)

        # Should NOT include web tools (default disabled)
        self.assertNotIn('WebSearch', allowed_tools)
        self.assertNotIn('WebFetch', allowed_tools)

    def test_permission_persistence(self):
        """Test that permissions persist across sessions"""
        self.login_client()

        # Update permissions
        initial_updates = {
            'webSearch': True,
            'vaultSearch': False
        }

        response = self.client.put('/api/permissions', json={
            'permissions': initial_updates
        })

        self.assertEqual(response.status_code, 200)

        # Simulate logout/login by creating new client session
        new_client = app.test_client()
        new_client.post('/api/auth/login', json={})

        # Check that permissions persisted
        response = new_client.get('/api/permissions')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        permissions = data['permissions']
        self.assertEqual(permissions['webSearch'], True)
        self.assertEqual(permissions['vaultSearch'], False)
        self.assertEqual(permissions['writeFiles'], False)  # Should remain False

    def test_permission_validation(self):
        """Test permission validation and error handling"""
        self.login_client()

        # Test invalid permission names
        response = self.client.put('/api/permissions', json={
            'permissions': {
                'invalidPermission': True
            }
        })

        # Should handle gracefully (might succeed but ignore invalid perms)
        self.assertIn(response.status_code, [200, 400])

        # Test invalid permission values
        response = self.client.put('/api/permissions', json={
            'permissions': {
                'webSearch': 'invalid_value'
            }
        })

        # Should handle gracefully
        self.assertIn(response.status_code, [200, 400])

        # Test missing permissions object
        response = self.client.put('/api/permissions', json={})
        self.assertEqual(response.status_code, 400)

        # Test malformed JSON
        response = self.client.put('/api/permissions',
                                 data='invalid json',
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_permission_manager_direct_access(self):
        """Test PermissionManager class directly"""
        # Test default permissions for new user
        permissions = self.permission_manager.get_user_permissions(self.test_user.id)

        expected_defaults = {
            'webSearch': False,
            'vaultSearch': True,
            'readFiles': True,
            'writeFiles': False
        }

        for perm_name, expected_value in expected_defaults.items():
            self.assertEqual(permissions[perm_name], expected_value)

        # Test permission updates
        updates = {
            'webSearch': True,
            'readFiles': False
        }

        success = self.permission_manager.update_user_permissions(self.test_user.id, updates)
        self.assertTrue(success)

        # Verify updates
        updated_permissions = self.permission_manager.get_user_permissions(self.test_user.id)
        self.assertEqual(updated_permissions['webSearch'], True)
        self.assertEqual(updated_permissions['readFiles'], False)
        self.assertEqual(updated_permissions['writeFiles'], False)  # Should remain False

        # Test write permission blocking at manager level
        write_updates = {'writeFiles': True}
        # This should be blocked at the manager level or handled gracefully
        result = self.permission_manager.update_user_permissions(self.test_user.id, write_updates)
        # Regardless of result, writeFiles should remain False
        final_permissions = self.permission_manager.get_user_permissions(self.test_user.id)
        self.assertEqual(final_permissions['writeFiles'], False)

    def test_allowed_tools_calculation(self):
        """Test calculation of allowed tools based on permissions"""
        # Set specific permissions
        updates = {
            'webSearch': True,
            'vaultSearch': True,
            'readFiles': False,
            'writeFiles': False
        }

        self.permission_manager.update_user_permissions(self.test_user.id, updates)

        # Get allowed tools
        allowed_tools = self.permission_manager.get_allowed_tools(self.test_user.id)

        # Should include web search tools
        self.assertIn('WebSearch', allowed_tools)
        self.assertIn('WebFetch', allowed_tools)

        # Should include vault search tools
        self.assertIn('Grep', allowed_tools)
        self.assertIn('Glob', allowed_tools)

        # Should NOT include read tools (disabled)
        self.assertNotIn('Read', allowed_tools)

        # Should NOT include write tools (disabled)
        self.assertNotIn('Write', allowed_tools)
        self.assertNotIn('Edit', allowed_tools)

        # Should always include core tools
        self.assertIn('Bash', allowed_tools)
        self.assertIn('TodoWrite', allowed_tools)

    def test_permission_info_structure(self):
        """Test the structure of permission information"""
        permission_info = self.permission_manager.get_permission_info()

        # Check top-level structure
        self.assertIn('permissions', permission_info)
        self.assertIn('core_tools', permission_info)

        # Check individual permission structure
        for perm_name, perm_data in permission_info['permissions'].items():
            self.assertIn('tools', perm_data)
            self.assertIn('description', perm_data)
            self.assertIn('category', perm_data)

            # Tools should be a list
            self.assertIsInstance(perm_data['tools'], list)

            # Description should be a string
            self.assertIsInstance(perm_data['description'], str)
            self.assertGreater(len(perm_data['description']), 0)

        # Core tools should be a list
        self.assertIsInstance(permission_info['core_tools'], list)
        self.assertGreater(len(permission_info['core_tools']), 0)

    def test_concurrent_permission_updates(self):
        """Test concurrent permission updates"""
        import threading
        import queue

        results = queue.Queue()
        errors = queue.Queue()

        def update_permissions(update_id):
            try:
                updates = {
                    'webSearch': update_id % 2 == 0,  # Alternate True/False
                    'vaultSearch': True
                }
                success = self.permission_manager.update_user_permissions(self.test_user.id, updates)
                results.put((update_id, success))
            except Exception as e:
                errors.put((update_id, str(e)))

        # Start multiple update threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_permissions, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check results
        self.assertEqual(results.qsize(), 5)
        self.assertEqual(errors.qsize(), 0)

        # Verify final state is consistent
        final_permissions = self.permission_manager.get_user_permissions(self.test_user.id)
        self.assertIn(final_permissions['webSearch'], [True, False])  # Should be one or the other
        self.assertEqual(final_permissions['vaultSearch'], True)  # Should be True from all updates
        self.assertEqual(final_permissions['writeFiles'], False)  # Should always be False

    def test_user_permissions_model(self):
        """Test the UserPermissions database model"""
        # Create user permissions
        user_perms = UserPermissions(
            user_id=self.test_user.id,
            web_search=True,
            vault_search=False,
            read_files=True,
            write_files=False
        )

        db.session.add(user_perms)
        db.session.commit()

        # Retrieve and verify
        retrieved = UserPermissions.query.filter_by(user_id=self.test_user.id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.web_search, True)
        self.assertEqual(retrieved.vault_search, False)
        self.assertEqual(retrieved.read_files, True)
        self.assertEqual(retrieved.write_files, False)

        # Test to_dict method if it exists
        if hasattr(retrieved, 'to_dict'):
            perm_dict = retrieved.to_dict()
            self.assertIsInstance(perm_dict, dict)
            self.assertIn('web_search', perm_dict)

    def test_authentication_required(self):
        """Test that permission endpoints require authentication"""
        # Don't login - test unauthenticated access

        # Test GET permissions
        response = self.client.get('/api/permissions')
        self.assertIn(response.status_code, [401, 302])  # Unauthorized or redirect to login

        # Test PUT permissions
        response = self.client.put('/api/permissions', json={
            'permissions': {'webSearch': True}
        })
        self.assertIn(response.status_code, [401, 302])

        # Test permission info
        response = self.client.get('/api/permissions/info')
        self.assertIn(response.status_code, [401, 302])

        # Test allowed tools
        response = self.client.get('/api/permissions/tools')
        self.assertIn(response.status_code, [401, 302])


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)