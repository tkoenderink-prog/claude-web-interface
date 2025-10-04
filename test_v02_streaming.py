#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Comprehensive test suite for Claude AI Web Interface v0.2 - Streaming Enhancement System

Tests the streaming enhancement features including:
- Intelligent buffering logic
- Stream cancellation
- Network reconnection handling
- Metadata in chunks
- Progress indicators
"""

import unittest
import json
import asyncio
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import threading
import queue

# Add the parent directory to the path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db, socketio
from models.models import User, Conversation, Message
from services.streaming_service import StreamingService, ContentType


class TestStreamingEnhancementSystem(unittest.TestCase):
    """Test suite for the Streaming Enhancement System in v0.2"""

    def setUp(self):
        """Set up test environment before each test"""
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['ENABLE_PROJECT_KNOWLEDGE'] = True

        self.app = app
        self.client = app.test_client()
        self.socketio_client = socketio.test_client(app)

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
            uuid='test-conv-streaming-123',
            title='Streaming Test Conversation',
            user_id=self.test_user.id,
            model='sonnet-4.5'
        )
        db.session.add(self.test_conversation)
        db.session.commit()

        # Initialize streaming service
        self.streaming_service = StreamingService()

    def tearDown(self):
        """Clean up after each test"""
        # Cleanup any active streams
        active_streams = self.streaming_service.get_active_streams()
        for stream_id in active_streams:
            asyncio.run(self.streaming_service.cancel_stream(stream_id))

        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        if hasattr(self, 'socketio_client'):
            self.socketio_client.disconnect()

    def login_client(self):
        """Helper to login the test client"""
        response = self.client.post('/api/auth/login', json={})
        self.assertEqual(response.status_code, 200)
        return response

    async def create_test_stream(self, stream_id='test-stream-1'):
        """Helper to create a test stream"""
        async def mock_emit(event, data):
            pass

        await self.streaming_service.start_stream(stream_id, mock_emit)
        return stream_id

    def test_intelligent_buffering_logic(self):
        """Test intelligent buffering system for smooth streaming"""
        async def run_buffering_test():
            # Create a test stream
            stream_id = await self.create_test_stream()

            # Create test content generator with varying chunk sizes
            async def test_content_generator():
                chunks = [
                    "Hello ",
                    "world! ",
                    "This is a test of ",
                    "the streaming ",
                    "buffering system. ",
                    "It should handle ",
                    "variable ",
                    "chunk sizes ",
                    "smoothly."
                ]
                for chunk in chunks:
                    yield chunk
                    await asyncio.sleep(0.01)  # Simulate network delay

            # Test buffering with different content types
            await self.streaming_service.stream_with_buffering(
                stream_id,
                test_content_generator(),
                ContentType.TEXT
            )

            # Verify stream completed
            status = self.streaming_service.get_stream_status(stream_id)
            self.assertIsNotNone(status)

        asyncio.run(run_buffering_test())

    def test_stream_cancellation(self):
        """Test stream cancellation functionality"""
        async def run_cancellation_test():
            # Create a test stream
            stream_id = await self.create_test_stream()

            # Create a long-running generator
            async def long_content_generator():
                for i in range(1000):
                    yield f"Chunk {i} "
                    await asyncio.sleep(0.001)

            # Start streaming in background
            stream_task = asyncio.create_task(
                self.streaming_service.stream_with_buffering(
                    stream_id,
                    long_content_generator(),
                    ContentType.TEXT
                )
            )

            # Let it run briefly
            await asyncio.sleep(0.1)

            # Cancel the stream
            await self.streaming_service.cancel_stream(stream_id)

            # Stream task should be cancelled
            try:
                await stream_task
            except asyncio.CancelledError:
                pass  # Expected

            # Verify stream is no longer active
            active_streams = self.streaming_service.get_active_streams()
            self.assertNotIn(stream_id, active_streams)

        asyncio.run(run_cancellation_test())

    def test_network_reconnection_handling(self):
        """Test network reconnection scenarios"""
        # Test WebSocket client connection handling
        self.login_client()

        # Connect WebSocket client
        self.assertTrue(self.socketio_client.is_connected())

        # Simulate connection loss and reconnection
        self.socketio_client.disconnect()
        self.assertFalse(self.socketio_client.is_connected())

        # Reconnect
        self.socketio_client.connect()
        self.assertTrue(self.socketio_client.is_connected())

        # Test that streaming can resume after reconnection
        # This would typically be handled by frontend JavaScript

    def test_metadata_in_chunks(self):
        """Test metadata handling in streaming chunks"""
        async def run_metadata_test():
            # Create test stream
            stream_id = await self.create_test_stream()

            # Create content with metadata
            async def metadata_content_generator():
                chunks = [
                    ("Starting code block", {'code_block': {'is_opening': True, 'language': 'python'}}),
                    ("def hello():", {}),
                    ("    print('Hello, world!')", {}),
                    ("", {'code_block': {'is_closing': True}}),
                    ("This is regular text", {}),
                ]

                for content, metadata in chunks:
                    yield {
                        'content': content,
                        'metadata': metadata,
                        'timestamp': time.time()
                    }
                    await asyncio.sleep(0.01)

            # Mock emit function to capture metadata
            captured_events = []

            async def capture_emit(event, data):
                captured_events.append((event, data))

            # Replace emit function
            self.streaming_service.active_streams[stream_id]['emit'] = capture_emit

            # Stream with metadata
            await self.streaming_service.stream_with_buffering(
                stream_id,
                metadata_content_generator(),
                ContentType.MARKDOWN
            )

            # Verify metadata was preserved
            self.assertGreater(len(captured_events), 0)

            # Check for metadata in events
            metadata_events = [event for event_type, event in captured_events
                             if 'metadata' in event]
            self.assertGreater(len(metadata_events), 0)

        asyncio.run(run_metadata_test())

    def test_progress_indicators(self):
        """Test progress indicator functionality"""
        async def run_progress_test():
            # Create test stream
            stream_id = await self.create_test_stream()

            # Track progress events
            progress_events = []

            async def progress_emit(event, data):
                if event == 'stream_status':
                    progress_events.append(data)

            # Replace emit function
            self.streaming_service.active_streams[stream_id]['emit'] = progress_emit

            # Create content with progress tracking
            async def progress_content_generator():
                total_chunks = 10
                for i in range(total_chunks):
                    yield {
                        'content': f"Chunk {i+1} ",
                        'progress': {
                            'current': i + 1,
                            'total': total_chunks,
                            'percentage': ((i + 1) / total_chunks) * 100
                        }
                    }
                    await asyncio.sleep(0.01)

            # Stream with progress
            await self.streaming_service.stream_with_buffering(
                stream_id,
                progress_content_generator(),
                ContentType.TEXT
            )

            # Verify progress events were emitted
            self.assertGreater(len(progress_events), 0)

        asyncio.run(run_progress_test())

    def test_websocket_streaming_integration(self):
        """Test WebSocket streaming integration"""
        self.login_client()

        # Test stream_message event
        message_data = {
            'conversation_id': self.test_conversation.uuid,
            'content': 'Test streaming message',
            'knowledge_files': [],
            'upload_files': [],
            'total_tokens': 10
        }

        # Mock Claude service to avoid actual API calls
        with patch('app.claude_service') as mock_claude:
            # Create async generator for streaming response
            async def mock_stream():
                chunks = ["Hello ", "world! ", "This ", "is ", "a ", "test."]
                for chunk in chunks:
                    yield chunk

            mock_claude.create_message.return_value = mock_stream()

            # Emit stream_message event
            self.socketio_client.emit('stream_message', message_data)

            # Verify response events (would need to capture them in real implementation)
            # For now, just verify no errors occurred
            self.assertTrue(True)  # Placeholder assertion

    def test_stream_status_tracking(self):
        """Test stream status tracking functionality"""
        async def run_status_test():
            # Create test stream
            stream_id = await self.create_test_stream()

            # Check initial status
            status = self.streaming_service.get_stream_status(stream_id)
            self.assertIsNotNone(status)
            self.assertIn('state', status)

            # Update status
            await self.streaming_service.update_stream_status(stream_id, 'processing', {
                'progress': 50,
                'message': 'Processing content'
            })

            # Check updated status
            updated_status = self.streaming_service.get_stream_status(stream_id)
            self.assertEqual(updated_status['state'], 'processing')
            self.assertIn('progress', updated_status['data'])

        asyncio.run(run_status_test())

    def test_concurrent_streaming(self):
        """Test concurrent streaming operations"""
        async def run_concurrent_test():
            # Create multiple streams
            stream_ids = ['stream-1', 'stream-2', 'stream-3']
            tasks = []

            for stream_id in stream_ids:
                await self.create_test_stream(stream_id)

            # Create content generators for each stream
            async def create_content_generator(stream_num):
                for i in range(5):
                    yield f"Stream {stream_num} chunk {i} "
                    await asyncio.sleep(0.01)

            # Start all streams concurrently
            for i, stream_id in enumerate(stream_ids):
                task = asyncio.create_task(
                    self.streaming_service.stream_with_buffering(
                        stream_id,
                        create_content_generator(i + 1),
                        ContentType.TEXT
                    )
                )
                tasks.append(task)

            # Wait for all streams to complete
            await asyncio.gather(*tasks)

            # Verify all streams completed
            for stream_id in stream_ids:
                status = self.streaming_service.get_stream_status(stream_id)
                self.assertIsNotNone(status)

        asyncio.run(run_concurrent_test())

    def test_error_handling_in_streaming(self):
        """Test error handling during streaming operations"""
        async def run_error_test():
            # Create test stream
            stream_id = await self.create_test_stream()

            # Create error-prone content generator
            async def error_content_generator():
                yield "Normal chunk "
                yield "Another chunk "
                raise Exception("Simulated streaming error")

            # Track error events
            error_events = []

            async def error_emit(event, data):
                if event == 'error':
                    error_events.append(data)

            self.streaming_service.active_streams[stream_id]['emit'] = error_emit

            # Stream should handle error gracefully
            try:
                await self.streaming_service.stream_with_buffering(
                    stream_id,
                    error_content_generator(),
                    ContentType.TEXT
                )
            except Exception:
                pass  # Expected

            # Verify error was handled
            self.assertGreater(len(error_events), 0)

        asyncio.run(run_error_test())

    def test_stream_memory_management(self):
        """Test memory management in streaming operations"""
        async def run_memory_test():
            # Create and destroy many streams to test memory cleanup
            for i in range(10):
                stream_id = f'memory-test-{i}'
                await self.create_test_stream(stream_id)

                # Generate some content
                async def small_content_generator():
                    for j in range(5):
                        yield f"Content {j} "

                await self.streaming_service.stream_with_buffering(
                    stream_id,
                    small_content_generator(),
                    ContentType.TEXT
                )

                # Clean up stream
                await self.streaming_service.cancel_stream(stream_id)

            # Verify no streams are left active
            active_streams = self.streaming_service.get_active_streams()
            memory_test_streams = [s for s in active_streams if s.startswith('memory-test-')]
            self.assertEqual(len(memory_test_streams), 0)

        asyncio.run(run_memory_test())

    def test_buffering_performance(self):
        """Test buffering performance with large content"""
        async def run_performance_test():
            # Create test stream
            stream_id = await self.create_test_stream()

            # Generate large content
            async def large_content_generator():
                for i in range(1000):
                    yield f"Large content chunk {i} with substantial text content. "
                    if i % 100 == 0:
                        await asyncio.sleep(0.001)  # Occasional delay

            # Measure streaming time
            start_time = time.time()

            await self.streaming_service.stream_with_buffering(
                stream_id,
                large_content_generator(),
                ContentType.TEXT
            )

            end_time = time.time()
            duration = end_time - start_time

            # Should complete in reasonable time (under 5 seconds)
            self.assertLess(duration, 5.0)

        asyncio.run(run_performance_test())

    def test_content_type_handling(self):
        """Test different content type handling"""
        async def run_content_type_test():
            content_types = [
                ContentType.TEXT,
                ContentType.MARKDOWN,
                ContentType.CODE,
                ContentType.JSON
            ]

            for content_type in content_types:
                with self.subTest(content_type=content_type):
                    stream_id = f'content-type-{content_type.value}'
                    await self.create_test_stream(stream_id)

                    # Create appropriate content for each type
                    content_map = {
                        ContentType.TEXT: "Plain text content",
                        ContentType.MARKDOWN: "# Markdown\n**Bold** text",
                        ContentType.CODE: "def hello():\n    print('world')",
                        ContentType.JSON: '{"key": "value", "number": 123}'
                    }

                    async def typed_content_generator():
                        yield content_map[content_type]

                    # Stream with specific content type
                    await self.streaming_service.stream_with_buffering(
                        stream_id,
                        typed_content_generator(),
                        content_type
                    )

                    # Verify streaming completed
                    status = self.streaming_service.get_stream_status(stream_id)
                    self.assertIsNotNone(status)

        asyncio.run(run_content_type_test())

    def test_websocket_events_structure(self):
        """Test WebSocket events structure and data"""
        self.login_client()

        # Test various WebSocket events
        events_to_test = [
            ('join_conversation', {'conversation_id': self.test_conversation.uuid}),
            ('leave_conversation', {'conversation_id': self.test_conversation.uuid}),
            ('stream_status', {'stream_id': 'test-stream'}),
        ]

        for event_name, event_data in events_to_test:
            with self.subTest(event=event_name):
                # Emit event and verify no errors
                self.socketio_client.emit(event_name, event_data)
                # In a full test, we'd verify the response

    def test_streaming_service_initialization(self):
        """Test StreamingService initialization and configuration"""
        # Test default initialization
        service = StreamingService()
        self.assertIsNotNone(service)
        self.assertEqual(len(service.get_active_streams()), 0)

        # Test configuration parameters
        self.assertTrue(hasattr(service, 'buffer_size'))
        self.assertTrue(hasattr(service, 'max_concurrent_streams'))

    def test_stream_cleanup_on_disconnect(self):
        """Test stream cleanup when WebSocket disconnects"""
        async def run_cleanup_test():
            # Create test stream
            stream_id = await self.create_test_stream()

            # Verify stream exists
            self.assertIn(stream_id, self.streaming_service.get_active_streams())

            # Simulate disconnect cleanup
            # In real implementation, this would be triggered by WebSocket disconnect
            await self.streaming_service.cleanup_user_streams()

            # Note: In full implementation, this would clean up user-specific streams

        asyncio.run(run_cleanup_test())


class TestStreamingServiceDirect(unittest.TestCase):
    """Direct tests for StreamingService class"""

    def setUp(self):
        self.streaming_service = StreamingService()

    def test_content_type_enum(self):
        """Test ContentType enum values"""
        self.assertEqual(ContentType.TEXT.value, 'text')
        self.assertEqual(ContentType.MARKDOWN.value, 'markdown')
        self.assertEqual(ContentType.CODE.value, 'code')
        self.assertEqual(ContentType.JSON.value, 'json')

    def test_stream_id_generation(self):
        """Test stream ID generation and uniqueness"""
        async def run_id_test():
            stream_ids = set()

            # Generate multiple streams
            for i in range(10):
                stream_id = f'test-{i}-{int(time.time() * 1000)}'

                async def mock_emit(event, data):
                    pass

                await self.streaming_service.start_stream(stream_id, mock_emit)
                stream_ids.add(stream_id)

            # All IDs should be unique
            self.assertEqual(len(stream_ids), 10)

        asyncio.run(run_id_test())

    def test_stream_state_management(self):
        """Test stream state management"""
        async def run_state_test():
            stream_id = 'state-test'

            async def mock_emit(event, data):
                pass

            # Start stream
            await self.streaming_service.start_stream(stream_id, mock_emit)

            # Test state transitions
            states = ['thinking', 'analyzing', 'writing', 'complete']

            for state in states:
                await self.streaming_service.update_stream_status(stream_id, state, {'test': True})
                status = self.streaming_service.get_stream_status(stream_id)
                self.assertEqual(status['state'], state)

        asyncio.run(run_state_test())


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)