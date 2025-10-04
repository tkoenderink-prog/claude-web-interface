// Claude Clone JavaScript Application

// Streaming UI class for enhanced real-time communication
class StreamingUI {
    constructor() {
        this.currentStream = null;
        this.messageBuffer = '';
        this.renderQueue = [];
        this.isStreaming = false;
        this.streamStartTime = null;
        this.typewriterSpeed = 30; // characters per second
        this.chunkBuffer = [];
        this.lastRenderTime = 0;
        this.animationFrame = null;
        this.progressElement = null;
        this.statusElement = null;
        this.cancelButton = null;

        // Markdown parser configuration
        this.markedOptions = {
            breaks: true,
            gfm: true,
            highlight: function(code, lang) {
                if (lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (err) {}
                }
                return hljs.highlightAuto(code).value;
            }
        };

        marked.setOptions(this.markedOptions);
        this.init();
    }

    init() {
        this.createStatusElements();
        this.bindEvents();
    }

    createStatusElements() {
        // Create streaming status bar
        const statusBar = document.createElement('div');
        statusBar.id = 'streamingStatusBar';
        statusBar.className = 'streaming-status-bar hidden';
        statusBar.innerHTML = `
            <div class="streaming-status-content">
                <div class="streaming-status-text">Claude is thinking...</div>
                <div class="streaming-progress">
                    <div class="streaming-progress-bar">
                        <div class="streaming-progress-fill"></div>
                    </div>
                    <div class="streaming-progress-text">0 chars</div>
                </div>
                <button class="streaming-cancel-btn" type="button" title="Cancel streaming">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        // Insert before messages container
        const messagesContainer = document.getElementById('messagesContainer');
        messagesContainer.parentNode.insertBefore(statusBar, messagesContainer);

        this.statusElement = statusBar.querySelector('.streaming-status-text');
        this.progressElement = statusBar.querySelector('.streaming-progress-fill');
        this.cancelButton = statusBar.querySelector('.streaming-cancel-btn');
    }

    bindEvents() {
        // Cancel button
        if (this.cancelButton) {
            this.cancelButton.addEventListener('click', () => {
                this.cancelStream();
            });
        }

        // Escape key to cancel streaming
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isStreaming) {
                this.cancelStream();
            }
        });
    }

    showThinking() {
        const statusBar = document.getElementById('streamingStatusBar');
        statusBar.classList.remove('hidden');

        this.statusElement.innerHTML = `
            <div class="thinking-indicator">
                <span class="thinking-text">Claude is thinking</span>
                <div class="thinking-dots">
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                </div>
            </div>
        `;

        // Hide progress during thinking
        statusBar.querySelector('.streaming-progress').style.display = 'none';
    }

    showAnalyzing() {
        this.statusElement.innerHTML = `
            <div class="analyzing-indicator">
                <i class="fas fa-search spinning"></i>
                <span>Claude is analyzing context...</span>
            </div>
        `;
    }

    startStream(streamId) {
        this.currentStream = streamId;
        this.isStreaming = true;
        this.streamStartTime = Date.now();
        this.messageBuffer = '';
        this.chunkBuffer = [];
        this.renderQueue = [];

        // Show writing status
        this.statusElement.innerHTML = `
            <div class="writing-indicator">
                <i class="fas fa-pen-nib typing-icon"></i>
                <span>Claude is writing...</span>
            </div>
        `;

        // Show progress bar
        const statusBar = document.getElementById('streamingStatusBar');
        statusBar.querySelector('.streaming-progress').style.display = 'flex';

        // Start render loop
        this.startRenderLoop();
    }

    processChunk(chunk) {
        if (!this.isStreaming || !chunk.content) return;

        this.chunkBuffer.push({
            content: chunk.content,
            timestamp: chunk.timestamp || Date.now(),
            metadata: chunk.metadata || {}
        });

        // Update progress
        this.updateProgress(chunk);
    }

    startRenderLoop() {
        const render = () => {
            if (!this.isStreaming) return;

            const now = Date.now();
            if (now - this.lastRenderTime >= 33) { // ~30fps
                this.processChunkBuffer();
                this.lastRenderTime = now;
            }

            this.animationFrame = requestAnimationFrame(render);
        };

        this.animationFrame = requestAnimationFrame(render);
    }

    processChunkBuffer() {
        if (this.chunkBuffer.length === 0) return;

        // Process all pending chunks
        let newContent = '';
        while (this.chunkBuffer.length > 0) {
            const chunk = this.chunkBuffer.shift();
            newContent += chunk.content;

            // Handle special content types
            if (chunk.metadata.code_block) {
                this.handleCodeBlock(chunk);
            }
        }

        if (newContent) {
            this.messageBuffer += newContent;
            this.updateStreamingMessage(this.messageBuffer);
        }
    }

    updateStreamingMessage(content) {
        const container = document.getElementById('messagesContainer');
        let streamingMessage = container.querySelector('.message.assistant.streaming');

        if (!streamingMessage) {
            // Create new streaming message
            streamingMessage = this.createStreamingMessage();
            container.appendChild(streamingMessage);
        }

        const textDiv = streamingMessage.querySelector('.message-text');

        // Progressive markdown rendering
        try {
            // Handle incomplete markdown gracefully
            const processedContent = this.preprocessMarkdown(content);
            textDiv.innerHTML = marked.parse(processedContent);

            // Apply syntax highlighting to any new code blocks
            textDiv.querySelectorAll('pre code:not(.hljs)').forEach((block) => {
                hljs.highlightElement(block);
                this.addCodeBlockFeatures(block);
            });

            // Add copy buttons to completed code blocks
            textDiv.querySelectorAll('pre:not(.copying)').forEach((pre) => {
                this.addCopyButton(pre);
            });

        } catch (e) {
            // Fallback to plain text if markdown parsing fails
            textDiv.textContent = content;
        }

        // Smooth scroll to bottom
        this.smoothScrollToBottom();
    }

    createStreamingMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant streaming';
        messageDiv.innerHTML = `
            <div class="message-avatar">A</div>
            <div class="message-content">
                <div class="message-role">Claude</div>
                <div class="message-text"></div>
                <div class="streaming-cursor"></div>
            </div>
        `;

        return messageDiv;
    }

    preprocessMarkdown(content) {
        // Handle incomplete code blocks
        let processedContent = content;

        // Count triple backticks
        const codeBlockMatches = (content.match(/```/g) || []).length;

        // If odd number of triple backticks, we have an open code block
        if (codeBlockMatches % 2 === 1) {
            // Temporarily close the code block for rendering
            processedContent += '\n```';
        }

        return processedContent;
    }

    handleCodeBlock(chunk) {
        if (chunk.metadata.code_block?.is_opening) {
            // Starting a new code block
            const language = chunk.metadata.code_block.language || 'text';
            this.showCodeBlockStart(language);
        } else if (chunk.metadata.code_block?.is_closing) {
            // Ending a code block
            this.showCodeBlockEnd();
        }
    }

    showCodeBlockStart(language) {
        // Could add special UI for code block detection
        console.log(`Starting code block: ${language}`);
    }

    showCodeBlockEnd() {
        // Could add special UI for code block completion
        console.log('Code block completed');
    }

    addCopyButton(preElement) {
        if (preElement.querySelector('.copy-button')) return;

        const copyButton = document.createElement('button');
        copyButton.className = 'copy-button';
        copyButton.innerHTML = '<i class="fas fa-copy"></i>';
        copyButton.title = 'Copy code';

        copyButton.addEventListener('click', async () => {
            const code = preElement.querySelector('code').textContent;
            try {
                await navigator.clipboard.writeText(code);
                copyButton.innerHTML = '<i class="fas fa-check"></i>';
                copyButton.classList.add('copied');

                setTimeout(() => {
                    copyButton.innerHTML = '<i class="fas fa-copy"></i>';
                    copyButton.classList.remove('copied');
                }, 2000);
            } catch (err) {
                console.error('Failed to copy code:', err);
            }
        });

        preElement.style.position = 'relative';
        preElement.appendChild(copyButton);
    }

    addCodeBlockFeatures(codeBlock) {
        const pre = codeBlock.parentElement;

        // Add language badge if detected
        const language = codeBlock.className.match(/language-(\w+)/)?.[1];
        if (language && !pre.querySelector('.language-badge')) {
            const badge = document.createElement('div');
            badge.className = 'language-badge';
            badge.textContent = language;
            pre.appendChild(badge);
        }

        // Add line numbers for long code blocks
        const lines = codeBlock.textContent.split('\n');
        if (lines.length > 5 && !pre.querySelector('.line-numbers')) {
            this.addLineNumbers(pre, lines.length);
        }
    }

    addLineNumbers(preElement, lineCount) {
        const lineNumbers = document.createElement('div');
        lineNumbers.className = 'line-numbers';

        for (let i = 1; i <= lineCount; i++) {
            const lineNumber = document.createElement('span');
            lineNumber.textContent = i;
            lineNumbers.appendChild(lineNumber);
        }

        preElement.classList.add('with-line-numbers');
        preElement.insertBefore(lineNumbers, preElement.firstChild);
    }

    updateProgress(chunk) {
        const totalChars = this.messageBuffer.length + (chunk.content?.length || 0);
        const progressText = document.querySelector('.streaming-progress-text');

        if (progressText) {
            progressText.textContent = `${totalChars} chars`;
        }

        // Animate progress bar (simulated)
        if (this.progressElement) {
            const progress = Math.min((totalChars / 1000) * 100, 100);
            this.progressElement.style.width = `${progress}%`;
        }

        // Update duration
        if (this.streamStartTime) {
            const duration = ((Date.now() - this.streamStartTime) / 1000).toFixed(1);
            const statusBar = document.getElementById('streamingStatusBar');
            const durationEl = statusBar.querySelector('.duration');
            if (durationEl) {
                durationEl.textContent = `${duration}s`;
            }
        }
    }

    smoothScrollToBottom() {
        const container = document.getElementById('messagesContainer');
        const isNearBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 100;

        if (isNearBottom) {
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        }
    }

    endStream() {
        this.isStreaming = false;

        // Cancel animation frame
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }

        // Process any remaining chunks
        this.processChunkBuffer();

        // Remove streaming cursor and class
        const container = document.getElementById('messagesContainer');
        const streamingMessage = container.querySelector('.message.assistant.streaming');
        if (streamingMessage) {
            streamingMessage.classList.remove('streaming');
            const cursor = streamingMessage.querySelector('.streaming-cursor');
            if (cursor) cursor.remove();
        }

        // Hide status bar with animation
        const statusBar = document.getElementById('streamingStatusBar');
        statusBar.classList.add('hiding');

        setTimeout(() => {
            statusBar.classList.add('hidden');
            statusBar.classList.remove('hiding');
        }, 300);

        // Show completion status briefly
        this.statusElement.innerHTML = `
            <div class="completion-indicator">
                <i class="fas fa-check-circle"></i>
                <span>Response complete</span>
            </div>
        `;

        // Reset state
        this.currentStream = null;
        this.messageBuffer = '';
        this.streamStartTime = null;
    }

    cancelStream() {
        if (!this.isStreaming || !this.currentStream) return;

        // Emit cancel event
        const event = new CustomEvent('streamCancel', {
            detail: { streamId: this.currentStream }
        });
        document.dispatchEvent(event);

        this.endStream();

        // Show cancellation status
        this.statusElement.innerHTML = `
            <div class="cancellation-indicator">
                <i class="fas fa-times-circle"></i>
                <span>Stream cancelled</span>
            </div>
        `;
    }

    showError(error) {
        this.isStreaming = false;

        const statusBar = document.getElementById('streamingStatusBar');
        statusBar.classList.remove('hidden');

        this.statusElement.innerHTML = `
            <div class="error-indicator">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Error: ${error}</span>
            </div>
        `;

        // Auto-hide after 5 seconds
        setTimeout(() => {
            statusBar.classList.add('hidden');
        }, 5000);
    }

    // Network resilience methods
    handleReconnection() {
        if (this.isStreaming) {
            this.statusElement.innerHTML = `
                <div class="reconnection-indicator">
                    <i class="fas fa-wifi spinning"></i>
                    <span>Reconnecting...</span>
                </div>
            `;
        }
    }

    handleReconnected() {
        if (this.isStreaming) {
            this.statusElement.innerHTML = `
                <div class="reconnected-indicator">
                    <i class="fas fa-check-circle"></i>
                    <span>Reconnected - resuming stream</span>
                </div>
            `;

            // Resume writing indicator after brief confirmation
            setTimeout(() => {
                this.statusElement.innerHTML = `
                    <div class="writing-indicator">
                        <i class="fas fa-pen-nib typing-icon"></i>
                        <span>Claude is writing...</span>
                    </div>
                `;
            }, 1500);
        }
    }
}

