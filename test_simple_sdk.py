#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Simple test of Claude Agent SDK."""

import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def test_simple():
    """Test simple query to Claude."""
    print("Testing Claude Agent SDK...")

    # Simple options - no tools, default settings
    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant. Keep responses concise.",
        allowed_tools=[],  # No tools for simplest test
        permission_mode="default"
    )

    response_text = ""
    message_count = 0

    try:
        async for message in query(prompt="What is 2 + 2?", options=options):
            message_count += 1
            print(f"Message {message_count}: {type(message).__name__}")

            if hasattr(message, 'content'):
                print(f"  Has content: {len(message.content)} blocks")
                for i, block in enumerate(message.content):
                    print(f"  Block {i}: type={getattr(block, 'type', 'unknown')}")
                    if hasattr(block, 'type') and block.type == "text":
                        text = block.text if hasattr(block, 'text') else str(block)
                        print(f"    Text: {text[:100]}")
                        response_text += text
            else:
                print(f"  No content attribute")
                print(f"  Message attrs: {dir(message)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    print(f"\nFinal response: {response_text}")
    return response_text

if __name__ == "__main__":
    asyncio.run(test_simple())