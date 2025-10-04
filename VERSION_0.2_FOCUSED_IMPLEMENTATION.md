# Version 0.2 Focused Implementation Plan

## Selected Features Overview
**Total Features**: 15 (7 core requirements + 8 selected enhancements)
**Timeline**: 2-3 weeks
**Priority**: Practical, achievable improvements focused on UX and efficiency

---

## Week 1: Core Infrastructure & Token Management

### Day 1-2: Token System Implementation

#### Backend: Token Counting Service
```python
# services/token_counter.py
import tiktoken
from functools import lru_cache
import hashlib

class TokenCounter:
    def __init__(self):
        # Use cl100k_base for Claude compatibility
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self._cache = {}

    @lru_cache(maxsize=1000)
    def count_tokens(self, text: str) -> int:
        """Count tokens with caching for repeated text."""
        return len(self.encoder.encode(text))

    def count_file_tokens(self, file_path: str, content: str) -> dict:
        """Count tokens for a file."""
        text_hash = hashlib.md5(content.encode()).hexdigest()

        # Check cache first
        if text_hash in self._cache:
            return self._cache[text_hash]

        token_count = self.count_tokens(content)
        result = {
            'path': file_path,
            'tokens': token_count,
            'hash': text_hash
        }

        self._cache[text_hash] = result
        return result
```

#### Frontend: Visual Token Display
```javascript
// static/js/token-manager.js
class TokenManager {
    constructor(maxTokens = 200000) {
        this.maxTokens = maxTokens;
        this.systemPromptTokens = 500; // Estimate
        this.conversationTokens = 0;
        this.knowledgeTokens = new Map();
        this.uploadTokens = new Map();
    }

    updateDisplay() {
        const total = this.getTotalTokens();
        const percentage = (total / this.maxTokens) * 100;

        // Update progress bar
        const bar = document.getElementById('contextBar');
        bar.style.width = `${percentage}%`;

        // Color coding
        if (percentage > 80) {
            bar.className = 'context-bar danger';
        } else if (percentage > 60) {
            bar.className = 'context-bar warning';
        } else {
            bar.className = 'context-bar safe';
        }

        // Update text
        document.getElementById('contextTokens').textContent =
            `${total.toLocaleString()} / ${this.maxTokens.toLocaleString()} tokens`;

        // Show warning if near limit
        if (percentage > 90) {
            this.showContextWarning();
        }
    }

    getTotalTokens() {
        let total = this.systemPromptTokens + this.conversationTokens;
        this.knowledgeTokens.forEach(tokens => total += tokens);
        this.uploadTokens.forEach(tokens => total += tokens);
        return total;
    }
}
```

#### HTML Structure for Token Display
```html
<!-- Add below message input -->
<div id="contextManager" class="context-manager">
    <!-- Token usage bar -->
    <div class="context-header">
        <span class="context-label">Context Usage</span>
        <span id="contextTokens">0 / 200,000 tokens</span>
    </div>
    <div class="context-bar-container">
        <div id="contextBar" class="context-bar safe"></div>
    </div>

    <!-- Selected files display -->
    <div id="selectedFiles" class="selected-files">
        <!-- Knowledge files -->
        <div class="file-group knowledge-group">
            <div class="file-group-header">📚 Project Knowledge</div>
            <div id="knowledgeFiles"></div>
        </div>
        <!-- Uploaded files -->
        <div class="file-group upload-group">
            <div class="file-group-header">📎 Uploads</div>
            <div id="uploadedFiles"></div>
        </div>
    </div>
</div>
```

### Day 3-4: "Add All" & Bulk Operations

#### Backend: Bulk Knowledge Endpoint
```python
# app.py additions
@app.route('/api/knowledge/add-bulk', methods=['POST'])
@login_required
@async_to_sync
async def add_bulk_knowledge():
    """Add multiple knowledge files at once."""
    data = request.json
    conversation_id = data['conversation_id']
    file_items = data['files']  # List of {vault, file_path, category}

    conversation = Conversation.query.filter_by(
        uuid=conversation_id,
        user_id=current_user.id
    ).first_or_404()

    added_files = []
    total_tokens = 0
    token_counter = TokenCounter()

    for item in file_items:
        # Get file content
        content = await obsidian_service.get_file_content(
            item['vault'],
            item['file_path']
        )

        if not content:
            continue

        # Count tokens
        token_info = token_counter.count_file_tokens(
            item['file_path'],
            content
        )
        total_tokens += token_info['tokens']

        # Check if would exceed limit
        if total_tokens > 180000:  # Leave 20k buffer
            return jsonify({
                'error': 'Token limit exceeded',
                'max_files': len(added_files),
                'total_tokens': total_tokens
            }), 400

        # Create or get knowledge item
        knowledge = ProjectKnowledge.query.filter_by(
            user_id=current_user.id,
            vault_type=item['vault'],
            file_path=item['file_path']
        ).first()

        if not knowledge:
            knowledge = ProjectKnowledge(
                user_id=current_user.id,
                name=Path(item['file_path']).stem,
                vault_type=item['vault'],
                file_path=item['file_path'],
                category=item.get('category', 'RESOURCE'),
                content_preview=content[:500],
                content_hash=obsidian_service.calculate_content_hash(content),
                token_count=token_info['tokens']  # Add token_count column
            )
            db.session.add(knowledge)
            db.session.flush()

        # Link to conversation
        existing_link = ConversationKnowledge.query.filter_by(
            conversation_id=conversation.id,
            knowledge_id=knowledge.id
        ).first()

        if not existing_link:
            link = ConversationKnowledge(
                conversation_id=conversation.id,
                knowledge_id=knowledge.id
            )
            db.session.add(link)

        added_files.append({
            'name': knowledge.name,
            'path': knowledge.file_path,
            'tokens': token_info['tokens']
        })

    db.session.commit()

    return jsonify({
        'success': True,
        'added_files': added_files,
        'total_tokens': total_tokens
    })
```

