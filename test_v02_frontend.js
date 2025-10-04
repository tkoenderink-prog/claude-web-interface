/*
Comprehensive test suite for Claude AI Web Interface v0.2 - Frontend Tests

JavaScript tests that can be run in browser console to test:
- KnowledgeSelector class
- FileChipsManager class
- PermissionManager class
- StreamingUI class

To run these tests:
1. Open the web interface in a browser
2. Open developer console
3. Copy and paste this entire file into the console
4. Run: runAllV02FrontendTests()
*/

// Test utilities
class FrontendTestRunner {
    constructor() {
        this.tests = [];
        this.results = {
            passed: 0,
            failed: 0,
            errors: []
        };
    }

    addTest(name, testFunction) {
        this.tests.push({ name, testFunction });
    }

    async runAll() {
        console.log('🚀 Starting Claude AI Web Interface v0.2 Frontend Tests');
        console.log('=' * 60);

        for (const test of this.tests) {
            try {
                console.log(`\n🧪 Running: ${test.name}`);
                await test.testFunction();
                console.log(`✅ PASSED: ${test.name}`);
                this.results.passed++;
            } catch (error) {
                console.error(`❌ FAILED: ${test.name}`);
                console.error(error);
                this.results.errors.push({ test: test.name, error: error.message });
                this.results.failed++;
            }
        }

        this.printSummary();
    }

    printSummary() {
        console.log('\n' + '=' * 60);
        console.log('📊 TEST SUMMARY');
        console.log('=' * 60);
        console.log(`✅ Passed: ${this.results.passed}`);
        console.log(`❌ Failed: ${this.results.failed}`);
        console.log(`📈 Success Rate: ${((this.results.passed / this.tests.length) * 100).toFixed(1)}%`);

        if (this.results.errors.length > 0) {
            console.log('\n❌ FAILED TESTS:');
            this.results.errors.forEach(({ test, error }) => {
                console.log(`  • ${test}: ${error}`);
            });
        }

        if (this.results.failed === 0) {
            console.log('\n🎉 All tests passed! v0.2 frontend is ready for production.');
        } else {
            console.log('\n⚠️  Some tests failed. Please review and fix issues before deployment.');
        }
    }

    assert(condition, message) {
        if (!condition) {
            throw new Error(`Assertion failed: ${message}`);
        }
    }

    assertEqual(actual, expected, message) {
        if (actual !== expected) {
            throw new Error(`${message}\nExpected: ${expected}\nActual: ${actual}`);
        }
    }

    assertGreater(actual, expected, message) {
        if (actual <= expected) {
            throw new Error(`${message}\nExpected: > ${expected}\nActual: ${actual}`);
        }
    }

    assertContains(array, item, message) {
        if (!array.includes(item)) {
            throw new Error(`${message}\nArray does not contain: ${item}`);
        }
    }
}

// Initialize test runner
const testRunner = new FrontendTestRunner();

// Test KnowledgeSelector class
testRunner.addTest('KnowledgeSelector - Initialization', async () => {
    const selector = new KnowledgeSelector();

    testRunner.assert(selector.selectedFiles instanceof Set, 'selectedFiles should be a Set');
    testRunner.assert(selector.tokenCounts instanceof Map, 'tokenCounts should be a Map');
    testRunner.assertEqual(selector.maxTokens, 200000, 'maxTokens should be 200000');
    testRunner.assertEqual(selector.selectedFiles.size, 0, 'Initially no files selected');
});

testRunner.addTest('KnowledgeSelector - File Selection', async () => {
    const selector = new KnowledgeSelector();

    // Test adding files
    const success1 = selector.toggleFile('test/file1.md', 1000);
    testRunner.assert(success1, 'Should successfully add file within token limit');
    testRunner.assertEqual(selector.selectedFiles.size, 1, 'Should have 1 selected file');
    testRunner.assertEqual(selector.getTotalTokens(), 1000, 'Total tokens should be 1000');

    // Test adding another file
    const success2 = selector.toggleFile('test/file2.md', 2000);
    testRunner.assert(success2, 'Should successfully add second file');
    testRunner.assertEqual(selector.selectedFiles.size, 2, 'Should have 2 selected files');
    testRunner.assertEqual(selector.getTotalTokens(), 3000, 'Total tokens should be 3000');

    // Test removing file
    const success3 = selector.toggleFile('test/file1.md', 1000);
    testRunner.assert(success3, 'Should successfully remove file');
    testRunner.assertEqual(selector.selectedFiles.size, 1, 'Should have 1 selected file after removal');
    testRunner.assertEqual(selector.getTotalTokens(), 2000, 'Total tokens should be 2000 after removal');
});

