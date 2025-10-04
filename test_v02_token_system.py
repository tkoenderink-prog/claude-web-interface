#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Comprehensive test suite for Claude AI Web Interface v0.2 - Token Estimation System

Tests the token estimation features including:
- Text token estimation accuracy
- File token estimation with caching
- Conversation token calculation
- Cache expiration and cleanup
- API endpoints for token operations
"""

import unittest
import tempfile
import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db
from models.models import User, Conversation, Message, TokenCache
from services.token_service import TokenService, TokenEstimationError


class TestTokenEstimationSystem(unittest.TestCase):
    """Test suite for the Token Estimation System in v0.2"""

    def setUp(self):
        """Set up test environment before each test"""
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['UPLOAD_FOLDER'] = Path(tempfile.mkdtemp())

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
            uuid='test-conv-123',
            title='Test Conversation',
            user_id=self.test_user.id,
            model='sonnet-4.5'
        )
        db.session.add(self.test_conversation)
        db.session.commit()

        # Initialize token service
        self.token_service = TokenService()

    def tearDown(self):
        """Clean up after each test"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        # Clean up upload folder
        import shutil
        if self.app.config['UPLOAD_FOLDER'].exists():
            shutil.rmtree(self.app.config['UPLOAD_FOLDER'])

    def test_text_token_estimation_accuracy(self):
        """Test accuracy of text token estimation"""
        test_cases = [
            ("Hello, world!", 3),  # Simple text
            ("This is a longer sentence with more words and punctuation.", 12),
            ("", 0),  # Empty string
            ("A" * 1000, 250),  # Long text (approximately)
            ("Code example:\n```python\nprint('hello')\n```", 10),  # Code block
            ("多言語テキスト Unicode 文字", 8),  # Multi-language text
        ]

        for text, expected_range in test_cases:
            with self.subTest(text=text[:20] + "..." if len(text) > 20 else text):
                result = self.token_service.estimate_text_tokens(text)

                # Check return structure
                self.assertIn('token_count', result)
                self.assertIn('character_count', result)
                self.assertIn('word_count', result)
                self.assertIn('estimation_method', result)

                # Check types
                self.assertIsInstance(result['token_count'], int)
                self.assertIsInstance(result['character_count'], int)
                self.assertIsInstance(result['word_count'], int)

                # Check basic accuracy (within 50% of expected for complex text)
                if expected_range > 0:
                    self.assertGreater(result['token_count'], 0)
                    # Allow for variation in tokenization
                    self.assertLess(abs(result['token_count'] - expected_range), expected_range * 0.5 + 2)
                else:
                    self.assertEqual(result['token_count'], 0)

    def test_file_token_estimation_with_caching(self):
        """Test file token estimation with caching system"""
        # Create test file
        test_file = self.app.config['UPLOAD_FOLDER'] / 'test_file.txt'
        test_content = "This is a test file for token estimation.\nIt has multiple lines.\nAnd some content."
        test_file.write_text(test_content)

        # First estimation (should cache result)
        result1 = self.token_service.estimate_file_tokens(test_file, use_cache=True)

        # Check result structure
        self.assertIn('token_count', result1)
        self.assertIn('file_path', result1)
        self.assertIn('file_size', result1)
        self.assertIn('modification_time', result1)
        self.assertIn('cached', result1)

        # Should not be cached on first run
        self.assertFalse(result1['cached'])

        # Second estimation (should use cache)
        result2 = self.token_service.estimate_file_tokens(test_file, use_cache=True)

        # Should be cached on second run
        self.assertTrue(result2['cached'])

        # Results should be identical
        self.assertEqual(result1['token_count'], result2['token_count'])

        # Test cache bypass
        result3 = self.token_service.estimate_file_tokens(test_file, use_cache=False)
        self.assertFalse(result3['cached'])
        self.assertEqual(result1['token_count'], result3['token_count'])

    def test_conversation_token_calculation(self):
        """Test token calculation for entire conversations"""
        # Add test messages
        messages = [
            {'role': 'user', 'content': 'Hello, can you help me?'},
            {'role': 'assistant', 'content': 'Of course! I\'d be happy to help. What do you need assistance with?'},
            {'role': 'user', 'content': 'I need help with Python programming.'},
        ]

        # Test conversation token estimation
        result = self.token_service.estimate_conversation_tokens(
            messages=messages,
            system_prompt="You are a helpful assistant.",
            project_knowledge=["# Knowledge\nSome additional context."]
        )

        # Check result structure
        self.assertIn('total_tokens', result)
        self.assertIn('message_tokens', result)
        self.assertIn('system_prompt_tokens', result)
        self.assertIn('knowledge_tokens', result)
        self.assertIn('breakdown', result)

        # Check that total is sum of parts
        expected_total = (
            result['message_tokens'] +
            result['system_prompt_tokens'] +
            result['knowledge_tokens']
        )
        self.assertEqual(result['total_tokens'], expected_total)

        # Check breakdown details
        breakdown = result['breakdown']
        self.assertEqual(len(breakdown['messages']), len(messages))

        for i, msg_breakdown in enumerate(breakdown['messages']):
            self.assertEqual(msg_breakdown['role'], messages[i]['role'])
            self.assertIn('tokens', msg_breakdown)
            self.assertGreater(msg_breakdown['tokens'], 0)

    def test_cache_expiration_and_cleanup(self):
        """Test cache expiration and cleanup functionality"""
        # Create test file
        test_file = self.app.config['UPLOAD_FOLDER'] / 'cache_test.txt'
        test_file.write_text("Test content for cache expiration")

        # Estimate tokens to create cache entry
        self.token_service.estimate_file_tokens(test_file, use_cache=True)

        # Verify cache entry exists
        cache_entry = TokenCache.query.filter_by(file_path=str(test_file)).first()
        self.assertIsNotNone(cache_entry)

        # Manually expire the cache entry
        cache_entry.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.session.commit()

        # Cleanup expired entries
        expired_count = TokenCache.cleanup_expired()
        db.session.commit()

        self.assertEqual(expired_count, 1)

        # Verify entry was removed
        cache_entry = TokenCache.query.filter_by(file_path=str(test_file)).first()
        self.assertIsNone(cache_entry)

    def test_token_estimation_error_handling(self):
        """Test error handling in token estimation"""
        # Test with non-existent file
        non_existent_file = Path('/non/existent/file.txt')

        with self.assertRaises(TokenEstimationError):
            self.token_service.estimate_file_tokens(non_existent_file)

        # Test with invalid text input
        with self.assertRaises(TokenEstimationError):
            self.token_service.estimate_text_tokens(None)

        # Test with binary file
        binary_file = self.app.config['UPLOAD_FOLDER'] / 'binary_test.bin'
        binary_file.write_bytes(b'\x00\x01\x02\x03\x04\x05')

        # Should handle binary files gracefully
        result = self.token_service.estimate_file_tokens(binary_file)
        self.assertIn('token_count', result)
        # Binary files should have minimal token count
        self.assertLessEqual(result['token_count'], 10)

    def test_api_endpoint_text_tokens(self):
        """Test /api/tokens/estimate endpoint"""
        with self.client:
            # Login first
            login_response = self.client.post('/api/auth/login', json={})
            self.assertEqual(login_response.status_code, 200)

            # Test valid text
            response = self.client.post('/api/tokens/estimate',
                json={'text': 'Hello, world! This is a test.'})

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)

            self.assertTrue(data['success'])
            self.assertIn('estimation', data)

            estimation = data['estimation']
            self.assertIn('token_count', estimation)
            self.assertGreater(estimation['token_count'], 0)

            # Test empty text
            response = self.client.post('/api/tokens/estimate', json={'text': ''})
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['estimation']['token_count'], 0)

            # Test invalid input
            response = self.client.post('/api/tokens/estimate', json={})
            self.assertEqual(response.status_code, 400)

    def test_api_endpoint_file_tokens(self):
        """Test /api/tokens/file endpoint"""
        with self.client:
            # Login first
            login_response = self.client.post('/api/auth/login', json={})
            self.assertEqual(login_response.status_code, 200)

            # Create test file
            test_file = self.app.config['UPLOAD_FOLDER'] / 'api_test.txt'
            test_file.write_text('This is a test file for API testing.')

            # Test file token estimation
            response = self.client.post('/api/tokens/file',
                json={'file_path': str(test_file), 'use_cache': True})

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)

            self.assertTrue(data['success'])
            self.assertIn('estimation', data)

            estimation = data['estimation']
            self.assertIn('token_count', estimation)
            self.assertGreater(estimation['token_count'], 0)

            # Test non-existent file
            response = self.client.post('/api/tokens/file',
                json={'file_path': '/non/existent.txt'})
            self.assertEqual(response.status_code, 400)

    def test_api_endpoint_conversation_tokens(self):
        """Test /api/tokens/conversation endpoint"""
        with self.client:
            # Login first
            login_response = self.client.post('/api/auth/login', json={})
            self.assertEqual(login_response.status_code, 200)

            # Add messages to conversation
            msg1 = Message(
                conversation_id=self.test_conversation.id,
                role='user',
                content='Hello, how are you?'
            )
            msg2 = Message(
                conversation_id=self.test_conversation.id,
                role='assistant',
                content='I\'m doing well, thank you! How can I help you today?'
            )
            db.session.add(msg1)
            db.session.add(msg2)
            db.session.commit()

            # Test conversation token estimation
            response = self.client.post('/api/tokens/conversation',
                json={'conversation_id': self.test_conversation.uuid})

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)

            self.assertTrue(data['success'])
            self.assertIn('estimation', data)

            estimation = data['estimation']
            self.assertIn('total_tokens', estimation)
            self.assertIn('message_tokens', estimation)
            self.assertGreater(estimation['total_tokens'], 0)

            # Verify conversation was updated with token count
            db.session.refresh(self.test_conversation)
            self.assertEqual(self.test_conversation.total_tokens, estimation['total_tokens'])

    def test_api_cache_management_endpoints(self):
        """Test cache management API endpoints"""
        with self.client:
            # Login first
            login_response = self.client.post('/api/auth/login', json={})
            self.assertEqual(login_response.status_code, 200)

            # Create cache entries
            test_file = self.app.config['UPLOAD_FOLDER'] / 'cache_mgmt_test.txt'
            test_file.write_text('Cache management test content')
            self.token_service.estimate_file_tokens(test_file, use_cache=True)

            # Test cache stats
            response = self.client.get('/api/tokens/cache/stats')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)

            self.assertTrue(data['success'])
            self.assertIn('cache_stats', data)
            stats = data['cache_stats']
            self.assertIn('database_cached_items', stats)
            self.assertGreaterEqual(stats['database_cached_items'], 1)

            # Test cache clear
            response = self.client.post('/api/tokens/cache/clear')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)

            self.assertTrue(data['success'])
            self.assertIn('cleared', data)
            self.assertGreaterEqual(data['cleared']['database_cache'], 1)

            # Verify cache was cleared
            cache_count = TokenCache.query.count()
            self.assertEqual(cache_count, 0)

    def test_token_estimation_performance(self):
        """Test performance of token estimation operations"""
        # Test with various text sizes
        small_text = "Short text"
        medium_text = "This is a medium-sized text that contains several sentences. " * 10
        large_text = "This is a large text block. " * 1000

        test_cases = [
            ("small", small_text),
            ("medium", medium_text),
            ("large", large_text)
        ]

        for size_name, text in test_cases:
            with self.subTest(size=size_name):
                start_time = time.time()
                result = self.token_service.estimate_text_tokens(text)
                end_time = time.time()

                # Performance should be reasonable (under 1 second for large text)
                duration = end_time - start_time
                self.assertLess(duration, 1.0, f"{size_name} text took too long: {duration:.3f}s")

                # Results should be valid
                self.assertGreater(result['token_count'], 0)

    def test_concurrent_token_estimation(self):
        """Test concurrent token estimation requests"""
        import threading
        import queue

        results = queue.Queue()
        errors = queue.Queue()

        def estimate_tokens(text, thread_id):
            try:
                result = self.token_service.estimate_text_tokens(f"Thread {thread_id}: {text}")
                results.put((thread_id, result))
            except Exception as e:
                errors.put((thread_id, e))

        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=estimate_tokens,
                args=(f"Test content for thread {i}", i)
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check results
        self.assertEqual(results.qsize(), 5)
        self.assertEqual(errors.qsize(), 0)

        # Verify all results are valid
        while not results.empty():
            thread_id, result = results.get()
            self.assertIn('token_count', result)
            self.assertGreater(result['token_count'], 0)

    def test_memory_usage_estimation(self):
        """Test memory usage during token estimation"""
        import tracemalloc

        # Start memory tracking
        tracemalloc.start()

        # Estimate tokens for large text
        large_text = "This is a memory usage test. " * 10000

        # Get memory before
        current, peak = tracemalloc.get_traced_memory()
        before_memory = current

        # Perform estimation
        result = self.token_service.estimate_text_tokens(large_text)

        # Get memory after
        current, peak = tracemalloc.get_traced_memory()
        after_memory = current

        tracemalloc.stop()

        # Memory usage should be reasonable (less than 50MB increase)
        memory_increase = after_memory - before_memory
        self.assertLess(memory_increase, 50 * 1024 * 1024,
                       f"Memory usage too high: {memory_increase / 1024 / 1024:.2f} MB")

        # Result should still be valid
        self.assertGreater(result['token_count'], 0)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)