#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test script to verify Claude Clone setup."""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that all required packages can be imported."""
    print("Testing package imports...")

    packages = {
        'flask': 'Flask web framework',
        'flask_cors': 'Flask CORS support',
        'flask_socketio': 'WebSocket support',
        'anthropic': 'Claude API client',
        'flask_sqlalchemy': 'Database ORM',
        'flask_login': 'Authentication',
        'markdown': 'Markdown parsing',
        'bs4': 'BeautifulSoup HTML parsing'
    }

    failed = []
    for package, description in packages.items():
        try:
            __import__(package)
            print(f"  ✓ {package:20} - {description}")
        except ImportError as e:
            print(f"  ✗ {package:20} - {description} (ERROR: {e})")
            failed.append(package)

    return len(failed) == 0

def test_directories():
    """Test that required directories exist."""
    print("\nTesting directory structure...")

    dirs = [
        'app',
        'config',
        'models',
        'services',
        'static/css',
        'static/js',
        'static/uploads',
        'templates',
        'data'
    ]

    failed = []
    for dir_path in dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"  ✓ {dir_path}")
        else:
            print(f"  ✗ {dir_path} - Creating...")
            path.mkdir(parents=True, exist_ok=True)
            if path.exists():
                print(f"    → Created successfully")
            else:
                failed.append(dir_path)

    return len(failed) == 0

def test_files():
    """Test that required files exist."""
    print("\nTesting required files...")

    files = {
        'app.py': 'Main application',
        'config/config.py': 'Configuration',
        'models/models.py': 'Database models',
        'services/claude_service.py': 'Claude service',
        'templates/index.html': 'Main template',
        'static/css/style.css': 'Styles',
        'static/js/app.js': 'JavaScript app',
        '.env': 'Environment config'
    }

    failed = []
    for file_path, description in files.items():
        path = Path(file_path)
        if path.exists():
            print(f"  ✓ {file_path:30} - {description}")
        else:
            print(f"  ✗ {file_path:30} - {description}")
            failed.append(file_path)

    return len(failed) == 0

def test_env_config():
    """Test environment configuration."""
    print("\nTesting environment configuration...")

    if not Path('.env').exists():
        print("  ✗ .env file not found")
        return False

    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('ANTHROPIC_API_KEY')

    if not api_key:
        print("  ✗ ANTHROPIC_API_KEY not set")
        return False
    elif api_key == 'your_api_key_here':
        print("  ⚠️  ANTHROPIC_API_KEY is still the default value")
        print("     Please edit .env and add your actual API key")
        return False
    else:
        print(f"  ✓ ANTHROPIC_API_KEY is configured ({api_key[:10]}...)")

    return True

def test_obsidian_vaults():
    """Test Obsidian vault accessibility."""
    print("\nTesting Obsidian vault access...")

    vaults = {
        '../Obsidian-Private': 'Private vault',
        '../Obsidian-POA': 'POA vault'
    }

    found = 0
    for vault_path, description in vaults.items():
        path = Path(vault_path)
        if path.exists() and path.is_dir():
            file_count = len(list(path.rglob('*.md')))
            print(f"  ✓ {vault_path:25} - {description} ({file_count} .md files)")
            found += 1
        else:
            print(f"  ⚠️  {vault_path:25} - {description} (not found)")

    return found > 0

def main():
    """Run all tests."""
    print("=" * 60)
    print("Claude Clone Setup Test")
    print("=" * 60)

    tests = [
        ("Package Imports", test_imports),
        ("Directory Structure", test_directories),
        ("Required Files", test_files),
        ("Environment Config", test_env_config),
        ("Obsidian Vaults", test_obsidian_vaults)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{name:25} - {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✅ All tests passed! The application is ready to run.")
        print("\nNext steps:")
        print("1. Edit .env and add your ANTHROPIC_API_KEY")
        print("2. Run: ./run.sh")
        print("3. Open: http://localhost:5000")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        if not results[3][1]:  # Environment config failed
            print("\n📝 To add your API key:")
            print("   nano .env")
            print("   # Replace 'your_api_key_here' with your actual key")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())