#### Frontend: Select All Implementation
```javascript
// Add to knowledge modal
class KnowledgeSelector {
    constructor() {
        this.selectedFiles = new Set();
        this.tokenEstimates = new Map();
    }

    async toggleSelectAll(checked) {
        const checkboxes = document.querySelectorAll('.knowledge-checkbox');
        const loadingIndicator = document.getElementById('selectAllLoading');

        if (checked) {
            loadingIndicator.style.display = 'inline-block';

            // Estimate tokens for all files
            const promises = [];
            checkboxes.forEach(cb => {
                if (!this.tokenEstimates.has(cb.value)) {
                    promises.push(this.estimateFileTokens(cb.value));
                }
            });

            await Promise.all(promises);

            // Check if total would exceed limit
            let totalTokens = 0;
            checkboxes.forEach(cb => {
                totalTokens += this.tokenEstimates.get(cb.value) || 0;
            });

            if (totalTokens > 180000) {
                alert(`Cannot add all files: would use ${totalTokens.toLocaleString()} tokens (limit: 180,000)`);
                loadingIndicator.style.display = 'none';
                return;
            }

            // Select all
            checkboxes.forEach(cb => {
                cb.checked = true;
                this.selectedFiles.add(cb.value);
            });

            loadingIndicator.style.display = 'none';
        } else {
            // Deselect all
            checkboxes.forEach(cb => {
                cb.checked = false;
                this.selectedFiles.delete(cb.value);
            });
        }

        this.updateTokenDisplay();
    }

    async estimateFileTokens(filePath) {
        const response = await fetch('/api/tokens/estimate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({file_path: filePath})
        });

        const data = await response.json();
        this.tokenEstimates.set(filePath, data.tokens);
        return data.tokens;
    }
}
```

### Day 5: Permission System & Toggles

#### Backend: Permission Management
```python
# services/permission_service.py
class PermissionService:
    """Manages tool permissions for Claude."""

    # Define available permissions and their tools
    PERMISSIONS = {
        'web_search': {
            'label': 'Web Search',
            'tools': ['WebSearch', 'WebFetch'],
            'default': False,
            'description': 'Search the internet and fetch web pages'
        },
        'vault_search': {
            'label': 'Vault Search',
            'tools': ['Grep', 'Glob'],
            'default': True,
            'description': 'Search through Obsidian vaults'
        },
        'read_files': {
            'label': 'Read Files',
            'tools': ['Read'],
            'default': True,
            'description': 'Read file contents',
            'always_on': True  # Cannot be disabled
        },
        'write_files': {
            'label': 'Write Files',
            'tools': [],  # Always empty - never allow writes
            'default': False,
            'description': 'Create or modify files',
            'always_off': True  # Cannot be enabled
        }
    }

    @classmethod
    def get_allowed_tools(cls, permissions: dict) -> list:
        """Convert permission flags to allowed tools list."""
        tools = []

        for perm_key, enabled in permissions.items():
            perm_config = cls.PERMISSIONS.get(perm_key, {})

            # Skip if always_off
            if perm_config.get('always_off'):
                continue

            # Include if enabled or always_on
            if enabled or perm_config.get('always_on'):
                tools.extend(perm_config.get('tools', []))

        return list(set(tools))  # Remove duplicates
```

