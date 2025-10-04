#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test script for Claude Agent SDK integration."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from services.claude_service import ClaudeService, ObsidianKnowledgeService

async def test_basic_query():
    """Test basic Claude query."""
    print("Testing basic Claude Agent SDK query...")

    service = ClaudeService()

    messages = [
        {"role": "user", "content": "What is 2 + 2?"}
    ]

    response = ""
    async for chunk in service.create_message(messages, stream=False):
        response += chunk

    print(f"Response: {response}")
    return response

async def test_with_system_prompt():
    """Test with system prompt."""
    print("\nTesting with system prompt...")

    service = ClaudeService()

    messages = [
        {"role": "user", "content": "Tell me about Python"}
    ]

    system_prompt = "You are a concise Python expert. Keep responses under 50 words."

    response = ""
    async for chunk in service.create_message(messages, system_prompt=system_prompt, stream=False):
        response += chunk

    print(f"Response: {response}")
    return response

async def test_obsidian_service():
    """Test Obsidian knowledge service."""
    print("\nTesting Obsidian knowledge service...")

    # Set up paths (adjust these to your actual paths)
    vault_paths = {
        'private': Path('/Users/tijlkoenderink/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian-Private'),
        'poa': Path('/Users/tijlkoenderink/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian-POA')
    }

    service = ObsidianKnowledgeService(vault_paths)

    # Test vault structure
    structure = await service.get_vault_structure('private')
    print(f"Vault structure: {structure.get('name', 'Unknown')}")
    for category, info in structure.get('categories', {}).items():
        print(f"  - {category}: {info.get('file_count', 0)} files")

    return structure

async def test_session():
    """Test persistent session."""
    print("\nTesting persistent session...")

    service = ClaudeService()

    async with await service.create_agent_session() as session:
        # First message
        response1 = await session.send_message("My name is TestUser")
        print(f"Response 1: {response1}")

        # Second message (should remember context)
        response2 = await session.send_message("What is my name?")
        print(f"Response 2: {response2}")

    return True

async def main():
    """Run all tests."""
    print("=" * 60)
    print("Claude Agent SDK Integration Test")
    print("=" * 60)

    try:
        # Test 1: Basic query
        await test_basic_query()

        # Test 2: With system prompt
        await test_with_system_prompt()

        # Test 3: Obsidian service
        await test_obsidian_service()

        # Test 4: Session (skip if it might take too long)
        # await test_session()

        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())