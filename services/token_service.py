#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Token estimation service for Claude AI web interface."""

import os
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
import logging

try:
    import tiktoken
except ImportError:
    raise ImportError("tiktoken library is required. Install with: pip install tiktoken")

# Set up logging
logger = logging.getLogger(__name__)


class TokenEstimationError(Exception):
    """Exception raised for token estimation errors."""
    pass


class TokenService:
    """
    Comprehensive token estimation service using tiktoken library.

    Features:
    - Uses cl100k_base encoding (compatible with Claude/GPT-4)
    - File-based caching with hash-based invalidation
    - Conversation token counting
    - Context window percentage calculations
    - Claude's 200,000 token context window support
    """

    # Claude's context window size
    CLAUDE_CONTEXT_WINDOW = 200_000

    # Supported encodings
    SUPPORTED_ENCODINGS = {
        'cl100k_base': 'claude-3-5-sonnet-20241022',  # Default for Claude/GPT-4
        'p50k_base': 'gpt-3.5-turbo',
        'r50k_base': 'text-davinci-003'
    }

    def __init__(self, encoding_name: str = 'cl100k_base', cache_ttl_hours: int = 24):
        """
        Initialize the token service.

        Args:
            encoding_name: Encoding to use for token counting (default: cl100k_base)
            cache_ttl_hours: Cache time-to-live in hours (default: 24)
        """
        self.encoding_name = encoding_name
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except KeyError:
            raise TokenEstimationError(f"Unsupported encoding: {encoding_name}")

        # In-memory cache for recent estimations
        self._memory_cache: Dict[str, Tuple[int, datetime]] = {}

        logger.info(f"TokenService initialized with encoding: {encoding_name}")

    def estimate_text_tokens(self, text: str) -> Dict[str, Union[int, float]]:
        """
        Estimate tokens for a text string.

        Args:
            text: Input text to analyze

        Returns:
            Dictionary with token count and context window percentage
        """
        if not isinstance(text, str):
            raise TokenEstimationError("Input must be a string")

        if not text.strip():
            return {
                'token_count': 0,
                'character_count': 0,
                'context_percentage': 0.0,
                'remaining_tokens': self.CLAUDE_CONTEXT_WINDOW,
                'encoding': self.encoding_name
            }

        try:
            # Generate cache key from text hash
            text_hash = self._generate_text_hash(text)

            # Check memory cache first
            if text_hash in self._memory_cache:
                cached_count, cache_time = self._memory_cache[text_hash]
                if datetime.utcnow() - cache_time < self.cache_ttl:
                    return self._format_token_response(cached_count, len(text))

            # Count tokens using tiktoken
            tokens = self.encoding.encode(text)
            token_count = len(tokens)

            # Cache the result
            self._memory_cache[text_hash] = (token_count, datetime.utcnow())

            return self._format_token_response(token_count, len(text))

        except Exception as e:
            logger.error(f"Error estimating tokens for text: {e}")
            raise TokenEstimationError(f"Failed to estimate tokens: {str(e)}")

    def estimate_file_tokens(self, file_path: Union[str, Path],
                           use_cache: bool = True) -> Dict[str, Union[int, float, str]]:
        """
        Estimate tokens for a file with caching support.

        Args:
            file_path: Path to the file
            use_cache: Whether to use cached results (default: True)

        Returns:
            Dictionary with token count, file info, and context window percentage
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise TokenEstimationError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise TokenEstimationError(f"Path is not a file: {file_path}")

        try:
            # Get file metadata
            file_size = file_path.stat().st_size
            file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)

            # Generate file hash for caching
            file_hash = self._generate_file_hash(file_path)
            cache_key = f"file_{file_hash}"

            # Check cache if enabled
            if use_cache and cache_key in self._memory_cache:
                cached_count, cache_time = self._memory_cache[cache_key]
                if datetime.utcnow() - cache_time < self.cache_ttl:
                    logger.info(f"Using cached token count for {file_path.name}")
                    response = self._format_token_response(cached_count, file_size)
                    response.update({
                        'file_path': str(file_path),
                        'file_size_bytes': file_size,
                        'file_modified': file_modified.isoformat(),
                        'cached': True
                    })
                    return response

            # Read and process file
            content = self._read_file_safely(file_path)

            # Count tokens
            tokens = self.encoding.encode(content)
            token_count = len(tokens)

            # Cache the result
            if use_cache:
                self._memory_cache[cache_key] = (token_count, datetime.utcnow())

            response = self._format_token_response(token_count, len(content))
            response.update({
                'file_path': str(file_path),
                'file_size_bytes': file_size,
                'file_modified': file_modified.isoformat(),
                'cached': False
            })

            logger.info(f"Estimated {token_count} tokens for {file_path.name}")
            return response

        except Exception as e:
            logger.error(f"Error estimating tokens for file {file_path}: {e}")
            raise TokenEstimationError(f"Failed to estimate file tokens: {str(e)}")

    def estimate_conversation_tokens(self, messages: List[Dict[str, str]],
                                   system_prompt: Optional[str] = None,
                                   project_knowledge: Optional[List[str]] = None) -> Dict[str, Union[int, float]]:
        """
        Estimate total tokens for an entire conversation context.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: Optional system prompt text
            project_knowledge: Optional list of project knowledge content

        Returns:
            Dictionary with detailed token breakdown
        """
        try:
            total_tokens = 0
            breakdown = {
                'system_prompt_tokens': 0,
                'messages_tokens': 0,
                'project_knowledge_tokens': 0,
                'message_count': len(messages)
            }

            # Count system prompt tokens
            if system_prompt:
                system_result = self.estimate_text_tokens(system_prompt)
                breakdown['system_prompt_tokens'] = system_result['token_count']
                total_tokens += breakdown['system_prompt_tokens']

            # Count message tokens
            for message in messages:
                if not isinstance(message, dict) or 'content' not in message:
                    continue

                message_result = self.estimate_text_tokens(message['content'])
                breakdown['messages_tokens'] += message_result['token_count']

                # Add role tokens (approximately 4 tokens per message for role formatting)
                breakdown['messages_tokens'] += 4

            total_tokens += breakdown['messages_tokens']

            # Count project knowledge tokens
            if project_knowledge:
                for knowledge_item in project_knowledge:
                    if isinstance(knowledge_item, str):
                        knowledge_result = self.estimate_text_tokens(knowledge_item)
                        breakdown['project_knowledge_tokens'] += knowledge_result['token_count']

                total_tokens += breakdown['project_knowledge_tokens']

            # Calculate percentages and remaining capacity
            context_percentage = (total_tokens / self.CLAUDE_CONTEXT_WINDOW) * 100
            remaining_tokens = max(0, self.CLAUDE_CONTEXT_WINDOW - total_tokens)

            response = {
                'total_tokens': total_tokens,
                'context_percentage': round(context_percentage, 2),
                'remaining_tokens': remaining_tokens,
                'context_window_size': self.CLAUDE_CONTEXT_WINDOW,
                'encoding': self.encoding_name,
                'breakdown': breakdown,
                'is_over_limit': total_tokens > self.CLAUDE_CONTEXT_WINDOW
            }

            logger.info(f"Conversation token estimate: {total_tokens} tokens ({context_percentage:.1f}% of context)")
            return response

        except Exception as e:
            logger.error(f"Error estimating conversation tokens: {e}")
            raise TokenEstimationError(f"Failed to estimate conversation tokens: {str(e)}")

    def clear_cache(self) -> int:
        """
        Clear the in-memory token cache.

        Returns:
            Number of cached items cleared
        """
        cleared_count = len(self._memory_cache)
        self._memory_cache.clear()
        logger.info(f"Cleared {cleared_count} cached token estimations")
        return cleared_count

    def get_cache_stats(self) -> Dict[str, Union[int, float]]:
        """
        Get statistics about the token cache.

        Returns:
            Dictionary with cache statistics
        """
        current_time = datetime.utcnow()
        expired_count = 0

        for cache_time in [item[1] for item in self._memory_cache.values()]:
            if current_time - cache_time >= self.cache_ttl:
                expired_count += 1

        return {
            'total_cached_items': len(self._memory_cache),
            'expired_items': expired_count,
            'cache_ttl_hours': self.cache_ttl.total_seconds() / 3600,
            'encoding': self.encoding_name
        }

    def _generate_text_hash(self, text: str) -> str:
        """Generate SHA256 hash for text content."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    def _generate_file_hash(self, file_path: Path) -> str:
        """Generate SHA256 hash for file content and metadata."""
        hasher = hashlib.sha256()

        # Include file size and modification time in hash
        stat = file_path.stat()
        hasher.update(f"{stat.st_size}_{stat.st_mtime}".encode('utf-8'))

        # Include first 1KB of file content for quick differentiation
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                hasher.update(chunk)
        except Exception:
            # If we can't read the file, just use metadata
            pass

        return hasher.hexdigest()[:16]

    def _read_file_safely(self, file_path: Path) -> str:
        """Safely read file content with encoding detection."""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception as e:
                raise TokenEstimationError(f"Failed to read file {file_path}: {str(e)}")

        raise TokenEstimationError(f"Could not decode file {file_path} with any supported encoding")

    def _format_token_response(self, token_count: int, character_count: int) -> Dict[str, Union[int, float]]:
        """Format a standard token response dictionary."""
        context_percentage = (token_count / self.CLAUDE_CONTEXT_WINDOW) * 100
        remaining_tokens = max(0, self.CLAUDE_CONTEXT_WINDOW - token_count)

        return {
            'token_count': token_count,
            'character_count': character_count,
            'context_percentage': round(context_percentage, 2),
            'remaining_tokens': remaining_tokens,
            'context_window_size': self.CLAUDE_CONTEXT_WINDOW,
            'encoding': self.encoding_name,
            'characters_per_token': round(character_count / token_count, 2) if token_count > 0 else 0
        }


# Global service instance
_token_service_instance: Optional[TokenService] = None


def get_token_service() -> TokenService:
    """
    Get the global token service instance.

    Returns:
        TokenService instance
    """
    global _token_service_instance

    if _token_service_instance is None:
        _token_service_instance = TokenService()

    return _token_service_instance


def estimate_tokens(text: str) -> Dict[str, Union[int, float]]:
    """
    Convenience function to estimate tokens for text.

    Args:
        text: Input text

    Returns:
        Token estimation dictionary
    """
    return get_token_service().estimate_text_tokens(text)


def estimate_file_tokens(file_path: Union[str, Path]) -> Dict[str, Union[int, float, str]]:
    """
    Convenience function to estimate tokens for a file.

    Args:
        file_path: Path to file

    Returns:
        Token estimation dictionary
    """
    return get_token_service().estimate_file_tokens(file_path)


if __name__ == "__main__":
    # Basic testing
    service = TokenService()

    test_text = "Hello, this is a test message for token estimation."
    result = service.estimate_text_tokens(test_text)

    print("Token Service Test:")
    print(f"Text: {test_text}")
    print(f"Result: {result}")