#### Frontend: Permission Toggles UI
```javascript
// static/js/permissions.js
class PermissionManager {
    constructor() {
        this.permissions = {
            web_search: false,
            vault_search: true,
            read_files: true,
            write_files: false
        };

        this.initializeToggles();
    }

    initializeToggles() {
        const container = document.getElementById('permissionToggles');

        const html = `
            <div class="permission-group">
                <h4>AI Capabilities</h4>

                <!-- Web Search -->
                <div class="permission-item">
                    <label class="toggle-switch">
                        <input type="checkbox" id="perm_web_search"
                               onchange="permissions.toggle('web_search', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                    <div class="permission-info">
                        <span class="permission-label">🌐 Web Search</span>
                        <span class="permission-desc">Search internet and fetch pages</span>
                    </div>
                </div>

                <!-- Vault Search -->
                <div class="permission-item">
                    <label class="toggle-switch">
                        <input type="checkbox" id="perm_vault_search" checked
                               onchange="permissions.toggle('vault_search', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                    <div class="permission-info">
                        <span class="permission-label">🔍 Vault Search</span>
                        <span class="permission-desc">Search your Obsidian vaults</span>
                    </div>
                </div>

                <!-- Read Files (Always On) -->
                <div class="permission-item disabled">
                    <label class="toggle-switch">
                        <input type="checkbox" checked disabled>
                        <span class="toggle-slider"></span>
                    </label>
                    <div class="permission-info">
                        <span class="permission-label">📖 Read Files</span>
                        <span class="permission-desc">Always enabled for knowledge</span>
                    </div>
                </div>

                <!-- Write Files (Always Off) -->
                <div class="permission-item disabled">
                    <label class="toggle-switch">
                        <input type="checkbox" disabled>
                        <span class="toggle-slider"></span>
                    </label>
                    <div class="permission-info">
                        <span class="permission-label">✍️ Write Files</span>
                        <span class="permission-desc">Disabled for safety</span>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    toggle(permission, enabled) {
        this.permissions[permission] = enabled;

        // Save to localStorage
        localStorage.setItem('permissions', JSON.stringify(this.permissions));

        // Update current conversation if active
        if (window.currentConversation) {
            this.updateConversationPermissions();
        }
    }
}
```

---

## Week 2: UI Enhancements & Smart Features

### Day 6-7: Improved Streaming & Progress Indicators

#### Backend: Enhanced Streaming Service
```python
# services/streaming_service.py
import asyncio
import time
from typing import AsyncGenerator

class EnhancedStreamingService:
    def __init__(self):
        self.buffer_size = 20  # Characters
        self.max_delay = 0.1   # Seconds
        self.thinking_messages = [
            "Analyzing your request...",
            "Processing documents...",
            "Formulating response...",
            "Thinking..."
        ]

    async def stream_with_status(self, claude_service, messages, **kwargs):
        """Stream with status updates."""
        # Send initial thinking status
        yield {'type': 'status', 'message': self.thinking_messages[0]}

        # Check if we have documents
        if kwargs.get('project_knowledge'):
            yield {'type': 'status', 'message': f'Analyzing {len(kwargs["project_knowledge"])} documents...'}
            await asyncio.sleep(0.5)  # Brief pause for UX

        # Start streaming from Claude
        buffer = ""
        last_yield = time.time()
        first_chunk = True

        async for chunk in claude_service.create_message(messages, **kwargs):
            if first_chunk:
                yield {'type': 'status', 'message': 'Generating response...'}
                first_chunk = False

            buffer += chunk

            # Yield if buffer is large enough or timeout
            if len(buffer) >= self.buffer_size or \
               time.time() - last_yield >= self.max_delay:
                yield {'type': 'chunk', 'content': buffer}
                buffer = ""
                last_yield = time.time()

        # Yield remaining buffer
        if buffer:
            yield {'type': 'chunk', 'content': buffer}

        yield {'type': 'complete'}
```

#### Frontend: Progress Indicators
```javascript
// Enhanced streaming display
class StreamingUI {
    constructor() {
        this.statusElement = null;
        this.messageElement = null;
        this.startTime = null;
    }

    showThinking() {
        const container = document.getElementById('messagesContainer');

        // Create thinking indicator
        const thinking = document.createElement('div');
        thinking.id = 'thinkingIndicator';
        thinking.className = 'thinking-indicator';
        thinking.innerHTML = `
            <div class="thinking-avatar">A</div>
            <div class="thinking-content">
                <div class="thinking-animation">
                    <span></span><span></span><span></span>
                </div>
                <div class="thinking-status">Analyzing your request...</div>
                <div class="thinking-timer">0s</div>
            </div>
        `;

        container.appendChild(thinking);
        this.statusElement = thinking.querySelector('.thinking-status');

        // Start timer
        this.startTime = Date.now();
        this.updateTimer();

        // Scroll to bottom
        container.scrollTop = container.scrollHeight;
    }

    updateStatus(message) {
        if (this.statusElement) {
            this.statusElement.textContent = message;
        }
    }

    updateTimer() {
        if (!this.startTime) return;

        const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
        const timer = document.querySelector('.thinking-timer');
        if (timer) {
            timer.textContent = `${elapsed}s`;
        }

        // Continue updating if still thinking
        if (document.getElementById('thinkingIndicator')) {
            setTimeout(() => this.updateTimer(), 1000);
        }
    }

