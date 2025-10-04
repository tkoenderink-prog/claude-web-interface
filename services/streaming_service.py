#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Intelligent streaming service with buffering and flow control."""

import asyncio
import time
import logging
import re
from collections import deque
from dataclasses import dataclass
from typing import AsyncGenerator, Callable, Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)

class ContentType(Enum):
    """Types of content being streamed."""
    TEXT = "text"
    CODE = "code"
    MARKDOWN = "markdown"
    JSON = "json"

class StreamState(Enum):
    """States of the streaming process."""
    IDLE = "idle"
    THINKING = "thinking"
    ANALYZING = "analyzing"
    WRITING = "writing"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"

@dataclass
class StreamChunk:
    """A chunk of streamed content with metadata."""
    content: str
    content_type: ContentType
    position: int
    total_chars: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

@dataclass
class StreamingConfig:
    """Configuration for streaming behavior."""
    min_chunk_size: int = 20  # Minimum characters before sending
    max_delay: float = 0.1    # Maximum seconds to wait before sending
    buffer_size: int = 10     # Maximum chunks to buffer
    retry_attempts: int = 3   # Number of retry attempts
    retry_delay: float = 1.0  # Base delay between retries
    typing_speed: float = 0.05  # Simulated typing speed in seconds per char

class StreamingService:
    """Intelligent streaming service with buffering and flow control."""

    def __init__(self, config: Optional[StreamingConfig] = None):
        self.config = config or StreamingConfig()
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.chunk_queue = asyncio.Queue()
        self.buffer = deque(maxlen=self.config.buffer_size)
        self.is_running = False

    async def start_stream(self, stream_id: str, emit_func: Callable) -> None:
        """Initialize a new streaming session."""
        self.active_streams[stream_id] = {
            'state': StreamState.THINKING,
            'emit_func': emit_func,
            'start_time': time.time(),
            'total_chars': 0,
            'buffer': deque(maxlen=self.config.buffer_size),
            'last_emit': 0,
            'cancelled': False
        }

        # Send initial thinking state
        await self._emit_status(stream_id, StreamState.THINKING, {
            'message': 'Claude is thinking...',
            'timestamp': time.time()
        })

        logger.info(f"Started stream {stream_id}")

    async def cancel_stream(self, stream_id: str) -> None:
        """Cancel an active stream."""
        if stream_id in self.active_streams:
            self.active_streams[stream_id]['cancelled'] = True
            self.active_streams[stream_id]['state'] = StreamState.CANCELLED

            await self._emit_status(stream_id, StreamState.CANCELLED, {
                'message': 'Stream cancelled by user',
                'timestamp': time.time()
            })

            # Clean up after a delay
            asyncio.create_task(self._cleanup_stream(stream_id, delay=1.0))

            logger.info(f"Cancelled stream {stream_id}")

    async def stream_with_buffering(self,
                                  stream_id: str,
                                  generator: AsyncGenerator[str, None],
                                  content_type: ContentType = ContentType.TEXT) -> None:
        """Stream content with intelligent buffering and flow control."""
        if stream_id not in self.active_streams:
            logger.error(f"Stream {stream_id} not initialized")
            return

        stream = self.active_streams[stream_id]
        emit_func = stream['emit_func']

        try:
            # Update state to analyzing/writing
            await self._emit_status(stream_id, StreamState.ANALYZING, {
                'message': 'Claude is analyzing context...',
                'timestamp': time.time()
            })

            # Small delay to show analyzing state
            await asyncio.sleep(0.5)

            await self._emit_status(stream_id, StreamState.WRITING, {
                'message': 'Claude is writing...',
                'timestamp': time.time()
            })

            position = 0
            buffer_content = ""
            last_emit_time = time.time()

            async for chunk in generator:
                if stream['cancelled']:
                    logger.info(f"Stream {stream_id} was cancelled during generation")
                    return

                buffer_content += chunk
                position += len(chunk)

                # Check if we should emit based on size or time
                current_time = time.time()
                time_since_emit = current_time - last_emit_time

                should_emit = (
                    len(buffer_content) >= self.config.min_chunk_size or
                    time_since_emit >= self.config.max_delay or
                    self._is_natural_break(buffer_content)
                )

                if should_emit and buffer_content.strip():
                    # Create chunk with metadata
                    stream_chunk = StreamChunk(
                        content=buffer_content,
                        content_type=content_type,
                        position=position,
                        metadata={
                            'stream_id': stream_id,
                            'is_partial': True,
                            'code_block': self._detect_code_block(buffer_content),
                            'markdown_elements': self._detect_markdown_elements(buffer_content)
                        }
                    )

                    await self._emit_chunk(stream_id, stream_chunk)

                    # Update tracking
                    stream['total_chars'] += len(buffer_content)
                    stream['last_emit'] = current_time
                    last_emit_time = current_time
                    buffer_content = ""

                    # Add small delay for smooth appearance
                    typing_delay = len(buffer_content) * self.config.typing_speed
                    await asyncio.sleep(min(typing_delay, 0.1))

            # Send any remaining content
            if buffer_content.strip():
                final_chunk = StreamChunk(
                    content=buffer_content,
                    content_type=content_type,
                    position=position,
                    total_chars=position,
                    metadata={
                        'stream_id': stream_id,
                        'is_final': True,
                        'code_block': self._detect_code_block(buffer_content),
                        'markdown_elements': self._detect_markdown_elements(buffer_content)
                    }
                )
                await self._emit_chunk(stream_id, final_chunk)

            # Mark stream as complete
            await self._emit_status(stream_id, StreamState.COMPLETE, {
                'message': 'Response complete',
                'total_chars': stream['total_chars'],
                'duration': time.time() - stream['start_time'],
                'timestamp': time.time()
            })

            # Schedule cleanup
            asyncio.create_task(self._cleanup_stream(stream_id, delay=5.0))

        except Exception as e:
            logger.error(f"Error in stream {stream_id}: {str(e)}")
            await self._emit_status(stream_id, StreamState.ERROR, {
                'message': f'Streaming error: {str(e)}',
                'error': str(e),
                'timestamp': time.time()
            })
            asyncio.create_task(self._cleanup_stream(stream_id, delay=1.0))

    async def _emit_chunk(self, stream_id: str, chunk: StreamChunk) -> None:
        """Emit a chunk with retry logic."""
        if stream_id not in self.active_streams:
            return

        emit_func = self.active_streams[stream_id]['emit_func']

        for attempt in range(self.config.retry_attempts):
            try:
                await emit_func('stream_chunk', {
                    'stream_id': stream_id,
                    'content': chunk.content,
                    'content_type': chunk.content_type.value,
                    'position': chunk.position,
                    'total_chars': chunk.total_chars,
                    'metadata': chunk.metadata,
                    'timestamp': chunk.timestamp
                })
                return

            except Exception as e:
                logger.warning(f"Emit attempt {attempt + 1} failed for stream {stream_id}: {str(e)}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    logger.error(f"Failed to emit chunk after {self.config.retry_attempts} attempts")
                    raise

    async def _emit_status(self, stream_id: str, state: StreamState, data: Dict[str, Any]) -> None:
        """Emit status update with retry logic."""
        if stream_id not in self.active_streams:
            return

        emit_func = self.active_streams[stream_id]['emit_func']
        self.active_streams[stream_id]['state'] = state

        try:
            await emit_func('stream_status', {
                'stream_id': stream_id,
                'state': state.value,
                'data': data
            })
        except Exception as e:
            logger.error(f"Failed to emit status for stream {stream_id}: {str(e)}")

    def _is_natural_break(self, content: str) -> bool:
        """Check if content ends at a natural breaking point."""
        if not content:
            return False

        # Natural breaks: sentence endings, paragraph breaks, code block boundaries
        natural_breaks = [
            r'\.\s*$',      # Sentence ending with period
            r'[!?]\s*$',    # Exclamation or question mark
            r'\n\n',        # Paragraph break
            r'```\s*$',     # Code block boundary
            r':\s*$',       # Colon (list or explanation start)
            r';\s*$',       # Semicolon
        ]

        for pattern in natural_breaks:
            if re.search(pattern, content):
                return True

        return False

    def _detect_code_block(self, content: str) -> Optional[Dict[str, Any]]:
        """Detect if content contains code block markers."""
        code_start = re.search(r'```(\w+)?', content)
        code_end = re.search(r'```\s*$', content)

        if code_start:
            return {
                'language': code_start.group(1) or 'text',
                'start_position': code_start.start(),
                'is_opening': True,
                'is_closing': code_end is not None
            }
        elif code_end:
            return {
                'is_closing': True,
                'end_position': code_end.start()
            }

        return None

    def _detect_markdown_elements(self, content: str) -> List[Dict[str, Any]]:
        """Detect markdown elements in content."""
        elements = []

        # Headers
        headers = re.finditer(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
        for match in headers:
            elements.append({
                'type': 'header',
                'level': len(match.group(1)),
                'text': match.group(2),
                'position': match.start()
            })

        # Bold/italic
        bold = re.finditer(r'\*\*(.*?)\*\*', content)
        for match in bold:
            elements.append({
                'type': 'bold',
                'text': match.group(1),
                'position': match.start()
            })

        # Lists
        lists = re.finditer(r'^[\s]*[-*+]\s+(.+)$', content, re.MULTILINE)
        for match in lists:
            elements.append({
                'type': 'list_item',
                'text': match.group(1),
                'position': match.start()
            })

        return elements

    async def _cleanup_stream(self, stream_id: str, delay: float = 0) -> None:
        """Clean up stream resources after delay."""
        if delay > 0:
            await asyncio.sleep(delay)

        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
            logger.info(f"Cleaned up stream {stream_id}")

    def get_stream_status(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a stream."""
        if stream_id in self.active_streams:
            stream = self.active_streams[stream_id]
            return {
                'stream_id': stream_id,
                'state': stream['state'].value,
                'total_chars': stream['total_chars'],
                'duration': time.time() - stream['start_time'],
                'cancelled': stream['cancelled']
            }
        return None

    def get_active_streams(self) -> List[str]:
        """Get list of active stream IDs."""
        return list(self.active_streams.keys())

# Global streaming service instance
_streaming_service = None

def get_streaming_service() -> StreamingService:
    """Get global streaming service instance."""
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = StreamingService()
    return _streaming_service