class KnowledgeSelector {
    constructor() {
        this.selectedFiles = new Set();
        this.tokenCounts = new Map();
        this.maxTokens = 200000;
        this.allFiles = [];
        this.currentResults = [];
    }

    selectAll() {
        // Clear current selection
        this.selectedFiles.clear();

        // Select all files that don't exceed token limit and aren't already added
        let totalTokens = 0;
        for (const file of this.currentResults) {
            if (file.is_added) continue; // Skip already added files

            const tokens = file.token_count || 0;
            if (totalTokens + tokens <= this.maxTokens) {
                this.selectedFiles.add(file.path);
                totalTokens += tokens;
                this.tokenCounts.set(file.path, tokens);
            }
        }

        this.updateUI();
    }

    selectNone() {
        this.selectedFiles.clear();
        this.tokenCounts.clear();
        this.updateUI();
    }

    toggleFile(filePath, tokenCount = 0) {
        if (this.selectedFiles.has(filePath)) {
            this.selectedFiles.delete(filePath);
            this.tokenCounts.delete(filePath);
        } else {
            // Check if adding this file would exceed token limit
            const currentTotal = this.getTotalTokens();
            if (currentTotal + tokenCount <= this.maxTokens) {
                this.selectedFiles.add(filePath);
                this.tokenCounts.set(filePath, tokenCount);
            } else {
                // Show warning
                this.showTokenLimitWarning();
                return false;
            }
        }
        this.updateUI();
        return true;
    }

    getTotalTokens() {
        let total = 0;
        for (const tokens of this.tokenCounts.values()) {
            total += tokens || 0;
        }
        return total;
    }

    updateUI() {
        this.updateSelectionCounter();
        this.updateTokenDisplay();
        this.updateSelectAllCheckbox();
        this.updateBulkButton();
        this.updateFileCheckboxes();
    }

    updateSelectionCounter() {
        const counter = document.getElementById('selectionCounter');
        const availableFiles = this.currentResults.filter(f => !f.is_added).length;
        counter.textContent = `${this.selectedFiles.size} of ${availableFiles} files selected`;
    }

    updateTokenDisplay() {
        const tokenCountEl = document.getElementById('selectedTokens');
        const warningEl = document.getElementById('tokenWarning');
        const totalTokens = this.getTotalTokens();

        tokenCountEl.textContent = totalTokens.toLocaleString();

        if (totalTokens > this.maxTokens) {
            warningEl.style.display = 'block';
            tokenCountEl.style.color = 'var(--error-color)';
        } else {
            warningEl.style.display = 'none';
            tokenCountEl.style.color = 'var(--accent-color)';
        }
    }

    updateSelectAllCheckbox() {
        const checkbox = document.getElementById('selectAllKnowledge');
        const availableFiles = this.currentResults.filter(f => !f.is_added);

        if (availableFiles.length === 0) {
            checkbox.checked = false;
            checkbox.indeterminate = false;
            checkbox.disabled = true;
        } else if (this.selectedFiles.size === 0) {
            checkbox.checked = false;
            checkbox.indeterminate = false;
            checkbox.disabled = false;
        } else if (this.selectedFiles.size === availableFiles.length) {
            checkbox.checked = true;
            checkbox.indeterminate = false;
            checkbox.disabled = false;
        } else {
            checkbox.checked = false;
            checkbox.indeterminate = true;
            checkbox.disabled = false;
        }
    }

    updateBulkButton() {
        const button = document.getElementById('bulkAddKnowledgeBtn');
        const textEl = button.querySelector('.bulk-btn-text');

        if (this.selectedFiles.size === 0) {
            button.disabled = true;
            textEl.textContent = 'Add Selected (0 files)';
        } else {
            button.disabled = false;
            textEl.textContent = `Add Selected (${this.selectedFiles.size} files)`;
        }
    }

    updateFileCheckboxes() {
        // Update individual file checkboxes to match selection state
        document.querySelectorAll('.knowledge-item-checkbox input').forEach(checkbox => {
            const filePath = checkbox.dataset.path;
            checkbox.checked = this.selectedFiles.has(filePath);
        });
    }

    showTokenLimitWarning() {
        // Show a brief warning message
        const warning = document.getElementById('tokenWarning');
        warning.style.display = 'block';
        warning.textContent = 'Cannot add file: would exceed token limit';

        setTimeout(() => {
            warning.style.display = 'none';
            warning.textContent = 'Warning: Selected files exceed recommended token limit';
        }, 3000);
    }