    startStreaming() {
        // Replace thinking with message container
        const thinking = document.getElementById('thinkingIndicator');
        if (thinking) {
            thinking.remove();
        }

        // Create message element
        const container = document.getElementById('messagesContainer');
        const message = document.createElement('div');
        message.className = 'message assistant streaming';
        message.innerHTML = `
            <div class="message-avatar">A</div>
            <div class="message-content">
                <div class="message-text"></div>
                <div class="message-status">
                    <span class="streaming-indicator">● Streaming</span>
                </div>
            </div>
        `;

        container.appendChild(message);
        this.messageElement = message.querySelector('.message-text');
    }
}
```

### Day 8-9: Smart Context Management

#### Backend: Context Compaction Service
```python
# services/context_service.py
class ContextManager:
    def __init__(self, max_tokens=200000):
        self.max_tokens = max_tokens
        self.buffer_tokens = 20000  # Reserve for response
        self.token_counter = TokenCounter()

    def should_compact(self, current_tokens: int) -> bool:
        """Check if context should be compacted."""
        return current_tokens > (self.max_tokens - self.buffer_tokens) * 0.8

    async def compact_messages(self, messages: list) -> list:
        """Compact old messages to save tokens."""
        if len(messages) < 10:
            return messages  # Don't compact if few messages

        # Keep first message (context) and last 5 messages
        keep_start = 1
        keep_end = 5

        # Summarize middle messages
        middle_messages = messages[keep_start:-keep_end]
        if not middle_messages:
            return messages

        # Create summary
        summary_prompt = "Summarize these messages concisely, preserving key information:"
        summary_content = "\n".join([
            f"{m['role']}: {m['content'][:200]}..."
            for m in middle_messages
        ])

        summary = await self.generate_summary(summary_content)

        # Reconstruct messages
        compacted = [messages[0]]  # Keep first
        compacted.append({
            'role': 'system',
            'content': f"[Previous conversation summary: {summary}]"
        })
        compacted.extend(messages[-keep_end:])  # Keep last 5

        return compacted

    def estimate_conversation_tokens(self, messages: list) -> int:
        """Estimate total tokens in conversation."""
        total = 0
        for message in messages:
            total += self.token_counter.count_tokens(message.get('content', ''))
        return total
```

#### Frontend: Context Management UI
```javascript
// Context management interface
class ContextUI {
    constructor() {
        this.contextManager = new ContextManager();
        this.initializeUI();
    }

    initializeUI() {
        // Add compact button to chat header
        const header = document.getElementById('chatHeader');
        const compactBtn = document.createElement('button');
        compactBtn.id = 'compactBtn';
        compactBtn.className = 'compact-btn';
        compactBtn.innerHTML = '🗜️ Compact';
        compactBtn.onclick = () => this.compactContext();
        compactBtn.style.display = 'none';  // Hidden by default

        header.appendChild(compactBtn);
    }

    checkContextUsage() {
        const usage = this.contextManager.getTokenUsage();
        const percentage = (usage.total / usage.max) * 100;

        // Show compact button if > 70% used
        const compactBtn = document.getElementById('compactBtn');
        if (percentage > 70) {
            compactBtn.style.display = 'inline-block';
            compactBtn.classList.toggle('warning', percentage > 80);
            compactBtn.classList.toggle('critical', percentage > 90);
        }

        // Auto-compact if > 90%
        if (percentage > 90) {
            this.showCompactWarning();
        }
    }

    async compactContext() {
        const btn = document.getElementById('compactBtn');
        btn.disabled = true;
        btn.innerHTML = '⏳ Compacting...';

        try {
            const response = await fetch('/api/conversation/compact', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    conversation_id: currentConversation.id
                })
            });

            const result = await response.json();

            // Update UI
            btn.innerHTML = '✓ Compacted';
            this.showCompactSuccess(result.saved_tokens);

            // Refresh token display
            tokenManager.conversationTokens = result.new_tokens;
            tokenManager.updateDisplay();

        } catch (error) {
            btn.innerHTML = '❌ Failed';
            console.error('Compact failed:', error);
        } finally {
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = '🗜️ Compact';
            }, 2000);
        }
    }
}
```

### Day 10: Robust Upload System

#### Backend: Chunked Upload Handler
```python
# app.py - Enhanced upload endpoint
import tempfile
import shutil

UPLOAD_SESSIONS = {}  # Track chunked uploads

