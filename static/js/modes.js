/**
 * Conversation Modes Management for v0.3.0
 */

class ModesManager {
    constructor() {
        this.modes = [];
        this.currentMode = null;
        this.defaultModeId = null;
        this.init();
    }

    async init() {
        await this.loadModes();
        this.setupUI();
        this.attachEventListeners();
    }

    async loadModes() {
        try {
            const response = await fetch('/api/modes');
            if (response.ok) {
                const data = await response.json();
                this.modes = data.modes || [];

                // Find default mode
                const defaultMode = this.modes.find(m => m.is_default);
                this.defaultModeId = defaultMode ? defaultMode.id : null;

                // Set current mode to default if not set
                if (!this.currentMode && defaultMode) {
                    this.currentMode = defaultMode;
                }

                this.updateModeDisplay();
            }
        } catch (error) {
            console.error('Failed to load modes:', error);
        }
    }

    setupUI() {
        // Add mode selector to conversation header
        this.addModeSelector();

        // Add modes section to settings
        this.addModesSettings();
    }

    addModeSelector() {
        // Find the conversation header
        const chatHeader = document.querySelector('.chat-header');
        if (!chatHeader) return;

        // Check if selector already exists
        if (document.getElementById('modeSelector')) return;

        // Create mode selector
        const selectorHtml = `
            <div class="mode-selector" id="modeSelector">
                <button class="mode-selector-btn" id="modeSelectorBtn">
                    <span class="mode-icon">💬</span>
                    <span class="mode-name">General</span>
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div class="mode-dropdown" id="modeDropdown" style="display: none;">
                    <!-- Modes will be populated here -->
                </div>
            </div>
        `;

        // Add to header
        const actionsDiv = chatHeader.querySelector('.chat-actions');
        if (actionsDiv) {
            actionsDiv.insertAdjacentHTML('beforebegin', selectorHtml);
        } else {
            chatHeader.insertAdjacentHTML('beforeend', selectorHtml);
        }

        // Add styles
        this.addModeStyles();
    }

    addModeStyles() {
        if (document.getElementById('modeStyles')) return;

        const styles = `
            <style id="modeStyles">
                .mode-selector {
                    position: relative;
                    margin-right: 10px;
                }

                .mode-selector-btn {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px 12px;
                    background: var(--bg-primary);
                    border: 1px solid var(--border-color);
                    border-radius: 8px;
                    cursor: pointer;
                    transition: all 0.2s;
                    font-size: 14px;
                }

                .mode-selector-btn:hover {
                    background: var(--bg-hover);
                    border-color: var(--primary-color);
                }

                .mode-icon {
                    font-size: 16px;
                }

                .mode-name {
                    font-weight: 500;
                }

                .mode-dropdown {
                    position: absolute;
                    top: 100%;
                    left: 0;
                    margin-top: 4px;
                    background: var(--bg-primary);
                    border: 1px solid var(--border-color);
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                    min-width: 200px;
                    z-index: 1000;
                    max-height: 300px;
                    overflow-y: auto;
                }

                .mode-option {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    padding: 10px 12px;
                    cursor: pointer;
                    transition: background 0.2s;
                }

                .mode-option:hover {
                    background: var(--bg-hover);
                }

                .mode-option.selected {
                    background: var(--bg-secondary);
                }

                .mode-option-icon {
                    font-size: 18px;
                }

                .mode-option-info {
                    flex: 1;
                }

                .mode-option-name {
                    font-weight: 500;
                    margin-bottom: 2px;
                }

                .mode-option-desc {
                    font-size: 11px;
                    color: var(--text-secondary);
                }

                .mode-option-badge {
                    font-size: 10px;
                    padding: 2px 6px;
                    background: var(--primary-color);
                    color: white;
                    border-radius: 4px;
                }

                /* Modes Settings Styles */
                .modes-settings {
                    margin-top: 20px;
                }

                #modeFormContainer {
                    position: relative;
                    z-index: 100;
                }

                #modeFormContainer[style*="display: block"] {
                    animation: slideDown 0.3s ease-out;
                }

                @keyframes slideDown {
                    from {
                        opacity: 0;
                        transform: translateY(-20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }

                .modes-list {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                    margin-bottom: 20px;
                }

                .mode-item {
                    display: flex;
                    align-items: center;
                    padding: 12px;
                    background: var(--bg-secondary);
                    border-radius: 8px;
                    border: 1px solid var(--border-color);
                }

                .mode-item-icon {
                    font-size: 24px;
                    margin-right: 12px;
                }

                .mode-item-info {
                    flex: 1;
                }

                .mode-item-name {
                    font-weight: 600;
                    margin-bottom: 4px;
                }

                .mode-item-details {
                    font-size: 12px;
                    color: var(--text-secondary);
                }

                .mode-item-actions {
                    display: flex;
                    gap: 8px;
                }

                .mode-action-btn {
                    padding: 6px 10px;
                    background: var(--bg-primary);
                    border: 1px solid var(--border-color);
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 12px;
                    transition: all 0.2s;
                }

                .mode-action-btn:hover {
                    background: var(--bg-hover);
                    border-color: var(--primary-color);
                }

                .mode-form {
                    display: flex !important;
                    flex-direction: column;
                    gap: 15px;
                    padding: 20px;
                    background: var(--bg-secondary);
                    border-radius: 8px;
                    margin-top: 20px;
                    border: 2px solid var(--primary-color);
                }

                .mode-form-group {
                    display: flex;
                    flex-direction: column;
                    gap: 5px;
                }

                .mode-form-label {
                    font-size: 12px;
                    font-weight: 600;
                    color: var(--text-secondary);
                }

                .mode-form-input,
                .mode-form-select,
                .mode-form-textarea {
                    padding: 8px 12px;
                    background: var(--bg-primary);
                    border: 1px solid var(--border-color);
                    border-radius: 6px;
                    font-size: 14px;
                }

                .mode-form-textarea {
                    min-height: 100px;
                    resize: vertical;
                }

                .mode-form-actions {
                    display: flex;
                    gap: 10px;
                    justify-content: flex-end;
                }
            </style>
        `;

        document.head.insertAdjacentHTML('beforeend', styles);
    }

