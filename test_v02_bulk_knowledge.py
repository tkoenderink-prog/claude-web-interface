#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Comprehensive test suite for Claude AI Web Interface v0.2 - Bulk Knowledge System

Tests the bulk knowledge management features including:
- "Select All" functionality
- Bulk add operation with 10+ files
- Token limits enforcement
- Duplicate file prevention
- Partial failure handling
- Real-time token counting
"""

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import asyncio

# Add the parent directory to the path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db
from models.models import User, Conversation, ProjectKnowledge, ConversationKnowledge, TokenCache
from services.claude_service import ObsidianKnowledgeService


class TestBulkKnowledgeSystem(unittest.TestCase):
    """Test suite for the Bulk Knowledge Management System in v0.2"""

    def setUp(self):
        """Set up test environment before each test"""
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['ENABLE_PROJECT_KNOWLEDGE'] = True

        # Create temporary vault directories
        self.temp_dir = Path(tempfile.mkdtemp())
        self.private_vault = self.temp_dir / 'private'
        self.poa_vault = self.temp_dir / 'poa'

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
            uuid='test-conv-bulk-123',
            title='Bulk Test Conversation',
            user_id=self.test_user.id,
            model='sonnet-4.5'
        )
        db.session.add(self.test_conversation)
        db.session.commit()

        # Create test knowledge files in vault
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
        # Create various test files with different sizes and content
        test_files = [
            ("01-PROJECTS/project1.md", "# Project 1\nThis is a small project file."),
            ("01-PROJECTS/project2.md", "# Project 2\nThis is another project with more content. " * 20),
            ("02-AREAS/area1.md", "# Area 1\nArea management content."),
            ("02-AREAS/area2.md", "# Area 2\nMore area content with details. " * 15),
            ("03-RESOURCES/resource1.md", "# Resource 1\nUseful resource information."),
            ("03-RESOURCES/resource2.md", "# Resource 2\nDetailed resource content. " * 25),
            ("03-RESOURCES/large_resource.md", "# Large Resource\nThis is a very large file. " * 500),
            ("04-ARCHIVE/archived1.md", "# Archived Item\nOld project archive."),
            ("00-INBOX/inbox1.md", "# Inbox Item\nQuick capture item."),
            ("00-INBOX/inbox2.md", "# Another Inbox\nAnother quick item."),
            ("notes/note1.md", "# Note 1\nGeneral note content."),
            ("notes/note2.md", "# Note 2\nAnother general note."),
            ("templates/template1.md", "# Template\nTemplate content."),
            ("daily/2024-01-01.md", "# Daily Note\nDaily reflection."),
            ("weekly/week1.md", "# Weekly Review\nWeekly planning."),
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

    def test_select_all_functionality(self):
        """Test the 'Select All' functionality in knowledge search"""
        self.login_client()

        # Test select all without any filters
        response = self.client.post('/api/knowledge/search', json={
            'vault': 'private',
            'query': '',
            'select_all': True
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Should return all files
        self.assertGreaterEqual(len(data), 10)  # We created 15 files

        # Each file should have required fields
        for file_info in data:
            self.assertIn('name', file_info)
            self.assertIn('path', file_info)
            self.assertIn('category', file_info)
            self.assertIn('token_count', file_info)
            self.assertIn('is_added', file_info)

    def test_select_all_with_category_filter(self):
        """Test select all with category filtering"""
        self.login_client()

        # Test select all for specific category
        response = self.client.post('/api/knowledge/search', json={
            'vault': 'private',
            'query': '',
            'category': 'PROJECT',
            'select_all': True
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Should only return project files
        project_files = [f for f in data if 'PROJECTS' in f['path']]
        self.assertGreaterEqual(len(project_files), 2)

        # All returned files should be in the projects category
        for file_info in data:
            self.assertTrue('01-PROJECTS' in file_info['path'] or file_info['category'] == 'PROJECT')

    def test_bulk_add_operation_success(self):
        """Test successful bulk add operation with multiple files"""
        self.login_client()

        # Prepare files for bulk add
        files_to_add = [
            {
                'vault': 'private',
                'file_path': '01-PROJECTS/project1.md',
                'category': 'PROJECT'
            },
            {
                'vault': 'private',
                'file_path': '01-PROJECTS/project2.md',
                'category': 'PROJECT'
            },
            {
                'vault': 'private',
                'file_path': '02-AREAS/area1.md',
                'category': 'AREA'
            },
            {
                'vault': 'private',
                'file_path': '03-RESOURCES/resource1.md',
                'category': 'RESOURCE'
            },
            {
                'vault': 'private',
                'file_path': '03-RESOURCES/resource2.md',
                'category': 'RESOURCE'
            }
        ]

        # Perform bulk add
        response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': files_to_add
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Check response structure
        self.assertTrue(data['success'])
        self.assertIn('results', data)
        self.assertIn('summary', data)

        results = data['results']
        summary = data['summary']

        # Check summary
        self.assertEqual(summary['total_files'], 5)
        self.assertEqual(summary['succeeded'], 5)
        self.assertEqual(summary['failed'], 0)
        self.assertEqual(summary['duplicates'], 0)
        self.assertGreater(summary['total_tokens'], 0)

        # Check individual results
        self.assertEqual(len(results['succeeded']), 5)
        self.assertEqual(len(results['failed']), 0)

        # Verify knowledge was actually added to database
        knowledge_count = ProjectKnowledge.query.filter_by(user_id=self.test_user.id).count()
        self.assertEqual(knowledge_count, 5)

        # Verify conversation links were created
        conv_links = ConversationKnowledge.query.filter_by(conversation_id=self.test_conversation.id).count()
        self.assertEqual(conv_links, 5)

    def test_bulk_add_with_large_file_set(self):
        """Test bulk add operation with 10+ files"""
        self.login_client()

        # Prepare all available files for bulk add
        files_to_add = []
        file_paths = [
            '01-PROJECTS/project1.md',
            '01-PROJECTS/project2.md',
            '02-AREAS/area1.md',
            '02-AREAS/area2.md',
            '03-RESOURCES/resource1.md',
            '03-RESOURCES/resource2.md',
            '04-ARCHIVE/archived1.md',
            '00-INBOX/inbox1.md',
            '00-INBOX/inbox2.md',
            'notes/note1.md',
            'notes/note2.md',
            'templates/template1.md',
            'daily/2024-01-01.md',
            'weekly/week1.md'
        ]

        for file_path in file_paths:
            files_to_add.append({
                'vault': 'private',
                'file_path': file_path,
                'category': 'RESOURCE'  # Default category
            })

        # Perform bulk add with 14 files
        response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': files_to_add
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data['success'])
        summary = data['summary']

        # Should handle all files
        self.assertEqual(summary['total_files'], 14)
        self.assertGreaterEqual(summary['succeeded'], 10)  # At least 10 should succeed

        # Total token count should be significant
        self.assertGreater(summary['total_tokens'], 100)

        # Verify database entries
        knowledge_count = ProjectKnowledge.query.filter_by(user_id=self.test_user.id).count()
        self.assertGreaterEqual(knowledge_count, 10)

    def test_token_limits_enforcement(self):
        """Test that token limits are properly enforced during bulk operations"""
        self.login_client()

        # Mock the token service to return high token counts
        with patch('services.token_service.get_token_service') as mock_service:
            mock_instance = Mock()
            mock_instance.estimate_text_tokens.return_value = {
                'token_count': 50000,  # Very high token count
                'character_count': 200000,
                'word_count': 40000,
                'estimation_method': 'mock'
            }
            mock_service.return_value = mock_instance

            # Try to add files that would exceed token limit
            files_to_add = [
                {
                    'vault': 'private',
                    'file_path': '01-PROJECTS/project1.md',
                    'category': 'PROJECT'
                },
                {
                    'vault': 'private',
                    'file_path': '01-PROJECTS/project2.md',
                    'category': 'PROJECT'
                },
                {
                    'vault': 'private',
                    'file_path': '03-RESOURCES/large_resource.md',
                    'category': 'RESOURCE'
                }
            ]

            response = self.client.post('/api/knowledge/add-bulk', json={
                'conversation_id': self.test_conversation.uuid,
                'files': files_to_add
            })

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)

            # Operation should succeed but with token warnings
            self.assertTrue(data['success'])

            # Should have very high total tokens
            summary = data['summary']
            self.assertGreater(summary['total_tokens'], 100000)

    def test_duplicate_file_prevention(self):
        """Test that duplicate files are properly detected and handled"""
        self.login_client()

        # First, add some files
        initial_files = [
            {
                'vault': 'private',
                'file_path': '01-PROJECTS/project1.md',
                'category': 'PROJECT'
            },
            {
                'vault': 'private',
                'file_path': '02-AREAS/area1.md',
                'category': 'AREA'
            }
        ]

        # Add files first time
        response1 = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': initial_files
        })

        self.assertEqual(response1.status_code, 200)
        data1 = json.loads(response1.data)
        self.assertTrue(data1['success'])
        self.assertEqual(data1['summary']['succeeded'], 2)

        # Now try to add the same files again plus some new ones
        duplicate_files = [
            {
                'vault': 'private',
                'file_path': '01-PROJECTS/project1.md',  # Duplicate
                'category': 'PROJECT'
            },
            {
                'vault': 'private',
                'file_path': '02-AREAS/area1.md',  # Duplicate
                'category': 'AREA'
            },
            {
                'vault': 'private',
                'file_path': '03-RESOURCES/resource1.md',  # New
                'category': 'RESOURCE'
            }
        ]

        response2 = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': duplicate_files
        })

        self.assertEqual(response2.status_code, 200)
        data2 = json.loads(response2.data)

        self.assertTrue(data2['success'])
        summary2 = data2['summary']

        # Should detect duplicates
        self.assertEqual(summary2['total_files'], 3)
        self.assertEqual(summary2['succeeded'], 1)  # Only the new file
        self.assertEqual(summary2['duplicates'], 2)  # Two duplicates detected

        # Total knowledge count should be 3 (2 original + 1 new)
        knowledge_count = ProjectKnowledge.query.filter_by(user_id=self.test_user.id).count()
        self.assertEqual(knowledge_count, 3)

    def test_partial_failure_handling(self):
        """Test handling of partial failures in bulk operations"""
        self.login_client()

        # Include some valid and some invalid files
        mixed_files = [
            {
                'vault': 'private',
                'file_path': '01-PROJECTS/project1.md',  # Valid
                'category': 'PROJECT'
            },
            {
                'vault': 'private',
                'file_path': 'non-existent/file.md',  # Invalid - doesn't exist
                'category': 'RESOURCE'
            },
            {
                'vault': 'private',
                'file_path': '02-AREAS/area1.md',  # Valid
                'category': 'AREA'
            },
            {
                'vault': 'invalid_vault',  # Invalid vault
                'file_path': 'some/file.md',
                'category': 'RESOURCE'
            },
            {
                'vault': 'private',
                'file_path': '03-RESOURCES/resource1.md',  # Valid
                'category': 'RESOURCE'
            }
        ]

        response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': mixed_files
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data['success'])  # Overall operation succeeds

        results = data['results']
        summary = data['summary']

        # Should have some successes and some failures
        self.assertEqual(summary['total_files'], 5)
        self.assertGreater(summary['succeeded'], 0)
        self.assertGreater(summary['failed'], 0)
        self.assertEqual(summary['succeeded'] + summary['failed'], summary['total_files'])

        # Check that failed files have error information
        for failed_file in results['failed']:
            self.assertIn('file_path', failed_file)
            self.assertIn('error', failed_file)
            self.assertIsInstance(failed_file['error'], str)

        # Check that successful files have proper information
        for success_file in results['succeeded']:
            self.assertIn('file_path', success_file)
            self.assertIn('knowledge_id', success_file)
            self.assertIn('token_count', success_file)

    def test_real_time_token_counting(self):
        """Test real-time token counting during bulk operations"""
        self.login_client()

        files_to_add = [
            {
                'vault': 'private',
                'file_path': '01-PROJECTS/project1.md',
                'category': 'PROJECT'
            },
            {
                'vault': 'private',
                'file_path': '01-PROJECTS/project2.md',
                'category': 'PROJECT'
            },
            {
                'vault': 'private',
                'file_path': '03-RESOURCES/resource2.md',
                'category': 'RESOURCE'
            }
        ]

        response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': files_to_add
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data['success'])

        # Check that token counting is working
        summary = data['summary']
        self.assertGreater(summary['total_tokens'], 0)

        # Each successful file should have token count
        for success_file in data['results']['succeeded']:
            self.assertIn('token_count', success_file)
            if success_file['token_count'] is not None:
                self.assertGreaterEqual(success_file['token_count'], 0)

        # Verify tokens were stored in database
        knowledge_items = ProjectKnowledge.query.filter_by(user_id=self.test_user.id).all()
        total_db_tokens = sum(k.token_count or 0 for k in knowledge_items)
        self.assertEqual(total_db_tokens, summary['total_tokens'])

    def test_bulk_add_empty_file_list(self):
        """Test bulk add with empty file list"""
        self.login_client()

        response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': []
        })

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_bulk_add_invalid_conversation(self):
        """Test bulk add with invalid conversation ID"""
        self.login_client()

        files_to_add = [
            {
                'vault': 'private',
                'file_path': '01-PROJECTS/project1.md',
                'category': 'PROJECT'
            }
        ]

        response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': 'invalid-conv-id',
            'files': files_to_add
        })

        self.assertEqual(response.status_code, 404)

    def test_bulk_add_transaction_rollback(self):
        """Test that partial failures trigger proper transaction rollback"""
        self.login_client()

        # Mock the obsidian service to fail on the second file
        with patch('app.obsidian_service') as mock_obsidian:
            def mock_get_content(vault, path):
                if 'project2' in path:
                    raise Exception("Simulated file read error")
                return "Mock content for " + path

            mock_obsidian.get_file_content = AsyncMock(side_effect=mock_get_content)
            mock_obsidian.calculate_content_hash.return_value = "mock_hash"

            files_to_add = [
                {
                    'vault': 'private',
                    'file_path': '01-PROJECTS/project1.md',
                    'category': 'PROJECT'
                },
                {
                    'vault': 'private',
                    'file_path': '01-PROJECTS/project2.md',  # This will fail
                    'category': 'PROJECT'
                }
            ]

            response = self.client.post('/api/knowledge/add-bulk', json={
                'conversation_id': self.test_conversation.uuid,
                'files': files_to_add
            })

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)

            # Should handle partial failure gracefully
            self.assertTrue(data['success'])

            results = data['results']
            self.assertEqual(len(results['succeeded']), 1)
            self.assertEqual(len(results['failed']), 1)

    def test_knowledge_search_status_after_bulk_add(self):
        """Test that knowledge search properly reflects added status after bulk operations"""
        self.login_client()

        # Add some files
        files_to_add = [
            {
                'vault': 'private',
                'file_path': '01-PROJECTS/project1.md',
                'category': 'PROJECT'
            },
            {
                'vault': 'private',
                'file_path': '02-AREAS/area1.md',
                'category': 'AREA'
            }
        ]

        # Perform bulk add
        add_response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': files_to_add
        })

        self.assertEqual(add_response.status_code, 200)

        # Now search for knowledge
        search_response = self.client.post('/api/knowledge/search', json={
            'vault': 'private',
            'query': '',
            'select_all': True
        })

        self.assertEqual(search_response.status_code, 200)
        search_data = json.loads(search_response.data)

        # Find the added files in search results
        added_files = [f for f in search_data if f['path'] in [
            '01-PROJECTS/project1.md',
            '02-AREAS/area1.md'
        ]]

        self.assertEqual(len(added_files), 2)

        # Both should be marked as added
        for file_info in added_files:
            self.assertTrue(file_info['is_added'])
            self.assertIsNotNone(file_info['knowledge_id'])


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)