testRunner.addTest('KnowledgeSelector - Token Limit Enforcement', async () => {
    const selector = new KnowledgeSelector();

    // Try to add file that exceeds token limit
    const success = selector.toggleFile('test/huge_file.md', 250000);
    testRunner.assert(!success, 'Should reject file that exceeds token limit');
    testRunner.assertEqual(selector.selectedFiles.size, 0, 'No files should be selected');
    testRunner.assertEqual(selector.getTotalTokens(), 0, 'Total tokens should remain 0');
});

testRunner.addTest('KnowledgeSelector - Select All Functionality', async () => {
    const selector = new KnowledgeSelector();

    // Mock current results
    selector.currentResults = [
        { path: 'file1.md', token_count: 1000, is_added: false },
        { path: 'file2.md', token_count: 2000, is_added: false },
        { path: 'file3.md', token_count: 3000, is_added: true }, // Already added
        { path: 'file4.md', token_count: 50000, is_added: false }
    ];

    selector.selectAll();

    // Should select files 1, 2, and 4 (skip already added file3)
    testRunner.assertGreater(selector.selectedFiles.size, 0, 'Should select some files');
    testRunner.assert(!selector.selectedFiles.has('file3.md'), 'Should not select already added files');

    // Test select none
    selector.selectNone();
    testRunner.assertEqual(selector.selectedFiles.size, 0, 'Should deselect all files');
    testRunner.assertEqual(selector.getTotalTokens(), 0, 'Total tokens should be 0');
});

// Test FileChipsManager class
testRunner.addTest('FileChipsManager - Initialization', async () => {
    const manager = new FileChipsManager();

    testRunner.assert(manager.selectedKnowledgeFiles instanceof Map, 'Knowledge files should be a Map');
    testRunner.assert(manager.selectedUploadFiles instanceof Map, 'Upload files should be a Map');
    testRunner.assertEqual(manager.maxTokens, 200000, 'Max tokens should be 200000');
    testRunner.assertEqual(manager.getTotalFileCount(), 0, 'Initially no files');
});

testRunner.addTest('FileChipsManager - Add Knowledge Files', async () => {
    const manager = new FileChipsManager();

    const success = manager.addKnowledgeFile('projects/test.md', 'Test Project', 1500);
    testRunner.assert(success, 'Should successfully add knowledge file');
    testRunner.assertEqual(manager.selectedKnowledgeFiles.size, 1, 'Should have 1 knowledge file');
    testRunner.assertEqual(manager.getTotalTokens(), 1500, 'Total tokens should be 1500');
    testRunner.assertEqual(manager.getTotalFileCount(), 1, 'Total file count should be 1');
});

testRunner.addTest('FileChipsManager - Add Upload Files', async () => {
    const manager = new FileChipsManager();

    const success = manager.addUploadedFile('upload123', 'uploaded_doc.txt', 800);
    testRunner.assert(success, 'Should successfully add upload file');
    testRunner.assertEqual(manager.selectedUploadFiles.size, 1, 'Should have 1 upload file');
    testRunner.assertEqual(manager.getTotalTokens(), 800, 'Total tokens should be 800');
    testRunner.assertEqual(manager.getTotalFileCount(), 1, 'Total file count should be 1');
});

testRunner.addTest('FileChipsManager - Mixed File Types', async () => {
    const manager = new FileChipsManager();

    // Add both types
    manager.addKnowledgeFile('areas/health.md', 'Health Notes', 1200);
    manager.addUploadedFile('upload456', 'report.pdf', 2300);

    testRunner.assertEqual(manager.getTotalFileCount(), 2, 'Should have 2 total files');
    testRunner.assertEqual(manager.getTotalTokens(), 3500, 'Total tokens should be 3500');

    const selectedFiles = manager.getSelectedFiles();
    testRunner.assertEqual(selectedFiles.knowledge.length, 1, 'Should have 1 knowledge file');
    testRunner.assertEqual(selectedFiles.uploads.length, 1, 'Should have 1 upload file');
});

