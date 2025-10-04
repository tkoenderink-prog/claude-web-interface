# Token Estimation System Documentation

## Overview

The Token Estimation System provides comprehensive token counting capabilities for the Claude AI web interface, enabling users and the system to understand and manage context window usage effectively.

## Features

### Core Capabilities
- **Text Token Estimation**: Count tokens for any text string
- **File Token Estimation**: Count tokens for files with caching
- **Conversation Token Estimation**: Calculate total tokens for entire conversations including system prompts and project knowledge
- **Smart Caching**: File-based caching with hash-based invalidation
- **Context Window Management**: Percentage calculations relative to Claude's 200,000 token context window
- **Multiple Encoding Support**: Primary support for `cl100k_base` (Claude/GPT-4 compatible)

### Performance Features
- **Memory Cache**: In-memory caching for frequently accessed content
- **Database Cache**: Persistent caching with TTL (24-hour default)
- **File Hash Caching**: Avoids recalculation when files haven't changed
- **Batch Processing**: Efficient handling of multiple estimation requests

## System Architecture

### Components

#### 1. Token Service (`services/token_service.py`)
Core service providing token estimation functionality:

```python
from services.token_service import get_token_service

token_service = get_token_service()
result = token_service.estimate_text_tokens("Hello, world!")
```

**Key Methods:**
- `estimate_text_tokens(text)` - Estimate tokens for text strings
- `estimate_file_tokens(file_path, use_cache=True)` - Estimate tokens for files
- `estimate_conversation_tokens(messages, system_prompt, project_knowledge)` - Full conversation estimation
- `clear_cache()` - Clear in-memory cache
- `get_cache_stats()` - Get cache statistics

#### 2. Database Models (`models/models.py`)
Enhanced models with token counting support:

**New Model: TokenCache**
```sql
CREATE TABLE token_cache (
    id INTEGER PRIMARY KEY,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    token_count INTEGER NOT NULL,
    character_count INTEGER NOT NULL,
    encoding_name VARCHAR(50) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    created_at DATETIME,
    expires_at DATETIME NOT NULL,
    source_info TEXT
);
```

**Enhanced Models:**
- `ProjectKnowledge.token_count` - Token count for knowledge files
- `Conversation.total_tokens` - Total tokens for conversation
- `FileAttachment.token_count` - Token count for uploaded files

#### 3. API Endpoints (`app.py`)
RESTful API for token estimation:

**Available Endpoints:**
- `POST /api/tokens/estimate` - Estimate tokens for text
- `POST /api/tokens/file` - Estimate tokens for files
- `POST /api/tokens/conversation` - Estimate conversation tokens
- `GET /api/tokens/cache/stats` - Get cache statistics
- `POST /api/tokens/cache/clear` - Clear all caches
- `POST /api/tokens/cache/cleanup` - Remove expired cache entries

## Usage Examples

### Basic Text Estimation

```python
# Direct service usage
from services.token_service import get_token_service

token_service = get_token_service()
result = token_service.estimate_text_tokens("Your text here")

print(f"Tokens: {result['token_count']}")
print(f"Context %: {result['context_percentage']:.2f}%")
print(f"Remaining: {result['remaining_tokens']:,}")
```

### API Usage

```bash
# Estimate text tokens
curl -X POST http://localhost:5000/api/tokens/estimate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, world!"}'

# Estimate file tokens
curl -X POST http://localhost:5000/api/tokens/file \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/path/to/file.txt", "use_cache": true}'

# Get conversation tokens
curl -X POST http://localhost:5000/api/tokens/conversation \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "uuid-here"}'
```

### Response Format

All estimation endpoints return structured JSON:

```json
{
  "success": true,
  "estimation": {
    "token_count": 150,
    "character_count": 800,
    "context_percentage": 0.075,
    "remaining_tokens": 199850,
    "context_window_size": 200000,
    "encoding": "cl100k_base",
    "characters_per_token": 5.33
  }
}
```

## Configuration

### Token Service Configuration

```python
from services.token_service import TokenService

# Custom configuration
token_service = TokenService(
    encoding_name='cl100k_base',  # Encoding to use
    cache_ttl_hours=24           # Cache time-to-live
)
```

### Supported Encodings

- `cl100k_base` - Claude 3.5 Sonnet / GPT-4 (default)
- `p50k_base` - GPT-3.5 Turbo
- `r50k_base` - Text-Davinci-003

### Context Window

- **Claude 3.5 Sonnet**: 200,000 tokens
- Configurable via `TokenService.CLAUDE_CONTEXT_WINDOW`

## Caching Strategy

### Two-Tier Caching System

#### 1. Memory Cache (Fast Access)
- **Storage**: In-memory dictionary
- **TTL**: 24 hours (configurable)
- **Key**: SHA256 hash of content (first 16 chars)
- **Use Case**: Frequently accessed content

#### 2. Database Cache (Persistent)
- **Storage**: SQLite/PostgreSQL table
- **TTL**: 24 hours with automatic cleanup
- **Key**: SHA256 hash of content + metadata
- **Use Case**: Long-term storage, cross-session persistence

### Cache Invalidation
- **Text**: Content hash changes when text changes
- **Files**: Hash includes file size, modification time, and content sample
- **Automatic Cleanup**: Expired entries removed via API or scheduled task

## Performance Characteristics

### Benchmark Results
Based on testing with various content sizes:

