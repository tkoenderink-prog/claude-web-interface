#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Comprehensive test suite for Claude AI Web Interface v0.2 - Performance Tests

Tests the performance characteristics including:
- Bulk operations with 100+ files
- Streaming latency
- Token calculation speed
- Database query optimization
"""

import unittest
import json
import tempfile
import time
import threading
import queue
import statistics
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from io import BytesIO
import asyncio
import tracemalloc
import psutil
import os

# Add the parent directory to the path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db
from models.models import User, Conversation, ProjectKnowledge, ConversationKnowledge, TokenCache
from services.token_service import get_token_service
from services.streaming_service import get_streaming_service


class TestV02Performance(unittest.TestCase):
    """Performance test suite for Claude AI Web Interface v0.2"""

    def setUp(self):
        """Set up test environment before each test"""
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['ENABLE_PROJECT_KNOWLEDGE'] = True

        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        app.config['UPLOAD_FOLDER'] = self.temp_dir

        # Create vault directories
        self.private_vault = self.temp_dir / 'vault' / 'private'
        self.private_vault.mkdir(parents=True)
        app.config['OBSIDIAN_PRIVATE_PATH'] = str(self.private_vault)

        self.app = app
        self.client = app.test_client()

        # Create application context
        self.app_context = app.app_context()
        self.app_context.push()

        # Create all database tables
        db.create_all()

        # Create test user and conversation
        self.test_user = User(username='perftest', email='perf@test.com')
        db.session.add(self.test_user)
        db.session.commit()

        self.test_conversation = Conversation(
            uuid='perf-conv-123',
            title='Performance Test Conversation',
            user_id=self.test_user.id,
            model='sonnet-4.5'
        )
        db.session.add(self.test_conversation)
        db.session.commit()

        # Initialize services
        self.token_service = get_token_service()
        self.streaming_service = get_streaming_service()

        # Performance thresholds
        self.BULK_OPERATION_THRESHOLD = 30.0  # seconds for 100+ files
        self.STREAMING_LATENCY_THRESHOLD = 0.1  # seconds per chunk
        self.TOKEN_CALCULATION_THRESHOLD = 5.0  # seconds for large text
        self.DATABASE_QUERY_THRESHOLD = 1.0  # seconds for complex queries

    def tearDown(self):
        """Clean up after each test"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        # Clean up temp directory
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def login_user(self):
        """Helper to login user"""
        response = self.client.post('/api/auth/login', json={})
        self.assertEqual(response.status_code, 200)
        return response

    def create_large_file_set(self, count=100):
        """Create a large set of test files"""
        files = []
        categories = ['01-PROJECTS', '02-AREAS', '03-RESOURCES', '04-ARCHIVE']

        for i in range(count):
            category = categories[i % len(categories)]
            file_path = f"{category}/perf_test_{i:04d}.md"

            # Vary content size
            content_size = 100 + (i % 500)  # 100 to 600 words
            content = f"# Performance Test File {i}\n\n" + "This is test content. " * content_size

            full_path = self.private_vault / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

            files.append({
                'vault': 'private',
                'file_path': file_path,
                'category': 'RESOURCE'
            })

        return files

    def test_bulk_operations_100_plus_files(self):
        """Test bulk operations with 100+ files"""
        self.login_user()

        # Create 150 test files
        print("\nCreating 150 test files...")
        files = self.create_large_file_set(150)

        # Test 1: Bulk knowledge search (select all)
        print("Testing bulk knowledge search...")
        start_time = time.time()

        search_response = self.client.post('/api/knowledge/search', json={
            'vault': 'private',
            'query': '',
            'select_all': True
        })

        search_time = time.time() - start_time
        self.assertEqual(search_response.status_code, 200)
        search_data = json.loads(search_response.data)

        print(f"Search completed in {search_time:.2f} seconds for {len(search_data)} files")
        self.assertLess(search_time, 10.0)  # Should complete in under 10 seconds
        self.assertGreaterEqual(len(search_data), 100)

        # Test 2: Bulk add operation
        print("Testing bulk add operation...")
        start_time = time.time()

        # Add first 100 files
        bulk_response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': files[:100]
        })

        bulk_time = time.time() - start_time
        self.assertEqual(bulk_response.status_code, 200)
        bulk_data = json.loads(bulk_response.data)

        print(f"Bulk add completed in {bulk_time:.2f} seconds for 100 files")
        self.assertLess(bulk_time, self.BULK_OPERATION_THRESHOLD)
        self.assertTrue(bulk_data['success'])
        self.assertGreaterEqual(bulk_data['summary']['succeeded'], 90)  # At least 90% success

        # Test 3: Token calculation for large set
        print("Testing token calculation for conversation...")
        start_time = time.time()

        token_response = self.client.post('/api/tokens/conversation', json={
            'conversation_id': self.test_conversation.uuid
        })

        token_time = time.time() - start_time
        self.assertEqual(token_response.status_code, 200)
        token_data = json.loads(token_response.data)

        print(f"Token calculation completed in {token_time:.2f} seconds")
        print(f"Total tokens: {token_data['estimation']['total_tokens']:,}")
        self.assertLess(token_time, 15.0)  # Should complete in under 15 seconds
        self.assertGreater(token_data['estimation']['total_tokens'], 10000)

    def test_streaming_latency(self):
        """Test streaming latency and throughput"""
        print("\nTesting streaming latency...")

        async def run_streaming_test():
            # Create test stream
            stream_id = 'latency-test'

            async def mock_emit(event, data):
                pass

            await self.streaming_service.start_stream(stream_id, mock_emit)

            # Test different chunk sizes
            chunk_sizes = [1, 10, 50, 100, 500]  # characters
            latencies = []

            for chunk_size in chunk_sizes:
                async def chunk_generator():
                    chunk = "x" * chunk_size
                    for _ in range(10):  # 10 chunks per size
                        start = time.time()
                        yield chunk
                        latency = time.time() - start
                        latencies.append(latency)

                await self.streaming_service.stream_with_buffering(
                    f"{stream_id}-{chunk_size}",
                    chunk_generator(),
                    self.streaming_service.ContentType.TEXT
                )

            # Calculate statistics
            avg_latency = statistics.mean(latencies)
            max_latency = max(latencies)

            print(f"Average chunk latency: {avg_latency*1000:.2f}ms")
            print(f"Maximum chunk latency: {max_latency*1000:.2f}ms")

            self.assertLess(avg_latency, self.STREAMING_LATENCY_THRESHOLD)
            self.assertLess(max_latency, self.STREAMING_LATENCY_THRESHOLD * 5)

        asyncio.run(run_streaming_test())

    def test_token_calculation_speed(self):
        """Test token calculation speed for various text sizes"""
        print("\nTesting token calculation speed...")

        test_cases = [
            ("Small", "Hello world! " * 10, 0.1),  # ~30 words
            ("Medium", "This is medium text. " * 100, 0.5),  # ~500 words
            ("Large", "Large text content. " * 1000, 2.0),  # ~3000 words
            ("Very Large", "Very large text. " * 10000, 5.0),  # ~30000 words
        ]

        for size_name, text, max_time in test_cases:
            with self.subTest(size=size_name):
                start_time = time.time()

                result = self.token_service.estimate_text_tokens(text)

                calculation_time = time.time() - start_time

                print(f"{size_name} text ({len(text):,} chars): {calculation_time:.3f}s, {result['token_count']:,} tokens")

                self.assertLess(calculation_time, max_time)
                self.assertGreater(result['token_count'], 0)

                # Test performance per token
                tokens_per_second = result['token_count'] / calculation_time if calculation_time > 0 else float('inf')
                self.assertGreater(tokens_per_second, 100)  # At least 100 tokens per second

    def test_database_query_optimization(self):
        """Test database query performance with large datasets"""
        self.login_user()

        print("\nTesting database query optimization...")

        # Create large dataset
        print("Creating large dataset (1000 knowledge entries)...")
        start_time = time.time()

        # Create knowledge entries directly in database for speed
        knowledge_entries = []
        for i in range(1000):
            knowledge = ProjectKnowledge(
                user_id=self.test_user.id,
                name=f'perf_knowledge_{i:04d}',
                vault_type='private',
                file_path=f'test/perf_{i:04d}.md',
                category='RESOURCE',
                content_preview=f'Performance test content {i}',
                content_hash=f'hash_{i}',
                token_count=50 + (i % 200)
            )
            knowledge_entries.append(knowledge)

            # Batch insert every 100 entries
            if (i + 1) % 100 == 0:
                db.session.add_all(knowledge_entries)
                db.session.commit()
                knowledge_entries = []

        if knowledge_entries:
            db.session.add_all(knowledge_entries)
            db.session.commit()

        creation_time = time.time() - start_time
        print(f"Dataset created in {creation_time:.2f} seconds")

        # Test 1: Simple query performance
        start_time = time.time()
        count = ProjectKnowledge.query.filter_by(user_id=self.test_user.id).count()
        simple_query_time = time.time() - start_time

        print(f"Simple count query: {simple_query_time:.3f}s ({count} records)")
        self.assertLess(simple_query_time, 0.5)
        self.assertEqual(count, 1000)

        # Test 2: Complex query with joins
        start_time = time.time()

        # Query knowledge with conversation links
        complex_query = db.session.query(ProjectKnowledge).join(
            ConversationKnowledge,
            ProjectKnowledge.id == ConversationKnowledge.knowledge_id,
            isouter=True
        ).filter(ProjectKnowledge.user_id == self.test_user.id).all()

        complex_query_time = time.time() - start_time

        print(f"Complex join query: {complex_query_time:.3f}s ({len(complex_query)} records)")
        self.assertLess(complex_query_time, 2.0)

        # Test 3: Search-like query
        start_time = time.time()

        search_results = ProjectKnowledge.query.filter(
            ProjectKnowledge.user_id == self.test_user.id,
            ProjectKnowledge.name.like('%perf%')
        ).limit(100).all()

        search_query_time = time.time() - start_time

        print(f"Search query: {search_query_time:.3f}s ({len(search_results)} results)")
        self.assertLess(search_query_time, 1.0)
        self.assertEqual(len(search_results), 100)

        # Test 4: Aggregate query
        start_time = time.time()

        total_tokens = db.session.query(
            db.func.sum(ProjectKnowledge.token_count)
        ).filter(ProjectKnowledge.user_id == self.test_user.id).scalar()

        aggregate_query_time = time.time() - start_time

        print(f"Aggregate query: {aggregate_query_time:.3f}s (total tokens: {total_tokens:,})")
        self.assertLess(aggregate_query_time, 0.5)
        self.assertGreater(total_tokens, 50000)

    def test_concurrent_operations_performance(self):
        """Test performance under concurrent operations"""
        self.login_user()

        print("\nTesting concurrent operations performance...")

        # Create test files
        files = self.create_large_file_set(50)

        results = queue.Queue()
        errors = queue.Queue()

        def worker_thread(thread_id, operation_type):
            """Worker thread for concurrent operations"""
            try:
                start_time = time.time()

                if operation_type == 'search':
                    response = self.client.post('/api/knowledge/search', json={
                        'vault': 'private',
                        'query': f'perf_test_{thread_id:04d}'
                    })

                elif operation_type == 'add':
                    file_subset = files[thread_id*5:(thread_id+1)*5]  # 5 files per thread
                    response = self.client.post('/api/knowledge/add-bulk', json={
                        'conversation_id': self.test_conversation.uuid,
                        'files': file_subset
                    })

                elif operation_type == 'token':
                    response = self.client.post('/api/tokens/text', json={
                        'text': f'Token test content for thread {thread_id}. ' * 100
                    })

                elif operation_type == 'permission':
                    response = self.client.put('/api/permissions', json={
                        'permissions': {
                            'webSearch': thread_id % 2 == 0,
                            'vaultSearch': True
                        }
                    })

                operation_time = time.time() - start_time

                results.put({
                    'thread_id': thread_id,
                    'operation': operation_type,
                    'time': operation_time,
                    'status': response.status_code,
                    'success': response.status_code in [200, 201]
                })

            except Exception as e:
                errors.put({
                    'thread_id': thread_id,
                    'operation': operation_type,
                    'error': str(e)
                })

        # Test different operation types concurrently
        operation_types = ['search', 'add', 'token', 'permission']
        threads = []

        start_time = time.time()

        # Start 20 threads (5 per operation type)
        for i in range(20):
            operation = operation_types[i % len(operation_types)]
            thread = threading.Thread(target=worker_thread, args=(i, operation))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        total_time = time.time() - start_time

        # Analyze results
        operation_results = []
        while not results.empty():
            operation_results.append(results.get())

        operation_errors = []
        while not errors.empty():
            operation_errors.append(errors.get())

        print(f"Concurrent operations completed in {total_time:.2f} seconds")
        print(f"Successful operations: {len(operation_results)}")
        print(f"Failed operations: {len(operation_errors)}")

        # Performance assertions
        self.assertLess(total_time, 60.0)  # Should complete in under 1 minute
        self.assertGreater(len(operation_results), 15)  # At least 75% should succeed
        self.assertLess(len(operation_errors), 5)  # Less than 25% should fail

        # Check individual operation times
        operation_times = [r['time'] for r in operation_results]
        avg_operation_time = statistics.mean(operation_times)
        max_operation_time = max(operation_times)

        print(f"Average operation time: {avg_operation_time:.3f}s")
        print(f"Maximum operation time: {max_operation_time:.3f}s")

        self.assertLess(avg_operation_time, 3.0)  # Average should be under 3 seconds
        self.assertLess(max_operation_time, 10.0)  # Max should be under 10 seconds

    def test_memory_usage_performance(self):
        """Test memory usage during intensive operations"""
        print("\nTesting memory usage performance...")

        # Start memory tracking
        tracemalloc.start()
        process = psutil.Process(os.getpid())

        # Get initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        initial_tracemalloc = tracemalloc.get_traced_memory()[0] / 1024 / 1024  # MB

        print(f"Initial memory: {initial_memory:.2f} MB")

        self.login_user()

        # Perform memory-intensive operations
        files = self.create_large_file_set(100)

        # Operation 1: Bulk add
        bulk_response = self.client.post('/api/knowledge/add-bulk', json={
            'conversation_id': self.test_conversation.uuid,
            'files': files
        })
        self.assertEqual(bulk_response.status_code, 200)

        # Check memory after bulk add
        after_bulk_memory = process.memory_info().rss / 1024 / 1024  # MB
        after_bulk_tracemalloc = tracemalloc.get_traced_memory()[0] / 1024 / 1024  # MB

        print(f"Memory after bulk add: {after_bulk_memory:.2f} MB (+{after_bulk_memory - initial_memory:.2f} MB)")

        # Operation 2: Large token calculation
        large_text = "Large text for token calculation. " * 10000
        token_response = self.client.post('/api/tokens/estimate', json={
            'text': large_text
        })
        self.assertEqual(token_response.status_code, 200)

        # Check memory after token calculation
        after_token_memory = process.memory_info().rss / 1024 / 1024  # MB
        after_token_tracemalloc = tracemalloc.get_traced_memory()[0] / 1024 / 1024  # MB

        print(f"Memory after token calculation: {after_token_memory:.2f} MB (+{after_token_memory - initial_memory:.2f} MB)")

        # Operation 3: Multiple searches
        for i in range(10):
            search_response = self.client.post('/api/knowledge/search', json={
                'vault': 'private',
                'query': f'test_{i}',
                'select_all': False
            })

        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        final_tracemalloc = tracemalloc.get_traced_memory()[0] / 1024 / 1024  # MB

        print(f"Final memory: {final_memory:.2f} MB (+{final_memory - initial_memory:.2f} MB)")

        tracemalloc.stop()

        # Memory assertions
        memory_increase = final_memory - initial_memory
        self.assertLess(memory_increase, 100)  # Should not increase by more than 100MB

        # Memory should not grow excessively during operations
        max_intermediate_increase = max(
            after_bulk_memory - initial_memory,
            after_token_memory - initial_memory
        )
        self.assertLess(max_intermediate_increase, 150)  # Max 150MB increase during operations

    def test_file_upload_performance(self):
        """Test file upload performance with various file sizes"""
        self.login_user()

        print("\nTesting file upload performance...")

        # Test different file sizes
        file_sizes = [
            (1, "1KB"),
            (10, "10KB"),
            (100, "100KB"),
            (1000, "1MB"),
            (5000, "5MB")
        ]

        upload_times = []

        for size_kb, size_name in file_sizes:
            # Create file content
            content = "x" * (size_kb * 1024)  # size_kb * 1024 bytes
            test_file = BytesIO(content.encode('utf-8'))
            test_file.name = f'perf_test_{size_name}.txt'

            start_time = time.time()

            response = self.client.post('/api/upload',
                data={'file': (test_file, f'perf_test_{size_name}.txt')},
                content_type='multipart/form-data'
            )

            upload_time = time.time() - start_time
            upload_times.append(upload_time)

            print(f"{size_name} upload: {upload_time:.3f}s")

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertTrue(data['success'])

            # Performance assertions based on file size
            if size_kb <= 100:  # Files up to 100KB should upload quickly
                self.assertLess(upload_time, 2.0)
            elif size_kb <= 1000:  # Files up to 1MB should upload reasonably fast
                self.assertLess(upload_time, 10.0)
            else:  # Larger files can take more time
                self.assertLess(upload_time, 30.0)

        # Check upload time scaling
        # Upload time should not scale exponentially with file size
        if len(upload_times) >= 3:
            # Ratio of last to first should be reasonable
            time_ratio = upload_times[-1] / upload_times[0] if upload_times[0] > 0 else 1
            size_ratio = file_sizes[-1][0] / file_sizes[0][0]

            print(f"Time scaling ratio: {time_ratio:.2f}x for {size_ratio:.2f}x size increase")

            # Time should not scale worse than O(n^2)
            self.assertLess(time_ratio, size_ratio ** 1.5)

    def test_cache_performance(self):
        """Test cache performance and hit rates"""
        print("\nTesting cache performance...")

        # Create test files for caching
        test_files = []
        for i in range(20):
            file_path = self.temp_dir / f'cache_test_{i}.txt'
            content = f"Cache test content {i}. " * (10 + i)  # Varying sizes
            file_path.write_text(content)
            test_files.append(file_path)

        # Test 1: Initial token estimation (should populate cache)
        cache_miss_times = []
        for file_path in test_files:
            start_time = time.time()

            result = self.token_service.estimate_file_tokens(file_path, use_cache=True)

            estimation_time = time.time() - start_time
            cache_miss_times.append(estimation_time)

            self.assertFalse(result.get('cached', True))  # Should not be cached initially

        avg_cache_miss_time = statistics.mean(cache_miss_times)
        print(f"Average cache miss time: {avg_cache_miss_time:.3f}s")

        # Test 2: Repeated token estimation (should use cache)
        cache_hit_times = []
        for file_path in test_files:
            start_time = time.time()

            result = self.token_service.estimate_file_tokens(file_path, use_cache=True)

            estimation_time = time.time() - start_time
            cache_hit_times.append(estimation_time)

            self.assertTrue(result.get('cached', False))  # Should be cached now

        avg_cache_hit_time = statistics.mean(cache_hit_times)
        print(f"Average cache hit time: {avg_cache_hit_time:.3f}s")

        # Cache hits should be significantly faster
        cache_speedup = avg_cache_miss_time / avg_cache_hit_time if avg_cache_hit_time > 0 else 1
        print(f"Cache speedup: {cache_speedup:.1f}x")

        self.assertGreater(cache_speedup, 5.0)  # Cache should be at least 5x faster
        self.assertLess(avg_cache_hit_time, 0.01)  # Cache hits should be under 10ms

        # Test cache cleanup performance
        start_time = time.time()
        expired_count = TokenCache.cleanup_expired()
        cleanup_time = time.time() - start_time

        print(f"Cache cleanup time: {cleanup_time:.3f}s ({expired_count} entries)")
        self.assertLess(cleanup_time, 1.0)  # Cleanup should be fast


if __name__ == '__main__':
    # Run tests with verbose output
    print("Starting Claude AI Web Interface v0.2 Performance Tests")
    print("=" * 60)

    # Check system resources
    process = psutil.Process()
    print(f"Available memory: {psutil.virtual_memory().available / 1024 / 1024 / 1024:.1f} GB")
    print(f"CPU count: {psutil.cpu_count()}")
    print()

    unittest.main(verbosity=2)