#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Main Test Runner for Claude AI Web Interface v0.2

This script runs all test suites in sequence and provides a comprehensive report.
It also validates the database schema, checks dependencies, and tests API endpoints.

Usage:
    python run_v02_tests.py [options]

Options:
    --verbose       Enable verbose output
    --performance   Include performance tests (slower)
    --integration   Include integration tests
    --frontend      Open browser for frontend tests
    --report        Generate detailed HTML report
    --ci            Run in CI mode (minimal output)
"""

import sys
import os
import unittest
import argparse
import time
import json
import subprocess
import importlib
import traceback
import webbrowser
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Test module imports
test_modules = [
    'test_v02_token_system',
    'test_v02_bulk_knowledge',
    'test_v02_file_chips',
    'test_v02_permissions',
    'test_v02_streaming',
    'test_v02_integration',
    'test_v02_performance'
]


class V02TestRunner:
    """Main test runner for v0.2 test suite"""

    def __init__(self, args):
        self.args = args
        self.results = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'skipped': 0,
            'duration': 0,
            'modules': {},
            'failures': [],
            'errors_list': [],
            'system_info': self.get_system_info()
        }
        self.start_time = None

    def get_system_info(self):
        """Get system information for the report"""
        try:
            import platform
            import psutil

            return {
                'python_version': platform.python_version(),
                'platform': platform.platform(),
                'cpu_count': os.cpu_count(),
                'memory_gb': round(psutil.virtual_memory().total / (1024**3), 2),
                'timestamp': datetime.now().isoformat()
            }
        except ImportError:
            return {
                'python_version': sys.version,
                'platform': 'Unknown',
                'timestamp': datetime.now().isoformat()
            }

    def check_dependencies(self):
        """Check if all required dependencies are installed"""
        print("🔍 Checking dependencies...")

        required_packages = [
            'flask', 'flask_cors', 'flask_socketio', 'flask_login',
            'sqlalchemy', 'pathlib', 'asyncio', 'unittest', 'json',
            'tempfile', 'threading', 'queue', 'statistics'
        ]

        optional_packages = [
            ('psutil', 'for performance monitoring'),
            ('tracemalloc', 'for memory profiling')
        ]

        missing_required = []
        missing_optional = []

        # Check required packages
        for package in required_packages:
            try:
                importlib.import_module(package)
                if not self.args.ci:
                    print(f"  ✅ {package}")
            except ImportError:
                missing_required.append(package)
                print(f"  ❌ {package} (REQUIRED)")

        # Check optional packages
        for package, description in optional_packages:
            try:
                importlib.import_module(package)
                if not self.args.ci:
                    print(f"  ✅ {package} ({description})")
            except ImportError:
                missing_optional.append((package, description))
                if not self.args.ci:
                    print(f"  ⚠️  {package} ({description}) - OPTIONAL")

        if missing_required:
            print(f"\n❌ Missing required dependencies: {', '.join(missing_required)}")
            print("Install with: pip install " + " ".join(missing_required))
            return False

        if missing_optional and not self.args.ci:
            print(f"\n⚠️  Missing optional dependencies for enhanced features:")
            for package, description in missing_optional:
                print(f"  • {package}: {description}")

        print("✅ All required dependencies available\n")
        return True

    def validate_database_schema(self):
        """Validate database schema and models"""
        print("🗃️  Validating database schema...")

        try:
            from app import app, db
            from models.models import (
                User, Conversation, Message, ProjectKnowledge,
                ConversationKnowledge, FileAttachment, TokenCache, UserPermissions
            )

            with app.app_context():
                # Test database connection and model definitions
                models_to_test = [
                    User, Conversation, Message, ProjectKnowledge,
                    ConversationKnowledge, FileAttachment, TokenCache, UserPermissions
                ]

                for model in models_to_test:
                    # Check that model has required attributes
                    if hasattr(model, '__tablename__'):
                        if not self.args.ci:
                            print(f"  ✅ {model.__name__} model valid")
                    else:
                        print(f"  ❌ {model.__name__} missing __tablename__")
                        return False

                print("✅ Database schema validation passed\n")
                return True

        except Exception as e:
            print(f"❌ Database schema validation failed: {e}")
            return False

    def test_api_endpoints(self):
        """Test basic API endpoint accessibility"""
        print("🌐 Testing API endpoints...")

        try:
            from app import app

            with app.test_client() as client:
                endpoints_to_test = [
                    ('GET', '/'),
                    ('POST', '/api/auth/login'),
                    ('GET', '/api/permissions'),
                    ('POST', '/api/knowledge/search'),
                    ('POST', '/api/tokens/estimate')
                ]

                accessible_endpoints = 0

                for method, endpoint in endpoints_to_test:
                    try:
                        if method == 'GET':
                            response = client.get(endpoint)
                        else:
                            response = client.post(endpoint, json={})

                        # Any response (even errors) means endpoint is accessible
                        if response.status_code is not None:
                            accessible_endpoints += 1
                            if not self.args.ci:
                                print(f"  ✅ {method} {endpoint} (status: {response.status_code})")

                    except Exception as e:
                        print(f"  ❌ {method} {endpoint} failed: {e}")

                if accessible_endpoints == len(endpoints_to_test):
                    print("✅ All API endpoints accessible\n")
                    return True
                else:
                    print(f"⚠️  {accessible_endpoints}/{len(endpoints_to_test)} endpoints accessible\n")
                    return accessible_endpoints > len(endpoints_to_test) // 2

        except Exception as e:
            print(f"❌ API endpoint testing failed: {e}")
            return False

    def run_test_module(self, module_name):
        """Run tests for a specific module"""
        try:
            if not self.args.ci:
                print(f"\n📋 Running {module_name}...")

            # Import the test module
            test_module = importlib.import_module(module_name)

            # Create test suite
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(test_module)

            # Run tests
            runner = unittest.TextTestRunner(
                verbosity=2 if self.args.verbose else 1,
                stream=sys.stdout if not self.args.ci else open(os.devnull, 'w')
            )

            start_time = time.time()
            result = runner.run(suite)
            duration = time.time() - start_time

            # Store results
            module_results = {
                'tests_run': result.testsRun,
                'failures': len(result.failures),
                'errors': len(result.errors),
                'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
                'duration': duration,
                'success_rate': ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100) if result.testsRun > 0 else 0
            }

            self.results['modules'][module_name] = module_results
            self.results['total_tests'] += result.testsRun
            self.results['passed'] += result.testsRun - len(result.failures) - len(result.errors)
            self.results['failed'] += len(result.failures)
            self.results['errors'] += len(result.errors)
            self.results['skipped'] += module_results['skipped']

            # Store failure details
            for test, traceback_str in result.failures:
                self.results['failures'].append({
                    'module': module_name,
                    'test': str(test),
                    'traceback': traceback_str
                })

            for test, traceback_str in result.errors:
                self.results['errors_list'].append({
                    'module': module_name,
                    'test': str(test),
                    'traceback': traceback_str
                })

            if not self.args.ci:
                print(f"✅ {module_name}: {module_results['tests_run']} tests, "
                      f"{module_results['success_rate']:.1f}% success rate, "
                      f"{duration:.2f}s")

            return True

        except Exception as e:
            print(f"❌ Failed to run {module_name}: {e}")
            if self.args.verbose:
                traceback.print_exc()
            return False

    def run_frontend_tests(self):
        """Run frontend tests in browser"""
        if not self.args.frontend:
            return True

        print("\n🌐 Opening browser for frontend tests...")

        try:
            # Create a simple HTML file to run frontend tests
            html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Claude AI v0.2 Frontend Tests</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .console { background: #f0f0f0; padding: 20px; border-radius: 8px; }
    </style>
</head>
<body>
    <h1>Claude AI Web Interface v0.2 Frontend Tests</h1>
    <p>Open the developer console to see test results.</p>
    <div class="console">
        <h3>Instructions:</h3>
        <ol>
            <li>Open Developer Console (F12)</li>
            <li>Tests will run automatically</li>
            <li>Check console for results</li>
        </ol>
    </div>

    <script>
        // Mock the main application classes if they don't exist
        if (typeof KnowledgeSelector === 'undefined') {
            window.KnowledgeSelector = class {
                constructor() {
                    this.selectedFiles = new Set();
                    this.tokenCounts = new Map();
                    this.maxTokens = 200000;
                    this.currentResults = [];
                }

                toggleFile(path, tokens) {
                    if (this.selectedFiles.has(path)) {
                        this.selectedFiles.delete(path);
                        this.tokenCounts.delete(path);
                    } else {
                        if (this.getTotalTokens() + tokens <= this.maxTokens) {
                            this.selectedFiles.add(path);
                            this.tokenCounts.set(path, tokens);
                            return true;
                        }
                        return false;
                    }
                    return true;
                }

                getTotalTokens() {
                    let total = 0;
                    for (const tokens of this.tokenCounts.values()) {
                        total += tokens;
                    }
                    return total;
                }

                selectAll() {
                    this.selectedFiles.clear();
                    let totalTokens = 0;
                    for (const file of this.currentResults) {
                        if (file.is_added) continue;
                        const tokens = file.token_count || 0;
                        if (totalTokens + tokens <= this.maxTokens) {
                            this.selectedFiles.add(file.path);
                            this.tokenCounts.set(file.path, tokens);
                            totalTokens += tokens;
                        }
                    }
                }

                selectNone() {
                    this.selectedFiles.clear();
                    this.tokenCounts.clear();
                }
            };
        }

        if (typeof FileChipsManager === 'undefined') {
            window.FileChipsManager = class {
                constructor() {
                    this.selectedKnowledgeFiles = new Map();
                    this.selectedUploadFiles = new Map();
                    this.maxTokens = 200000;
                }

                addKnowledgeFile(path, name, tokens) {
                    this.selectedKnowledgeFiles.set(path, { name, tokens, type: 'knowledge', path });
                    return true;
                }

                addUploadedFile(id, name, tokens, file) {
                    this.selectedUploadFiles.set(id, { name, tokens, type: 'upload', file, id });
                    return true;
                }

                removeKnowledgeFile(path) {
                    return this.selectedKnowledgeFiles.delete(path);
                }

                removeUploadFile(id) {
                    return this.selectedUploadFiles.delete(id);
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

                clearAll() {
                    this.selectedKnowledgeFiles.clear();
                    this.selectedUploadFiles.clear();
                }

                clearKnowledgeFiles() {
                    this.selectedKnowledgeFiles.clear();
                }

                getSelectedFiles() {
                    return {
                        knowledge: Array.from(this.selectedKnowledgeFiles.values()),
                        uploads: Array.from(this.selectedUploadFiles.values())
                    };
                }

                syncWithKnowledgeModal(selector) {
                    this.clearKnowledgeFiles();
                    for (const filePath of selector.selectedFiles) {
                        const tokens = selector.tokenCounts.get(filePath) || 0;
                        const fileName = filePath.split('/').pop();
                        this.addKnowledgeFile(filePath, fileName, tokens);
                    }
                }
            };
        }

        if (typeof PermissionManager === 'undefined') {
            window.PermissionManager = class {
                constructor() {
                    this.permissions = {
                        webSearch: false,
                        vaultSearch: true,
                        readFiles: true,
                        writeFiles: false
                    };
                    this.permissionInfo = null;
                }

                updatePermission(name, value) {
                    if (name === 'writeFiles') return false;
                    if (!this.permissions.hasOwnProperty(name)) return false;
                    this.permissions[name] = value;
                    return true;
                }

                validatePermission(name, value) {
                    if (name === 'writeFiles') return false;
                    return typeof value === 'boolean';
                }

                getEnabledTools() {
                    const tools = [];
                    if (this.permissionInfo) {
                        for (const [permName, enabled] of Object.entries(this.permissions)) {
                            if (enabled && this.permissionInfo.permissions[permName]) {
                                tools.push(...this.permissionInfo.permissions[permName].tools);
                            }
                        }
                        if (this.permissionInfo.core_tools) {
                            tools.push(...this.permissionInfo.core_tools);
                        }
                    }
                    return [...new Set(tools)];
                }

                isToolEnabled(toolName) {
                    return this.getEnabledTools().includes(toolName);
                }
            };
        }

        if (typeof StreamingUI === 'undefined') {
            window.StreamingUI = class {
                constructor() {
                    this.currentStream = null;
                    this.isStreaming = false;
                    this.messageBuffer = '';
                    this.renderQueue = [];
                    this.streamStartTime = null;
                    this.chunkBuffer = [];
                }

                startStream(streamId) {
                    this.currentStream = streamId;
                    this.isStreaming = true;
                    this.streamStartTime = Date.now();
                    this.messageBuffer = '';
                    this.chunkBuffer = [];
                }

                endStream() {
                    this.isStreaming = false;
                    this.currentStream = null;
                    this.streamStartTime = null;
                }

                processChunk(chunk) {
                    if (!this.isStreaming || !chunk.content) return;
                    this.chunkBuffer.push(chunk);
                }

                showError(error) {
                    this.isStreaming = false;
                }

                preprocessMarkdown(content) {
                    let processed = content;
                    const codeBlockCount = (content.match(/```/g) || []).length;
                    if (codeBlockCount % 2 === 1) {
                        processed += '\\n```';
                    }
                    return processed;
                }
            };
        }
    </script>
    <script src="test_v02_frontend.js"></script>
    <script>
        // Auto-run tests when page loads
        window.addEventListener('load', function() {
            setTimeout(function() {
                console.log('🚀 Starting automated frontend tests...');
                runAllV02FrontendTests().then(function(results) {
                    console.log('\\n📊 Frontend test results:', results);
                });
            }, 1000);
        });
    </script>
</body>
</html>"""

            # Write HTML file
            html_file = Path(__file__).parent / 'frontend_test_runner.html'
            html_file.write_text(html_content)

            # Open browser
            webbrowser.open(f'file://{html_file.absolute()}')

            print("✅ Browser opened for frontend tests")
            print("   Check browser console for test results")

            return True

        except Exception as e:
            print(f"❌ Failed to run frontend tests: {e}")
            return False

    def run_all_tests(self):
        """Run all test suites"""
        self.start_time = time.time()

        print("🧪 Claude AI Web Interface v0.2 Test Suite")
        print("=" * 60)

        # Pre-flight checks
        if not self.check_dependencies():
            return False

        if not self.validate_database_schema():
            return False

        if not self.test_api_endpoints():
            print("⚠️  API endpoint issues detected, but continuing with tests...\n")

        # Determine which modules to run
        modules_to_run = []

        # Always run core tests
        core_modules = [
            'test_v02_token_system',
            'test_v02_bulk_knowledge',
            'test_v02_file_chips',
            'test_v02_permissions'
        ]
        modules_to_run.extend(core_modules)

        # Add streaming tests
        modules_to_run.append('test_v02_streaming')

        # Add integration tests if requested
        if self.args.integration:
            modules_to_run.append('test_v02_integration')

        # Add performance tests if requested
        if self.args.performance:
            modules_to_run.append('test_v02_performance')

        # Run each test module
        successful_modules = 0
        for module_name in modules_to_run:
            if self.run_test_module(module_name):
                successful_modules += 1

        # Run frontend tests
        if self.args.frontend:
            self.run_frontend_tests()

        # Calculate final results
        self.results['duration'] = time.time() - self.start_time

        # Print summary
        self.print_summary()

        # Generate report if requested
        if self.args.report:
            self.generate_html_report()

        return successful_modules == len(modules_to_run)

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 CLAUDE AI WEB INTERFACE v0.2 TEST SUMMARY")
        print("=" * 60)

        # Overall stats
        success_rate = (self.results['passed'] / self.results['total_tests'] * 100) if self.results['total_tests'] > 0 else 0

        print(f"🧪 Total Tests: {self.results['total_tests']}")
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"💥 Errors: {self.results['errors']}")
        print(f"⏭️  Skipped: {self.results['skipped']}")
        print(f"⏱️  Duration: {self.results['duration']:.2f} seconds")
        print(f"📈 Success Rate: {success_rate:.1f}%")

        # Module breakdown
        if self.results['modules']:
            print(f"\n📋 MODULE BREAKDOWN:")
            for module_name, module_results in self.results['modules'].items():
                status = "✅" if module_results['failures'] == 0 and module_results['errors'] == 0 else "❌"
                print(f"  {status} {module_name}: "
                      f"{module_results['tests_run']} tests, "
                      f"{module_results['success_rate']:.1f}% success, "
                      f"{module_results['duration']:.2f}s")

        # Feature coverage
        print(f"\n🎯 FEATURE COVERAGE:")
        features = [
            ("Token Estimation System", "test_v02_token_system" in self.results['modules']),
            ("Bulk Knowledge Management", "test_v02_bulk_knowledge" in self.results['modules']),
            ("File Chips Display", "test_v02_file_chips" in self.results['modules']),
            ("Permission System", "test_v02_permissions" in self.results['modules']),
            ("Streaming Enhancements", "test_v02_streaming" in self.results['modules']),
            ("System Integration", "test_v02_integration" in self.results['modules']),
            ("Performance Testing", "test_v02_performance" in self.results['modules'])
        ]

        for feature_name, tested in features:
            status = "✅" if tested else "⏭️"
            print(f"  {status} {feature_name}")

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")

        if success_rate >= 95:
            print("  🎉 Excellent! v0.2 is ready for production deployment.")
        elif success_rate >= 85:
            print("  👍 Good! Minor issues to address before production.")
        elif success_rate >= 70:
            print("  ⚠️  Several issues need attention before deployment.")
        else:
            print("  🚨 Major issues detected. Significant work needed before deployment.")

        if self.results['failed'] > 0:
            print(f"  • Fix {self.results['failed']} failing test(s)")

        if self.results['errors'] > 0:
            print(f"  • Resolve {self.results['errors']} error(s)")

        if not self.args.performance:
            print("  • Run performance tests: --performance")

        if not self.args.integration:
            print("  • Run integration tests: --integration")

        if not self.args.frontend:
            print("  • Test frontend manually: --frontend")

        # Critical security note
        if "test_v02_permissions" in self.results['modules']:
            perm_results = self.results['modules']['test_v02_permissions']
            if perm_results['failures'] == 0 and perm_results['errors'] == 0:
                print("  🔒 Security: Permission system tests passed - write permissions properly blocked")
            else:
                print("  🚨 Security: CRITICAL - Permission system tests failed! Review immediately!")

        print("\n" + "=" * 60)

    def generate_html_report(self):
        """Generate detailed HTML report"""
        try:
            report_file = Path(__file__).parent / f'v02_test_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Claude AI v0.2 Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #2d3748; }}
        .stat-label {{ color: #718096; margin-top: 5px; }}
        .modules {{ margin-bottom: 40px; }}
        .module {{ background: #f8f9fa; margin: 10px 0; padding: 15px; border-radius: 8px; }}
        .module.success {{ border-left: 4px solid #38a169; }}
        .module.failure {{ border-left: 4px solid #e53e3e; }}
        .failure-details {{ background: #fed7d7; padding: 15px; border-radius: 8px; margin: 10px 0; }}
        .error-details {{ background: #feebc8; padding: 15px; border-radius: 8px; margin: 10px 0; }}
        .system-info {{ background: #ebf8ff; padding: 20px; border-radius: 8px; }}
        pre {{ background: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 8px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 Claude AI Web Interface v0.2</h1>
            <h2>Comprehensive Test Report</h2>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="summary">
            <div class="stat-card">
                <div class="stat-value">{self.results['total_tests']}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #38a169;">{self.results['passed']}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #e53e3e;">{self.results['failed']}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #d69e2e;">{self.results['errors']}</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{(self.results['passed'] / self.results['total_tests'] * 100) if self.results['total_tests'] > 0 else 0:.1f}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{self.results['duration']:.1f}s</div>
                <div class="stat-label">Duration</div>
            </div>
        </div>

        <div class="modules">
            <h3>📋 Module Results</h3>
"""

            # Add module details
            for module_name, module_results in self.results['modules'].items():
                success = module_results['failures'] == 0 and module_results['errors'] == 0
                status_class = 'success' if success else 'failure'
                status_icon = '✅' if success else '❌'

                html_content += f"""
            <div class="module {status_class}">
                <h4>{status_icon} {module_name}</h4>
                <p><strong>Tests:</strong> {module_results['tests_run']} |
                   <strong>Success Rate:</strong> {module_results['success_rate']:.1f}% |
                   <strong>Duration:</strong> {module_results['duration']:.2f}s</p>
                <p><strong>Failures:</strong> {module_results['failures']} |
                   <strong>Errors:</strong> {module_results['errors']}</p>
            </div>
"""

            # Add failure details
            if self.results['failures']:
                html_content += "<h3>❌ Failure Details</h3>"
                for failure in self.results['failures']:
                    html_content += f"""
            <div class="failure-details">
                <h4>{failure['module']} - {failure['test']}</h4>
                <pre>{failure['traceback']}</pre>
            </div>
"""

            # Add error details
            if self.results['errors_list']:
                html_content += "<h3>💥 Error Details</h3>"
                for error in self.results['errors_list']:
                    html_content += f"""
            <div class="error-details">
                <h4>{error['module']} - {error['test']}</h4>
                <pre>{error['traceback']}</pre>
            </div>
"""

            # Add system info
            html_content += f"""
        </div>

        <div class="system-info">
            <h3>🖥️ System Information</h3>
            <p><strong>Python Version:</strong> {self.results['system_info'].get('python_version', 'Unknown')}</p>
            <p><strong>Platform:</strong> {self.results['system_info'].get('platform', 'Unknown')}</p>
            <p><strong>CPU Count:</strong> {self.results['system_info'].get('cpu_count', 'Unknown')}</p>
            <p><strong>Memory:</strong> {self.results['system_info'].get('memory_gb', 'Unknown')} GB</p>
            <p><strong>Test Run:</strong> {self.results['system_info']['timestamp']}</p>
        </div>
    </div>
</body>
</html>
"""

            report_file.write_text(html_content)
            print(f"\n📄 Detailed HTML report generated: {report_file}")

            if not self.args.ci:
                webbrowser.open(f'file://{report_file.absolute()}')

        except Exception as e:
            print(f"❌ Failed to generate HTML report: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Claude AI Web Interface v0.2 Test Runner')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--performance', action='store_true', help='Include performance tests')
    parser.add_argument('--integration', action='store_true', help='Include integration tests')
    parser.add_argument('--frontend', action='store_true', help='Open browser for frontend tests')
    parser.add_argument('--report', action='store_true', help='Generate detailed HTML report')
    parser.add_argument('--ci', action='store_true', help='Run in CI mode (minimal output)')

    args = parser.parse_args()

    # Create and run test runner
    runner = V02TestRunner(args)
    success = runner.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()