@app.route('/api/upload/chunk', methods=['POST'])
@login_required
def upload_chunk():
    """Handle chunked file uploads."""
    chunk = request.files.get('chunk')
    upload_id = request.form.get('uploadId')
    chunk_index = int(request.form.get('chunkIndex'))
    total_chunks = int(request.form.get('totalChunks'))
    filename = request.form.get('filename')

    if not all([chunk, upload_id, filename]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Initialize session
    if upload_id not in UPLOAD_SESSIONS:
        temp_dir = tempfile.mkdtemp()
        UPLOAD_SESSIONS[upload_id] = {
            'temp_dir': temp_dir,
            'chunks_received': set(),
            'total_chunks': total_chunks,
            'filename': secure_filename(filename),
            'user_id': current_user.id,
            'started_at': datetime.utcnow()
        }

    session = UPLOAD_SESSIONS[upload_id]

    # Verify user
    if session['user_id'] != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Save chunk
    chunk_path = Path(session['temp_dir']) / f"chunk_{chunk_index}"
    chunk.save(chunk_path)
    session['chunks_received'].add(chunk_index)

    # Check if all chunks received
    if len(session['chunks_received']) == total_chunks:
        # Assemble file
        final_path = app.config['UPLOAD_FOLDER'] / session['filename']

        with open(final_path, 'wb') as final_file:
            for i in range(total_chunks):
                chunk_path = Path(session['temp_dir']) / f"chunk_{i}"
                with open(chunk_path, 'rb') as chunk_file:
                    final_file.write(chunk_file.read())

        # Clean up
        shutil.rmtree(session['temp_dir'])
        del UPLOAD_SESSIONS[upload_id]

        # Process file (extract text, count tokens, etc.)
        file_info = process_uploaded_file(final_path)

        return jsonify({
            'complete': True,
            'file_info': file_info
        })

    return jsonify({
        'chunk_received': chunk_index,
        'progress': len(session['chunks_received']) / total_chunks
    })

# Cleanup old sessions periodically
@app.before_request
def cleanup_upload_sessions():
    """Clean up abandoned upload sessions."""
    now = datetime.utcnow()
    expired = []

    for upload_id, session in UPLOAD_SESSIONS.items():
        if (now - session['started_at']).seconds > 3600:  # 1 hour timeout
            shutil.rmtree(session['temp_dir'], ignore_errors=True)
            expired.append(upload_id)

    for upload_id in expired:
        del UPLOAD_SESSIONS[upload_id]
```

#### Frontend: Robust Upload UI
```javascript
// Enhanced file upload with retry and progress
class RobustUploader {
    constructor() {
        this.queue = [];
        this.uploading = false;
        this.maxRetries = 3;
        this.chunkSize = 512 * 1024;  // 512KB chunks
        this.currentUpload = null;
    }

    async uploadFile(file) {
        return new Promise((resolve, reject) => {
            this.queue.push({file, resolve, reject, retries: 0});
            if (!this.uploading) {
                this.processQueue();
            }
        });
    }

    async processQueue() {
        if (this.queue.length === 0) {
            this.uploading = false;
            return;
        }

        this.uploading = true;
        const item = this.queue.shift();

        try {
            const result = await this.uploadWithRetry(item.file, item.retries);
            item.resolve(result);
        } catch (error) {
            if (item.retries < this.maxRetries) {
                item.retries++;
                this.queue.unshift(item);  // Retry
                await this.delay(1000 * item.retries);  // Exponential backoff
            } else {
                item.reject(error);
            }
        }

        this.processQueue();
    }

    async uploadWithRetry(file, retryCount) {
        const uploadId = crypto.randomUUID();
        const chunks = Math.ceil(file.size / this.chunkSize);

        // Create progress UI
        const progressUI = this.createProgressUI(file.name);

        for (let i = 0; i < chunks; i++) {
            const start = i * this.chunkSize;
            const end = Math.min(start + this.chunkSize, file.size);
            const chunk = file.slice(start, end);

            const formData = new FormData();
            formData.append('chunk', chunk);
            formData.append('uploadId', uploadId);
            formData.append('chunkIndex', i);
            formData.append('totalChunks', chunks);
            formData.append('filename', file.name);

            let success = false;
            let chunkRetries = 0;

            while (!success && chunkRetries < 3) {
                try {
                    const response = await fetch('/api/upload/chunk', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        throw new Error(`Upload failed: ${response.status}`);
                    }

                    const result = await response.json();
                    success = true;

                    // Update progress
                    const progress = ((i + 1) / chunks) * 100;
                    progressUI.update(progress);

                    if (result.complete) {
                        progressUI.complete();
                        return result.file_info;
                    }

                } catch (error) {
                    chunkRetries++;
                    if (chunkRetries >= 3) {
                        progressUI.error();
                        throw error;
                    }
                    await this.delay(500 * chunkRetries);
                }
            }
        }
    }

    createProgressUI(filename) {
        const container = document.getElementById('uploadProgress');
        const progressDiv = document.createElement('div');
        progressDiv.className = 'upload-progress-item';
        progressDiv.innerHTML = `
            <div class="upload-filename">${filename}</div>
            <div class="upload-progress-bar">
                <div class="upload-progress-fill" style="width: 0%"></div>
            </div>
            <div class="upload-status">Uploading...</div>
        `;
        container.appendChild(progressDiv);

        return {
            update: (percent) => {
                progressDiv.querySelector('.upload-progress-fill').style.width = percent + '%';
                progressDiv.querySelector('.upload-status').textContent = `${Math.round(percent)}%`;
            },
            complete: () => {
                progressDiv.classList.add('complete');
                progressDiv.querySelector('.upload-status').textContent = 'Complete';
                setTimeout(() => progressDiv.remove(), 3000);
            },
            error: () => {
                progressDiv.classList.add('error');
                progressDiv.querySelector('.upload-status').textContent = 'Failed';
            }
        };
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}
```

---

## Week 3: Advanced Features

### Day 11-12: Conversation Search & Export

#### Backend: Search Implementation
```python
# services/search_service.py
from sqlalchemy import or_, and_
from datetime import datetime, timedelta

class ConversationSearchService:
    @staticmethod
    def search_all_conversations(user_id: int, query: str, filters: dict = None):
        """Search across all user conversations."""

        # Base query
        conversations = Conversation.query.filter_by(user_id=user_id)

        # Apply filters
        if filters:
            if filters.get('date_from'):
                conversations = conversations.filter(
                    Conversation.created_at >= filters['date_from']
                )
            if filters.get('date_to'):
                conversations = conversations.filter(
                    Conversation.created_at <= filters['date_to']
                )
            if filters.get('model'):
                conversations = conversations.filter(
                    Conversation.model == filters['model']
                )
            if filters.get('has_attachments'):
                conversations = conversations.join(ConversationKnowledge).distinct()

        # Search in conversation titles and messages
        if query:
            conversations = conversations.join(Message).filter(
                or_(
                    Conversation.title.ilike(f'%{query}%'),
                    Message.content.ilike(f'%{query}%')
                )
            ).distinct()

        results = []
        for conv in conversations.all():
            # Find matching messages
            matching_messages = Message.query.filter(
                and_(
                    Message.conversation_id == conv.id,
                    Message.content.ilike(f'%{query}%')
                )
            ).limit(3).all()

            results.append({
                'conversation': conv.to_dict(),
                'matching_messages': [
                    {
                        'id': msg.id,
                        'role': msg.role,
                        'preview': msg.content[:200],
                        'created_at': msg.created_at.isoformat()
                    }
                    for msg in matching_messages
                ]
            })

        return results
```

#### Frontend: Search Interface
```javascript
// Conversation search UI
class ConversationSearch {
    constructor() {
        this.searchResults = [];
        this.initializeUI();
    }

    initializeUI() {
        // Add search bar to sidebar
        const searchHTML = `
            <div class="conversation-search">
                <div class="search-input-group">
                    <input type="text"
                           id="searchInput"
                           placeholder="Search all conversations..."
                           onkeyup="conversationSearch.handleSearch(event)">
                    <button onclick="conversationSearch.toggleFilters()">
                        🔧
                    </button>
                </div>

                <div id="searchFilters" class="search-filters" style="display: none;">
                    <input type="date" id="dateFrom" placeholder="From">
                    <input type="date" id="dateTo" placeholder="To">
                    <select id="modelFilter">
                        <option value="">All Models</option>
                        <option value="claude-3-5-sonnet">Sonnet</option>
                        <option value="claude-3-opus">Opus</option>
                    </select>
                    <label>
                        <input type="checkbox" id="hasAttachments">
                        Has Attachments
                    </label>
                </div>

                <div id="searchResults" class="search-results"></div>
            </div>
        `;

        document.getElementById('conversationsPanel').insertAdjacentHTML(
            'afterbegin',
            searchHTML
        );
    }

    async handleSearch(event) {
        const query = event.target.value;

        if (query.length < 3 && event.key !== 'Enter') {
            return;  // Minimum 3 characters
        }

        const filters = this.getFilters();

        const response = await fetch('/api/conversations/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({query, filters})
        });

        const results = await response.json();
        this.displayResults(results);
    }

    displayResults(results) {
        const container = document.getElementById('searchResults');

        if (results.length === 0) {
            container.innerHTML = '<div class="no-results">No results found</div>';
            return;
        }

        container.innerHTML = results.map(r => `
            <div class="search-result" onclick="loadConversation('${r.conversation.uuid}')">
                <div class="result-title">${r.conversation.title}</div>
                <div class="result-date">${new Date(r.conversation.created_at).toLocaleDateString()}</div>
                ${r.matching_messages.map(m => `
                    <div class="result-message">
                        <span class="message-role">${m.role}:</span>
                        ${this.highlightMatch(m.preview)}
                    </div>
                `).join('')}
            </div>
        `).join('');
    }
}
```

### Day 13: Export Options

#### Backend: Export Service
```python
# services/export_service.py
import markdown2
from weasyprint import HTML
import zipfile

class ExportService:
    @staticmethod
    def export_conversation(conversation_id: int, format: str):
        """Export conversation in various formats."""
        conversation = Conversation.query.get(conversation_id)
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.created_at).all()

        # Get attachments
        knowledge_links = ConversationKnowledge.query.filter_by(
            conversation_id=conversation_id
        ).all()

        if format == 'markdown':
            return ExportService.export_as_markdown(conversation, messages, knowledge_links)
        elif format == 'pdf':
            return ExportService.export_as_pdf(conversation, messages, knowledge_links)
        elif format == 'html':
            return ExportService.export_as_html(conversation, messages, knowledge_links)

    @staticmethod
    def export_as_markdown(conversation, messages, knowledge_links):
        """Export as Markdown."""
        content = f"# {conversation.title}\n\n"
        content += f"*Created: {conversation.created_at}*\n\n"

        # Add knowledge files
        if knowledge_links:
            content += "## Attached Knowledge\n\n"
            for link in knowledge_links:
                content += f"- {link.knowledge.name}\n"
            content += "\n---\n\n"

        # Add messages
        content += "## Conversation\n\n"
        for msg in messages:
            role = msg.role.capitalize()
            content += f"### {role}\n\n{msg.content}\n\n---\n\n"

        return content

    @staticmethod
    def export_as_pdf(conversation, messages, knowledge_links):
        """Export as PDF."""
        # First generate HTML
        html_content = ExportService.export_as_html(conversation, messages, knowledge_links)

        # Convert to PDF
        pdf = HTML(string=html_content).write_pdf()
        return pdf

    @staticmethod
    def export_as_html(conversation, messages, knowledge_links):
        """Export as HTML."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{conversation.title}</title>
            <style>
                body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .message {{ margin: 20px 0; padding: 15px; border-radius: 8px; }}
                .user {{ background: #f0f0f0; }}
                .assistant {{ background: #e3f2fd; }}
                .role {{ font-weight: bold; margin-bottom: 10px; }}
                .metadata {{ color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <h1>{conversation.title}</h1>
            <p class="metadata">Created: {conversation.created_at}</p>
        """

        if knowledge_links:
            html += "<h2>Attached Knowledge</h2><ul>"
            for link in knowledge_links:
                html += f"<li>{link.knowledge.name}</li>"
            html += "</ul>"

        html += "<h2>Conversation</h2>"
        for msg in messages:
            html += f"""
            <div class="message {msg.role}">
                <div class="role">{msg.role.capitalize()}</div>
                <div>{markdown2.markdown(msg.content)}</div>
            </div>
            """

        html += "</body></html>"
        return html
