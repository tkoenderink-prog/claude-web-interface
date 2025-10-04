# Claude Agent SDK Web Interface - Version 0.2 Implementation Plan

## Version 0.1 → 0.2 Upgrade Overview
**Current Version**: 0.1 (Basic Claude Agent SDK integration)
**Target Version**: 0.2 (Enhanced UX, Token Management, Advanced Features)
**Estimated Development Time**: 2-3 weeks

---

## Core Feature Requirements

### 1. Enhanced Project Knowledge Management

#### 1.1 "Add All" Functionality
**Implementation**:
```javascript
// Frontend: Add "Select All" checkbox in knowledge modal
<input type="checkbox" id="selectAllKnowledge" onchange="toggleAllKnowledge()">

// JavaScript function
function toggleAllKnowledge() {
    const checkboxes = document.querySelectorAll('.knowledge-checkbox');
    const selectAll = document.getElementById('selectAllKnowledge').checked;
    checkboxes.forEach(cb => cb.checked = selectAll);
    updateTokenCount();
}
```

**Backend Changes**:
- Add endpoint `/api/knowledge/add-bulk` for batch processing
- Optimize database inserts with bulk operations

#### 1.2 Token Estimation System
**Implementation Components**:

```python
# services/token_service.py
import tiktoken  # OpenAI's tokenizer library

class TokenService:
    def __init__(self):
        # Use cl100k_base encoding (Claude/GPT-4 compatible)
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(self.encoder.encode(text))

    def estimate_file_tokens(self, file_path: Path) -> dict:
        """Estimate tokens for a file with caching."""
        content = file_path.read_text()
        return {
            'file': file_path.name,
            'tokens': self.estimate_tokens(content),
            'size_kb': file_path.stat().st_size / 1024
        }
```

**Frontend Display**:
```javascript
// Real-time token counter
class TokenCounter {
    constructor() {
        this.totalTokens = 0;
        this.maxTokens = 200000;  // Claude's context window
        this.files = new Map();
    }

    addFile(fileId, tokens) {
        this.files.set(fileId, tokens);
        this.updateDisplay();
    }

    updateDisplay() {
        this.totalTokens = Array.from(this.files.values()).reduce((a, b) => a + b, 0);
        const percentage = (this.totalTokens / this.maxTokens) * 100;

        // Update UI
        document.getElementById('tokenCount').textContent =
            `${this.totalTokens.toLocaleString()} / ${this.maxTokens.toLocaleString()} tokens`;
        document.getElementById('tokenBar').style.width = `${percentage}%`;

        // Color coding
        if (percentage > 80) {
            document.getElementById('tokenBar').className = 'token-bar danger';
        } else if (percentage > 60) {
            document.getElementById('tokenBar').className = 'token-bar warning';
        } else {
            document.getElementById('tokenBar').className = 'token-bar safe';
        }
    }
}
```

#### 1.3 Visual File Display Under Prompt
**UI Design**:
```html
<!-- Below prompt textarea -->
<div id="selectedFiles" class="selected-files-container">
    <!-- Project Knowledge Files -->
    <div class="file-chip knowledge-file">
        <span class="file-icon">📚</span>
        <span class="file-name">CLAUDE.md</span>
        <span class="token-count">(1,234 tokens)</span>
        <button class="remove-file">×</button>
    </div>

    <!-- Uploaded Files -->
    <div class="file-chip upload-file">
        <span class="file-icon">📎</span>
        <span class="file-name">report.pdf</span>
        <span class="token-count">(5,678 tokens)</span>
        <button class="remove-file">×</button>
    </div>

    <!-- Token Summary Bar -->
    <div class="token-summary">
        <div class="token-bar-container">
            <div id="tokenBar" class="token-bar safe"></div>
        </div>
        <span id="tokenCount">6,912 / 200,000 tokens</span>
    </div>
</div>
```

**CSS Styling**:
```css
.file-chip {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    margin: 4px;
    border-radius: 20px;
    font-size: 14px;
}

.knowledge-file {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.upload-file {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
}

.token-count {
    opacity: 0.8;
    font-size: 12px;
    margin-left: 8px;
}
```

### 2. Advanced Permission Controls

