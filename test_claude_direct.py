#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test Claude service directly to see if it's working"""

import asyncio
import sys
import os

# Add to path
sys.path.insert(0, '.')
os.chdir('/Users/tijlkoenderink/Library/Mobile Documents/iCloud~md~obsidian/Documents/web-interface')

from services.claude_service import ClaudeService
from pathlib import Path

async def test_claude():
    """Test Claude service directly"""

    print("Testing Claude service...")
    print("=" * 60)

    # Initialize service
    claude = ClaudeService(working_directory=Path.cwd())

    # Simple test messages
    messages = [
        {'role': 'user', 'content': 'Can you summarize in one sentence: The sky is blue.'}
    ]

    print("Sending test message to Claude...")
    print("Message:", messages[0]['content'])
    print("\nWaiting for response...")

    response = ""
    try:
        async for chunk in claude.create_message(
            messages=messages,
            system_prompt="You are a helpful assistant. Keep responses very brief.",
            project_knowledge=None,
            stream=True,
            tools=[]
        ):
            response += chunk
            print(f"Chunk received: {chunk[:50]}..." if len(chunk) > 50 else f"Chunk: {chunk}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Full response:", response if response else "NO RESPONSE")
    print("=" * 60)

    return response

if __name__ == "__main__":
    result = asyncio.run(test_claude())

    if result:
        print("\n✅ Claude service is working!")
    else:
        print("\n❌ Claude service is not responding!")
        print("\nPossible issues:")
        print("1. Claude Agent SDK not installed properly")
        print("2. API key not configured")
        print("3. Network/firewall issues")
        print("4. Claude service timeout")