testRunner.addTest('FileChipsManager - File Removal', async () => {
    const manager = new FileChipsManager();

    // Add files
    manager.addKnowledgeFile('test1.md', 'Test 1', 1000);
    manager.addUploadedFile('upload1', 'test.txt', 500);

    // Remove knowledge file
    const removed1 = manager.removeKnowledgeFile('test1.md');
    testRunner.assert(removed1, 'Should successfully remove knowledge file');
    testRunner.assertEqual(manager.selectedKnowledgeFiles.size, 0, 'Knowledge files should be empty');
    testRunner.assertEqual(manager.getTotalTokens(), 500, 'Should only have upload tokens');

    // Remove upload file
    const removed2 = manager.removeUploadFile('upload1');
    testRunner.assert(removed2, 'Should successfully remove upload file');
    testRunner.assertEqual(manager.selectedUploadFiles.size, 0, 'Upload files should be empty');
    testRunner.assertEqual(manager.getTotalTokens(), 0, 'Total tokens should be 0');
});

testRunner.addTest('FileChipsManager - Clear Operations', async () => {
    const manager = new FileChipsManager();

    // Add files
    manager.addKnowledgeFile('test1.md', 'Test 1', 1000);
    manager.addKnowledgeFile('test2.md', 'Test 2', 1500);
    manager.addUploadedFile('upload1', 'test1.txt', 500);
    manager.addUploadedFile('upload2', 'test2.txt', 800);

    // Clear knowledge files only
    manager.clearKnowledgeFiles();
    testRunner.assertEqual(manager.selectedKnowledgeFiles.size, 0, 'Knowledge files should be cleared');
    testRunner.assertEqual(manager.selectedUploadFiles.size, 2, 'Upload files should remain');
    testRunner.assertEqual(manager.getTotalTokens(), 1300, 'Should only have upload tokens');

    // Clear all
    manager.clearAll();
    testRunner.assertEqual(manager.getTotalFileCount(), 0, 'All files should be cleared');
    testRunner.assertEqual(manager.getTotalTokens(), 0, 'Total tokens should be 0');
});

// Test PermissionManager class
testRunner.addTest('PermissionManager - Initialization', async () => {
    const manager = new PermissionManager();

    testRunner.assert(typeof manager.permissions === 'object', 'Permissions should be an object');
    testRunner.assertEqual(manager.permissions.writeFiles, false, 'Write files should be disabled by default');
    testRunner.assertEqual(manager.permissions.readFiles, true, 'Read files should be enabled by default');
    testRunner.assertEqual(manager.permissions.vaultSearch, true, 'Vault search should be enabled by default');
});

testRunner.addTest('PermissionManager - Permission Updates', async () => {
    const manager = new PermissionManager();

    // Test valid permission update
    const success = manager.updatePermission('webSearch', true);
    testRunner.assert(success, 'Should successfully update webSearch permission');
    testRunner.assertEqual(manager.permissions.webSearch, true, 'webSearch should be enabled');

    // Test invalid permission
    const invalidSuccess = manager.updatePermission('invalidPerm', true);
    testRunner.assert(!invalidSuccess, 'Should reject invalid permission names');
});

testRunner.addTest('PermissionManager - Write Permission Blocking', async () => {
    const manager = new PermissionManager();

    // CRITICAL TEST: Ensure write permissions cannot be enabled
    const blocked = manager.updatePermission('writeFiles', true);
    testRunner.assert(!blocked, 'Should block write permission updates');
    testRunner.assertEqual(manager.permissions.writeFiles, false, 'Write files should remain disabled');

    // Test validation function
    const valid = manager.validatePermission('writeFiles', true);
    testRunner.assert(!valid, 'Should validate writeFiles as invalid when true');

    const validFalse = manager.validatePermission('writeFiles', false);
    testRunner.assert(validFalse, 'Should validate writeFiles as valid when false');
});

testRunner.addTest('PermissionManager - Tool Mapping', async () => {
    const manager = new PermissionManager();

    // Mock permission info
    manager.permissionInfo = {
        permissions: {
            webSearch: { tools: ['WebSearch', 'WebFetch'] },
            readFiles: { tools: ['Read'] },
            vaultSearch: { tools: ['Grep', 'Glob'] },
            writeFiles: { tools: ['Write', 'Edit'] }
        },
        core_tools: ['Bash', 'TodoWrite']
    };

    // Set permissions
    manager.permissions = {
        webSearch: true,
        readFiles: true,
        vaultSearch: false,
        writeFiles: false
    };

    const enabledTools = manager.getEnabledTools();

    // Should include tools for enabled permissions
    testRunner.assertContains(enabledTools, 'WebSearch', 'Should include WebSearch tool');
    testRunner.assertContains(enabledTools, 'Read', 'Should include Read tool');
    testRunner.assertContains(enabledTools, 'Bash', 'Should include core tools');

    // Should NOT include tools for disabled permissions
    testRunner.assert(!enabledTools.includes('Grep'), 'Should not include Grep (vault search disabled)');
    testRunner.assert(!enabledTools.includes('Write'), 'Should not include Write tools');
});