    getSelectedFilesData() {
        return Array.from(this.selectedFiles).map(filePath => {
            const file = this.currentResults.find(f => f.path === filePath);
            return {
                vault: document.getElementById('vaultSelect').value,
                file_path: filePath,
                category: file?.category || 'RESOURCE'
            };
        });
    }

    reset() {
        this.selectedFiles.clear();
        this.tokenCounts.clear();
        this.currentResults = [];
        this.updateUI();
    }
}

class FileChipsManager {
    constructor() {
        this.selectedKnowledgeFiles = new Map(); // path -> {name, tokens, type}
        this.selectedUploadFiles = new Map();    // id -> {name, tokens, type, file}
        this.maxTokens = 200000;
        this.container = document.getElementById('selectedFilesDisplay');
        this.chipsContainer = document.getElementById('fileChipsContainer');
        this.tokenCountText = document.getElementById('tokenCountText');
        this.tokenPercentage = document.getElementById('tokenPercentage');
        this.tokenProgressFill = document.getElementById('tokenProgressFill');
        this.tokenUsageInfo = document.querySelector('.token-usage-info');

        this.debounceTimer = null;
        this.init();
    }

    init() {
        // Initially hidden
        this.updateDisplay();
    }

    addKnowledgeFile(filePath, fileName, tokens = 0) {
        // Extract clean filename from path
        const cleanName = fileName || filePath.split('/').pop().replace(/\.(md|txt)$/, '');

        this.selectedKnowledgeFiles.set(filePath, {
            name: cleanName,
            tokens: tokens,
            type: 'knowledge',
            path: filePath
        });

        this.debouncedUpdate();
        return true;
    }

    addUploadedFile(fileId, fileName, tokens = 0, file = null) {
        this.selectedUploadFiles.set(fileId, {
            name: fileName,
            tokens: tokens,
            type: 'upload',
            file: file,
            id: fileId
        });

        this.debouncedUpdate();
        return true;
    }


    removeKnowledgeFile(filePath) {
        return this.removeFile(filePath, 'knowledge');
    }

    removeUploadFile(fileId) {
        return this.removeFile(fileId, 'upload');
    }

    clearAll() {
        this.selectedKnowledgeFiles.clear();
        this.selectedUploadFiles.clear();
        this.updateDisplay();
    }

    clearKnowledgeFiles() {
        this.selectedKnowledgeFiles.clear();
        this.debouncedUpdate();
    }

    clearUploadFiles() {
        this.selectedUploadFiles.clear();
        this.debouncedUpdate();
    }

    getTotalTokens() {
        let total = 0;

        for (const file of this.selectedKnowledgeFiles.values()) {
            total += file.tokens || 0;
        }

        for (const file of this.selectedUploadFiles.values()) {
            total += file.tokens || 0;
        }

        return total;
    }

    getTotalFileCount() {
        return this.selectedKnowledgeFiles.size + this.selectedUploadFiles.size;
    }

    getSelectedFiles() {
        const files = {
            knowledge: Array.from(this.selectedKnowledgeFiles.values()),
            uploads: Array.from(this.selectedUploadFiles.values())
        };
        return files;
    }

    hasFiles() {
        return this.selectedKnowledgeFiles.size > 0 || this.selectedUploadFiles.size > 0;
    }

    debouncedUpdate() {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        this.debounceTimer = setTimeout(() => {
            this.updateDisplay();
        }, 100);
    }

    updateDisplay() {
        this.renderChips();
        this.updateTokenDisplay();
        this.updateContainerVisibility();
    }

    updateContainerVisibility() {
        if (this.hasFiles()) {
            this.container.style.display = 'block';
        } else {
            this.container.style.display = 'none';
        }
    }

    renderChips() {
        // Create document fragment for efficient DOM updates
        const fragment = document.createDocumentFragment();

        // Add knowledge file chips
        for (const [filePath, file] of this.selectedKnowledgeFiles) {
            const chip = this.createFileChip(filePath, file, 'knowledge');
            fragment.appendChild(chip);
        }

        // Add upload file chips
        for (const [fileId, file] of this.selectedUploadFiles) {
            const chip = this.createFileChip(fileId, file, 'upload');
            fragment.appendChild(chip);
        }

        // Clear and update container
        this.chipsContainer.innerHTML = '';
        this.chipsContainer.appendChild(fragment);
    }

    createFileChip(fileId, file, type) {
        const chip = document.createElement('div');
        chip.className = `file-chip ${type}-file`;
        chip.dataset.fileId = fileId;
        chip.dataset.fileType = type;

        const icon = type === 'knowledge' ? '📚' : '📎';
        const tokenText = file.tokens ? `(${file.tokens.toLocaleString()})` : '(0)';

        chip.innerHTML = `
            <span class="file-chip-icon">${icon}</span>
            <span class="file-chip-name" title="${file.name}">${this.truncateFileName(file.name)}</span>
            <span class="file-chip-tokens">${tokenText}</span>
            <button class="file-chip-remove" type="button" aria-label="Remove file">×</button>
        `;

        // Add click handler for remove button
        const removeBtn = chip.querySelector('.file-chip-remove');
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.animateChipRemoval(chip, fileId, type);
        });

        return chip;
    }

    truncateFileName(name, maxLength = 30) {
        if (name.length <= maxLength) return name;
        return name.substring(0, maxLength - 3) + '...';
    }

    animateChipRemoval(chipElement, fileId, type) {
        chipElement.classList.add('removing');

        // Wait for animation to complete, then remove
        setTimeout(() => {
            this.removeFile(fileId, type);
        }, 300);
    }

    updateTokenDisplay() {
        const totalTokens = this.getTotalTokens();
        const percentage = Math.min((totalTokens / this.maxTokens) * 100, 100);

        // Update text displays
        this.tokenCountText.textContent = `${totalTokens.toLocaleString()} / ${this.maxTokens.toLocaleString()} tokens`;
        this.tokenPercentage.textContent = `${percentage.toFixed(1)}%`;

        // Update progress bar
        this.tokenProgressFill.style.width = `${percentage}%`;

        // Update color coding based on usage levels
        this.updateUsageColors(percentage);
    }

    updateUsageColors(percentage) {
        // Remove existing usage classes
        this.tokenProgressFill.classList.remove('usage-low', 'usage-medium', 'usage-high');
        this.tokenUsageInfo.classList.remove('usage-low', 'usage-medium', 'usage-high');

        // Add appropriate class based on percentage
        let usageClass;
        if (percentage < 60) {
            usageClass = 'usage-low';
        } else if (percentage < 80) {
            usageClass = 'usage-medium';
        } else {
            usageClass = 'usage-high';
        }

        this.tokenProgressFill.classList.add(usageClass);
        this.tokenUsageInfo.classList.add(usageClass);
    }

    // Method to sync with knowledge modal selections
    syncWithKnowledgeModal(knowledgeSelector) {
        // Clear existing knowledge files
        this.clearKnowledgeFiles();

        // Add selected files from knowledge selector
        for (const filePath of knowledgeSelector.selectedFiles) {
            const tokens = knowledgeSelector.tokenCounts.get(filePath) || 0;
            // Extract filename from path
            const fileName = filePath.split('/').pop().replace(/\.(md|txt)$/, '');
            this.addKnowledgeFile(filePath, fileName, tokens);
        }
    }

    // Method to get data for API calls
    getApiData() {
        return {
            knowledge_files: Array.from(this.selectedKnowledgeFiles.keys()),
            upload_files: Array.from(this.selectedUploadFiles.keys()),
            total_tokens: this.getTotalTokens()
        };
    }

    // Method to handle when files are removed from chips (for conversation updates)
    onFileRemoved(callback) {
        this.removeFileCallback = callback;
    }

    // Override removeFile to call callback when files are removed
    removeFile(fileId, fileType = null) {
        // Try to determine file type if not provided
        if (!fileType) {
            if (this.selectedKnowledgeFiles.has(fileId)) {
                fileType = 'knowledge';
            } else if (this.selectedUploadFiles.has(fileId)) {
                fileType = 'upload';
            }
        }

        let removed = false;
        let removedFile = null;

        if (fileType === 'knowledge' && this.selectedKnowledgeFiles.has(fileId)) {
            removedFile = this.selectedKnowledgeFiles.get(fileId);
            this.selectedKnowledgeFiles.delete(fileId);
            removed = true;
        } else if (fileType === 'upload' && this.selectedUploadFiles.has(fileId)) {
            removedFile = this.selectedUploadFiles.get(fileId);
            this.selectedUploadFiles.delete(fileId);
            removed = true;
        }

        if (removed) {
            this.debouncedUpdate();

            // Call callback if registered
            if (this.removeFileCallback && removedFile) {
                this.removeFileCallback(fileId, fileType, removedFile);
            }
        }
        return removed;
    }
}