```

### Day 14: Basic Voice Input & Memory System

#### Frontend: Voice Input (Speech-to-Text)
```javascript
// Voice input implementation
class VoiceInput {
    constructor() {
        this.recognition = null;
        this.isListening = false;
        this.initializeSpeechRecognition();
    }

    initializeSpeechRecognition() {
        if (!('webkitSpeechRecognition' in window) &&
            !('SpeechRecognition' in window)) {
            console.warn('Speech recognition not supported');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition ||
                                  window.webkitSpeechRecognition;

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';

        this.recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');

            // Update input field
            const input = document.getElementById('messageInput');
            if (event.results[0].isFinal) {
                input.value = transcript;
            } else {
                // Show interim results
                input.placeholder = transcript;
            }
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.stopListening();
        };

        this.recognition.onend = () => {
            this.stopListening();
        };
    }

    toggleListening() {
        if (this.isListening) {
            this.stopListening();
        } else {
            this.startListening();
        }
    }

    startListening() {
        if (!this.recognition) {
            alert('Speech recognition not supported in your browser');
            return;
        }

        this.recognition.start();
        this.isListening = true;

        // Update UI
        const btn = document.getElementById('voiceBtn');
        btn.classList.add('listening');
        btn.innerHTML = '🎤 Listening...';
    }

