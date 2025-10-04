#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Conversation export service for Obsidian inbox"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import current_app
from models.models import db, Conversation, Message, ConversationKnowledge

logger = logging.getLogger(__name__)

class ExportService:
    """Handles exporting conversations to Obsidian vaults"""

    def __init__(self):
        self._vault_paths = None

    @property
    def vault_paths(self):
        """Lazy load vault paths when needed"""
        if self._vault_paths is None:
            self._vault_paths = {
                'private': Path(current_app.config.get('OBSIDIAN_PRIVATE_PATH', '')),
                'poa': Path(current_app.config.get('OBSIDIAN_POA_PATH', ''))
            }
        return self._vault_paths

    def export_to_inbox(self, conversation_id: int, vault: str = 'private') -> str:
        """Export conversation to vault's 00-INBOX folder"""
        try:
            # Get conversation
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")

            # Get vault path
            vault_path = self.vault_paths.get(vault)
            if not vault_path or not vault_path.exists():
                raise ValueError(f"Vault '{vault}' not configured or doesn't exist")

            # Generate filename
            title = conversation.auto_title or conversation.title or f"Conversation_{conversation_id}"
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_'))[:50]
            filename = f"[CHAT] {datetime.now().strftime('%Y-%m-%d')}_{safe_title}.md"

            # Build markdown content
            content = self._build_markdown(conversation)

            # Save to inbox
            inbox_path = vault_path / '00-INBOX'
            inbox_path.mkdir(parents=True, exist_ok=True)

            filepath = inbox_path / filename
            filepath.write_text(content, encoding='utf-8')

            logger.info(f"Exported conversation {conversation_id} to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to export conversation: {e}")
            raise

    def _build_markdown(self, conversation: Conversation) -> str:
        """Build markdown content for export"""
        # Get messages
        messages = Message.query.filter_by(
            conversation_id=conversation.id
        ).order_by(Message.created_at).all()

        # Get knowledge files
        knowledge_files = []
        knowledge_links = ConversationKnowledge.query.filter_by(
            conversation_id=conversation.id
        ).all()
        for link in knowledge_links:
            if link.knowledge:
                knowledge_files.append(link.knowledge.file_path)

        # Build frontmatter
        mode_name = conversation.mode.name if conversation.mode else 'General'
        model = conversation.mode.configuration.model if conversation.mode and conversation.mode.configuration else 'claude-3-5-sonnet-20241022'

        # Calculate total tokens
        total_tokens = sum(msg.tokens_used or 0 for msg in messages)

        frontmatter = f"""---
type: conversation
created: {conversation.created_at.isoformat()}Z
mode: {mode_name}
model: {model}
tokens_used: {total_tokens}
knowledge_files:
"""
        for file_path in knowledge_files:
            frontmatter += f'  - "{file_path}"\n'

        frontmatter += """tags:
  - chat-export
  - processed/pending
---

"""

        # Build content
        title = conversation.auto_title or conversation.title or f"Conversation {conversation.id}"
        content = frontmatter
        content += f"# {title}\n\n"
        content += f"## Conversation Details\n"
        content += f"- **Date**: {conversation.created_at.strftime('%B %d, %Y')}\n"
        content += f"- **Mode**: {mode_name}\n"
        content += f"- **Model**: {model.replace('-', ' ').title()}\n"
        content += f"- **Total Tokens**: {total_tokens:,}\n\n"

        # Add knowledge file references
        if knowledge_files:
            content += "## Context Files\n"
            vault_name = 'Private' if 'private' in str(self.vault_paths['private']).lower() else 'POA'
            for file_path in knowledge_files:
                file_name = Path(file_path).stem
                encoded_path = file_path.replace(' ', '%20')
                content += f"- [{file_name}](obsidian://open?vault={vault_name}&file={encoded_path})\n"
            content += "\n"

        # Add messages
        content += "## Messages\n\n"
        for msg in messages:
            if msg.role in ['user', 'assistant']:
                content += f"### {msg.role.title()}\n"
                content += f"{msg.content}\n\n"

        content += "---\n"
        content += "*Exported from Claude Web Interface v0.3.0*\n"

        return content

# Singleton pattern
_export_service = None

def get_export_service():
    """Get singleton export service instance"""
    global _export_service
    if _export_service is None:
        _export_service = ExportService()
    return _export_service
