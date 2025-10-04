#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test script for the Token Estimation System."""

import os
import sys
import json
import tempfile
import requests
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import our token service for direct testing
from services.token_service import TokenService, TokenEstimationError


class TokenSystemTester:
    """Comprehensive test suite for the Token Estimation System."""

    def __init__(self, base_url: str = "http://localhost:5000"):
        """Initialize the tester with the base URL of the web interface."""
        self.base_url = base_url
        self.token_service = TokenService()
        self.session = requests.Session()

        # Test data
        self.test_texts = [
            "Hello, world!",
            "This is a short test message for token estimation.",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 10,
            "A very long text that should use significantly more tokens. " * 100,
            "",  # Empty string
            "🚀 Testing Unicode and emojis: 你好世界 🌍",
            "Mixed content with\nnewlines\tand\ttabs and special chars: @#$%^&*()",
        ]

    def run_all_tests(self):
        """Run all tests and report results."""
        print("=" * 60)
        print("COMPREHENSIVE TOKEN ESTIMATION SYSTEM TEST")
        print("=" * 60)

        results = {}

        # Test 1: Direct service testing
        print("\n1. TESTING TOKEN SERVICE DIRECTLY")
        print("-" * 40)
        results['service_tests'] = self.test_token_service_direct()

        # Test 2: File token estimation
        print("\n2. TESTING FILE TOKEN ESTIMATION")
        print("-" * 40)
        results['file_tests'] = self.test_file_token_estimation()

        # Test 3: Conversation token estimation
        print("\n3. TESTING CONVERSATION TOKEN ESTIMATION")
        print("-" * 40)
        results['conversation_tests'] = self.test_conversation_token_estimation()

        # Test 4: Cache functionality
        print("\n4. TESTING CACHE FUNCTIONALITY")
        print("-" * 40)
        results['cache_tests'] = self.test_cache_functionality()

        # Test 5: API endpoints (if server is running)
        print("\n5. TESTING API ENDPOINTS")
        print("-" * 40)
        results['api_tests'] = self.test_api_endpoints()

        # Test 6: Error handling
        print("\n6. TESTING ERROR HANDLING")
        print("-" * 40)
        results['error_tests'] = self.test_error_handling()

        # Summary
        self.print_test_summary(results)

        return results

    def test_token_service_direct(self):
        """Test the token service directly."""
        results = {}

        for i, text in enumerate(self.test_texts):
            try:
                result = self.token_service.estimate_text_tokens(text)
                results[f'text_{i}'] = {
                    'text': text[:50] + ('...' if len(text) > 50 else ''),
                    'success': True,
                    'tokens': result['token_count'],
                    'characters': result['character_count'],
                    'context_percentage': result['context_percentage']
                }
                print(f"  ✓ Text {i}: {result['token_count']} tokens, {result['context_percentage']:.2f}% of context")

            except Exception as e:
                results[f'text_{i}'] = {
                    'text': text[:50] + ('...' if len(text) > 50 else ''),
                    'success': False,
                    'error': str(e)
                }
                print(f"  ✗ Text {i}: Failed - {e}")

        return results

    def test_file_token_estimation(self):
        """Test file token estimation with temporary files."""
        results = {}

        # Create temporary files with different content
        test_files = [
            ("simple.txt", "This is a simple test file with basic content."),
            ("markdown.md", "# Test Document\n\nThis is a **markdown** file with *formatting*."),
            ("large.txt", "Large content test. " * 1000),
            ("unicode.txt", "Unicode test: 你好世界 🌍 ñáéíóú αβγδε"),
            ("empty.txt", ""),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            for filename, content in test_files:
                file_path = Path(temp_dir) / filename
                file_path.write_text(content, encoding='utf-8')

                try:
                    result = self.token_service.estimate_file_tokens(file_path)
                    results[filename] = {
                        'success': True,
                        'tokens': result['token_count'],
                        'file_size': result['file_size_bytes'],
                        'cached': result['cached']
                    }
                    print(f"  ✓ {filename}: {result['token_count']} tokens ({result['file_size_bytes']} bytes)")

                    # Test caching by calling again
                    result2 = self.token_service.estimate_file_tokens(file_path)
                    if result2['cached']:
                        print(f"    ✓ Cache working: second call used cache")
                    else:
                        print(f"    ? Cache status: {result2['cached']}")

                except Exception as e:
                    results[filename] = {
                        'success': False,
                        'error': str(e)
                    }
                    print(f"  ✗ {filename}: Failed - {e}")

        return results

    def test_conversation_token_estimation(self):
        """Test conversation token estimation."""
        results = {}

        # Test conversation scenarios
        test_conversations = [
            {
                'name': 'simple_chat',
                'messages': [
                    {'role': 'user', 'content': 'Hello, how are you?'},
                    {'role': 'assistant', 'content': 'I am doing well, thank you! How can I help you today?'}
                ],
                'system_prompt': None,
                'project_knowledge': None
            },
            {
                'name': 'complex_chat',
                'messages': [
                    {'role': 'user', 'content': 'Can you help me write a Python function?'},
                    {'role': 'assistant', 'content': 'Certainly! What kind of function would you like to create?'},
                    {'role': 'user', 'content': 'A function that calculates the factorial of a number recursively.'}
                ],
                'system_prompt': 'You are a helpful Python programming assistant.',
                'project_knowledge': ['# Python Best Practices\n\nAlways use type hints and docstrings.']
            },
            {
                'name': 'empty_conversation',
                'messages': [],
                'system_prompt': None,
                'project_knowledge': None
            }
        ]

        for conv in test_conversations:
            try:
                result = self.token_service.estimate_conversation_tokens(
                    messages=conv['messages'],
                    system_prompt=conv['system_prompt'],
                    project_knowledge=conv['project_knowledge']
                )

                results[conv['name']] = {
                    'success': True,
                    'total_tokens': result['total_tokens'],
                    'context_percentage': result['context_percentage'],
                    'breakdown': result['breakdown'],
                    'is_over_limit': result['is_over_limit']
                }

                print(f"  ✓ {conv['name']}: {result['total_tokens']} total tokens")
                print(f"    - Messages: {result['breakdown']['messages_tokens']} tokens")
                print(f"    - System: {result['breakdown']['system_prompt_tokens']} tokens")
                print(f"    - Knowledge: {result['breakdown']['project_knowledge_tokens']} tokens")

            except Exception as e:
                results[conv['name']] = {
                    'success': False,
                    'error': str(e)
                }
                print(f"  ✗ {conv['name']}: Failed - {e}")

        return results

    def test_cache_functionality(self):
        """Test cache functionality."""
        results = {}

        # Test memory cache
        try:
            # Clear cache first
            cleared = self.token_service.clear_cache()
            print(f"  ✓ Cleared {cleared} cached items")

            # Test text that should be cached
            test_text = "This text will be used to test caching functionality."

            # First call - should not be cached
            result1 = self.token_service.estimate_text_tokens(test_text)

            # Second call - should use cache (though we can't directly verify this in the current implementation)
            result2 = self.token_service.estimate_text_tokens(test_text)

            if result1['token_count'] == result2['token_count']:
                print(f"  ✓ Consistent results: {result1['token_count']} tokens")
                results['consistency'] = True
            else:
                print(f"  ✗ Inconsistent results: {result1['token_count']} vs {result2['token_count']}")
                results['consistency'] = False

            # Test cache stats
            stats = self.token_service.get_cache_stats()
            print(f"  ✓ Cache stats: {stats['total_cached_items']} items, TTL: {stats['cache_ttl_hours']}h")
            results['stats'] = stats

        except Exception as e:
            results['cache_error'] = str(e)
            print(f"  ✗ Cache test failed: {e}")

        return results

    def test_api_endpoints(self):
        """Test API endpoints if server is running."""
        results = {}

        try:
            # Test if server is running
            response = self.session.get(f"{self.base_url}/")
            if response.status_code != 200:
                print(f"  ⚠ Server not accessible at {self.base_url}")
                return {'server_unavailable': True}

            # Note: For a full test, we would need to handle authentication
            # This is a basic connectivity test
            print(f"  ✓ Server is accessible at {self.base_url}")
            results['server_accessible'] = True

            # Test endpoints would require authentication setup
            print(f"  ℹ API endpoint testing requires authentication setup")
            results['auth_required'] = True

        except requests.exceptions.ConnectionError:
            print(f"  ⚠ Cannot connect to server at {self.base_url}")
            results['connection_error'] = True
        except Exception as e:
            print(f"  ✗ API test error: {e}")
            results['error'] = str(e)

        return results

    def test_error_handling(self):
        """Test error handling scenarios."""
        results = {}

        # Test invalid inputs
        error_tests = [
            ('invalid_type', lambda: self.token_service.estimate_text_tokens(123)),
            ('none_input', lambda: self.token_service.estimate_text_tokens(None)),
            ('nonexistent_file', lambda: self.token_service.estimate_file_tokens('/nonexistent/file.txt')),
            ('invalid_conversation', lambda: self.token_service.estimate_conversation_tokens([{'invalid': 'data'}]))
        ]

        for test_name, test_func in error_tests:
            try:
                test_func()
                results[test_name] = {'success': False, 'error': 'No exception raised'}
                print(f"  ✗ {test_name}: Expected exception but none was raised")
            except TokenEstimationError as e:
                results[test_name] = {'success': True, 'error_type': 'TokenEstimationError'}
                print(f"  ✓ {test_name}: Correctly raised TokenEstimationError")
            except Exception as e:
                results[test_name] = {'success': True, 'error_type': type(e).__name__}
                print(f"  ✓ {test_name}: Raised {type(e).__name__}")

        return results

    def print_test_summary(self, results):
        """Print a summary of test results."""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        total_tests = 0
        passed_tests = 0

        for category, tests in results.items():
            if isinstance(tests, dict):
                category_tests = sum(1 for test in tests.values() if isinstance(test, dict))
                category_passed = sum(1 for test in tests.values()
                                    if isinstance(test, dict) and test.get('success', False))

                total_tests += category_tests
                passed_tests += category_passed

                print(f"{category.upper()}: {category_passed}/{category_tests} passed")

        print(f"\nOVERALL: {passed_tests}/{total_tests} tests passed")

        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed")

        print("\nRECOMMENDATIONS:")
        print("- Install tiktoken if not already installed: pip install tiktoken")
        print("- Start the web server to test API endpoints")
        print("- Check logs for any warnings about token estimation failures")


def main():
    """Run the token system tests."""
    tester = TokenSystemTester()

    # Check if tiktoken is available
    try:
        import tiktoken
        print("✓ tiktoken library is available")
    except ImportError:
        print("✗ tiktoken library not found - please install with: pip install tiktoken")
        return

    # Run tests
    results = tester.run_all_tests()

    # Save results to file
    results_file = Path(__file__).parent / "token_test_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nDetailed results saved to: {results_file}")


if __name__ == "__main__":
    main()