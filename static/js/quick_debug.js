// Quick debug to find why button doesn't work
console.log("=== QUICK DEBUG LOADED ===");

// Test the button click directly
setTimeout(() => {
    const button = document.getElementById('bulkAddKnowledgeBtn');
    if (!button) {
        console.error("❌ Button not found!");
        return;
    }

    console.log("✅ Button found:", button);
    console.log("Button disabled?", button.disabled);
    console.log("Button onclick:", button.onclick);

    // Check if event listener is attached
    const origAddEventListener = button.addEventListener;
    button.addEventListener = function(type, listener, ...args) {
        console.log(`Event listener added: ${type}`);
        return origAddEventListener.call(this, type, listener, ...args);
    };

    // Check the instance
    if (window.chatInterface) {
        console.log("✅ chatInterface exists");
        console.log("  currentConversation:", window.chatInterface.currentConversation);
        console.log("  knowledgeSelector:", window.chatInterface.knowledgeSelector);
        console.log("  bulkAddKnowledge exists?", typeof window.chatInterface.bulkAddKnowledge === 'function');

        // Check selected files
        if (window.chatInterface.knowledgeSelector) {
            console.log("  Selected files count:", window.chatInterface.knowledgeSelector.selectedFiles.size);
            console.log("  Selected files:", Array.from(window.chatInterface.knowledgeSelector.selectedFiles));
        }

        // Test calling the function directly
        console.log("\n=== TESTING DIRECT CALL ===");
        console.log("Attempting to call bulkAddKnowledge directly...");

        try {
            // First check preconditions
            if (!window.chatInterface.currentConversation) {
                console.error("❌ No current conversation - this will block the function");
                console.log("Create or select a conversation first!");
            } else if (!window.chatInterface.knowledgeSelector || window.chatInterface.knowledgeSelector.selectedFiles.size === 0) {
                console.error("❌ No files selected - this will block the function");
                console.log("Select some files first!");
            } else {
                console.log("✅ All preconditions met, calling function...");
                window.chatInterface.bulkAddKnowledge();
            }
        } catch (error) {
            console.error("❌ Error calling bulkAddKnowledge:", error);
            console.error("Stack:", error.stack);
        }
    } else {
        console.error("❌ chatInterface not found!");
    }

    // Override the click to see what happens
    const originalClick = button.click;
    button.click = function() {
        console.log("=== BUTTON.CLICK() INTERCEPTED ===");
        console.log("Button disabled?", this.disabled);

        // Check if we can find the handler
        if (window.chatInterface && window.chatInterface.bulkAddKnowledge) {
            console.log("Calling bulkAddKnowledge from intercepted click...");
            window.chatInterface.bulkAddKnowledge();
        } else {
            console.error("Cannot find bulkAddKnowledge!");
        }

        return originalClick.call(this);
    };

    console.log("\n=== Ready to test ===");
    console.log("1. Try clicking the button in the UI");
    console.log("2. Or type: document.getElementById('bulkAddKnowledgeBtn').click()");
    console.log("3. Or type: window.chatInterface.bulkAddKnowledge()");

}, 1000);