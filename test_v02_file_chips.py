#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Comprehensive test suite for Claude AI Web Interface v0.2 - File Chips Display System

Tests the file chips display features including:
- File chip creation for knowledge files
- File chip creation for uploaded files
- Token bar visualization
- Chip removal functionality
- Integration with message sending
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# Add the parent directory to the path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db
from models.models import User, Conversation, ProjectKnowledge, ConversationKnowledge


class TestFileChipsDisplaySystem(unittest.TestCase):
    """Test suite for the File Chips Display System in v0.2"""

    def setUp(self):
        """Set up test environment before each test"""
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['ENABLE_PROJECT_KNOWLEDGE'] = True

        # Create temporary upload folder
        self.temp_dir = Path(tempfile.mkdtemp())
        app.config['UPLOAD_FOLDER'] = self.temp_dir
        app.config['ALLOWED_EXTENSIONS'] = {'txt', 'md', 'pdf', 'docx', 'csv', 'json'}

        # Create temporary vault directories
        self.private_vault = self.temp_dir / 'vault' / 'private'
        self.poa_vault = self.temp_dir / 'vault' / 'poa'

        self.private_vault.mkdir(parents=True)
        self.poa_vault.mkdir(parents=True)

        app.config['OBSIDIAN_PRIVATE_PATH'] = str(self.private_vault)
        app.config['OBSIDIAN_POA_PATH'] = str(self.poa_vault)

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

        # Create test conversation
        self.test_conversation = Conversation(
            uuid='test-conv-chips-123',
            title='Chips Test Conversation',
            user_id=self.test_user.id,
            model='sonnet-4.5'
        )
        db.session.add(self.test_conversation)
        db.session.commit()

        # Create test vault files
        self.create_test_vault_files()

    def tearDown(self):
        """Clean up after each test"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        # Clean up temp directory
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def create_test_vault_files(self):
        """Create test files in the vault directories"""
        test_files = [
            ("projects/ai_project.md", "# AI Project\nThis is an AI project document with detailed content."),
            ("areas/health.md", "# Health Management\nHealth tracking and wellness content."),
            ("resources/python_guide.md", "# Python Guide\nComprehensive Python programming guide with examples."),
            ("archive/old_project.md", "# Old Project\nArchived project documentation."),
        ]

        for file_path, content in test_files:
            full_path = self.private_vault / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

    def login_client(self):
        """Helper to login the test client"""
        response = self.client.post('/api/auth/login', json={})
        self.assertEqual(response.status_code, 200)
        return response

    def test_file_chip_creation_for_knowledge_files(self):
        """Test file chip data creation for knowledge files"""
        self.login_client()

        # Add knowledge file to conversation
        response = self.client.post('/api/knowledge/add', json={
            'conversation_id': self.test_conversation.uuid,
            'vault': 'private',
            'file_path': 'projects/ai_project.md',
            'category': 'PROJECT'
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data['success'])
        self.assertIn('knowledge', data)

        knowledge = data['knowledge']

        # Check that knowledge has all required fields for file chips
        self.assertIn('id', knowledge)
        self.assertIn('name', knowledge)
        self.assertIn('file_path', knowledge)
        self.assertIn('token_count', knowledge)
        self.assertIn('category', knowledge)

        # Verify the knowledge was stored with proper data
        db_knowledge = ProjectKnowledge.query.get(knowledge['id'])
        self.assertIsNotNone(db_knowledge)
        self.assertEqual(db_knowledge.name, 'ai_project')
        self.assertIsNotNone(db_knowledge.token_count)
        self.assertGreater(db_knowledge.token_count, 0)

    def test_file_chip_creation_for_uploaded_files(self):
        """Test file chip data creation for uploaded files"""
        self.login_client()

        # Create test file content
        test_content = "This is a test file for upload.\nIt contains multiple lines of content."
        test_file = BytesIO(test_content.encode('utf-8'))
        test_file.name = 'test_upload.txt'

        # Upload file
        response = self.client.post('/api/upload',
            data={'file': (test_file, 'test_upload.txt')},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data['success'])

        # Check that upload response has all required fields for file chips
        self.assertIn('filename', data)
        self.assertIn('size', data)
        self.assertIn('tokens', data)
        self.assertIn('file_id', data)

        # Verify file was actually saved
        uploaded_filename = data['filename']
        uploaded_file_path = self.temp_dir / uploaded_filename
        self.assertTrue(uploaded_file_path.exists())

        # Token count should be reasonable
        self.assertGreater(data['tokens'], 0)
        self.assertLess(data['tokens'], 100)  # Should be small for this test file

    def test_token_bar_visualization_data(self):
        """Test data structure for token bar visualization"""
        self.login_client()

        # Add multiple knowledge files with different token counts
        knowledge_files = [
            ('projects/ai_project.md', 'PROJECT'),
            ('areas/health.md', 'AREA'),
            ('resources/python_guide.md', 'RESOURCE')
        ]

        added_knowledge = []
        total_expected_tokens = 0

        for file_path, category in knowledge_files:
            response = self.client.post('/api/knowledge/add', json={
                'conversation_id': self.test_conversation.uuid,
                'vault': 'private',
                'file_path': file_path,
                'category': category
            })

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            added_knowledge.append(data['knowledge'])
            total_expected_tokens += data['knowledge']['token_count'] or 0

        # Upload a file as well
        test_content = "Uploaded file content for token testing."
        test_file = BytesIO(test_content.encode('utf-8'))
        test_file.name = 'token_test.txt'

        upload_response = self.client.post('/api/upload',
            data={'file': (test_file, 'token_test.txt')},
            content_type='multipart/form-data'
        )

        self.assertEqual(upload_response.status_code, 200)
        upload_data = json.loads(upload_response.data)
        total_expected_tokens += upload_data['tokens']

        # Verify we have comprehensive token data
        self.assertGreater(total_expected_tokens, 0)

        # Check individual file token data
        for knowledge in added_knowledge:
            self.assertIsInstance(knowledge['token_count'], int)
            self.assertGreaterEqual(knowledge['token_count'], 0)

        # Upload token data should be valid
        self.assertIsInstance(upload_data['tokens'], int)
        self.assertGreaterEqual(upload_data['tokens'], 0)

    def test_chip_removal_functionality(self):
        """Test file chip removal through conversation knowledge links"""
        self.login_client()

        # Add knowledge file
        add_response = self.client.post('/api/knowledge/add', json={
            'conversation_id': self.test_conversation.uuid,
            'vault': 'private',
            'file_path': 'projects/ai_project.md',
            'category': 'PROJECT'
        })

        self.assertEqual(add_response.status_code, 200)
        add_data = json.loads(add_response.data)
        knowledge_id = add_data['knowledge']['id']

        # Verify knowledge was linked to conversation
        conv_link = ConversationKnowledge.query.filter_by(
            conversation_id=self.test_conversation.id,
            knowledge_id=knowledge_id
        ).first()
        self.assertIsNotNone(conv_link)

        # Simulate chip removal by deleting the conversation link
        # (In the actual UI, this would be triggered by the remove button)
        db.session.delete(conv_link)
        db.session.commit()

        # Verify link was removed
        removed_link = ConversationKnowledge.query.filter_by(
            conversation_id=self.test_conversation.id,
            knowledge_id=knowledge_id
        ).first()
        self.assertIsNone(removed_link)

        # Verify knowledge still exists in database (just unlinked)
        knowledge_still_exists = ProjectKnowledge.query.get(knowledge_id)
        self.assertIsNotNone(knowledge_still_exists)

    def test_multiple_file_types_chip_display(self):
        """Test chip display data for multiple file types"""
        self.login_client()

        # Test various file types
        file_types = [
            ('test.txt', 'text/plain', b'Plain text content'),
            ('test.md', 'text/markdown', b'# Markdown Content\nWith some text'),
            ('test.json', 'application/json', b'{"key": "value", "test": true}'),
            ('test.csv', 'text/csv', b'name,value\ntest,123\nother,456'),
        ]

        uploaded_files = []

        for filename, content_type, content in file_types:
            test_file = BytesIO(content)
            test_file.name = filename

            response = self.client.post('/api/upload',
                data={'file': (test_file, filename)},
                content_type='multipart/form-data'
            )

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            uploaded_files.append(data)

            # Each file should have proper chip data
            self.assertIn('filename', data)
            self.assertIn('tokens', data)
            self.assertIn('file_id', data)
            self.assertIn('size', data)

            # Filename should be timestamped
            self.assertTrue(data['filename'].endswith(filename))

        # Verify all files have different IDs
        file_ids = [f['file_id'] for f in uploaded_files]
        self.assertEqual(len(file_ids), len(set(file_ids)))  # All unique

    def test_integration_with_message_sending(self):
        """Test integration of file chips with message sending"""
        self.login_client()

        # Add knowledge file
        knowledge_response = self.client.post('/api/knowledge/add', json={
            'conversation_id': self.test_conversation.uuid,
            'vault': 'private',
            'file_path': 'projects/ai_project.md',
            'category': 'PROJECT'
        })

        self.assertEqual(knowledge_response.status_code, 200)
        knowledge_data = json.loads(knowledge_response.data)

        # Upload file
        test_content = "Content for message integration test."
        test_file = BytesIO(test_content.encode('utf-8'))
        test_file.name = 'integration_test.txt'

        upload_response = self.client.post('/api/upload',
            data={'file': (test_file, 'integration_test.txt')},
            content_type='multipart/form-data'
        )

        self.assertEqual(upload_response.status_code, 200)
        upload_data = json.loads(upload_response.data)

        # Mock the Claude service to avoid actual API calls
        with patch('app.claude_service') as mock_claude:
            mock_claude.create_message.return_value.__aiter__ = lambda: iter(['Test response'])

            # Send message with file data (simulating what frontend would send)
            message_data = {
                'content': 'Test message with files attached',
                'knowledge_files': [knowledge_data['knowledge']['file_path']],
                'upload_files': [upload_data['file_id']],
                'total_tokens': (knowledge_data['knowledge']['token_count'] + upload_data['tokens'])
            }

            message_response = self.client.post(
                f'/api/conversations/{self.test_conversation.uuid}/messages',
                json=message_data
            )

            self.assertEqual(message_response.status_code, 200)
            message_response_data = json.loads(message_response.data)

            # Verify message was created
            self.assertIn('content', message_response_data)
            self.assertIn('role', message_response_data)
            self.assertEqual(message_response_data['role'], 'assistant')

    def test_token_calculation_accuracy(self):
        """Test accuracy of token calculations for different file sizes"""
        self.login_client()

        # Test files with known approximate token counts
        test_cases = [
            ("Small file", "Hello world", 3),
            ("Medium file", "This is a medium-sized file with several sentences. " * 5, 50),
            ("Large file", "Large file content. " * 100, 300),
        ]

        for test_name, content, expected_tokens in test_cases:
            with self.subTest(test_name=test_name):
                test_file = BytesIO(content.encode('utf-8'))
                test_file.name = f'{test_name.lower().replace(" ", "_")}.txt'

                response = self.client.post('/api/upload',
                    data={'file': (test_file, test_file.name)},
                    content_type='multipart/form-data'
                )

                self.assertEqual(response.status_code, 200)
                data = json.loads(response.data)

                # Token count should be reasonable (within 50% of expected)
                actual_tokens = data['tokens']
                self.assertGreater(actual_tokens, 0)
                self.assertLess(abs(actual_tokens - expected_tokens), expected_tokens * 0.5 + 2)

    def test_chip_data_persistence(self):
        """Test that chip data persists correctly across operations"""
        self.login_client()

        # Add knowledge file
        knowledge_response = self.client.post('/api/knowledge/add', json={
            'conversation_id': self.test_conversation.uuid,
            'vault': 'private',
            'file_path': 'resources/python_guide.md',
            'category': 'RESOURCE'
        })

        self.assertEqual(knowledge_response.status_code, 200)
        knowledge_data = json.loads(knowledge_response.data)
        original_token_count = knowledge_data['knowledge']['token_count']

        # Search for knowledge to see if it's marked as added
        search_response = self.client.post('/api/knowledge/search', json={
            'vault': 'private',
            'query': 'python'
        })

        self.assertEqual(search_response.status_code, 200)
        search_data = json.loads(search_response.data)

        # Find our added file in search results
        added_file = None
        for file_info in search_data:
            if file_info['path'] == 'resources/python_guide.md':
                added_file = file_info
                break

        self.assertIsNotNone(added_file)
        self.assertTrue(added_file['is_added'])
        self.assertEqual(added_file['token_count'], original_token_count)
        self.assertEqual(added_file['knowledge_id'], knowledge_data['knowledge']['id'])

    def test_chip_display_edge_cases(self):
        """Test edge cases in chip display functionality"""
        self.login_client()

        # Test empty file
        empty_file = BytesIO(b'')
        empty_file.name = 'empty.txt'

        response = self.client.post('/api/upload',
            data={'file': (empty_file, 'empty.txt')},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Empty file should have 0 tokens
        self.assertEqual(data['tokens'], 0)
        self.assertEqual(data['size'], 0)

        # Test file with very long name
        long_name = 'very_long_filename_that_exceeds_normal_length_expectations_and_might_cause_display_issues.txt'
        long_name_file = BytesIO(b'Content with long filename')
        long_name_file.name = long_name

        response = self.client.post('/api/upload',
            data={'file': (long_name_file, long_name)},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Should handle long filename gracefully
        self.assertIn('filename', data)
        self.assertTrue(data['filename'].endswith(long_name))

    def test_file_chip_error_handling(self):
        """Test error handling in file chip operations"""
        self.login_client()

        # Test upload with no file
        response = self.client.post('/api/upload', data={})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

        # Test upload with empty filename
        empty_name_file = BytesIO(b'content')
        empty_name_file.name = ''

        response = self.client.post('/api/upload',
            data={'file': (empty_name_file, '')},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, 400)

        # Test knowledge add with non-existent file
        response = self.client.post('/api/knowledge/add', json={
            'conversation_id': self.test_conversation.uuid,
            'vault': 'private',
            'file_path': 'non_existent/file.md',
            'category': 'RESOURCE'
        })

        self.assertEqual(response.status_code, 404)

    def test_file_size_limits(self):
        """Test file size handling for chip display"""
        self.login_client()

        # Test reasonably large file
        large_content = "Large file content. " * 1000  # ~20KB
        large_file = BytesIO(large_content.encode('utf-8'))
        large_file.name = 'large_test.txt'

        response = self.client.post('/api/upload',
            data={'file': (large_file, 'large_test.txt')},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Should handle large file appropriately
        self.assertGreater(data['size'], 10000)  # Should be > 10KB
        self.assertGreater(data['tokens'], 100)  # Should have many tokens

    def test_concurrent_file_operations(self):
        """Test concurrent file operations for chip display"""
        self.login_client()

        import threading
        import queue

        results = queue.Queue()
        errors = queue.Queue()

        def upload_file(file_id):
            try:
                content = f"Concurrent upload test file {file_id}"
                test_file = BytesIO(content.encode('utf-8'))
                test_file.name = f'concurrent_{file_id}.txt'

                response = self.client.post('/api/upload',
                    data={'file': (test_file, f'concurrent_{file_id}.txt')},
                    content_type='multipart/form-data'
                )

                if response.status_code == 200:
                    data = json.loads(response.data)
                    results.put((file_id, data))
                else:
                    errors.put((file_id, response.status_code))

            except Exception as e:
                errors.put((file_id, str(e)))

        # Start multiple upload threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=upload_file, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check results
        self.assertEqual(results.qsize(), 3)
        self.assertEqual(errors.qsize(), 0)

        # Verify all uploads were successful and unique
        file_ids = set()
        while not results.empty():
            thread_id, data = results.get()
            self.assertIn('file_id', data)
            self.assertIn('filename', data)
            file_ids.add(data['file_id'])

        # All file IDs should be unique
        self.assertEqual(len(file_ids), 3)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)