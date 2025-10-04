#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Download service for exporting conversations in multiple formats"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
import json
import base64
from io import BytesIO
from pathlib import Path

from flask import current_app
from models.models import db, Conversation, Message

logger = logging.getLogger(__name__)

class DownloadService:
    """Handles downloading conversations in various formats"""

    def __init__(self):
        self.formats = ['json', 'markdown', 'pdf']

    def export_conversation(self, conversation_id: int, format: str = 'markdown') -> Dict[str, Any]:
        """Export a conversation in the specified format"""
        try:
            # Get conversation with all messages
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")

            # Get ALL messages, not just visible ones
            messages = Message.query.filter_by(
                conversation_id=conversation.id
            ).order_by(Message.created_at).all()

            if format == 'json':
                return self._export_as_json(conversation, messages)
            elif format == 'markdown':
                return self._export_as_markdown(conversation, messages)
            elif format == 'pdf':
                return self._export_as_pdf(conversation, messages)
            else:
                raise ValueError(f"Unsupported format: {format}")

        except Exception as e:
            logger.error(f"Failed to export conversation: {e}")
            raise

    def _export_as_json(self, conversation: Conversation, messages: list) -> Dict[str, Any]:
        """Export as JSON format"""
        export_data = {
            'title': conversation.title or f'Conversation {conversation.id}',
            'created_at': conversation.created_at.isoformat() if conversation.created_at else None,
            'updated_at': conversation.updated_at.isoformat() if conversation.updated_at else None,
            'model': conversation.model or 'claude-3-5-sonnet-20241022',
            'mode': conversation.mode.name if conversation.mode else 'General',
            'total_tokens': conversation.total_tokens or 0,
            'messages': []
        }

        for msg in messages:
            export_data['messages'].append({
                'role': msg.role,
                'content': msg.content,
                'created_at': msg.created_at.isoformat() if msg.created_at else None,
                'token_count': msg.token_count or 0
            })

        content = json.dumps(export_data, indent=2, ensure_ascii=False)
        filename = f"{self._safe_filename(conversation.title)}.json"

        return {
            'content': content,
            'filename': filename,
            'mime_type': 'application/json'
        }

    def _export_as_markdown(self, conversation: Conversation, messages: list) -> Dict[str, Any]:
        """Export as Markdown format"""
        title = conversation.title or f'Conversation {conversation.id}'

        # Build markdown content
        lines = []

        # Add title
        lines.append(f"# {title}")
        lines.append("")

        # Add metadata
        lines.append("## Metadata")
        lines.append(f"- **Date Created**: {conversation.created_at.strftime('%B %d, %Y at %I:%M %p') if conversation.created_at else 'Unknown'}")
        lines.append(f"- **Last Updated**: {conversation.updated_at.strftime('%B %d, %Y at %I:%M %p') if conversation.updated_at else 'Unknown'}")
        lines.append(f"- **Model**: {conversation.model or 'claude-3-5-sonnet-20241022'}")
        lines.append(f"- **Mode**: {conversation.mode.name if conversation.mode else 'General'}")
        lines.append(f"- **Total Tokens**: {conversation.total_tokens or 0:,}")
        lines.append(f"- **Total Messages**: {len(messages)}")
        lines.append("")

        # Add messages
        lines.append("## Conversation")
        lines.append("")

        for i, msg in enumerate(messages, 1):
            # Add role header
            if msg.role == 'user':
                lines.append(f"### 👤 User (Message {i})")
            elif msg.role == 'assistant':
                lines.append(f"### 🤖 Assistant (Message {i})")
            else:
                lines.append(f"### 📋 {msg.role.title()} (Message {i})")

            # Add timestamp
            if msg.created_at:
                lines.append(f"*{msg.created_at.strftime('%I:%M %p')}*")
                lines.append("")

            # Add content
            # Ensure code blocks are properly formatted
            content = msg.content
            if '```' in content:
                # Already has code blocks, just add it
                lines.append(content)
            else:
                # Regular content
                lines.append(content)

            lines.append("")
            lines.append("---")
            lines.append("")

        # Add footer
        lines.append("## Export Information")
        lines.append(f"- Exported on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        lines.append(f"- Exported from: Claude Web Interface v0.3.0")
        lines.append(f"- Total characters: {sum(len(msg.content) for msg in messages):,}")

        content = '\n'.join(lines)
        filename = f"{self._safe_filename(title)}.md"

        return {
            'content': content,
            'filename': filename,
            'mime_type': 'text/markdown'
        }

    def _export_as_pdf(self, conversation: Conversation, messages: list) -> Dict[str, Any]:
        """Export as PDF format (requires additional library)"""
        try:
            # Try to import required libraries
            import markdown2
            from weasyprint import HTML, CSS

            # First get markdown content
            md_export = self._export_as_markdown(conversation, messages)
            markdown_content = md_export['content']

            # Convert markdown to HTML
            html_content = markdown2.markdown(
                markdown_content,
                extras=['fenced-code-blocks', 'tables', 'break-on-newline']
            )

            # Add CSS styling for PDF
            css = CSS(string='''
                @page {
                    size: A4;
                    margin: 2cm;
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 100%;
                }
                h1 {
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                }
                h2 {
                    color: #34495e;
                    margin-top: 30px;
                }
                h3 {
                    color: #7f8c8d;
                    margin-top: 20px;
                }
                code {
                    background-color: #f4f4f4;
                    padding: 2px 4px;
                    border-radius: 3px;
                }
                pre {
                    background-color: #f8f8f8;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 10px;
                    overflow-x: auto;
                }
                blockquote {
                    border-left: 4px solid #3498db;
                    padding-left: 15px;
                    color: #666;
                }
                hr {
                    border: none;
                    border-top: 1px solid #ddd;
                    margin: 20px 0;
                }
            ''')

            # Generate PDF
            pdf_buffer = BytesIO()
            HTML(string=f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>{conversation.title or "Conversation"}</title>
                </head>
                <body>
                    {html_content}
                </body>
                </html>
            ''').write_pdf(pdf_buffer, stylesheets=[css])

            # Encode PDF as base64
            pdf_buffer.seek(0)
            pdf_base64 = base64.b64encode(pdf_buffer.read()).decode('utf-8')

            filename = f"{self._safe_filename(conversation.title)}.pdf"

            return {
                'content': pdf_base64,
                'filename': filename,
                'mime_type': 'application/pdf',
                'is_base64': True
            }

        except ImportError as e:
            # Fallback: return markdown with instructions
            logger.warning(f"PDF export not available: {e}")

            # Return markdown instead with a note
            md_export = self._export_as_markdown(conversation, messages)
            md_export['error'] = 'PDF export requires additional libraries. Exported as Markdown instead.'
            md_export['missing_libraries'] = ['markdown2', 'weasyprint']
            return md_export

    def _safe_filename(self, title: Optional[str]) -> str:
        """Generate a safe filename from title"""
        if not title:
            title = f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Remove invalid characters
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_'))[:50]

        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')

        return f"{safe_title.strip()}_{timestamp}"

# Singleton pattern
_download_service = None

def get_download_service():
    """Get singleton download service instance"""
    global _download_service
    if _download_service is None:
        _download_service = DownloadService()
    return _download_service