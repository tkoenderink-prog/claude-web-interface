# Fixes Implemented for Claude Agent SDK Web Interface

## Issues Fixed (October 2, 2025)

### 1. UTF-8 Encoding Errors
**Problem**: Some Obsidian vault files couldn't be read due to non-UTF-8 encoding
**Solution**:
- Added fallback to Latin-1 encoding when UTF-8 fails
- Implemented in `services/claude_service.py` ObsidianKnowledgeService class
- Now handles files with special characters gracefully

### 2. Database Constraint Violation
**Problem**: `NOT NULL constraint failed: conversation_knowledge.knowledge_id`
**Solution**:
- Added `db.session.flush()` after creating ProjectKnowledge to get the ID
- Fixed in `app.py` `add_knowledge_to_conversation()` function
- Knowledge items now properly save with IDs before linking

### 3. Project Knowledge Not Passed to Claude
**Problem**: Documents added to conversation weren't being sent to Claude
**Solution**:
- Added debug logging to track knowledge items
- Verified knowledge collection in both HTTP and WebSocket endpoints
- Fixed in `app.py` message handling

### 4. No Streaming/Progress Indication
**Problem**: Long response times with no user feedback
**Solutions Implemented**:
- Changed `stream=False` to `stream=True` in Claude service calls
- Added chunk-by-chunk streaming in WebSocket handler
- Added JavaScript handler for incremental updates
- Created `replaceLastMessage()` function for full text updates
- Added debug logging for streaming progress

## Testing

### Test Files Created
1. `test_knowledge.py` - Tests project knowledge functionality
2. `test_claude_sdk.py` - Tests basic Claude Agent SDK integration
3. `test_simple_sdk.py` - Simple SDK verification
4. `test_inspect_sdk.py` - Message structure inspection

### How to Test
```bash
# Test knowledge functionality
python3.11 test_knowledge.py

# Test basic SDK integration
python3.11 test_claude_sdk.py
```

## Performance Improvements

1. **Real-time Streaming**: Responses now appear as they're generated
2. **Better Error Handling**: Gracefully handles encoding issues
3. **Debug Logging**: Added comprehensive logging for troubleshooting

## Remaining Optimizations

1. **Add Progress Indicator**: Show "Claude is thinking..." before response starts
2. **Implement Chunk Buffering**: Group small chunks for smoother display
3. **Add Retry Logic**: Auto-retry on transient failures
4. **Optimize Knowledge Loading**: Cache frequently used documents

## How to Launch

```bash
# Option 1: Use the launch script
./launch.sh

# Option 2: Run directly
/opt/homebrew/opt/python@3.11/bin/python3.11 app.py

# Option 3: Use port 5001 if 5000 is busy
./run_port_5001.sh
```

## Configuration

In `.env` file:
```bash
# Enable features
ENABLE_PROJECT_KNOWLEDGE=True
ENABLE_TOOLS=True

# For faster responses with subscription
unset ANTHROPIC_API_KEY  # Use subscription instead of API
```

## Monitoring

Watch the terminal for:
- "Sending X knowledge items to Claude" - Confirms documents are attached
- "Streamed X chunks" - Shows streaming is working
- UTF-8 fallback messages - Indicates encoding issues handled

## Known Issues

1. **Initial Response Delay**: First chunk may take 2-5 seconds (Claude processing time)
2. **Large Documents**: Very large vault files may slow down responses
3. **WebSocket Reconnection**: May need page refresh if connection drops

## Next Steps

To further improve performance:
1. Implement response caching for common queries
2. Add document summarization for large files
3. Implement parallel knowledge loading
4. Add WebSocket heartbeat for connection stability