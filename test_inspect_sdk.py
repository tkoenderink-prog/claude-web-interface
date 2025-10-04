#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Inspect Claude Agent SDK message structure."""

import asyncio
import json
from claude_agent_sdk import query, ClaudeAgentOptions

async def inspect_messages():
    """Inspect message structure from Claude Agent SDK."""
    print("Inspecting Claude Agent SDK messages...")

    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant.",
        allowed_tools=[],
        permission_mode="default"
    )

    all_messages = []

    try:
        async for message in query(prompt="What is 2 + 2? Respond with just the number.", options=options):
            message_info = {
                "type": type(message).__name__,
                "attributes": list(vars(message).keys()) if hasattr(message, '__dict__') else [],
            }

            # Check for content in different ways
            if hasattr(message, 'content'):
                content = message.content
                if isinstance(content, list):
                    message_info["content_type"] = "list"
                    message_info["content_length"] = len(content)
                    message_info["content_items"] = []
                    for item in content[:3]:  # First 3 items
                        item_info = {
                            "type": type(item).__name__,
                            "attrs": list(vars(item).keys()) if hasattr(item, '__dict__') else []
                        }
                        if hasattr(item, 'text'):
                            item_info["text"] = item.text[:100]
                        message_info["content_items"].append(item_info)
                elif isinstance(content, str):
                    message_info["content_type"] = "string"
                    message_info["content"] = content[:100]
                else:
                    message_info["content_type"] = type(content).__name__

            # Check for result
            if hasattr(message, 'result'):
                message_info["result"] = str(message.result)[:200]

            # Check for data
            if hasattr(message, 'data'):
                message_info["data"] = str(message.data)[:200]

            all_messages.append(message_info)
            print(f"\nMessage: {json.dumps(message_info, indent=2)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    return all_messages

if __name__ == "__main__":
    messages = asyncio.run(inspect_messages())