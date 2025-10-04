#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Database models for Claude Clone application."""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    conversations = db.relationship('Conversation', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    project_knowledge = db.relationship('ProjectKnowledge', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

class Conversation(db.Model):
    """Conversation model to store chat sessions."""
    __tablename__ = 'conversations'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    title = db.Column(db.String(200), default='New Conversation')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    model = db.Column(db.String(50), default='claude-3-5-sonnet-20241022')
    custom_instructions = db.Column(db.Text)
    is_archived = db.Column(db.Boolean, default=False)

    # Token counting
    total_tokens = db.Column(db.Integer)  # Total estimated tokens for this conversation

    # Relationships
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade='all, delete-orphan', order_by='Message.created_at')
    knowledge_links = db.relationship('ConversationKnowledge', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        """Convert conversation to dictionary."""
        return {
            'id': self.id,
            'uuid': self.uuid,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'model': self.model,
            'custom_instructions': self.custom_instructions,
            'is_archived': self.is_archived,
            'total_tokens': self.total_tokens,
            'message_count': self.messages.count()
        }

class Message(db.Model):
    """Message model to store individual messages in conversations."""
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Tool use tracking
    tool_calls = db.Column(db.Text)  # JSON string of tool calls
    tool_results = db.Column(db.Text)  # JSON string of tool results

    # Metadata
    tokens_used = db.Column(db.Integer)
    processing_time_ms = db.Column(db.Integer)
    model_used = db.Column(db.String(50))

    # File attachments
    attachments = db.relationship('FileAttachment', backref='message', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        """Convert message to dictionary."""
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'tool_calls': json.loads(self.tool_calls) if self.tool_calls else None,
            'tool_results': json.loads(self.tool_results) if self.tool_results else None,
            'tokens_used': self.tokens_used,
            'model_used': self.model_used,
            'attachments': [a.to_dict() for a in self.attachments]
        }

class ProjectKnowledge(db.Model):
    """Project Knowledge model to store Obsidian vault references."""
    __tablename__ = 'project_knowledge'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    vault_type = db.Column(db.String(50), nullable=False)  # 'obsidian-private' or 'obsidian-poa'
    file_path = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(50))  # 'PROJECT', 'AREA', 'RESOURCE', 'ARCHIVE'
    content_hash = db.Column(db.String(64))  # SHA256 hash of content for change detection
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    file_metadata = db.Column(db.Text)  # JSON string of additional metadata (renamed from 'metadata')

    # Full-text search content
    content_preview = db.Column(db.Text)  # First 500 chars of content

    # Token counting
    token_count = db.Column(db.Integer)  # Estimated token count for this content

    # Relationships
    conversation_links = db.relationship('ConversationKnowledge', backref='knowledge', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        """Convert project knowledge to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'vault_type': self.vault_type,
            'file_path': self.file_path,
            'category': self.category,
            'last_synced': self.last_synced.isoformat(),
            'is_active': self.is_active,
            'content_preview': self.content_preview,
            'token_count': self.token_count,
            'metadata': json.loads(self.file_metadata) if self.file_metadata else {}
        }

class ConversationKnowledge(db.Model):
    """Link table between conversations and project knowledge."""
    __tablename__ = 'conversation_knowledge'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    knowledge_id = db.Column(db.Integer, db.ForeignKey('project_knowledge.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    added_by_user = db.Column(db.Boolean, default=True)  # False if auto-suggested

class FileAttachment(db.Model):
    """File attachment model for messages."""
    __tablename__ = 'file_attachments'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Token counting
    token_count = db.Column(db.Integer)  # Estimated token count for this file

    def to_dict(self):
        """Convert file attachment to dictionary."""
        return {
            'id': self.id,
            'filename': self.filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'token_count': self.token_count,
            'uploaded_at': self.uploaded_at.isoformat()
        }

class TokenCache(db.Model):
    """Token cache model for storing cached token counts."""
    __tablename__ = 'token_cache'

    id = db.Column(db.Integer, primary_key=True)
    content_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    token_count = db.Column(db.Integer, nullable=False)
    character_count = db.Column(db.Integer, nullable=False)
    encoding_name = db.Column(db.String(50), nullable=False, default='cl100k_base')
    content_type = db.Column(db.String(50), nullable=False)  # 'text', 'file', 'conversation'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)

    # Optional metadata
    source_info = db.Column(db.Text)  # JSON string of source information

    def to_dict(self):
        """Convert token cache to dictionary."""
        return {
            'id': self.id,
            'content_hash': self.content_hash,
            'token_count': self.token_count,
            'character_count': self.character_count,
            'encoding_name': self.encoding_name,
            'content_type': self.content_type,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'source_info': json.loads(self.source_info) if self.source_info else {}
        }

    @classmethod
    def cleanup_expired(cls):
        """Remove expired cache entries."""
        current_time = datetime.utcnow()
        expired_count = cls.query.filter(cls.expires_at <= current_time).count()
        cls.query.filter(cls.expires_at <= current_time).delete()
        return expired_count

class SystemPrompt(db.Model):
    """System prompts and custom instructions."""
    __tablename__ = 'system_prompts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserPermissions(db.Model):
    """User permissions model for controlling Claude tool access."""
    __tablename__ = 'user_permissions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    # Permission flags - CRITICAL: write_files MUST ALWAYS be False
    web_search = db.Column(db.Boolean, default=False, nullable=False)
    vault_search = db.Column(db.Boolean, default=True, nullable=False)
    read_files = db.Column(db.Boolean, default=True, nullable=False)
    write_files = db.Column(db.Boolean, default=False, nullable=False)  # HARDCODED: Always False for safety

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship
    user = db.relationship('User', backref=db.backref('permissions', uselist=False, cascade='all, delete-orphan'))

    def __init__(self, **kwargs):
        """Initialize user permissions with safety check."""
        # CRITICAL SAFETY: Force write_files to False regardless of input
        kwargs['write_files'] = False
        super().__init__(**kwargs)

    def to_dict(self):
        """Convert user permissions to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'web_search': self.web_search,
            'vault_search': self.vault_search,
            'read_files': self.read_files,
            'write_files': self.write_files,  # Always False
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f'<UserPermissions user_id={self.user_id} web={self.web_search} vault={self.vault_search} read={self.read_files} write={self.write_files}>'