class PermissionManager {
    constructor() {
        this.permissions = {
            webSearch: false,
            vaultSearch: true,
            readFiles: true,
            writeFiles: false  // ALWAYS FALSE - HARDCODED FOR SAFETY
        };
        this.permissionInfo = null;
        this.isLoading = false;
        this.callbacks = new Set();

        // Initialize UI event listeners
        this.initializeEventListeners();
        this.loadPermissions();
    }

    /**
     * Initialize event listeners for permission toggles
     */
    initializeEventListeners() {
        // Wait for DOM to ensure elements exist
        setTimeout(() => {
            const checkboxes = ['permWebSearch', 'permVaultSearch', 'permReadFiles'];

            checkboxes.forEach(id => {
                const checkbox = document.getElementById(id);
                if (checkbox) {
                    checkbox.addEventListener('change', (e) => {
                        const permission = id.replace('perm', '').toLowerCase().replace('search', 'Search').replace('files', 'Files');
                        this.updatePermission(permission, e.target.checked);
                    });
                }
            });

            // Settings save button
            const saveBtn = document.getElementById('saveSettingsBtn');
            if (saveBtn) {
                saveBtn.addEventListener('click', () => {
                    this.savePermissions();
                });
            }
        }, 100);
    }

    /**
     * Load permissions from server and localStorage
     */
    async loadPermissions() {
        try {
            this.isLoading = true;

            // Load from localStorage first for immediate UI update
            const localPerms = localStorage.getItem('userPermissions');
            if (localPerms) {
                this.permissions = { ...this.permissions, ...JSON.parse(localPerms) };
                this.updateUI();
            }

            // Load from server
            const response = await fetch('/api/permissions');
            const data = await response.json();

            if (data.success) {
                this.permissions = data.permissions;
                this.permissionInfo = data.permission_info;

                // Save to localStorage
                localStorage.setItem('userPermissions', JSON.stringify(this.permissions));

                this.updateUI();
                this.notifyCallbacks('loaded');
            } else {
                console.error('Failed to load permissions:', data.error);
                this.showError('Failed to load permissions');
            }
        } catch (error) {
            console.error('Permission loading error:', error);
            this.showError('Failed to connect to permission service');
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Update a specific permission
     */
    updatePermission(permissionName, value) {
        // CRITICAL SAFETY: Never allow writeFiles to be true
        if (permissionName === 'writeFiles') {
            console.warn('Attempt to modify write permissions blocked');
            return false;
        }

        // Validate permission name
        if (!this.permissions.hasOwnProperty(permissionName)) {
            console.error('Invalid permission name:', permissionName);
            return false;
        }

        const oldValue = this.permissions[permissionName];
        this.permissions[permissionName] = value;

        // Update localStorage immediately
        localStorage.setItem('userPermissions', JSON.stringify(this.permissions));

        // Update UI
        this.updateUI();

        // Show visual feedback
        this.showPermissionChange(permissionName, value);

        // Notify callbacks
        this.notifyCallbacks('changed', { permission: permissionName, value, oldValue });

        return true;
    }

    /**
     * Save permissions to server
     */
    async savePermissions() {
        try {
            this.isLoading = true;

            const response = await fetch('/api/permissions', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    permissions: this.permissions
                })
            });

            const data = await response.json();

            if (data.success) {
                this.permissions = data.permissions;
                localStorage.setItem('userPermissions', JSON.stringify(this.permissions));
                this.updateUI();
                this.showSuccess('Permissions saved successfully');
                this.notifyCallbacks('saved');
            } else {
                console.error('Failed to save permissions:', data.error);
                this.showError(data.error || 'Failed to save permissions');
            }
        } catch (error) {
            console.error('Permission save error:', error);
            this.showError('Failed to save permissions');
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Get list of enabled tools based on current permissions
     */
    getEnabledTools() {
        if (!this.permissionInfo) {
            return [];
        }

        const enabledTools = [];

        for (const [permName, enabled] of Object.entries(this.permissions)) {
            if (enabled && this.permissionInfo.permissions[permName]) {
                enabledTools.push(...this.permissionInfo.permissions[permName].tools);
            }
        }

        // Always include core tools
        if (this.permissionInfo.core_tools) {
            enabledTools.push(...this.permissionInfo.core_tools);
        }

        return [...new Set(enabledTools)]; // Remove duplicates
    }

    /**
     * Check if a specific tool is enabled
     */
    isToolEnabled(toolName) {
        const enabledTools = this.getEnabledTools();
        return enabledTools.includes(toolName);
    }

    /**
     * Update UI elements to reflect current permissions
     */
    updateUI() {
        // Update checkboxes
        const permissionMap = {
            'permWebSearch': 'webSearch',
            'permVaultSearch': 'vaultSearch',
            'permReadFiles': 'readFiles',
            'permWriteFiles': 'writeFiles'
        };

        for (const [elementId, permissionKey] of Object.entries(permissionMap)) {
            const checkbox = document.getElementById(elementId);
            if (checkbox) {
                checkbox.checked = this.permissions[permissionKey];

                // Disable write files checkbox permanently
                if (permissionKey === 'writeFiles') {
                    checkbox.disabled = true;
                    checkbox.checked = false;
                }
            }
        }

        // Update active tools count
        const countElement = document.getElementById('activeToolsCount');
        if (countElement) {
            const enabledCount = Object.values(this.permissions).filter(Boolean).length;
            countElement.textContent = enabledCount;
        }

        // Update permission status
        this.updatePermissionStatus();
    }

    /**
     * Update permission status display
     */
    updatePermissionStatus() {
        const statusElement = document.getElementById('permissionStatus');
        if (!statusElement) return;

        const enabledTools = this.getEnabledTools();
        const enabledCount = enabledTools.length;

        statusElement.innerHTML = `
            <div class="permission-summary">
                <span class="active-tools-count">${enabledCount}</span> tools enabled
            </div>
        `;
    }

    /**
     * Show visual feedback for permission changes
     */
    showPermissionChange(permissionName, value) {
        const elementId = 'perm' + permissionName.charAt(0).toUpperCase() + permissionName.slice(1);
        const toggleElement = document.querySelector(`#${elementId}`).closest('.permission-toggle');

        if (toggleElement) {
            toggleElement.classList.add('changing');
            setTimeout(() => {
                toggleElement.classList.remove('changing');
                toggleElement.classList.add('changed');
                setTimeout(() => {
                    toggleElement.classList.remove('changed');
                }, 600);
            }, 200);
        }
    }

    /**
     * Validate permission value
     */
    validatePermission(permission, value) {
        // CRITICAL: Never allow writeFiles to be true
        if (permission === 'writeFiles') return false;

        // Validate boolean
        return typeof value === 'boolean';
    }

    /**
     * Add callback for permission events
     */
    onPermissionChange(callback) {
        this.callbacks.add(callback);
    }

    /**
     * Remove callback
     */
    offPermissionChange(callback) {
        this.callbacks.delete(callback);
    }

    /**
     * Notify all callbacks
     */
    notifyCallbacks(event, data) {
        this.callbacks.forEach(callback => {
            try {
                callback(event, data);
            } catch (error) {
                console.error('Permission callback error:', error);
            }
        });
    }

    /**
     * Show success message
     */
    showSuccess(message) {
        // You can integrate this with your existing notification system
        console.log('SUCCESS:', message);
        this.showNotification(message, 'success');
    }

    /**
     * Show error message
     */
    showError(message) {
        // You can integrate this with your existing notification system
        console.error('ERROR:', message);
        this.showNotification(message, 'error');
    }

    /**
     * Show notification (integrate with existing system)
     */
    showNotification(message, type = 'info') {
        // This can be enhanced to use your existing notification system
        const notification = document.createElement('div');
        notification.className = `permission-notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 6px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            background: ${type === 'success' ? '#10a37f' : type === 'error' ? '#ef4444' : '#6b7280'};
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
        `;

        document.body.appendChild(notification);

        // Auto remove after 3 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }

    /**
     * Clear all cached permissions
     */
    clearCache() {
        localStorage.removeItem('userPermissions');
        this.permissions = {
            webSearch: false,
            vaultSearch: true,
            readFiles: true,
            writeFiles: false
        };
        this.updateUI();
    }
}

class ClaudeClone {
    constructor() {
        this.socket = null;
        this.currentConversation = null;
        this.conversations = [];
        this.selectedKnowledge = [];
        this.knowledgeSelector = new KnowledgeSelector();
        this.fileChipsManager = new FileChipsManager();
        this.permissionManager = new PermissionManager();
        this.streamingUI = new StreamingUI();

        // Register callback for file removal
        this.fileChipsManager.onFileRemoved((fileId, fileType, removedFile) => {
            this.handleFileRemovedFromChips(fileId, fileType, removedFile);
        });

        this.settings = {
            model: 'sonnet-4.5',  // Updated to Sonnet 4.5
            streaming: true,
            darkMode: false,
            temperature: 0.7,
            maxTokens: 4096
        };

        this.init();
    }

    async init() {
        // Auto-login for demo
        await this.login();

        // Initialize WebSocket
        this.initWebSocket();

        // Load conversations
        await this.loadConversations();

        // Bind events
        this.bindEvents();

        // Load settings from localStorage
        this.loadSettings();

        // Initialize enhanced progressive rendering
        this.enhanceProgressiveRendering();
    }

    async login() {
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            });
            const data = await response.json();
            if (data.success) {
                console.log('Logged in as:', data.user);
            }
        } catch (error) {
            console.error('Login error:', error);
        }
    }

    initWebSocket() {
        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            maxReconnectionAttempts: 10,
            timeout: 20000,
            autoConnect: true
        });

        // Network resilience handling
        this.socket.on('connect', () => {
            console.log('Connected to WebSocket');
            this.streamingUI.handleReconnected();
            this.hideConnectionStatus();
        });

        this.socket.on('disconnect', (reason) => {
            console.log('Socket disconnected:', reason);
            this.streamingUI.handleReconnection();
            this.showConnectionStatus('Disconnected - attempting to reconnect...', 'warning');
        });

        this.socket.on('reconnect', (attemptNumber) => {
            console.log('Reconnected after', attemptNumber, 'attempts');
            this.showConnectionStatus('Reconnected successfully!', 'success');
            setTimeout(() => this.hideConnectionStatus(), 3000);
        });

        this.socket.on('reconnect_attempt', (attemptNumber) => {
            console.log('Reconnection attempt', attemptNumber);
            this.showConnectionStatus(`Reconnecting... (attempt ${attemptNumber})`, 'info');
        });

        this.socket.on('reconnect_error', (error) => {
            console.error('Reconnection error:', error);
            this.showConnectionStatus('Connection failed - check your internet connection', 'error');
        });

        this.socket.on('reconnect_failed', () => {
            console.error('Reconnection failed');
            this.showConnectionStatus('Unable to reconnect - please refresh the page', 'error');
        });

        this.socket.on('stream_start', (data) => {
            console.log('Stream started:', data);
            this.streamingUI.showThinking();
        });

        this.socket.on('stream_status', (data) => {
            console.log('Stream status:', data);
            switch(data.state) {
                case 'thinking':
                    this.streamingUI.showThinking();
                    break;
                case 'analyzing':
                    this.streamingUI.showAnalyzing();
                    break;
                case 'writing':
                    this.streamingUI.startStream(data.stream_id);
                    break;
                case 'complete':
                    this.streamingUI.endStream();
                    break;
                case 'error':
                    this.streamingUI.showError(data.data.error || 'Unknown error');
                    break;
                case 'cancelled':
                    this.streamingUI.endStream();
                    break;
            }
        });

        this.socket.on('stream_chunk', (data) => {
            console.log('Stream chunk received:', data);

            // Use new streaming UI
            this.streamingUI.processChunk({
                content: data.content || data.chunk || data.total || '',
                content_type: data.content_type || 'text',
                position: data.position || 0,
                metadata: data.metadata || {},
                timestamp: data.timestamp || Date.now()
            });

            // Fallback to old method if needed
            if (data.chunk) {
                this.appendToLastMessage(data.chunk);
            } else if (data.total) {
                this.replaceLastMessage(data.total);
            }
        });

        this.socket.on('stream_end', () => {
            console.log('Stream ended');
            this.streamingUI.endStream();
            this.hideTypingIndicator();
        });

        this.socket.on('disconnect', () => {
            console.log('Socket disconnected');
            this.streamingUI.handleReconnection();
        });

        this.socket.on('connect', () => {
            console.log('Socket connected');
            if (this.streamingUI.isStreaming) {
                this.streamingUI.handleReconnected();
            }
        });

        // Listen for stream cancellation events
        document.addEventListener('streamCancel', (event) => {
            const streamId = event.detail.streamId;
            console.log('Cancelling stream:', streamId);

            if (this.socket && this.socket.connected) {
                this.socket.emit('cancel_stream', { stream_id: streamId });
            }
        });

        this.socket.on('message_saved', (message) => {
            this.updateLastMessage(message);
        });
    }

    bindEvents() {
        // New chat button
        document.getElementById('newChatBtn').addEventListener('click', () => {
            this.createNewConversation();
        });

        // Send message
        document.getElementById('sendBtn').addEventListener('click', () => {
            this.sendMessage();
        });

        // Enter key to send
        document.getElementById('messageInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        document.getElementById('messageInput').addEventListener('input', (e) => {
            e.target.style.height = 'auto';
            e.target.style.height = e.target.scrollHeight + 'px';
        });

        // File attachment
        document.getElementById('attachBtn').addEventListener('click', () => {
            document.getElementById('fileInput').click();
        });

        document.getElementById('fileInput').addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files);
        });

        // Knowledge management
        document.getElementById('knowledgeBtn').addEventListener('click', () => {
            this.showKnowledgeModal();
        });

        document.getElementById('searchKnowledgeBtn').addEventListener('click', () => {
            this.searchKnowledge();
        });

        document.getElementById('addKnowledgeBtn').addEventListener('click', () => {
            this.addKnowledgeToConversation();
        });

        // Bulk knowledge management
        document.getElementById('selectAllKnowledge').addEventListener('change', (e) => {
            this.toggleAllKnowledge(e.target.checked);
        });

        document.getElementById('bulkAddKnowledgeBtn').addEventListener('click', () => {
            this.bulkAddKnowledge();
        });

        // Category buttons
        document.querySelectorAll('.category-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.searchKnowledge();
            });
        });

        // Settings
        document.getElementById('settingsBtn').addEventListener('click', () => {
            this.showSettingsModal();
        });

        document.getElementById('saveSettingsBtn').addEventListener('click', () => {
            this.saveSettings();
        });

        // Dark mode
        document.getElementById('darkMode').addEventListener('change', (e) => {
            this.toggleDarkMode(e.target.checked);
        });

        // Temperature slider
        document.getElementById('temperatureSlider').addEventListener('input', (e) => {
            const value = e.target.value / 100;
            document.getElementById('temperatureValue').textContent = value.toFixed(2);
        });

        // Export conversation
        document.getElementById('exportBtn').addEventListener('click', () => {
            this.exportConversation();
        });

        // Delete conversation
        document.getElementById('deleteBtn').addEventListener('click', () => {
            this.deleteConversation();
        });

        // Modal close buttons
        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modalId = e.target.dataset.modal || e.target.closest('button').dataset.modal;
                this.hideModal(modalId);
            });
        });

        // Suggestion chips
        document.querySelectorAll('.suggestion-chip').forEach(chip => {
            chip.addEventListener('click', (e) => {
                const prompt = e.target.dataset.prompt;
                document.getElementById('messageInput').value = prompt;
                this.sendMessage();
            });
        });
    }

    async loadConversations() {
        try {
            const response = await fetch('/api/conversations');
            this.conversations = await response.json();
            this.renderConversations();
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    }

    renderConversations() {
        const container = document.getElementById('conversationsList');
        container.innerHTML = '';

        this.conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            if (this.currentConversation?.uuid === conv.uuid) {
                item.classList.add('active');
            }

            item.innerHTML = `
                <div class="conversation-item-title">${conv.title}</div>
                <div class="conversation-item-date">${this.formatDate(conv.updated_at)}</div>
            `;

            item.addEventListener('click', () => {
                this.loadConversation(conv.uuid);
            });

            container.appendChild(item);
        });
    }

    async createNewConversation() {
        try {
            const response = await fetch('/api/conversations', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    title: 'New Conversation',
                    model: this.settings.model
                })
            });

            const conversation = await response.json();
            this.currentConversation = conversation;
            this.conversations.unshift(conversation);
            this.renderConversations();
            this.clearMessages();
            this.showWelcomeMessage();

            // Clear file chips when starting new conversation
            this.fileChipsManager.clearAll();

            // Join WebSocket room
            if (this.socket) {
                this.socket.emit('join_conversation', {conversation_id: conversation.uuid});
            }
        } catch (error) {
            console.error('Error creating conversation:', error);
        }
    }

    async loadConversation(conversationId) {
        try {
            const response = await fetch(`/api/conversations/${conversationId}`);
            const conversation = await response.json();

            this.currentConversation = conversation;
            this.renderConversations();
            this.renderMessages(conversation.messages);

            document.getElementById('chatTitle').textContent = conversation.title;

            // Join WebSocket room
            if (this.socket) {
                this.socket.emit('join_conversation', {conversation_id: conversationId});
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    }

    renderMessages(messages) {
        const container = document.getElementById('messagesContainer');
        container.innerHTML = '';

        if (!messages || messages.length === 0) {
            this.showWelcomeMessage();
            return;
        }

        messages.forEach(message => {
            this.appendMessage(message);
        });

        container.scrollTop = container.scrollHeight;
    }

    appendMessage(message) {
        const container = document.getElementById('messagesContainer');

        // Remove welcome message if exists
        const welcome = document.getElementById('welcomeMessage');
        if (welcome) welcome.remove();

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role}`;
        messageDiv.dataset.messageId = message.id;

        const avatar = message.role === 'user' ? 'U' : 'A';
        const roleName = message.role === 'user' ? 'You' : 'Claude';

        // Parse markdown content
        const parsedContent = marked.parse(message.content);

        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-role">${roleName}</div>
                <div class="message-text">${parsedContent}</div>
                ${message.attachments && message.attachments.length > 0 ? this.renderAttachments(message.attachments) : ''}
            </div>
        `;

        container.appendChild(messageDiv);

        // Highlight code blocks
        messageDiv.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
    }

    renderAttachments(attachments) {
        return `
            <div class="message-attachments">
                ${attachments.map(att => `
                    <div class="attachment-chip">
                        <i class="fas fa-file"></i>
                        ${att.filename}
                    </div>
                `).join('')}
            </div>
        `;
    }

    async sendMessage() {
        const input = document.getElementById('messageInput');
        const content = input.value.trim();

        if (!content) return;

        if (!this.currentConversation) {
            console.log('No current conversation, creating new one...');
            await this.createNewConversation();
        }

        console.log('Current conversation:', this.currentConversation);
        console.log('Socket status:', this.socket ? 'connected' : 'not connected');
        console.log('Streaming enabled:', this.settings.streaming);

        // Add user message to UI
        const userMessage = {
            role: 'user',
            content: content,
            attachments: []
        };
        this.appendMessage(userMessage);

        // Clear input
        input.value = '';
        input.style.height = 'auto';

        // Send via WebSocket if streaming enabled
        if (this.settings.streaming && this.socket) {
            const fileData = this.fileChipsManager.getApiData();
            const messageData = {
                conversation_id: this.currentConversation.uuid,
                content: content,
                ...fileData
            };
            console.log('Sending via WebSocket with data:', messageData);

            // Add comprehensive error handling
            this.socket.once('error', (error) => {
                console.error('WebSocket error:', error);
                this.showNotification(`Error: ${error.error || error}`, 'error');

                // Fallback to HTTP if WebSocket fails
                console.log('Falling back to HTTP due to WebSocket error');
                this.sendMessageHTTP(content);
            });

            // Send the message
            this.socket.emit('stream_message', messageData);
        } else {
            console.log('Sending via HTTP fallback...');
            // Send via regular HTTP
            await this.sendMessageHTTP(content);
        }
    }

    async sendMessageHTTP(content) {
        try {
            this.showTypingIndicator();

            // Include selected files in the request
            const fileData = this.fileChipsManager.getApiData();

            // Get allowed tools based on current permissions
            const allowedTools = this.permissionManager.getEnabledTools();

            const response = await fetch(`/api/conversations/${this.currentConversation.uuid}/messages`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    content: content,
                    allowed_tools: allowedTools,
                    ...fileData
                })
            });

            const message = await response.json();
            this.hideTypingIndicator();
            this.appendMessage(message);

            // Update conversation list
            await this.loadConversations();
        } catch (error) {
            console.error('Error sending message:', error);
            this.hideTypingIndicator();
        }
    }

    showTypingIndicator() {
        const container = document.getElementById('messagesContainer');

        // Remove existing indicator if any
        this.hideTypingIndicator();

        const indicator = document.createElement('div');
        indicator.className = 'message assistant typing';
        indicator.id = 'typingIndicator';
        indicator.innerHTML = `
            <div class="message-avatar">A</div>
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;

        container.appendChild(indicator);
        container.scrollTop = container.scrollHeight;
    }

    hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) indicator.remove();
    }

    replaceLastMessage(fullText) {
        const container = document.getElementById('messagesContainer');
        let lastMessage = container.querySelector('.message.assistant:last-child');

        if (lastMessage && lastMessage.id !== 'typingIndicator') {
            const textDiv = lastMessage.querySelector('.message-text');
            if (textDiv) {
                textDiv.textContent = fullText;
            }
        }

        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;
    }

    appendToLastMessage(chunk) {
        const container = document.getElementById('messagesContainer');
        let lastMessage = container.querySelector('.message.assistant:last-child');

        if (!lastMessage || lastMessage.id === 'typingIndicator') {
            // Remove typing indicator and create new message
            this.hideTypingIndicator();

            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant streaming';
            messageDiv.innerHTML = `
                <div class="message-avatar">A</div>
                <div class="message-content">
                    <div class="message-role">Claude</div>
                    <div class="message-text"></div>
                </div>
            `;
            container.appendChild(messageDiv);
            lastMessage = messageDiv;
        }

        const textDiv = lastMessage.querySelector('.message-text');
        const currentContent = textDiv.dataset.rawContent || '';
        const newContent = currentContent + chunk;

        // Store raw content
        textDiv.dataset.rawContent = newContent;

        // Parse and render markdown
        textDiv.innerHTML = marked.parse(newContent);

        // Highlight code blocks
        textDiv.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });

        container.scrollTop = container.scrollHeight;
    }

    updateLastMessage(message) {
        const container = document.getElementById('messagesContainer');
        const lastMessage = container.querySelector('.message.assistant.streaming');

        if (lastMessage) {
            lastMessage.classList.remove('streaming');
            lastMessage.dataset.messageId = message.id;
        }
    }

    showWelcomeMessage() {
        const container = document.getElementById('messagesContainer');
        container.innerHTML = `
            <div class="welcome-message" id="welcomeMessage">
                <h2>Welcome to Claude Clone</h2>
                <p>Start a conversation or select from your chat history</p>
                <div class="suggestions">
                    <button class="suggestion-chip" data-prompt="Help me understand the PARA method">
                        PARA Method
                    </button>
                    <button class="suggestion-chip" data-prompt="Analyze my Obsidian vault structure">
                        Vault Analysis
                    </button>
                    <button class="suggestion-chip" data-prompt="Create a project plan template">
                        Project Template
                    </button>
                </div>
            </div>
        `;

        // Re-bind suggestion chip events
        container.querySelectorAll('.suggestion-chip').forEach(chip => {
            chip.addEventListener('click', (e) => {
                const prompt = e.target.dataset.prompt;
                document.getElementById('messageInput').value = prompt;
                this.sendMessage();
            });
        });
    }

    clearMessages() {
        document.getElementById('messagesContainer').innerHTML = '';
    }

    async handleFileSelect(files) {
        if (!files || files.length === 0) return;

        const formData = new FormData();
        for (const file of files) {
            formData.append('file', file);
        }

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            if (result.success) {
                this.addAttachment(result.filename, result.tokens || 0, result.file_id);
            }
        } catch (error) {
            console.error('Error uploading file:', error);
        }
    }

    addAttachment(filename, tokens = 0, fileId = null) {
        // Add to legacy attachment display
        const container = document.getElementById('attachments');
        const chip = document.createElement('div');
        chip.className = 'attachment-chip';
        chip.innerHTML = `
            <i class="fas fa-file"></i>
            ${filename}
            <span class="remove" onclick="this.parentElement.remove()">×</span>
        `;
        container.appendChild(chip);

        // Add to file chips manager
        const id = fileId || `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        this.fileChipsManager.addUploadedFile(id, filename, tokens);
    }

    async showKnowledgeModal() {
        // Check if we have a current conversation, create one if not
        if (!this.currentConversation) {
            console.log('No current conversation, creating one...');
            await this.createNewConversation();
        }

        this.showModal('knowledgeModal');

        // Reset the knowledge selector
        this.knowledgeSelector.reset();

        // Load vault structure and search for all files
        await this.loadVaultStructure();
        await this.searchKnowledge();
    }

    async loadVaultStructure() {
        const vault = document.getElementById('vaultSelect').value;

        try {
            const response = await fetch(`/api/knowledge/structure?vault=${vault}`);
            const structure = await response.json();
            console.log('Vault structure:', structure);
        } catch (error) {
            console.error('Error loading vault structure:', error);
        }
    }

    async searchKnowledge() {
        const vault = document.getElementById('vaultSelect').value;
        const query = document.getElementById('knowledgeSearch').value;
        const category = document.querySelector('.category-btn.active').dataset.category;

        try {
            const response = await fetch('/api/knowledge/search', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    vault: vault,
                    query: query,
                    category: category === 'all' ? null : category,
                    select_all: query === '', // If no query, get all files
                    conversation_id: this.currentConversation ? this.currentConversation.uuid : null
                })
            });

            const results = await response.json();
            this.knowledgeSelector.currentResults = results;
            this.renderKnowledgeResults(results);
        } catch (error) {
            console.error('Error searching knowledge:', error);
        }
    }

    renderKnowledgeResults(results) {
        const container = document.getElementById('knowledgeResults');
        container.innerHTML = '';

        if (results.length === 0) {
            container.innerHTML = '<div class="no-results">No results found</div>';
            this.knowledgeSelector.updateUI();
            return;
        }

        results.forEach(item => {
            const div = document.createElement('div');
            div.className = 'knowledge-item';
            if (item.is_added) {
                div.classList.add('already-added');
            }

            const tokenDisplay = item.token_count ?
                `<div class="knowledge-item-tokens">
                    <i class="fas fa-calculator"></i>
                    ${item.token_count.toLocaleString()} tokens
                </div>` : '';

            const categoryDisplay = item.category ?
                `<div class="knowledge-item-category">${item.category}</div>` : '';

            div.innerHTML = `
                <div class="knowledge-item-checkbox">
                    <input type="checkbox"
                           data-path="${item.path}"
                           data-tokens="${item.token_count || 0}"
                           ${item.is_added ? 'disabled' : ''}>
                </div>
                <div class="knowledge-item-content">
                    <div class="knowledge-item-title">${item.name}</div>
                    <div class="knowledge-item-path">${item.path}</div>
                    <div class="knowledge-item-meta">
                        ${tokenDisplay}
                        ${categoryDisplay}
                    </div>
                </div>
            `;

            // Add event listener to checkbox
            const checkbox = div.querySelector('input[type="checkbox"]');
            if (!item.is_added) {
                checkbox.addEventListener('change', (e) => {
                    e.stopPropagation();
                    const success = this.knowledgeSelector.toggleFile(
                        item.path,
                        item.token_count || 0
                    );
                    if (!success) {
                        // Revert checkbox if token limit exceeded
                        e.target.checked = false;
                    }
                });
            }

            container.appendChild(div);
        });

        // Update UI after rendering
        this.knowledgeSelector.updateUI();
    }

    updateSelectedKnowledge() {
        const selected = document.querySelectorAll('.knowledge-item.selected');
        const container = document.getElementById('selectedKnowledge');

        this.selectedKnowledge = [];
        container.innerHTML = '';

        selected.forEach(item => {
            const path = item.dataset.path;
            const vault = item.dataset.vault;
            const name = item.querySelector('.knowledge-item-title').textContent;

            this.selectedKnowledge.push({vault, path, name});

            const chip = document.createElement('div');
            chip.className = 'attachment-chip';
            chip.innerHTML = `
                <i class="fas fa-file"></i>
                ${name}
            `;
            container.appendChild(chip);
        });
    }

    async addKnowledgeToConversation() {
        if (!this.currentConversation || this.selectedKnowledge.length === 0) return;

        for (const item of this.selectedKnowledge) {
            try {
                await fetch('/api/knowledge/add', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        conversation_id: this.currentConversation.uuid,
                        vault: item.vault,
                        file_path: item.path
                    })
                });
            } catch (error) {
                console.error('Error adding knowledge:', error);
            }
        }

        this.selectedKnowledge = [];
        this.hideModal('knowledgeModal');

        // Show confirmation
        this.showNotification('Knowledge added to conversation');
    }

    toggleAllKnowledge(selectAll) {
        if (selectAll) {
            this.knowledgeSelector.selectAll();
        } else {
            this.knowledgeSelector.selectNone();
        }
    }

    async bulkAddKnowledge() {
        // Check for current conversation
        if (!this.currentConversation) {
            this.showNotification('Please create or select a conversation first', 'error');
            console.error('No current conversation selected');
            return;
        }

        // Check for selected files
        if (this.knowledgeSelector.selectedFiles.size === 0) {
            this.showNotification('Please select at least one file', 'warning');
            console.error('No files selected');
            return;
        }

        const button = document.getElementById('bulkAddKnowledgeBtn');
        const textEl = button.querySelector('.bulk-btn-text');
        const loadingEl = button.querySelector('.bulk-loading');

        // Show loading state
        button.classList.add('loading');
        button.disabled = true;

        try {
            const filesData = this.knowledgeSelector.getSelectedFilesData();

            const response = await fetch('/api/knowledge/add-bulk', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    conversation_id: this.currentConversation.uuid,
                    files: filesData
                })
            });

            const result = await response.json();

            if (result.success) {
                // Show success notification with details
                const summary = result.summary;
                let message = `Successfully added ${summary.succeeded} files`;

                if (summary.failed > 0) {
                    message += `, ${summary.failed} failed`;
                }

                if (summary.duplicates > 0) {
                    message += `, ${summary.duplicates} were already added`;
                }

                if (summary.total_tokens > 0) {
                    message += ` (${summary.total_tokens.toLocaleString()} tokens)`;
                }

                this.showNotification(message);

                // Update file chips manager with successfully added files BEFORE reset
                if (summary.succeeded > 0) {
                    this.fileChipsManager.syncWithKnowledgeModal(this.knowledgeSelector);
                }

                // Reset selection and refresh results
                this.knowledgeSelector.reset();
                await this.searchKnowledge();

                // Close modal if all files were successfully added
                if (summary.failed === 0) {
                    this.hideModal('knowledgeModal');
                }
            } else {
                this.showNotification('Failed to add knowledge: ' + result.error);
            }

        } catch (error) {
            console.error('Error adding bulk knowledge:', error);
            this.showNotification('Error adding knowledge files');
        } finally {
            // Hide loading state
            button.classList.remove('loading');
            button.disabled = this.knowledgeSelector.selectedFiles.size === 0;
        }
    }

    showSettingsModal() {
        // Load current settings
        document.getElementById('modelSelect').value = this.settings.model;
        document.getElementById('temperatureSlider').value = this.settings.temperature * 100;
        document.getElementById('temperatureValue').textContent = this.settings.temperature;
        document.getElementById('maxTokens').value = this.settings.maxTokens;
        document.getElementById('streamingEnabled').checked = this.settings.streaming;
        document.getElementById('darkMode').checked = this.settings.darkMode;

        this.showModal('settingsModal');
    }

    saveSettings() {
        this.settings.model = document.getElementById('modelSelect').value;
        this.settings.temperature = document.getElementById('temperatureSlider').value / 100;
        this.settings.maxTokens = parseInt(document.getElementById('maxTokens').value);
        this.settings.streaming = document.getElementById('streamingEnabled').checked;
        this.settings.darkMode = document.getElementById('darkMode').checked;

        // Save to localStorage
        localStorage.setItem('claude_clone_settings', JSON.stringify(this.settings));

        this.hideModal('settingsModal');
        this.showNotification('Settings saved');
    }

    loadSettings() {
        const saved = localStorage.getItem('claude_clone_settings');
        if (saved) {
            this.settings = {...this.settings, ...JSON.parse(saved)};

            // Apply dark mode if enabled
            if (this.settings.darkMode) {
                document.body.classList.add('dark-mode');
            }
        }
    }

    toggleDarkMode(enabled) {
        if (enabled) {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }
        this.settings.darkMode = enabled;
    }

    async exportConversation() {
        if (!this.currentConversation) return;

        try {
            const response = await fetch(`/api/conversations/${this.currentConversation.uuid}`);
            const conversation = await response.json();

            const exportData = {
                title: conversation.title,
                created_at: conversation.created_at,
                updated_at: conversation.updated_at,
                messages: conversation.messages,
                model: conversation.model
            };

            const blob = new Blob([JSON.stringify(exportData, null, 2)], {type: 'application/json'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${conversation.title.replace(/[^a-z0-9]/gi, '_')}_${Date.now()}.json`;
            a.click();
            URL.revokeObjectURL(url);

            this.showNotification('Conversation exported');
        } catch (error) {
            console.error('Error exporting conversation:', error);
        }
    }

    async deleteConversation() {
        if (!this.currentConversation) return;

        if (!confirm('Are you sure you want to delete this conversation?')) return;

        try {
            const response = await fetch(`/api/conversations/${this.currentConversation.uuid}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.currentConversation = null;
                await this.loadConversations();
                this.showWelcomeMessage();
                this.showNotification('Conversation deleted');
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
        }
    }

    showModal(modalId) {
        document.getElementById(modalId).classList.add('active');
    }

    hideModal(modalId) {
        document.getElementById(modalId).classList.remove('active');
    }

    showNotification(message) {
        // Simple notification implementation
        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--accent-color);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            z-index: 2000;
            animation: slideIn 0.3s ease;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    handleFileRemovedFromChips(fileId, fileType, removedFile) {
        // Handle when a file is removed from the chips display
        if (fileType === 'knowledge') {
            // For knowledge files, we might want to remove them from conversation knowledge
            // This would require an API call to remove the knowledge link
            console.log(`Knowledge file removed from chips: ${removedFile.name}`);

            // Optionally show notification
            this.showNotification(`Removed ${removedFile.name} from context`);
        } else if (fileType === 'upload') {
            // For upload files, we might want to clean up temporary files
            console.log(`Upload file removed from chips: ${removedFile.name}`);

            // Also remove from legacy attachments display if present
            const attachments = document.getElementById('attachments');
            const attachmentChips = attachments.querySelectorAll('.attachment-chip');
            attachmentChips.forEach(chip => {
                if (chip.textContent.includes(removedFile.name)) {
                    chip.remove();
                }
            });

            this.showNotification(`Removed ${removedFile.name} from attachments`);
        }
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));

        if (days === 0) {
            const hours = Math.floor(diff / (1000 * 60 * 60));
            if (hours === 0) {
                const minutes = Math.floor(diff / (1000 * 60));
                return `${minutes} minutes ago`;
            }
            return `${hours} hours ago`;
        } else if (days === 1) {
            return 'Yesterday';
        } else if (days < 7) {
            return `${days} days ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    // Network resilience methods
    showConnectionStatus(message, type = 'info') {
        let statusBar = document.getElementById('connectionStatusBar');

        if (!statusBar) {
            statusBar = document.createElement('div');
            statusBar.id = 'connectionStatusBar';
            statusBar.className = 'connection-status-bar';

            // Insert at the top of main content
            const mainContent = document.querySelector('.main-content');
            mainContent.insertBefore(statusBar, mainContent.firstChild);
        }

        statusBar.className = `connection-status-bar ${type}`;
        statusBar.innerHTML = `
            <div class="connection-status-content">
                <i class="fas ${this.getStatusIcon(type)}"></i>
                <span>${message}</span>
            </div>
        `;

        statusBar.style.display = 'block';

        // Auto-hide info/success messages
        if (type === 'info' || type === 'success') {
            setTimeout(() => this.hideConnectionStatus(), 5000);
        }
    }

    hideConnectionStatus() {
        const statusBar = document.getElementById('connectionStatusBar');
        if (statusBar) {
            statusBar.style.display = 'none';
        }
    }

    getStatusIcon(type) {
        switch (type) {
            case 'success': return 'fa-check-circle';
            case 'warning': return 'fa-exclamation-triangle';
            case 'error': return 'fa-times-circle';
            case 'info': return 'fa-info-circle';
            default: return 'fa-info-circle';
        }
    }

    // Enhanced markdown processing for progressive rendering
    processMarkdownProgressively(content, isComplete = false) {
        // Configure marked for better progressive rendering
        marked.setOptions({
            breaks: true,
            gfm: true,
            sanitize: false,
            smartLists: true,
            smartypants: true,
            highlight: function(code, lang) {
                if (lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (err) {
                        console.warn('Highlight error:', err);
                    }
                }
                return hljs.highlightAuto(code).value;
            }
        });

        try {
            // Handle incomplete markdown structures
            let processedContent = content;

            if (!isComplete) {
                // Fix incomplete code blocks
                const codeBlockCount = (content.match(/```/g) || []).length;
                if (codeBlockCount % 2 === 1) {
                    processedContent += '\n```';
                }

                // Fix incomplete tables
                const lines = content.split('\n');
                const lastLine = lines[lines.length - 1];
                if (lastLine && lastLine.includes('|') && !lastLine.endsWith('|')) {
                    processedContent += '|';
                }

                // Fix incomplete lists
                if (content.endsWith('- ') || content.endsWith('* ') || content.endsWith('+ ')) {
                    processedContent += 'Loading...';
                }
            }

            return marked.parse(processedContent);
        } catch (error) {
            console.warn('Markdown parsing error:', error);
            // Fallback to plain text with basic formatting
            return this.fallbackTextFormatting(content);
        }
    }

    fallbackTextFormatting(content) {
        // Basic formatting when markdown parsing fails
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>')
            .replace(/#{1,6}\s*(.*)/g, '<h3>$1</h3>');
    }

    // Enhanced message processing with progressive rendering
    enhanceProgressiveRendering() {
        // Override the existing appendToLastMessage for better progressive rendering
        const originalAppendToLastMessage = this.appendToLastMessage.bind(this);

        this.appendToLastMessage = (chunk) => {
            const container = document.getElementById('messagesContainer');
            let lastMessage = container.querySelector('.message.assistant:last-child');

            if (!lastMessage || lastMessage.id === 'typingIndicator') {
                // Remove typing indicator and create new message
                this.hideTypingIndicator();

                const messageDiv = document.createElement('div');
                messageDiv.className = 'message assistant streaming streaming-optimized';
                messageDiv.innerHTML = `
                    <div class="message-avatar">A</div>
                    <div class="message-content">
                        <div class="message-role">Claude</div>
                        <div class="message-text"></div>
                    </div>
                `;
                container.appendChild(messageDiv);
                lastMessage = messageDiv;
            }

            const textDiv = lastMessage.querySelector('.message-text');
            const currentContent = textDiv.dataset.rawContent || '';
            const newContent = currentContent + chunk;

            // Store raw content
            textDiv.dataset.rawContent = newContent;

            // Progressive markdown rendering
            const processedHTML = this.processMarkdownProgressively(newContent, false);

            // Use DocumentFragment for efficient DOM updates
            const fragment = document.createDocumentFragment();
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = processedHTML;

            while (tempDiv.firstChild) {
                fragment.appendChild(tempDiv.firstChild);
            }

            // Clear and update content
            textDiv.innerHTML = '';
            textDiv.appendChild(fragment);

            // Highlight new code blocks
            textDiv.querySelectorAll('pre code:not(.hljs)').forEach((block) => {
                hljs.highlightElement(block);
                this.enhanceCodeBlock(block);
            });

            // Smooth scroll to bottom
            this.smoothScrollToBottom();
        };
    }

    enhanceCodeBlock(codeBlock) {
        const pre = codeBlock.parentElement;

        // Add copy button if not already present
        if (!pre.querySelector('.copy-button')) {
            this.streamingUI.addCopyButton(pre);
        }

        // Add language badge if detected
        const language = codeBlock.className.match(/language-(\\w+)/)?.[1];
        if (language && !pre.querySelector('.language-badge')) {
            const badge = document.createElement('div');
            badge.className = 'language-badge';
            badge.textContent = language;
            pre.appendChild(badge);
        }

        // Add line numbers for long code blocks
        const lines = codeBlock.textContent.split('\n');
        if (lines.length > 5 && !pre.querySelector('.line-numbers')) {
            this.addLineNumbers(pre, lines.length);
        }
    }

    addLineNumbers(preElement, lineCount) {
        const lineNumbers = document.createElement('div');
        lineNumbers.className = 'line-numbers';

        for (let i = 1; i <= lineCount; i++) {
            const lineNumber = document.createElement('span');
            lineNumber.textContent = i;
            lineNumbers.appendChild(lineNumber);
        }

        preElement.classList.add('with-line-numbers');
        preElement.insertBefore(lineNumbers, preElement.firstChild);
    }

    smoothScrollToBottom() {
        const container = document.getElementById('messagesContainer');
        const isNearBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 100;

        if (isNearBottom) {
            // Use requestAnimationFrame for smooth scrolling
            requestAnimationFrame(() => {
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'smooth'
                });
            });
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatInterface = new ClaudeClone();
    console.log('ClaudeClone initialized and available at window.chatInterface');
});