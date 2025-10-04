// Debug script for Add Selected button issue
console.log("=== ADD BUTTON DEBUG SCRIPT LOADED ===");

// Wait for page to be ready
function debugAddButton() {
    console.log("Starting Add button debugging...");

    // Check if button exists
    const button = document.getElementById('bulkAddKnowledgeBtn');
    if (!button) {
        console.error("❌ bulkAddKnowledgeBtn not found!");
        return;
    }
    console.log("✅ Button found:", button);

    // Check button sub-elements
    const textEl = button.querySelector('.bulk-btn-text');
    const loadingEl = button.querySelector('.bulk-loading');
    console.log("Text element:", textEl ? "✅ Found" : "❌ Missing");
    console.log("Loading element:", loadingEl ? "✅ Found" : "❌ Missing");

    // Check if ClaudeClone instance exists
    if (typeof window.chatInterface === 'undefined') {
        console.warn("⚠️ chatInterface (ClaudeClone instance) not found in window");

        // Try to find it
        const possibleInstances = Object.keys(window).filter(k => window[k] && window[k].constructor && window[k].constructor.name === 'ClaudeClone');
        if (possibleInstances.length > 0) {
            console.log("Found ClaudeClone instance at:", possibleInstances);
        }
    } else {
        console.log("✅ chatInterface found");
    }

    // Override bulkAddKnowledge to add debugging
    if (typeof ClaudeClone !== 'undefined') {
        const original = ClaudeClone.prototype.bulkAddKnowledge;
        ClaudeClone.prototype.bulkAddKnowledge = async function() {
            console.log("=== BULK ADD KNOWLEDGE TRIGGERED ===");

            // Check preconditions
            console.log("Current conversation:", this.currentConversation);
            console.log("Selected files count:", this.knowledgeSelector.selectedFiles.size);

            if (!this.currentConversation) {
                console.error("❌ No current conversation!");
                alert("Please select or create a conversation first");
                return;
            }

            if (this.knowledgeSelector.selectedFiles.size === 0) {
                console.error("❌ No files selected!");
                alert("Please select files first");
                return;
            }

            console.log("Selected files:", Array.from(this.knowledgeSelector.selectedFiles));

            // Get files data
            const filesData = this.knowledgeSelector.getSelectedFilesData();
            console.log("Files data to send:", filesData);

            // Check button state before proceeding
            const button = document.getElementById('bulkAddKnowledgeBtn');
            console.log("Button disabled?", button.disabled);
            console.log("Button classes:", button.className);

            try {
                // Call original method
                console.log("Calling original bulkAddKnowledge...");
                await original.call(this);
                console.log("✅ bulkAddKnowledge completed");
            } catch (error) {
                console.error("❌ Error in bulkAddKnowledge:", error);
                console.error("Stack trace:", error.stack);
            }
        };
        console.log("✅ bulkAddKnowledge override installed");
    }

    // Add direct click listener for debugging
    const existingListeners = button.onclick || button.addEventListener;
    console.log("Existing onclick:", button.onclick);

    // Add our debug listener
    button.addEventListener('click', function(e) {
        console.log("=== BUTTON CLICKED (Debug Listener) ===");
        console.log("Event:", e);
        console.log("Button disabled?", this.disabled);
        console.log("Event default prevented?", e.defaultPrevented);

        // Check if the button is actually calling the function
        if (window.chatInterface && window.chatInterface.bulkAddKnowledge) {
            console.log("Manually calling bulkAddKnowledge...");
            // Don't actually call it here, just log
            // window.chatInterface.bulkAddKnowledge();
        } else {
            console.error("❌ Cannot find bulkAddKnowledge method!");
        }
    }, true); // Use capture phase

    console.log("✅ Debug listener added to button");

    // Check the event listeners on the button
    if (typeof getEventListeners !== 'undefined') {
        // This only works in Chrome DevTools console
        console.log("Event listeners on button:", getEventListeners(button));
    }

    // Try to find the ClaudeClone instance
    const checkForInstance = () => {
        if (window.chatInterface) {
            console.log("✅ Found chatInterface");
            console.log("  - currentConversation:", window.chatInterface.currentConversation);
            console.log("  - knowledgeSelector:", window.chatInterface.knowledgeSelector);
            console.log("  - bulkAddKnowledge method exists:", typeof window.chatInterface.bulkAddKnowledge === 'function');
        } else {
            // Look for it in other places
            for (let key in window) {
                if (window[key] && window[key].bulkAddKnowledge && typeof window[key].bulkAddKnowledge === 'function') {
                    console.log("✅ Found ClaudeClone instance at window." + key);
                    window.chatInterface = window[key]; // Set it for easier access
                    break;
                }
            }
        }
    };

    // Check now and after a delay
    checkForInstance();
    setTimeout(checkForInstance, 1000);

    console.log("=== Debug setup complete ===");
    console.log("Click the 'Add Selected' button to see debug output");
}

// Run when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', debugAddButton);
} else {
    setTimeout(debugAddButton, 100);
}