#### 2.1 Permission Toggle Interface
**Frontend Component**:
```javascript
// Permission toggles configuration
const permissionConfig = {
    webSearch: {
        label: "Enable Web Search",
        icon: "🌐",
        tools: ["WebSearch", "WebFetch"],
        description: "Allow Claude to search the internet"
    },
    vaultSearch: {
        label: "Autonomous Vault Search",
        icon: "🔍",
        tools: ["Grep", "Glob", "Task"],
        description: "Allow Claude to search your Obsidian vaults autonomously"
    },
    readFiles: {
        label: "Read Files",
        icon: "📖",
        tools: ["Read"],
        description: "Allow Claude to read files (always enabled for knowledge)"
    },
    writeFiles: {
        label: "Write Files",
        icon: "✍️",
        tools: ["Write", "Edit", "MultiEdit"],
        description: "Allow Claude to create/edit files (DISABLED by default)",
        defaultOff: true,
        requiresConfirmation: true
    }
};
```

**Backend Permission Mapping**:
```python
# app.py
class PermissionManager:
    PERMISSION_MAPPING = {
        'webSearch': ['WebSearch', 'WebFetch'],
        'vaultSearch': ['Grep', 'Glob', 'Task'],
        'readFiles': ['Read'],
        'writeFiles': [],  # Explicitly disabled
    }

    @staticmethod
    def get_allowed_tools(permissions: dict) -> list:
        """Convert permission toggles to allowed tools list."""
        tools = []
        for perm, enabled in permissions.items():
            if enabled and perm != 'writeFiles':  # Never allow write
                tools.extend(PermissionManager.PERMISSION_MAPPING.get(perm, []))
        return tools
```

### 3. Improved Upload Interface

#### 3.1 Robust File Upload Component
```javascript
// Enhanced upload handler with retry logic
class FileUploadManager {
    constructor() {
        this.queue = [];
        this.uploading = false;
        this.maxRetries = 3;
        this.chunkSize = 1024 * 1024; // 1MB chunks
    }

    async uploadFile(file) {
        // Add progress tracking
        const progressId = this.createProgressBar(file.name);

        try {
            // For large files, use chunked upload
            if (file.size > this.chunkSize) {
                await this.chunkedUpload(file, progressId);
            } else {
                await this.simpleUpload(file, progressId);
            }
        } catch (error) {
            await this.retryUpload(file, progressId);
        }
    }

    async chunkedUpload(file, progressId) {
        const chunks = Math.ceil(file.size / this.chunkSize);
        const uploadId = crypto.randomUUID();

        for (let i = 0; i < chunks; i++) {
            const chunk = file.slice(
                i * this.chunkSize,
                Math.min((i + 1) * this.chunkSize, file.size)
            );

            const formData = new FormData();
            formData.append('chunk', chunk);
            formData.append('uploadId', uploadId);
            formData.append('chunkIndex', i);
            formData.append('totalChunks', chunks);

            await fetch('/api/upload/chunk', {
                method: 'POST',
                body: formData
            });

            this.updateProgress(progressId, ((i + 1) / chunks) * 100);
        }
    }
}
```

### 4. Enhanced Streaming Implementation

#### 4.1 Optimized Streaming with Buffering
```python
# services/streaming_service.py
import asyncio
from collections import deque

class StreamingService:
    def __init__(self):
        self.buffer = deque(maxlen=10)
        self.min_chunk_size = 20  # Minimum chars before sending
        self.max_delay = 0.1  # Maximum seconds to wait

    async def stream_with_buffering(self, generator, emit_func):
        """Buffer small chunks for smoother streaming."""
        buffer = ""
        last_emit = asyncio.get_event_loop().time()

        async for chunk in generator:
            buffer += chunk
            current_time = asyncio.get_event_loop().time()

            # Emit if buffer is large enough or timeout reached
            if (len(buffer) >= self.min_chunk_size or
                current_time - last_emit >= self.max_delay):
                await emit_func(buffer)
                buffer = ""
                last_emit = current_time

        # Emit remaining buffer
        if buffer:
            await emit_func(buffer)
```

#### 4.2 Pre-streaming Status Updates
```javascript
// Show immediate feedback before Claude responds
class StreamingUI {
    showThinking() {
        const indicator = document.createElement('div');
        indicator.className = 'thinking-indicator';
        indicator.innerHTML = `
            <div class="thinking-dots">
                <span></span><span></span><span></span>
            </div>
            <div class="thinking-text">Claude is thinking...</div>
            <div class="thinking-status">Analyzing context and documents...</div>
        `;
        document.getElementById('messagesContainer').appendChild(indicator);
    }

    updateThinkingStatus(status) {
        const statusEl = document.querySelector('.thinking-status');
        if (statusEl) {
            statusEl.textContent = status;
        }
    }
}
```

