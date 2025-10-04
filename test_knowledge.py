#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test project knowledge functionality."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.claude_service import ClaudeService, ObsidianKnowledgeService

async def test_with_knowledge():
    """Test Claude with project knowledge."""

    # Initialize services
    claude_service = ClaudeService()
    obsidian_service = ObsidianKnowledgeService({
        'private': Path('/Users/tijlkoenderink/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian-Private'),
        'poa': Path('/Users/tijlkoenderink/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian-POA')
    })

    # Get some sample knowledge files
    print("Searching for knowledge files...")
    results = await obsidian_service.search_vault('private', 'Claude', limit=3)

    project_knowledge = []
    for result in results:
        print(f"Found: {result['name']}")
        content = await obsidian_service.get_file_content('private', result['path'])
        if content:
            project_knowledge.append(f"# {result['name']}\n\n{content[:500]}...")

    if not project_knowledge:
        print("No knowledge files found, using dummy content")
        project_knowledge = [
            "# Test Document 1\nThis is test document 1 about Python programming.",
            "# Test Document 2\nThis is test document 2 about Claude SDK.",
            "# Test Document 3\nThis is test document 3 about Obsidian vaults."
        ]

    print(f"\nUsing {len(project_knowledge)} knowledge items")

    # Test query with knowledge
    messages = [
        {"role": "user", "content": "Can you see the documents I provided? Please summarize what documents you have access to."}
    ]

    print("\nSending query to Claude...")
    response = ""
    chunk_count = 0

    async for chunk in claude_service.create_message(
        messages=messages,
        system_prompt="You are a helpful assistant. When asked about documents, clearly list and describe any project knowledge that has been provided to you.",
        project_knowledge=project_knowledge,
        stream=True
    ):
        response += chunk
        chunk_count += 1
        if chunk_count == 1:
            print("Receiving response...")
        print(chunk, end="", flush=True)

    print(f"\n\nReceived {chunk_count} chunks")
    print(f"Total response length: {len(response)} characters")

    return response

if __name__ == "__main__":
    asyncio.run(test_with_knowledge())