#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Claude Agent SDK service for handling AI interactions."""

import os
import json
import asyncio
from typing import Dict, List, Optional, AsyncGenerator, Any
from pathlib import Path
from datetime import datetime
import hashlib

# Import Claude Agent SDK
from claude_agent_sdk import query, ClaudeAgentOptions, ClaudeSDKClient, tool, create_sdk_mcp_server

class ClaudeService:
    """Service for managing Claude AI interactions using the Claude Agent SDK."""

    def __init__(self, working_directory: Optional[Path] = None):
        """Initialize Claude service."""
        self.working_directory = working_directory or Path.cwd()
        # Check if API key is set - if so, unset to use subscription
        if os.getenv('ANTHROPIC_API_KEY'):
            print("Warning: ANTHROPIC_API_KEY is set. This will use API billing instead of subscription.")
            print("To use subscription, unset ANTHROPIC_API_KEY")

    async def create_message(
        self,
        messages: List[Dict],
        system_prompt: Optional[str] = None,
        project_knowledge: Optional[List[str]] = None,
        stream: bool = True,
        tools: Optional[List[str]] = None,
        custom_tools: Optional[List[callable]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Create a message with Claude using the Agent SDK.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: Optional system prompt to guide Claude's behavior
            project_knowledge: Optional list of file contents from Obsidian vault
            stream: Whether to stream the response (currently returns full response)
            tools: Optional list of tool names Claude can use
            custom_tools: Optional list of custom tool functions

        Yields:
            Response text from Claude
        """
        # Build the prompt from messages
        prompt_parts = []

        # Add project knowledge as context if provided
        if project_knowledge:
            knowledge_text = "\n\n---\n\n".join(project_knowledge)
            prompt_parts.append(f"## Project Knowledge\n\n{knowledge_text}\n\n")

        # Convert messages to a single prompt
        for msg in messages:
            if msg['role'] == 'user':
                prompt_parts.append(f"User: {msg['content']}")
            elif msg['role'] == 'assistant':
                prompt_parts.append(f"Assistant: {msg['content']}")

        prompt = "\n\n".join(prompt_parts)

        # Configure options
        options = ClaudeAgentOptions(
            system_prompt=system_prompt or "You are a helpful AI assistant.",
            cwd=str(self.working_directory),
            allowed_tools=tools or [],
            permission_mode="default",  # Use default permission mode
            setting_sources=[]  # Don't load project settings
        )

        # Add custom tools if provided
        if custom_tools:
            mcp_server = create_sdk_mcp_server(custom_tools)
            options.mcp_servers = [mcp_server]

        # Query Claude
        response_text = ""
        async for message in query(prompt=prompt, options=options):
            # Only process AssistantMessage types
            if message.__class__.__name__ == 'AssistantMessage' and hasattr(message, 'content'):
                for block in message.content:
                    # TextBlock has a 'text' attribute
                    if hasattr(block, 'text'):
                        response_text += block.text
                        if stream:
                            yield block.text

        if not stream and response_text:
            yield response_text
        elif not response_text:
            yield ""  # Return empty string if no response

    async def create_agent_session(
        self,
        system_prompt: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None
    ) -> 'ClaudeAgentSession':
        """
        Create a persistent Claude agent session for interactive conversations.

        Args:
            system_prompt: System prompt for the agent
            allowed_tools: List of allowed tool names

        Returns:
            ClaudeAgentSession instance
        """
        return ClaudeAgentSession(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            working_directory=self.working_directory
        )

    def create_custom_tool(
        self,
        name: str,
        description: str,
        handler: callable
    ) -> callable:
        """
        Create a custom tool for Claude to use.

        Args:
            name: Tool name
            description: Tool description
            handler: Async function to handle the tool call

        Returns:
            Decorated tool function
        """
        @tool
        async def custom_tool(**kwargs) -> Any:
            f"""{description}"""
            return await handler(kwargs)

        custom_tool.__name__ = name
        return custom_tool


class ClaudeAgentSession:
    """Persistent Claude agent session for interactive conversations."""

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        working_directory: Optional[Path] = None
    ):
        """Initialize a Claude agent session."""
        self.system_prompt = system_prompt or "You are a helpful AI assistant."
        self.allowed_tools = allowed_tools or []
        self.working_directory = working_directory or Path.cwd()
        self.client = None
        self.conversation_history = []

    async def __aenter__(self):
        """Enter the session context."""
        options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            cwd=str(self.working_directory),
            allowed_tools=self.allowed_tools,
            permission_mode="default",
            setting_sources=[]
        )
        self.client = ClaudeSDKClient(options=options)
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the session context."""
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def send_message(self, message: str) -> str:
        """
        Send a message in the session and get a response.

        Args:
            message: User message to send

        Returns:
            Assistant's response
        """
        if not self.client:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")

        # Add to history
        self.conversation_history.append({"role": "user", "content": message})

        # Query Claude
        response_text = ""
        async for msg in self.client.query(prompt=message):
            # Only process AssistantMessage types
            if msg.__class__.__name__ == 'AssistantMessage' and hasattr(msg, 'content'):
                for block in msg.content:
                    # TextBlock has a 'text' attribute
                    if hasattr(block, 'text'):
                        response_text += block.text

        # Add response to history
        self.conversation_history.append({"role": "assistant", "content": response_text})

        return response_text


class ObsidianKnowledgeService:
    """Service for managing Obsidian vault knowledge integration."""

    def __init__(self, vault_paths: Dict[str, Path]):
        """
        Initialize Obsidian knowledge service.

        Args:
            vault_paths: Dictionary of vault names to paths
        """
        self.vault_paths = vault_paths
        self.cache = {}

    async def get_file_content(self, vault_name: str, file_path: str) -> Optional[str]:
        """
        Get content of a file from Obsidian vault.

        Args:
            vault_name: Name of the vault ('private' or 'poa')
            file_path: Relative path to the file in the vault

        Returns:
            File content as string or None if not found
        """
        if vault_name not in self.vault_paths:
            return None

        full_path = self.vault_paths[vault_name] / file_path

        if not full_path.exists() or not full_path.is_file():
            return None

        try:
            # Try UTF-8 first
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback to Latin-1 which accepts all byte values
            try:
                with open(full_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading file {full_path}: {e}")
                return None
        except Exception as e:
            print(f"Error reading file {full_path}: {e}")
            return None

    async def search_vault(
        self,
        vault_name: str,
        query: str,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search Obsidian vault for relevant files.

        Args:
            vault_name: Name of the vault to search
            query: Search query
            category: Optional category filter (PROJECT, AREA, RESOURCE, ARCHIVE)
            limit: Maximum number of results

        Returns:
            List of matching files with metadata
        """
        if vault_name not in self.vault_paths:
            return []

        vault_path = self.vault_paths[vault_name]
        results = []

        # Define category paths
        category_paths = {
            'PROJECT': '01-PROJECTS',
            'AREA': '02-AREAS',
            'RESOURCE': '03-RESOURCES',
            'ARCHIVE': '04-ARCHIVE'
        }

        search_paths = [vault_path]
        if category and category in category_paths:
            search_paths = [vault_path / category_paths[category]]

        for search_path in search_paths:
            if not search_path.exists():
                continue

            for file_path in search_path.rglob('*.md'):
                try:
                    # Try UTF-8 first
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        # Fallback to Latin-1
                        with open(file_path, 'r', encoding='latin-1') as f:
                            content = f.read()

                    # Simple keyword search (can be enhanced with better search algorithms)
                    if query.lower() in content.lower() or query.lower() in file_path.name.lower():
                        relative_path = file_path.relative_to(vault_path)

                        # Determine category from path
                        file_category = 'INBOX'
                        for cat, cat_path in category_paths.items():
                            if str(relative_path).startswith(cat_path):
                                file_category = cat
                                break

                        results.append({
                            'name': file_path.stem,
                            'path': str(relative_path),
                            'category': file_category,
                            'preview': content[:500],
                            'size': len(content),
                            'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                        })

                        if len(results) >= limit:
                            return results

                except Exception as e:
                    print(f"Error searching file {file_path}: {e}")
                    continue

        return results

    async def get_all_files(
        self,
        vault_name: str,
        category: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Get all files in an Obsidian vault.

        Args:
            vault_name: Name of the vault to search
            category: Optional category filter (PROJECT, AREA, RESOURCE, ARCHIVE)
            limit: Maximum number of results

        Returns:
            List of all files with metadata
        """
        if vault_name not in self.vault_paths:
            return []

        vault_path = self.vault_paths[vault_name]
        results = []

        # Define category paths
        category_paths = {
            'PROJECT': '01-PROJECTS',
            'AREA': '02-AREAS',
            'RESOURCE': '03-RESOURCES',
            'ARCHIVE': '04-ARCHIVE'
        }

        search_paths = [vault_path]
        if category and category in category_paths:
            search_paths = [vault_path / category_paths[category]]

        for search_path in search_paths:
            if not search_path.exists():
                continue

            for file_path in search_path.rglob('*.md'):
                try:
                    relative_path = file_path.relative_to(vault_path)

                    # Skip hidden files and system files
                    if any(part.startswith('.') or part.startswith('_') for part in relative_path.parts):
                        continue

                    # Determine category from path
                    file_category = 'INBOX'
                    for cat, cat_path in category_paths.items():
                        if str(relative_path).startswith(cat_path):
                            file_category = cat
                            break

                    # Get file stats
                    stat = file_path.stat()

                    results.append({
                        'name': file_path.stem,
                        'path': str(relative_path),
                        'category': file_category,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })

                    if len(results) >= limit:
                        return results

                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
                    continue

        return results

    async def get_vault_structure(self, vault_name: str) -> Dict:
        """
        Get the structure of an Obsidian vault.

        Args:
            vault_name: Name of the vault

        Returns:
            Dictionary representing the vault structure
        """
        if vault_name not in self.vault_paths:
            return {}

        vault_path = self.vault_paths[vault_name]

        structure = {
            'name': vault_name,
            'path': str(vault_path),
            'categories': {}
        }

        # Standard PARA categories
        categories = {
            '00-INBOX': 'INBOX',
            '01-PROJECTS': 'PROJECT',
            '02-AREAS': 'AREA',
            '03-RESOURCES': 'RESOURCE',
            '04-ARCHIVE': 'ARCHIVE'
        }

        for cat_path, cat_name in categories.items():
            full_path = vault_path / cat_path
            if full_path.exists() and full_path.is_dir():
                structure['categories'][cat_name] = {
                    'path': cat_path,
                    'file_count': len(list(full_path.rglob('*.md'))),
                    'subdirs': [d.name for d in full_path.iterdir() if d.is_dir()]
                }

        return structure

    def calculate_content_hash(self, content: str) -> str:
        """Calculate SHA256 hash of content for change detection."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()