---

## 20-30 Proposed New Features for Version 0.2

### 🎯 **Core Functionality Enhancements**

1. **Smart Context Management**
   - Automatic context pruning when approaching limits
   - Visual context window usage indicator
   - "Compact" button to summarize old messages

2. **Conversation Templates**
   - Save conversation setups as templates
   - Quick-start templates for common tasks (coding, research, analysis)
   - Custom system prompt library

3. **Multi-Model Support**
   - Switch between Claude models mid-conversation
   - Compare responses from different models side-by-side
   - Automatic fallback to cheaper models for simple queries

4. **Advanced Search Within Conversations**
   - Full-text search across all conversations
   - Filter by date, model, attachments
   - Export search results

5. **Conversation Branching**
   - Create branches from any message point
   - Compare different conversation paths
   - Merge branches back together

### 📊 **Analytics & Insights**

6. **Usage Analytics Dashboard**
   - Token usage over time
   - Cost tracking (if using API)
   - Most accessed vault files
   - Response time metrics

7. **Knowledge Graph Visualization**
   - Visual map of connected Obsidian notes
   - Click to add related notes to context
   - Show link strength between documents

8. **Response Quality Metrics**
   - Track helpful/unhelpful responses
   - Automatic quality scoring
   - Feedback loop for improvement

### 🔧 **Developer Tools**

9. **Code Execution Sandbox**
   - Run Python/JavaScript code snippets safely
   - Display output directly in chat
   - Syntax highlighting and error display

10. **API Request Builder**
    - Visual tool to build API requests
    - Test APIs directly from chat
    - Save common API configurations

11. **Git Integration**
    - View git diff in conversations
    - Create commits from chat
    - Browse repository structure

### 🎨 **UI/UX Improvements**

12. **Customizable Interface Layouts**
    - Drag-and-drop panel arrangement
    - Save custom layouts
    - Focus mode for distraction-free chat

13. **Markdown Preview Mode**
    - Live preview of markdown as you type
    - Split-screen editor/preview
    - Export to various formats

14. **Voice Input/Output**
    - Speech-to-text for prompts
    - Text-to-speech for responses
    - Voice commands for navigation

15. **Keyboard Shortcuts System**
    - Customizable hotkeys
    - Vim-style navigation mode
    - Command palette (Cmd+K style)

### 🤝 **Collaboration Features**

16. **Share Conversations**
    - Generate shareable links
    - Public/private sharing options
    - Embed conversations in websites

17. **Team Workspaces**
    - Shared conversation history
    - Role-based permissions
    - Comment on messages

18. **Real-time Collaboration**
    - Multiple users in same conversation
    - See others' typing indicators
    - Collaborative editing of prompts

### 📁 **Data Management**

19. **Smart File Processing**
    - Automatic OCR for images
    - PDF text extraction with layout preservation
    - Excel/CSV data analysis tools

20. **Conversation Export Options**
    - Export as Markdown, PDF, HTML
    - Include attachments in exports
    - Batch export functionality

21. **Auto-save and Version Control**
    - Automatic conversation snapshots
    - Restore previous versions
    - Diff view between versions

### 🧠 **AI Enhancements**

22. **Memory System**
    - Persistent facts across conversations
    - User preference learning
    - Context carry-over options

23. **Smart Suggestions**
    - Auto-complete for prompts
    - Suggested follow-up questions
    - Related document recommendations

24. **Custom AI Agents**
    - Create specialized agents for tasks
    - Agent marketplace
    - Chain multiple agents together

### 🔐 **Security & Privacy**

25. **Encryption Options**
    - End-to-end encryption for sensitive chats
    - Local-only mode (no cloud sync)
    - Encrypted file storage

26. **Audit Logging**
    - Complete activity history
    - Export audit logs
    - Compliance reporting tools

### 🎭 **Personalization**

27. **Theme Marketplace**
    - Download community themes
    - Create custom themes
    - Seasonal/holiday themes

28. **Custom CSS Injection**
    - Advanced styling options
    - Per-conversation styling
    - CSS snippet library