    stopListening() {
        if (this.recognition) {
            this.recognition.stop();
        }
        this.isListening = false;

        // Update UI
        const btn = document.getElementById('voiceBtn');
        btn.classList.remove('listening');
        btn.innerHTML = '🎤';
    }
}
```

#### Backend: Memory System
```python
# models/memory.py
class UserMemory(db.Model):
    """Persistent facts about users across conversations."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    key = db.Column(db.String(100), index=True)
    value = db.Column(db.Text)
    category = db.Column(db.String(50))  # 'preference', 'fact', 'context'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'key'),)

class MemoryService:
    @staticmethod
    def store_memory(user_id: int, key: str, value: str, category: str = 'fact'):
        """Store or update a memory."""
        memory = UserMemory.query.filter_by(
            user_id=user_id,
            key=key
        ).first()

        if memory:
            memory.value = value
            memory.updated_at = datetime.utcnow()
        else:
            memory = UserMemory(
                user_id=user_id,
                key=key,
                value=value,
                category=category
            )
            db.session.add(memory)

        db.session.commit()
        return memory

    @staticmethod
    def get_user_memories(user_id: int, category: str = None):
        """Get all memories for a user."""
        query = UserMemory.query.filter_by(user_id=user_id)
        if category:
            query = query.filter_by(category=category)

        return query.all()

    @staticmethod
    def format_memories_for_context(user_id: int):
        """Format memories as context for Claude."""
        memories = MemoryService.get_user_memories(user_id)

        if not memories:
            return None

        context = "## User Context\n\n"

        # Group by category
        categories = {}
        for memory in memories:
            if memory.category not in categories:
                categories[memory.category] = []
            categories[memory.category].append(f"- {memory.key}: {memory.value}")

        for category, items in categories.items():
            context += f"### {category.capitalize()}\n"
            context += "\n".join(items) + "\n\n"

        return context
```

### Day 15: Final UI Polish

#### Custom Layouts & Markdown Preview
```javascript
// Layout manager
class LayoutManager {
    constructor() {
        this.layouts = {
            default: {
                sidebar: '300px',
                main: 'auto',
                rightPanel: '0px'
            },
            focus: {
                sidebar: '0px',
                main: '100%',
                rightPanel: '0px'
            },
            wide: {
                sidebar: '250px',
                main: 'auto',
                rightPanel: '300px'
            }
        };

        this.currentLayout = 'default';
        this.loadSavedLayout();
    }

    switchLayout(layoutName) {
        const layout = this.layouts[layoutName];
        if (!layout) return;

        const container = document.getElementById('appContainer');
        container.style.gridTemplateColumns =
            `${layout.sidebar} ${layout.main} ${layout.rightPanel}`;

        this.currentLayout = layoutName;
        localStorage.setItem('preferredLayout', layoutName);
    }
}

// Markdown preview
class MarkdownPreview {
    constructor() {
        this.previewEnabled = false;
        this.converter = new showdown.Converter({
            tables: true,
            tasklists: true,
            strikethrough: true,
            ghCodeBlocks: true
        });
    }

    togglePreview() {
        this.previewEnabled = !this.previewEnabled;

        if (this.previewEnabled) {
            this.showPreview();
        } else {
            this.hidePreview();
        }
    }

    showPreview() {
        const input = document.getElementById('messageInput');
        const previewDiv = document.createElement('div');
        previewDiv.id = 'markdownPreview';
        previewDiv.className = 'markdown-preview';

        input.addEventListener('input', () => {
            const html = this.converter.makeHtml(input.value);
            previewDiv.innerHTML = html;
        });

        input.parentElement.appendChild(previewDiv);
    }
}
```

---

## Database Migrations

```sql
-- Add token_count to project_knowledge
ALTER TABLE project_knowledge ADD COLUMN token_count INTEGER DEFAULT 0;

-- Add user memories table
CREATE TABLE user_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    key VARCHAR(100) NOT NULL,
    value TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Add conversation search index
CREATE INDEX idx_conversation_title ON conversations(title);
CREATE INDEX idx_message_content ON messages(content);

-- Add export tracking
CREATE TABLE export_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    conversation_id INTEGER NOT NULL,
    format VARCHAR(20),
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

---

## Testing Plan

### Week 1 Tests
- [ ] Token counting accuracy
- [ ] Bulk knowledge addition
- [ ] Permission enforcement
- [ ] Upload with interruption

### Week 2 Tests
- [ ] Streaming performance
- [ ] Context compaction
- [ ] Search functionality
- [ ] Export formats

### Week 3 Tests
- [ ] Voice input across browsers
- [ ] Memory persistence
- [ ] Layout saving
- [ ] Full integration test

---

## Deployment Checklist

### Pre-deployment
- [ ] Run all unit tests
- [ ] Test token counting with large files
- [ ] Verify permission system blocks writes
- [ ] Test upload with 10MB+ files
- [ ] Check memory usage with 50+ files

### Deployment
- [ ] Backup v0.1 database
- [ ] Run database migrations
- [ ] Update static assets
- [ ] Clear browser cache
- [ ] Update documentation

### Post-deployment
- [ ] Monitor error logs
- [ ] Check streaming latency
- [ ] Verify token counts accurate
- [ ] Test export functionality
- [ ] Gather user feedback

---

## Summary

Version 0.2 focuses on practical improvements:

**Week 1**: Core infrastructure (token management, permissions, uploads)
**Week 2**: UX enhancements (streaming, context management, search)
**Week 3**: Advanced features (export, voice, memory)

Total estimated development time: 15 days

This plan delivers all requested features plus selected enhancements in a realistic timeframe.