| Content Size | Tokens | Processing Time | Cache Hit Time |
|-------------|--------|----------------|----------------|
| Short text (< 100 chars) | ~25 | 5-10ms | <1ms |
| Medium text (1KB) | ~250 | 10-15ms | <1ms |
| Large text (10KB) | ~2,500 | 50-100ms | <1ms |
| Very large (100KB) | ~25,000 | 500ms-1s | <1ms |

### Optimization Tips
1. **Enable Caching**: Always use `use_cache=True` for files
2. **Batch Operations**: Group multiple estimations when possible
3. **Cache Management**: Regular cleanup of expired entries
4. **File Watching**: Monitor file changes to invalidate cache

## Error Handling

### Exception Types

```python
from services.token_service import TokenEstimationError

try:
    result = token_service.estimate_text_tokens(invalid_input)
except TokenEstimationError as e:
    print(f"Token estimation failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Common Error Scenarios
- **Invalid Input Types**: Non-string input for text estimation
- **File Not Found**: Attempting to estimate tokens for non-existent files
- **Encoding Errors**: Unsupported file encodings
- **Memory Limits**: Very large files exceeding system memory

## Database Integration

### Schema Migrations

When upgrading existing installations, run database migrations:

```python
# Migration script example
from flask import Flask
from models.models import db

app = Flask(__name__)
# Configure app...

with app.app_context():
    # Add new columns
    db.engine.execute("ALTER TABLE project_knowledge ADD COLUMN token_count INTEGER")
    db.engine.execute("ALTER TABLE conversations ADD COLUMN total_tokens INTEGER")
    db.engine.execute("ALTER TABLE file_attachments ADD COLUMN token_count INTEGER")

    # Create new table
    db.create_all()
```

### Data Population

Populate token counts for existing data:

```python
# Update existing ProjectKnowledge entries
for knowledge in ProjectKnowledge.query.filter_by(token_count=None).all():
    if knowledge.content_preview:
        try:
            result = token_service.estimate_text_tokens(knowledge.content_preview)
            knowledge.token_count = result['token_count']
        except Exception:
            knowledge.token_count = 0
    db.session.commit()
```

## Testing

### Test Files Included

1. **`test_token_system.py`** - Comprehensive system test
2. **`test_token_db_integration.py`** - Database integration test
3. **`test_token_api_demo.py`** - API demonstration

### Running Tests

```bash
# Run comprehensive test
python test_token_system.py

# Test database integration
python test_token_db_integration.py

# Demo API endpoints (requires server running)
python test_token_api_demo.py
```

### Test Coverage

- ✅ Text token estimation (various sizes, encodings)
- ✅ File token estimation (different file types, caching)
- ✅ Conversation token estimation (with/without context)
- ✅ Cache functionality (memory and database)
- ✅ Error handling (invalid inputs, missing files)
- ✅ Database model integration
- ✅ API endpoint functionality

## Monitoring & Maintenance

### Cache Statistics

Monitor cache performance via API:

```bash
curl http://localhost:5000/api/tokens/cache/stats
```

### Regular Maintenance Tasks

1. **Cache Cleanup**: Remove expired entries
   ```bash
   curl -X POST http://localhost:5000/api/tokens/cache/cleanup
   ```

2. **Cache Clear**: Clear all caches if needed
   ```bash
   curl -X POST http://localhost:5000/api/tokens/cache/clear
   ```

3. **Database Optimization**: Regular VACUUM on cache table
   ```sql
   VACUUM token_cache;
   ```

### Logging

Token service logs important events:
- Cache hits/misses
- Performance warnings for large files
- Estimation errors and fallbacks
- Cache cleanup operations

## Security Considerations

### File Access
- Token service respects file system permissions
- No arbitrary file access via API (path validation)
- Uploaded files restricted to configured directories

### Rate Limiting
Consider implementing rate limiting for API endpoints:
```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=get_remote_address)

@app.route('/api/tokens/estimate')
@limiter.limit("100 per minute")
def estimate_text_tokens():
    # ...
```

### Data Privacy
- Token counts are cached but not the original content
- Cache entries expire automatically
- Database cache can be encrypted at rest

## Troubleshooting

### Common Issues

**1. "tiktoken not found" Error**
```bash
pip install tiktoken>=0.11.0
```

**2. Cache Not Working**
- Check database connection
- Verify cache TTL settings
- Review file permissions

**3. High Memory Usage**
- Reduce cache TTL
- Implement cache size limits
- Clear cache more frequently

**4. Slow Performance**
- Enable caching for repeated operations
- Use appropriate encoding for your use case
- Consider batch processing for multiple files

### Debug Mode

Enable debug logging:
```python
import logging
logging.getLogger('services.token_service').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
- [ ] Batch API endpoints for multiple files
- [ ] Real-time token estimation in web UI
- [ ] Token usage analytics and reporting
- [ ] Integration with conversation cost tracking
- [ ] Support for additional model encodings
- [ ] Advanced caching strategies (LRU, size-based)

### Performance Improvements
- [ ] Async token estimation for large files
- [ ] Streaming token counting for very large content
- [ ] Background cache warming
- [ ] Distributed caching support

## API Reference

### Complete API Documentation

Refer to the inline API documentation in `app.py` for complete parameter details and response formats. All endpoints require authentication and return JSON responses with consistent error handling.

## License & Support

This token estimation system is part of the Claude AI web interface project. For support, issues, or feature requests, refer to the main project documentation.

---

*Last updated: October 2025 - Token Estimation System v1.0*