// Test StreamingUI class
testRunner.addTest('StreamingUI - Initialization', async () => {
    const streamingUI = new StreamingUI();

    testRunner.assert(streamingUI.currentStream === null, 'No current stream initially');
    testRunner.assert(streamingUI.isStreaming === false, 'Not streaming initially');
    testRunner.assertEqual(streamingUI.messageBuffer, '', 'Message buffer should be empty');
    testRunner.assert(Array.isArray(streamingUI.renderQueue), 'Render queue should be an array');
});

testRunner.addTest('StreamingUI - Stream Start/End', async () => {
    const streamingUI = new StreamingUI();

    // Start stream
    streamingUI.startStream('test-stream-123');
    testRunner.assertEqual(streamingUI.currentStream, 'test-stream-123', 'Should set current stream');
    testRunner.assert(streamingUI.isStreaming, 'Should be streaming');
    testRunner.assert(streamingUI.streamStartTime !== null, 'Should set start time');

    // End stream
    streamingUI.endStream();
    testRunner.assert(!streamingUI.isStreaming, 'Should not be streaming');
    testRunner.assertEqual(streamingUI.currentStream, null, 'Should clear current stream');
});

testRunner.addTest('StreamingUI - Chunk Processing', async () => {
    const streamingUI = new StreamingUI();

    streamingUI.startStream('test-stream');

    // Process chunks
    const chunk1 = {
        content: 'Hello ',
        timestamp: Date.now(),
        metadata: {}
    };

    const chunk2 = {
        content: 'world!',
        timestamp: Date.now(),
        metadata: {}
    };

    streamingUI.processChunk(chunk1);
    streamingUI.processChunk(chunk2);

    testRunner.assertGreater(streamingUI.chunkBuffer.length, 0, 'Should have chunks in buffer');
});

testRunner.addTest('StreamingUI - Markdown Processing', async () => {
    const streamingUI = new StreamingUI();

    // Test incomplete markdown
    const incompleteMarkdown = '# Title\n\nSome text with ```python\nprint("hello")';
    const processed = streamingUI.preprocessMarkdown(incompleteMarkdown);

    testRunner.assert(processed.includes('```'), 'Should handle incomplete code blocks');

    // Test complete markdown
    const completeMarkdown = '# Title\n\n**Bold text**';
    const processedComplete = streamingUI.preprocessMarkdown(completeMarkdown);
    testRunner.assertEqual(processedComplete, completeMarkdown, 'Should not modify complete markdown');
});

testRunner.addTest('StreamingUI - Error Handling', async () => {
    const streamingUI = new StreamingUI();

    // Test error display
    streamingUI.showError('Test error message');
    testRunner.assert(!streamingUI.isStreaming, 'Should not be streaming after error');

    // Test status elements exist (if in DOM)
    if (typeof document !== 'undefined') {
        const statusBar = document.getElementById('streamingStatusBar');
        if (statusBar) {
            testRunner.assert(statusBar.style.display !== 'none', 'Status bar should be visible during error');
        }
    }
});

// Integration tests for class interactions
testRunner.addTest('Integration - KnowledgeSelector with FileChipsManager', async () => {
    const selector = new KnowledgeSelector();
    const chipsManager = new FileChipsManager();

    // Mock current results in selector
    selector.currentResults = [
        { path: 'file1.md', token_count: 1000 },
        { path: 'file2.md', token_count: 1500 }
    ];

    // Select files
    selector.toggleFile('file1.md', 1000);
    selector.toggleFile('file2.md', 1500);

    // Sync with chips manager
    chipsManager.syncWithKnowledgeModal(selector);

    testRunner.assertEqual(chipsManager.selectedKnowledgeFiles.size, 2, 'Should sync all selected files');
    testRunner.assertEqual(chipsManager.getTotalTokens(), 2500, 'Should sync token counts');
});