### 🚀 **Performance**

29. **Response Caching**
    - Cache common queries
    - Offline mode with cached responses
    - Smart cache invalidation

30. **Background Processing**
    - Queue multiple queries
    - Process conversations in background
    - Batch operations on conversations

---

## Implementation Priority Matrix

### 🔴 **High Priority** (Week 1)
1. Token estimation and display
2. "Add all" for project knowledge
3. Visual file chips under prompt
4. Permission toggles (web search, vault search)
5. Improved streaming with buffering

### 🟡 **Medium Priority** (Week 2)
1. Robust upload interface
2. Smart context management
3. Conversation templates
4. Usage analytics dashboard
5. Markdown preview mode

### 🟢 **Low Priority** (Week 3+)
1. Knowledge graph visualization
2. Voice input/output
3. Team workspaces
4. Custom AI agents
5. Theme marketplace

---

## Technical Implementation Details

### Database Schema Updates
```sql
-- New tables for v0.2
CREATE TABLE token_cache (
    id INTEGER PRIMARY KEY,
    file_hash VARCHAR(64) UNIQUE,
    token_count INTEGER,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_permissions (
    user_id INTEGER REFERENCES users(id),
    permission_key VARCHAR(50),
    enabled BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (user_id, permission_key)
);

CREATE TABLE conversation_templates (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(200),
    system_prompt TEXT,
    default_permissions JSON,
    default_model VARCHAR(50)
);
```

### API Endpoint Additions
```python
# New endpoints for v0.2
/api/tokens/estimate POST - Estimate tokens for text/files
/api/knowledge/bulk-add POST - Add multiple knowledge items
/api/permissions GET/PUT - Get/update user permissions
/api/templates GET/POST - Manage conversation templates
/api/analytics/usage GET - Get usage statistics
/api/upload/chunk POST - Chunked file upload
```

### Frontend State Management
```javascript
// Enhanced state management with Vuex-like store
class AppStore {
    constructor() {
        this.state = {
            tokens: {
                used: 0,
                max: 200000,
                files: new Map()
            },
            permissions: {
                webSearch: false,
                vaultSearch: true,
                readFiles: true,
                writeFiles: false
            },
            selectedFiles: {
                knowledge: [],
                uploads: []
            },
            streaming: {
                isStreaming: false,
                buffer: '',
                chunks: []
            }
        };

        this.subscribers = [];
    }

    dispatch(action, payload) {
        switch(action) {
            case 'ADD_FILE':
                this.addFile(payload);
                break;
            case 'UPDATE_PERMISSIONS':
                this.updatePermissions(payload);
                break;
            case 'UPDATE_TOKENS':
                this.updateTokens(payload);
                break;
        }
        this.notify();
    }

    subscribe(callback) {
        this.subscribers.push(callback);
    }

    notify() {
        this.subscribers.forEach(cb => cb(this.state));
    }
}
```

---

## Testing Strategy

### Unit Tests
```python
# tests/test_token_service.py
def test_token_estimation():
    service = TokenService()
    text = "Hello, world!"
    tokens = service.estimate_tokens(text)
    assert 3 <= tokens <= 5  # Approximate range

def test_bulk_knowledge_add():
    # Test adding multiple files at once
    files = [...]
    result = add_bulk_knowledge(files)
    assert len(result) == len(files)
```

### Integration Tests
- Test file upload with various sizes
- Test streaming with network interruptions
- Test permission enforcement
- Test token counting accuracy

### Performance Tests
- Load test with 100+ files
- Streaming latency measurements
- Database query optimization
- Frontend rendering performance

---

## Deployment Checklist

### Pre-deployment
- [ ] Run all tests
- [ ] Update version number to 0.2
- [ ] Create database migrations
- [ ] Update documentation
- [ ] Test in staging environment

### Deployment
- [ ] Backup v0.1 database
- [ ] Run database migrations
- [ ] Deploy backend changes
- [ ] Deploy frontend changes
- [ ] Clear caches

### Post-deployment
- [ ] Verify all features working
- [ ] Monitor error logs
- [ ] Check performance metrics
- [ ] Gather user feedback

---

## Questions for User

**Which of the 30 proposed features would you like prioritized for v0.2?**

Please indicate your top 10 choices, and I'll create a detailed implementation plan for those specific features.