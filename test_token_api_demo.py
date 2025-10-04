#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Demo script showing how to use the Token Estimation API endpoints.

This script demonstrates the API endpoints but requires the web server to be running.
Run this after starting the Flask application with: python app.py
"""

import requests
import json
import tempfile
from pathlib import Path

class TokenAPIDemo:
    """Demonstration of the Token Estimation API endpoints."""

    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()

    def demo_text_estimation_api(self):
        """Demonstrate the /api/tokens/estimate endpoint."""
        print("=" * 60)
        print("DEMO: Text Token Estimation API")
        print("=" * 60)

        # Test different text samples
        test_texts = [
            "Hello, world!",
            "This is a longer text that should have more tokens for demonstration purposes.",
            "Very long text that will help us understand token estimation. " * 20
        ]

        for i, text in enumerate(test_texts):
            try:
                response = self.session.post(
                    f"{self.base_url}/api/tokens/estimate",
                    json={"text": text},
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    result = response.json()
                    estimation = result['estimation']
                    print(f"\nText {i+1}: '{text[:50]}{'...' if len(text) > 50 else ''}'")
                    print(f"  Tokens: {estimation['token_count']}")
                    print(f"  Characters: {estimation['character_count']}")
                    print(f"  Context %: {estimation['context_percentage']:.2f}%")
                    print(f"  Remaining: {estimation['remaining_tokens']:,} tokens")
                else:
                    print(f"  Error {response.status_code}: {response.text}")

            except requests.exceptions.ConnectionError:
                print(f"  ❌ Cannot connect to server at {self.base_url}")
                print("     Please start the Flask server with: python app.py")
                return False
            except Exception as e:
                print(f"  ❌ Error: {e}")

        return True

    def demo_file_estimation_api(self):
        """Demonstrate the /api/tokens/file endpoint."""
        print("\n" + "=" * 60)
        print("DEMO: File Token Estimation API")
        print("=" * 60)

        # Create temporary test files
        with tempfile.TemporaryDirectory() as temp_dir:
            test_files = [
                ("test.txt", "This is a test file for token estimation."),
                ("markdown.md", "# Test Document\n\n**Bold text** and *italic text*."),
                ("large.txt", "Large file content. " * 100)
            ]

            for filename, content in test_files:
                file_path = Path(temp_dir) / filename
                file_path.write_text(content)

                try:
                    response = self.session.post(
                        f"{self.base_url}/api/tokens/file",
                        json={"file_path": str(file_path)},
                        headers={"Content-Type": "application/json"}
                    )

                    if response.status_code == 200:
                        result = response.json()
                        estimation = result['estimation']
                        print(f"\nFile: {filename}")
                        print(f"  Tokens: {estimation['token_count']}")
                        print(f"  File size: {estimation['file_size_bytes']} bytes")
                        print(f"  Context %: {estimation['context_percentage']:.2f}%")
                        print(f"  Cached: {estimation['cached']}")
                    else:
                        print(f"  Error {response.status_code}: {response.text}")

                except Exception as e:
                    print(f"  ❌ Error with {filename}: {e}")

    def demo_cache_management_api(self):
        """Demonstrate cache management endpoints."""
        print("\n" + "=" * 60)
        print("DEMO: Cache Management API")
        print("=" * 60)

        # Get cache stats
        try:
            response = self.session.get(f"{self.base_url}/api/tokens/cache/stats")
            if response.status_code == 200:
                result = response.json()
                stats = result['cache_stats']
                print("Current Cache Statistics:")
                print(f"  Memory cached items: {stats['total_cached_items']}")
                print(f"  Database cached items: {stats.get('database_cached_items', 0)}")
                print(f"  Cache TTL: {stats['cache_ttl_hours']} hours")
                print(f"  Encoding: {stats['encoding']}")
            else:
                print(f"  Error getting cache stats: {response.status_code}")

        except Exception as e:
            print(f"  ❌ Error getting cache stats: {e}")

        # Clean up expired cache
        try:
            response = self.session.post(f"{self.base_url}/api/tokens/cache/cleanup")
            if response.status_code == 200:
                result = response.json()
                print(f"\nCache cleanup: {result['expired_removed']} expired items removed")
            else:
                print(f"  Error cleaning cache: {response.status_code}")

        except Exception as e:
            print(f"  ❌ Error cleaning cache: {e}")

    def run_demo(self):
        """Run the complete API demonstration."""
        print("🚀 Starting Token Estimation API Demo")
        print(f"🌐 Server URL: {self.base_url}")
        print("\nNote: This demo requires authentication. The endpoints will return 401")
        print("unless you're logged in to the web interface or have proper API keys.")

        # Try to connect to server first
        try:
            response = self.session.get(self.base_url)
            if response.status_code == 200:
                print("✅ Server is accessible")
            else:
                print(f"⚠️  Server responded with status {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to server. Please start with: python app.py")
            return

        # Run demos
        if self.demo_text_estimation_api():
            self.demo_file_estimation_api()
            self.demo_cache_management_api()

        print("\n" + "=" * 60)
        print("🎯 API DEMO COMPLETE")
        print("=" * 60)
        print("\n📋 Available API Endpoints:")
        print("  POST /api/tokens/estimate - Estimate tokens for text")
        print("  POST /api/tokens/file - Estimate tokens for file")
        print("  POST /api/tokens/conversation - Estimate conversation tokens")
        print("  GET  /api/tokens/cache/stats - Get cache statistics")
        print("  POST /api/tokens/cache/clear - Clear all cache")
        print("  POST /api/tokens/cache/cleanup - Clean expired cache")

        print("\n📖 Usage Examples:")
        print("  curl -X POST http://localhost:5000/api/tokens/estimate \\")
        print("       -H 'Content-Type: application/json' \\")
        print("       -d '{\"text\": \"Hello, world!\"}'")

        print("\n  curl -X POST http://localhost:5000/api/tokens/file \\")
        print("       -H 'Content-Type: application/json' \\")
        print("       -d '{\"file_path\": \"/path/to/file.txt\"}'")


if __name__ == "__main__":
    demo = TokenAPIDemo()
    demo.run_demo()