testRunner.addTest('Integration - PermissionManager with Tool Lists', async () => {
    const permManager = new PermissionManager();

    // Mock permission info
    permManager.permissionInfo = {
        permissions: {
            webSearch: { tools: ['WebSearch'], description: 'Web search tools' },
            readFiles: { tools: ['Read'], description: 'File reading tools' }
        },
        core_tools: ['Bash']
    };

    // Test tool checking
    permManager.permissions = { webSearch: true, readFiles: false };

    const isWebSearchEnabled = permManager.isToolEnabled('WebSearch');
    const isReadEnabled = permManager.isToolEnabled('Read');
    const isBashEnabled = permManager.isToolEnabled('Bash');

    testRunner.assert(isWebSearchEnabled, 'WebSearch should be enabled');
    testRunner.assert(!isReadEnabled, 'Read should be disabled');
    testRunner.assert(isBashEnabled, 'Core tools should always be enabled');
});

// Performance tests
testRunner.addTest('Performance - Large File Set Handling', async () => {
    const selector = new KnowledgeSelector();

    // Create large result set
    const largeResultSet = [];
    for (let i = 0; i < 1000; i++) {
        largeResultSet.push({
            path: `test_file_${i}.md`,
            token_count: Math.floor(Math.random() * 5000),
            is_added: false
        });
    }

    selector.currentResults = largeResultSet;

    const startTime = performance.now();
    selector.selectAll();
    const endTime = performance.now();

    const duration = endTime - startTime;
    testRunner.assert(duration < 1000, `Select all should complete quickly, took ${duration}ms`);
    testRunner.assertGreater(selector.selectedFiles.size, 0, 'Should select some files');
});

testRunner.addTest('Performance - FileChipsManager Updates', async () => {
    const manager = new FileChipsManager();

    // Add many files quickly
    const startTime = performance.now();

    for (let i = 0; i < 100; i++) {
        manager.addKnowledgeFile(`file_${i}.md`, `File ${i}`, 100 + i);
    }

    const endTime = performance.now();
    const duration = endTime - startTime;

    testRunner.assert(duration < 1000, `Adding 100 files should be fast, took ${duration}ms`);
    testRunner.assertEqual(manager.selectedKnowledgeFiles.size, 100, 'Should have 100 files');
});

// UI Interaction tests (only if DOM elements exist)
if (typeof document !== 'undefined') {
    testRunner.addTest('UI - Status Elements Exist', async () => {
        // Check for key UI elements
        const elements = [
            'streamingStatusBar',
            'selectedFilesDisplay',
            'fileChipsContainer'
        ];

        let foundElements = 0;
        elements.forEach(id => {
            if (document.getElementById(id)) {
                foundElements++;
            }
        });

        console.log(`Found ${foundElements}/${elements.length} expected UI elements`);
        // Don't fail if elements don't exist, just report
    });
}

// Error handling tests
testRunner.addTest('Error Handling - Invalid Operations', async () => {
    const selector = new KnowledgeSelector();
    const chipsManager = new FileChipsManager();
    const permManager = new PermissionManager();

    // Test graceful handling of invalid operations
    try {
        selector.toggleFile(null, 1000);
        chipsManager.addKnowledgeFile('', '', -1);
        permManager.updatePermission('', true);

        // If we get here, the methods handled invalid input gracefully
        console.log('✓ Invalid operations handled gracefully');
    } catch (error) {
        // Methods should handle invalid input without throwing
        throw new Error('Methods should handle invalid input gracefully');
    }
});

// Function to run all tests
window.runAllV02FrontendTests = async function() {
    await testRunner.runAll();

    // Return results for programmatic access
    return {
        total: testRunner.tests.length,
        passed: testRunner.results.passed,
        failed: testRunner.results.failed,
        successRate: (testRunner.results.passed / testRunner.tests.length) * 100,
        errors: testRunner.results.errors
    };
};

// Auto-run if not in a module environment
if (typeof module === 'undefined') {
    console.log('Claude AI Web Interface v0.2 Frontend Tests Loaded');
    console.log('Run tests with: runAllV02FrontendTests()');
    console.log('');
    console.log('Available test classes:');
    console.log('- KnowledgeSelector');
    console.log('- FileChipsManager');
    console.log('- PermissionManager');
    console.log('- StreamingUI');
    console.log('');
    console.log('Test categories:');
    console.log('- Initialization tests');
    console.log('- Functionality tests');
    console.log('- Integration tests');
    console.log('- Performance tests');
    console.log('- Error handling tests');
}

// Export for use in other contexts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        FrontendTestRunner,
        runAllV02FrontendTests: window.runAllV02FrontendTests
    };
}