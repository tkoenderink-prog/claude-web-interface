#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Comprehensive test suite for Claude AI Web Interface v0.2 - Integration Tests

Tests the integration between all v0.2 systems including:
- Full workflow: Login → Add Knowledge → Send Message with Permissions
- Interaction between all new systems
- Database integrity
- Session management
- Error handling across features
"""

import unittest
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from io import BytesIO

# Add the parent directory to the path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db, socketio
from models.models import (
    User, Conversation, Message, ProjectKnowledge,
    ConversationKnowledge, TokenCache, UserPermissions
)


class TestV02Integration(unittest.TestCase):
    """Integration test suite for Claude AI Web Interface v0.2"""

    def setUp(self):
        """Set up test environment before each test"""
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['ENABLE_PROJECT_KNOWLEDGE'] = True

        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        app.config['UPLOAD_FOLDER'] = self.temp_dir
        app.config['ALLOWED_EXTENSIONS'] = {'txt', 'md', 'pdf', 'docx', 'csv', 'json'}

        # Create vault directories
        self.private_vault = self.temp_dir / 'vault' / 'private'
        self.poa_vault = self.temp_dir / 'vault' / 'poa'
        self.private_vault.mkdir(parents=True)
        self.poa_vault.mkdir(parents=True)

        app.config['OBSIDIAN_PRIVATE_PATH'] = str(self.private_vault)
        app.config['OBSIDIAN_POA_PATH'] = str(self.poa_vault)

        self.app = app
        self.client = app.test_client()
        self.socketio_client = socketio.test_client(app)

        # Create application context
        self.app_context = app.app_context()
        self.app_context.push()

        # Create all database tables
        db.create_all()

        # Create test data
        self.create_test_data()

    def tearDown(self):
        """Clean up after each test"""
        if hasattr(self, 'socketio_client'):
            self.socketio_client.disconnect()

        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        # Clean up temp directory
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def create_test_data(self):
        """Create test data for integration tests"""
        # Create test user
        self.test_user = User(username='integrationtest', email='integration@test.com')
        db.session.add(self.test_user)
        db.session.commit()

        # Create test conversation
        self.test_conversation = Conversation(
            uuid='integration-conv-123',
            title='Integration Test Conversation',
            user_id=self.test_user.id,
            model='sonnet-4.5'
        )
        db.session.add(self.test_conversation)
        db.session.commit()

        # Create test vault files
        self.create_test_vault_files()

    def create_test_vault_files(self):
        """Create test files in vault directories"""
        test_files = [
            ("projects/integration_project.md", "# Integration Project\nThis project tests system integration."),
            ("areas/integration_area.md", "# Integration Area\nArea for testing integrations."),
            ("resources/integration_resource.md", "# Integration Resource\nResource for integration testing."),
            ("notes/integration_note.md", "# Integration Note\nGeneral note for testing."),
        ]

        for file_path, content in test_files:
            full_path = self.private_vault / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

    def login_user(self):
        """Helper to login user and return response"""
        response = self.client.post('/api/auth/login', json={})
        self.assertEqual(response.status_code, 200)
        return json.loads(response.data)

    def test_full_workflow_login_to_message(self):
        """Test complete workflow from login to sending message with all v0.2 features"""

        # Step 1: Login
        login_data = self.login_user()
        self.assertTrue(login_data['success'])
        self.assertIn('user', login_data)

        # Step 2: Get and configure permissions
        perm_response = self.client.get('/api/permissions')
        self.assertEqual(perm_response.status_code, 200)
        perm_data = json.loads(perm_response.data)

        # Enable web search and keep others as default
        perm_update = self.client.put('/api/permissions', json={
            'permissions': {
                'webSearch': True,
                'vaultSearch': True,
                'readFiles': True
                # writeFiles intentionally omitted - should remain False
            }
        })
        self.assertEqual(perm_update.status_code, 200)

        # Step 3: Search and add knowledge via bulk operation
        search_response = self.client.post('/api/knowledge/search', json={
            'vault': 'private',
            'query': '',
            'select_all': True
        })
        self.assertEqual(search_response.status_code, 200)
        search_data = json.loads(search_response.data)
        self.assertGreater(len(search_data), 0)

        # Select first 3 files for bulk add
        files_to_add = []
        for i, file_info in enumerate(search_data[:3]):
            files_to_add.append({
                'vault': 'private',
                'file_path': file_info['path'],
                'category': file_info.get('category', 'RESOURCE')
            })

        bulk_add_response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': files_to_add
        })
        self.assertEqual(bulk_add_response.status_code, 200)
        bulk_data = json.loads(bulk_add_response.data)
        self.assertTrue(bulk_data['success'])
        self.assertEqual(bulk_data['summary']['succeeded'], 3)

        # Step 4: Upload a file
        test_content = "Integration test file content for comprehensive testing."
        test_file = BytesIO(test_content.encode('utf-8'))
        test_file.name = 'integration_test.txt'

        upload_response = self.client.post('/api/upload',
            data={'file': (test_file, 'integration_test.txt')},
            content_type='multipart/form-data'
        )
        self.assertEqual(upload_response.status_code, 200)
        upload_data = json.loads(upload_response.data)
        self.assertTrue(upload_data['success'])

        # Step 5: Get token estimates for conversation
        token_response = self.client.post('/api/tokens/conversation', json={
            'conversation_id': self.test_conversation.uuid
        })
        self.assertEqual(token_response.status_code, 200)
        token_data = json.loads(token_response.data)
        total_tokens = token_data['estimation']['total_tokens']

        # Step 6: Get allowed tools based on permissions
        tools_response = self.client.get('/api/permissions/tools')
        self.assertEqual(tools_response.status_code, 200)
        tools_data = json.loads(tools_response.data)
        allowed_tools = tools_data['allowed_tools']

        # Should include web search tools (enabled) but not write tools
        self.assertIn('WebSearch', allowed_tools)
        self.assertIn('Read', allowed_tools)
        self.assertNotIn('Write', allowed_tools)

        # Step 7: Send message with all file data
        with patch('app.claude_service') as mock_claude:
            # Mock streaming response
            async def mock_stream():
                chunks = [
                    "Thank you for the integration test. ",
                    "I can see you've attached ",
                    f"{len(files_to_add)} knowledge files ",
                    "and 1 uploaded file. ",
                    f"The total context is approximately {total_tokens} tokens. ",
                    "This integration test is working well!"
                ]
                for chunk in chunks:
                    yield chunk

            mock_claude.create_message.return_value = mock_stream()

            message_data = {
                'content': 'Please analyze the attached files and provide insights.',
                'knowledge_files': [f['file_path'] for f in files_to_add],
                'upload_files': [upload_data['file_id']],
                'total_tokens': total_tokens,
                'allowed_tools': allowed_tools
            }

            message_response = self.client.post(
                f'/api/conversations/{self.test_conversation.uuid}/messages',
                json=message_data
            )

            self.assertEqual(message_response.status_code, 200)
            message_response_data = json.loads(message_response.data)

            # Verify message was created properly
            self.assertIn('content', message_response_data)
            self.assertEqual(message_response_data['role'], 'assistant')
            self.assertGreater(len(message_response_data['content']), 0)

        # Step 8: Verify database integrity
        self.verify_database_integrity()

        # Step 9: Verify conversation state
        conv_response = self.client.get(f'/api/conversations/{self.test_conversation.uuid}')
        self.assertEqual(conv_response.status_code, 200)
        conv_data = json.loads(conv_response.data)

        # Should have user message and assistant response
        self.assertGreaterEqual(len(conv_data['messages']), 2)

    def test_cross_system_interaction(self):
        """Test interaction between token system, permissions, and knowledge management"""
        self.login_user()

        # Test permission changes affecting token calculations
        # 1. Add knowledge with default permissions
        initial_knowledge = {
            'conversation_id': self.test_conversation.uuid,
            'vault': 'private',
            'file_path': 'projects/integration_project.md',
            'category': 'PROJECT'
        }

        add_response = self.client.post('/api/knowledge/add', json=initial_knowledge)
        self.assertEqual(add_response.status_code, 200)

        # 2. Change permissions
        perm_response = self.client.put('/api/permissions', json={
            'permissions': {
                'webSearch': True,
                'vaultSearch': False,  # Disable vault search
                'readFiles': True
            }
        })
        self.assertEqual(perm_response.status_code, 200)

        # 3. Verify tools reflect permission changes
        tools_response = self.client.get('/api/permissions/tools')
        tools_data = json.loads(tools_response.data)
        allowed_tools = tools_data['allowed_tools']

        # Should have web tools but not vault search tools
        self.assertIn('WebSearch', allowed_tools)
        self.assertNotIn('Grep', allowed_tools)
        self.assertNotIn('Glob', allowed_tools)

        # 4. Test token estimation with new permissions context
        token_response = self.client.post('/api/tokens/conversation', json={
            'conversation_id': self.test_conversation.uuid
        })
        self.assertEqual(token_response.status_code, 200)

        # Token calculation should still work regardless of permissions
        token_data = json.loads(token_response.data)
        self.assertGreater(token_data['estimation']['total_tokens'], 0)

    def test_database_integrity_across_operations(self):
        """Test database integrity across multiple operations"""
        self.login_user()

        # Perform multiple operations that modify database
        operations = [
            self.add_multiple_knowledge_files,
            self.upload_multiple_files,
            self.update_permissions_multiple_times,
            self.create_token_cache_entries,
            self.send_multiple_messages
        ]

        for operation in operations:
            with self.subTest(operation=operation.__name__):
                operation()
                self.verify_database_integrity()

    def add_multiple_knowledge_files(self):
        """Helper: Add multiple knowledge files"""
        files = [
            'projects/integration_project.md',
            'areas/integration_area.md',
            'resources/integration_resource.md'
        ]

        for file_path in files:
            response = self.client.post('/api/knowledge/add', json={
                'conversation_id': self.test_conversation.uuid,
                'vault': 'private',
                'file_path': file_path,
                'category': 'RESOURCE'
            })
            self.assertEqual(response.status_code, 200)

    def upload_multiple_files(self):
        """Helper: Upload multiple files"""
        files = [
            ('test1.txt', 'Content 1'),
            ('test2.txt', 'Content 2'),
            ('test3.txt', 'Content 3')
        ]

        for filename, content in files:
            test_file = BytesIO(content.encode('utf-8'))
            test_file.name = filename

            response = self.client.post('/api/upload',
                data={'file': (test_file, filename)},
                content_type='multipart/form-data'
            )
            self.assertEqual(response.status_code, 200)

    def update_permissions_multiple_times(self):
        """Helper: Update permissions multiple times"""
        permission_sets = [
            {'webSearch': True, 'vaultSearch': True},
            {'webSearch': False, 'vaultSearch': True},
            {'webSearch': True, 'vaultSearch': False},
            {'webSearch': False, 'vaultSearch': False}
        ]

        for permissions in permission_sets:
            response = self.client.put('/api/permissions', json={
                'permissions': permissions
            })
            # Some might fail due to write permission blocking, which is expected

    def create_token_cache_entries(self):
        """Helper: Create token cache entries"""
        # Create test files and estimate tokens to populate cache
        test_files = ['cache1.txt', 'cache2.txt', 'cache3.txt']

        for filename in test_files:
            # Create file
            test_file_path = self.temp_dir / filename
            test_file_path.write_text(f"Cache test content for {filename}")

            # Estimate tokens
            response = self.client.post('/api/tokens/file', json={
                'file_path': str(test_file_path),
                'use_cache': True
            })
            self.assertEqual(response.status_code, 200)

    def send_multiple_messages(self):
        """Helper: Send multiple messages"""
        with patch('app.claude_service') as mock_claude:
            mock_claude.create_message.return_value.__aiter__ = lambda: iter(['Test response'])

            messages = [
                'First test message',
                'Second test message',
                'Third test message'
            ]

            for content in messages:
                response = self.client.post(
                    f'/api/conversations/{self.test_conversation.uuid}/messages',
                    json={'content': content, 'allowed_tools': ['Bash', 'Read']}
                )
                self.assertEqual(response.status_code, 200)

    def test_session_management(self):
        """Test session management across different operations"""
        # Test 1: Operations without login should fail
        response = self.client.get('/api/permissions')
        self.assertIn(response.status_code, [401, 302])

        # Test 2: Login and perform operations
        self.login_user()

        # Should now work
        response = self.client.get('/api/permissions')
        self.assertEqual(response.status_code, 200)

        # Test 3: Logout
        logout_response = self.client.post('/api/auth/logout')
        self.assertEqual(logout_response.status_code, 200)

        # Test 4: Operations after logout should fail again
        response = self.client.get('/api/permissions')
        self.assertIn(response.status_code, [401, 302])

    def test_error_handling_across_features(self):
        """Test error handling across different features"""
        self.login_user()

        # Test error scenarios
        error_scenarios = [
            # Invalid conversation ID
            ('POST', '/api/knowledge/add', {
                'conversation_id': 'invalid-id',
                'vault': 'private',
                'file_path': 'projects/integration_project.md'
            }, 404),

            # Invalid vault
            ('POST', '/api/knowledge/search', {
                'vault': 'invalid_vault',
                'query': 'test'
            }, None),  # Might return 200 with empty results

            # Invalid file path for tokens
            ('POST', '/api/tokens/file', {
                'file_path': '/non/existent/file.txt'
            }, 400),

            # Invalid permission update (write permissions)
            ('PUT', '/api/permissions', {
                'permissions': {'writeFiles': True}
            }, 403),
        ]

        for method, endpoint, data, expected_status in error_scenarios:
            with self.subTest(endpoint=endpoint):
                if method == 'POST':
                    response = self.client.post(endpoint, json=data)
                elif method == 'PUT':
                    response = self.client.put(endpoint, json=data)
                elif method == 'GET':
                    response = self.client.get(endpoint)

                if expected_status:
                    self.assertEqual(response.status_code, expected_status)

                # Verify database integrity after each error
                self.verify_database_integrity()

    def test_websocket_integration(self):
        """Test WebSocket integration with other systems"""
        self.login_user()

        # Test WebSocket connection
        self.assertTrue(self.socketio_client.is_connected())

        # Test joining conversation
        self.socketio_client.emit('join_conversation', {
            'conversation_id': self.test_conversation.uuid
        })

        # Test streaming message with file data
        with patch('app.claude_service') as mock_claude:
            async def mock_stream():
                yield "WebSocket integration test response"

            mock_claude.create_message.return_value = mock_stream()

            message_data = {
                'conversation_id': self.test_conversation.uuid,
                'content': 'WebSocket test message',
                'knowledge_files': [],
                'upload_files': [],
                'total_tokens': 10
            }

            # Emit message
            self.socketio_client.emit('stream_message', message_data)

            # In a full test, we'd verify the response events

    def test_performance_under_load(self):
        """Test system performance under moderate load"""
        self.login_user()

        start_time = time.time()

        # Perform multiple operations concurrently (simulated)
        operations = []

        # Add knowledge files
        for i in range(5):
            response = self.client.post('/api/knowledge/add', json={
                'conversation_id': self.test_conversation.uuid,
                'vault': 'private',
                'file_path': 'projects/integration_project.md',
                'category': 'PROJECT'
            })
            operations.append(('add_knowledge', response.status_code))

        # Upload files
        for i in range(3):
            content = f"Performance test file {i}"
            test_file = BytesIO(content.encode('utf-8'))
            test_file.name = f'perf_test_{i}.txt'

            response = self.client.post('/api/upload',
                data={'file': (test_file, f'perf_test_{i}.txt')},
                content_type='multipart/form-data'
            )
            operations.append(('upload', response.status_code))

        # Update permissions
        for i in range(3):
            response = self.client.put('/api/permissions', json={
                'permissions': {
                    'webSearch': i % 2 == 0,
                    'vaultSearch': True
                }
            })
            operations.append(('permissions', response.status_code))

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete in reasonable time (under 10 seconds)
        self.assertLess(total_time, 10.0)

        # Most operations should succeed
        successful_ops = sum(1 for _, status in operations if status in [200, 201])
        self.assertGreater(successful_ops, len(operations) * 0.8)  # At least 80% success

    def verify_database_integrity(self):
        """Verify database integrity after operations"""
        # Check for orphaned records

        # 1. All conversation knowledge links should reference valid conversations and knowledge
        orphaned_conv_knowledge = db.session.query(ConversationKnowledge).filter(
            ~ConversationKnowledge.conversation_id.in_(
                db.session.query(Conversation.id)
            )
        ).count()
        self.assertEqual(orphaned_conv_knowledge, 0, "Found orphaned conversation knowledge links")

        orphaned_knowledge_conv = db.session.query(ConversationKnowledge).filter(
            ~ConversationKnowledge.knowledge_id.in_(
                db.session.query(ProjectKnowledge.id)
            )
        ).count()
        self.assertEqual(orphaned_knowledge_conv, 0, "Found orphaned knowledge conversation links")

        # 2. All conversations should belong to valid users
        orphaned_conversations = db.session.query(Conversation).filter(
            ~Conversation.user_id.in_(
                db.session.query(User.id)
            )
        ).count()
        self.assertEqual(orphaned_conversations, 0, "Found orphaned conversations")

        # 3. All messages should belong to valid conversations
        orphaned_messages = db.session.query(Message).filter(
            ~Message.conversation_id.in_(
                db.session.query(Conversation.id)
            )
        ).count()
        self.assertEqual(orphaned_messages, 0, "Found orphaned messages")

        # 4. User permissions should reference valid users
        orphaned_permissions = db.session.query(UserPermissions).filter(
            ~UserPermissions.user_id.in_(
                db.session.query(User.id)
            )
        ).count()
        self.assertEqual(orphaned_permissions, 0, "Found orphaned user permissions")

        # 5. Check for data consistency
        # Conversations should have valid timestamps
        invalid_timestamps = db.session.query(Conversation).filter(
            Conversation.created_at > Conversation.updated_at
        ).count()
        self.assertEqual(invalid_timestamps, 0, "Found conversations with invalid timestamps")

    def test_data_consistency_across_systems(self):
        """Test data consistency across all v0.2 systems"""
        self.login_user()

        # Add knowledge and verify token counts are consistent
        add_response = self.client.post('/api/knowledge/add', json={
            'conversation_id': self.test_conversation.uuid,
            'vault': 'private',
            'file_path': 'projects/integration_project.md',
            'category': 'PROJECT'
        })
        self.assertEqual(add_response.status_code, 200)
        add_data = json.loads(add_response.data)
        knowledge_tokens = add_data['knowledge']['token_count']

        # Get conversation tokens
        token_response = self.client.post('/api/tokens/conversation', json={
            'conversation_id': self.test_conversation.uuid
        })
        self.assertEqual(token_response.status_code, 200)
        token_data = json.loads(token_response.data)

        # Knowledge tokens should be included in conversation total
        self.assertGreaterEqual(token_data['estimation']['knowledge_tokens'], knowledge_tokens)

        # Search for the added knowledge - should show as added
        search_response = self.client.post('/api/knowledge/search', json={
            'vault': 'private',
            'query': 'integration_project'
        })
        self.assertEqual(search_response.status_code, 200)
        search_data = json.loads(search_response.data)

        # Find our file in results
        our_file = None
        for file_info in search_data:
            if 'integration_project.md' in file_info['path']:
                our_file = file_info
                break

        self.assertIsNotNone(our_file)
        self.assertTrue(our_file['is_added'])
        self.assertEqual(our_file['token_count'], knowledge_tokens)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)