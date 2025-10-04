// Frontend Fix for Knowledge Selection Issues - v2
// This script enhances the knowledge selection system with debugging and fixes

// Wait for ClaudeClone to be available
function waitForClaudeClone(callback) {
    if (typeof ClaudeClone !== 'undefined' && typeof KnowledgeSelector !== 'undefined') {
        callback();
    } else {
        setTimeout(() => waitForClaudeClone(callback), 100);
    }
}

function applyKnowledgeFixes() {
    console.log("Frontend fixes v2: Applying knowledge selection enhancements...");

    // Enhance KnowledgeSelector selectAll with debugging
    const originalSelectAll = KnowledgeSelector.prototype.selectAll;
    KnowledgeSelector.prototype.selectAll = function() {
        console.log("=== SELECT ALL TRIGGERED ===");
        console.log("Current results count:", this.currentResults.length);

        const availableFiles = this.currentResults.filter(f => !f.is_added);
        console.log("Available files (not added to current conversation):", availableFiles.length);

        // Show token counts for first 5 files
        availableFiles.slice(0, 5).forEach(file => {
            console.log(`  - ${file.name}: ${file.token_count || 0} tokens`);
        });

        // Call original method
        originalSelectAll.call(this);

        console.log("After selection:");
        console.log("  Selected files:", this.selectedFiles.size);
        console.log("  Total tokens:", this.getTotalTokens());

        // Force UI update
        this.updateUI();

        // Force visual update of checkboxes
        document.querySelectorAll('.knowledge-item-checkbox input').forEach(checkbox => {
            const shouldBeChecked = this.selectedFiles.has(checkbox.dataset.path);
            if (checkbox.checked !== shouldBeChecked && !checkbox.disabled) {
                checkbox.checked = shouldBeChecked;
                console.log(`  Checkbox ${checkbox.dataset.path}: ${shouldBeChecked ? 'checked' : 'unchecked'}`);
            }
        });
    };

    // Enhance renderKnowledgeResults with debugging
    const originalRenderResults = ClaudeClone.prototype.renderKnowledgeResults;
    ClaudeClone.prototype.renderKnowledgeResults = function(results) {
        console.log("=== RENDERING KNOWLEDGE RESULTS ===");
        console.log("Total results:", results.length);

        // Count statistics
        const stats = {
            total: results.length,
            withTokens: results.filter(r => r.token_count && r.token_count > 0).length,
            alreadyAdded: results.filter(r => r.is_added).length,
            available: results.filter(r => !r.is_added).length
        };

        console.log("Statistics:", stats);

        // Show first 3 results for debugging
        results.slice(0, 3).forEach(item => {
            console.log(`File: ${item.name}`);
            console.log(`  Path: ${item.path}`);
            console.log(`  Tokens: ${item.token_count || 'not calculated'}`);
            console.log(`  Added to current conversation: ${item.is_added}`);
        });

        // Call original render method
        originalRenderResults.call(this, results);

        // Ensure Select All checkbox state is correct
        const selectAllCheckbox = document.getElementById('selectAllKnowledge');
        if (selectAllCheckbox) {
            const hasAvailableFiles = stats.available > 0;
            selectAllCheckbox.disabled = !hasAvailableFiles;

            if (!hasAvailableFiles) {
                console.log("No files available to select (all already added to current conversation)");
            } else {
                console.log(`${stats.available} files available for selection`);
            }
        }
    };

    // Enhance bulk button update with debugging
    const originalUpdateBulkButton = KnowledgeSelector.prototype.updateBulkButton;
    KnowledgeSelector.prototype.updateBulkButton = function() {
        const selectedCount = this.selectedFiles.size;
        const totalTokens = this.getTotalTokens();

        console.log(`Bulk button update: ${selectedCount} files, ${totalTokens} tokens`);

        originalUpdateBulkButton.call(this);

        // Force enable button if files are selected
        const button = document.getElementById('bulkAddKnowledgeBtn');
        if (button) {
            const shouldBeEnabled = selectedCount > 0;
            if (button.disabled === shouldBeEnabled) {
                button.disabled = !shouldBeEnabled;
                console.log(`Bulk button ${shouldBeEnabled ? 'enabled' : 'disabled'}`);
            }
        }
    };

    // Monitor conversation changes
    const originalShowKnowledgeModal = ClaudeClone.prototype.showKnowledgeModal;
    ClaudeClone.prototype.showKnowledgeModal = async function() {
        console.log("=== KNOWLEDGE MODAL OPENING ===");
        console.log("Current conversation:", this.currentConversation ? this.currentConversation.uuid : 'none');

        if (!this.currentConversation) {
            console.warn("⚠️ No conversation selected! Knowledge won't be properly linked.");
        }

        // Call original method
        await originalShowKnowledgeModal.call(this);
    };

    console.log("✅ Frontend fixes v2 applied successfully!");
    console.log("Open the Knowledge modal to see debugging output in console.");
}

// Apply fixes when ready
waitForClaudeClone(() => {
    applyKnowledgeFixes();
});

// Also apply on DOM ready as backup
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        waitForClaudeClone(applyKnowledgeFixes);
    });
}