    addModesSettings() {
        // Add to settings modal if it exists
        const settingsModal = document.getElementById('settingsModal');
        if (!settingsModal) return;

        const settingsBody = settingsModal.querySelector('.modal-body');
        if (!settingsBody) return;

        // Check if modes section already exists
        if (document.getElementById('modesSettings')) {
            // Just populate the list if it already exists
            this.populateModesList();
            return;
        }

        // Create modes settings section
        const modesHtml = `
            <div class="modes-settings" id="modesSettings">
                <h3>Conversation Modes</h3>
                <p class="text-secondary">Create custom modes with specific models and system prompts.</p>

                <div class="modes-list" id="modesList">
                    <!-- Modes will be populated here -->
                </div>

                <button class="btn btn-primary" id="addModeBtn" type="button">
                    <i class="fas fa-plus"></i> Add New Mode
                </button>

                <div id="modeFormContainer" style="display: none;">
                    <!-- Mode form will be inserted here -->
                </div>
            </div>
        `;

        settingsBody.insertAdjacentHTML('beforeend', modesHtml);

        // Populate the modes list after adding the section
        this.populateModesList();
    }

    attachEventListeners() {
        // Mode selector dropdown
        document.addEventListener('click', (e) => {
            const selectorBtn = e.target.closest('#modeSelectorBtn');
            const dropdown = document.getElementById('modeDropdown');

            if (selectorBtn) {
                e.stopPropagation();
                const isOpen = dropdown && dropdown.style.display !== 'none';
                if (dropdown) {
                    dropdown.style.display = isOpen ? 'none' : 'block';
                    if (!isOpen) {
                        this.populateModeDropdown();
                    }
                }
            } else if (!e.target.closest('#modeDropdown')) {
                if (dropdown) {
                    dropdown.style.display = 'none';
                }
            }

            // Handle Add Mode button
            if (e.target.closest('#addModeBtn')) {
                console.log('Add Mode button clicked!');
                e.preventDefault();
                e.stopPropagation();
                this.showModeForm();
                return;
            }

            // Handle Edit Mode buttons
            const editBtn = e.target.closest('.mode-edit-btn');
            if (editBtn) {
                console.log('Edit button clicked!');
                e.preventDefault();
                e.stopPropagation();
                const modeId = parseInt(editBtn.dataset.modeId);
                this.editMode(modeId);
                return;
            }

            // Handle Duplicate Mode buttons
            const duplicateBtn = e.target.closest('.mode-duplicate-btn');
            if (duplicateBtn) {
                e.preventDefault();
                e.stopPropagation();
                const modeId = parseInt(duplicateBtn.dataset.modeId);
                this.duplicateMode(modeId);
                return;
            }

            // Handle Delete Mode buttons
            const deleteBtn = e.target.closest('.mode-delete-btn');
            if (deleteBtn) {
                e.preventDefault();
                e.stopPropagation();
                const modeId = parseInt(deleteBtn.dataset.modeId);
                this.deleteMode(modeId);
                return;
            }
        });

        // Hook into settings modal visibility using MutationObserver
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.target.id === 'settingsModal' &&
                    mutation.target.style.display === 'block') {
                    console.log('Settings modal opened, adding modes section...');
                    setTimeout(() => {
                        this.addModesSettings();
                        this.populateModesList();
                    }, 50);
                }
            });
        });

        // Start observing the settings modal if it exists
        const settingsModal = document.getElementById('settingsModal');
        if (settingsModal) {
            observer.observe(settingsModal, {
                attributes: true,
                attributeFilter: ['style']
            });
        }

        // Also add listener to settings button as backup
        const settingsBtn = document.getElementById('settingsBtn');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', () => {
                console.log('Settings button clicked...');
                setTimeout(() => {
                    this.addModesSettings();
                    this.populateModesList();
                }, 200);
            });
        }
    }

    populateModeDropdown() {
        const dropdown = document.getElementById('modeDropdown');
        if (!dropdown) return;

        dropdown.innerHTML = this.modes.map(mode => `
            <div class="mode-option ${mode.id === this.currentMode?.id ? 'selected' : ''}"
                 data-mode-id="${mode.id}">
                <span class="mode-option-icon">${mode.icon || '💬'}</span>
                <div class="mode-option-info">
                    <div class="mode-option-name">${mode.name}</div>
                    ${mode.description ? `<div class="mode-option-desc">${mode.description}</div>` : ''}
                </div>
                ${mode.is_default ? '<span class="mode-option-badge">Default</span>' : ''}
            </div>
        `).join('');

        // Add click handlers
        dropdown.querySelectorAll('.mode-option').forEach(option => {
            option.addEventListener('click', () => {
                const modeId = parseInt(option.dataset.modeId);
                this.selectMode(modeId);
            });
        });
    }

    populateModesList() {
        const modesList = document.getElementById('modesList');
        if (!modesList) return;

        modesList.innerHTML = this.modes.map(mode => `
            <div class="mode-item" data-mode-id="${mode.id}">
                <span class="mode-item-icon">${mode.icon || '💬'}</span>
                <div class="mode-item-info">
                    <div class="mode-item-name">
                        ${mode.name}
                        ${mode.is_default ? '<span class="mode-option-badge">Default</span>' : ''}
                    </div>
                    <div class="mode-item-details">
                        ${mode.model || 'claude-3-5-sonnet-20241022'} •
                        ${mode.knowledge_files_count || 0} knowledge files •
                        ${mode.system_tokens || 0} system tokens
                    </div>
                </div>
                <div class="mode-item-actions">
                    <button class="mode-action-btn mode-edit-btn" data-mode-id="${mode.id}">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                    ${!mode.is_default ? `
                        <button class="mode-action-btn mode-duplicate-btn" data-mode-id="${mode.id}">
                            <i class="fas fa-copy"></i> Duplicate
                        </button>
                        <button class="mode-action-btn mode-delete-btn" data-mode-id="${mode.id}">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    async selectMode(modeId) {
        const mode = this.modes.find(m => m.id === modeId);
        if (!mode) return;

        this.currentMode = mode;
        this.updateModeDisplay();

        // Store in localStorage
        localStorage.setItem('selectedModeId', modeId);

        // Update current conversation if exists
        if (window.conversationManager?.currentConversation || window.chatInterface?.currentConversation) {
            const currentConv = window.conversationManager?.currentConversation || window.chatInterface?.currentConversation;
            await this.updateConversationMode(currentConv.uuid, modeId);
        }

        // Store mode in app settings for new conversations
        if (window.chatInterface) {
            window.chatInterface.selectedModeId = modeId;
            window.chatInterface.selectedMode = mode;
        }

        // Close dropdown
        document.getElementById('modeDropdown').style.display = 'none';

        // Show notification
        this.showNotification(`Switched to ${mode.name} mode`);
    }

    updateModeDisplay() {
        const selectorBtn = document.getElementById('modeSelectorBtn');
        if (!selectorBtn) return;

        const mode = this.currentMode || this.modes.find(m => m.is_default) || this.modes[0];
        if (!mode) return;

        selectorBtn.querySelector('.mode-icon').textContent = mode.icon || '💬';
        selectorBtn.querySelector('.mode-name').textContent = mode.name;
    }

    showModeForm(modeId = null) {
        console.log('showModeForm called with modeId:', modeId);

        let container = document.getElementById('modeFormContainer');
        if (!container) {
            console.log('Mode form container not found, adding settings section...');
            // Try to add the settings section first
            this.addModesSettings();
            // Try again
            container = document.getElementById('modeFormContainer');
            if (!container) {
                console.error('Still no mode form container after adding settings!');
                alert('Error: Unable to show mode form. Please refresh the page and try again.');
                return;
            }
        }

        const isEdit = modeId !== null;
        const mode = isEdit ? this.modes.find(m => m.id === modeId) : null;

        console.log('Showing form for mode:', mode);

        // Build form HTML first
        const formHtml = `
            <form class="mode-form" id="modeForm">
                <h4>${isEdit ? 'Edit Mode' : 'Create New Mode'}</h4>

                <div class="mode-form-group">
                    <label class="mode-form-label">Name</label>
                    <input type="text" class="mode-form-input" id="modeName"
                           value="${mode?.name || ''}" required>
                </div>

                <div class="mode-form-group">
                    <label class="mode-form-label">Description</label>
                    <input type="text" class="mode-form-input" id="modeDescription"
                           value="${mode?.description || ''}">
                </div>

                <div class="mode-form-group">
                    <label class="mode-form-label">Icon (Emoji)</label>
                    <input type="text" class="mode-form-input" id="modeIcon"
                           value="${mode?.icon || '💬'}" maxlength="2">
                </div>

                <div class="mode-form-group">
                    <label class="mode-form-label">Model</label>
                    <select class="mode-form-select" id="modeModel">
                        <option value="sonnet-4.5">Sonnet 4.5 (Latest)</option>
                        <option value="opus-4.1">Opus 4.1 (Most Capable)</option>
                        <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                        <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                        <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
                        <option value="claude-2.1">Claude 2.1</option>
                        <option value="claude-instant-1.2">Claude Instant</option>
                    </select>
                </div>

                <div class="mode-form-group">
                    <label class="mode-form-label">Temperature (0.0 - 1.0)</label>
                    <input type="number" class="mode-form-input" id="modeTemperature"
                           value="${mode?.configuration?.temperature || mode?.temperature || 0.7}" min="0" max="1" step="0.1">
                </div>

                <div class="mode-form-group">
                    <label class="mode-form-label">System Prompt</label>
                    <textarea class="mode-form-textarea" id="modeSystemPrompt">${mode?.configuration?.system_prompt || mode?.system_prompt || ''}</textarea>
                </div>

                <div class="mode-form-actions">
                    <button type="button" class="btn btn-secondary" onclick="modesManager.cancelModeForm()">
                        Cancel
                    </button>
                    <button type="submit" class="btn btn-primary">
                        ${isEdit ? 'Save Changes' : 'Create Mode'}
                    </button>
                </div>
            </form>
        `;

        // Set the HTML content
        container.innerHTML = formHtml;

        // Force container to be visible with multiple methods
        container.style.display = 'block';
        container.style.visibility = 'visible';
        container.style.opacity = '1';
        container.classList.remove('hidden');

        // Hide the Add New Mode button when form is shown
        const addBtn = document.getElementById('addModeBtn');
        if (addBtn) {
            addBtn.style.display = 'none';
        }

        // Scroll to the form
        setTimeout(() => {
            container.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Also try to focus the first input
            const firstInput = document.getElementById('modeName');
            if (firstInput) {
                firstInput.focus();
            }
        }, 100);

        console.log('Form container display:', container.style.display);
        console.log('Form container visibility:', container.style.visibility);
        console.log('Form HTML length:', formHtml.length);

        // Handle form submission
        document.getElementById('modeForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveModeForm(modeId);
        });

        // Set selected model if editing
        const modelValue = mode?.configuration?.model || mode?.model;
        if (modelValue) {
            const modelSelect = document.getElementById('modeModel');
            if (modelSelect) {
                modelSelect.value = modelValue;
                console.log('Set model to:', modelValue);
            }
        }
    }

    async saveModeForm(modeId = null) {
        const formData = {
            name: document.getElementById('modeName').value,
            description: document.getElementById('modeDescription').value,
            icon: document.getElementById('modeIcon').value || '💬',
            configuration: {
                model: document.getElementById('modeModel').value,
                temperature: parseFloat(document.getElementById('modeTemperature').value),
                system_prompt: document.getElementById('modeSystemPrompt').value
            }
        };

        try {
            const url = modeId ? `/api/modes/${modeId}` : '/api/modes';
            const method = modeId ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method: method,
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                this.showNotification(`Mode ${modeId ? 'updated' : 'created'} successfully`);

                // Hide form and show button
                this.cancelModeForm();

                // Reload modes list
                await this.loadModes();
                this.populateModesList();
            } else {
                const error = await response.json();
                this.showNotification(error.error || 'Failed to save mode', 'error');
            }
        } catch (error) {
            console.error('Failed to save mode:', error);
            this.showNotification('Failed to save mode', 'error');
        }
    }

    cancelModeForm() {
        const container = document.getElementById('modeFormContainer');
        if (container) {
            container.style.display = 'none';
            container.innerHTML = '';
        }

        // Show the Add New Mode button again
        const addBtn = document.getElementById('addModeBtn');
        if (addBtn) {
            addBtn.style.display = 'block';
        }
    }

    async editMode(modeId) {
        console.log('editMode called with id:', modeId);
        // Load full mode details first
        try {
            const response = await fetch(`/api/modes/${modeId}`);
            if (response.ok) {
                const mode = await response.json();
                console.log('Loaded mode details:', mode);

                // Update local cache with full details including configuration
                const index = this.modes.findIndex(m => m.id === modeId);
                if (index !== -1) {
                    // Store complete mode object with configuration
                    this.modes[index] = {
                        ...this.modes[index],
                        ...mode,
                        configuration: mode.configuration,
                        system_prompt: mode.configuration?.system_prompt,
                        temperature: mode.configuration?.temperature,
                        model: mode.configuration?.model
                    };
                }

                this.showModeForm(modeId);
            } else {
                console.error('Failed to load mode, status:', response.status);
                alert('Failed to load mode details');
            }
        } catch (error) {
            console.error('Failed to load mode details:', error);
            alert('Error loading mode: ' + error.message);
        }
    }

    async duplicateMode(modeId) {
        try {
            const response = await fetch(`/api/modes/${modeId}/duplicate`, {
                method: 'POST'
            });

            if (response.ok) {
                this.showNotification('Mode duplicated successfully');
                await this.loadModes();
                this.populateModesList();
            } else {
                const error = await response.json();
                this.showNotification(error.error || 'Failed to duplicate mode', 'error');
            }
        } catch (error) {
            console.error('Failed to duplicate mode:', error);
            this.showNotification('Failed to duplicate mode', 'error');
        }
    }

    async deleteMode(modeId) {
        if (!confirm('Are you sure you want to delete this mode?')) return;

        try {
            const response = await fetch(`/api/modes/${modeId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.showNotification('Mode deleted successfully');
                await this.loadModes();
                this.populateModesList();
            } else {
                const error = await response.json();
                this.showNotification(error.error || 'Failed to delete mode', 'error');
            }
        } catch (error) {
            console.error('Failed to delete mode:', error);
            this.showNotification('Failed to delete mode', 'error');
        }
    }

    async updateConversationMode(conversationUuid, modeId) {
        try {
            // Update the conversation's mode via API
            const response = await fetch(`/api/conversations/${conversationUuid}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    mode_id: modeId
                })
            });

            if (response.ok) {
                console.log(`Updated conversation ${conversationUuid} to mode ${modeId}`);

                // Update the local conversation object
                if (window.chatInterface?.currentConversation) {
                    window.chatInterface.currentConversation.mode_id = modeId;
                }
            } else {
                console.error('Failed to update conversation mode');
            }
        } catch (error) {
            console.error('Error updating conversation mode:', error);
        }
    }

    showNotification(message, type = 'success') {
        // Use existing notification system if available
        if (window.showToast) {
            window.showToast(message);
        } else if (window.conversationManager?.showNotification) {
            window.conversationManager.showNotification(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }
}

// Initialize modes manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.modesManager = new ModesManager();
});

// Also initialize if the DOM is already loaded
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    if (!window.modesManager) {
        window.modesManager = new ModesManager();
    }
}