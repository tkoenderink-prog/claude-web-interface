# Web Interface v0.3.0 - Complete Implementation Specification

## Executive Summary

Version 0.3.0 transforms the Claude AI Web Interface from a desktop-only chat interface into a fully responsive, mode-aware conversation platform that seamlessly integrates with the Obsidian vault ecosystem. This document provides **complete implementation specifications** with zero ambiguity for rapid development using Claude Agent SDK subagents.

## Current System Context (v0.2.0 Foundation)

### Existing Architecture
```
web-interface/
├── app.py                    # Main Flask application (1,150 lines)
├── models/
│   └── models.py            # SQLAlchemy models with existing tables
├── services/
│   ├── claude_service.py    # Claude Agent SDK integration
│   ├── token_service.py     # Token estimation with caching
│   ├── permission_service.py # Permission management (write disabled)
│   └── streaming_service.py # WebSocket streaming
├── templates/
│   ├── base.html            # Base template with common resources
│   ├── index.html           # Main chat interface
│   └── settings.html        # Settings page
├── static/
│   ├── css/style.css        # Main styles (1,800 lines)
│   └── js/app.js            # Frontend logic (2,500 lines)
└── data/
    └── claude.db            # SQLite database
```

### Existing Database Tables (DO NOT MODIFY)
- `users` - User authentication
- `conversations` - Conversation storage
- `messages` - Message history
- `project_knowledge` - Knowledge file tracking
- `conversation_knowledge` - Knowledge-conversation links
- `file_attachments` - Uploaded files
- `token_cache` - Token count caching
- `user_permissions` - Permission toggles

### Existing Services (REUSE THESE)
- **ClaudeService**: Handles Claude Agent SDK communication
- **TokenService**: Estimates tokens with caching (USE THIS for mode token counting)
- **PermissionManager**: Security layer (DO NOT MODIFY)
- **StreamingService**: WebSocket management (EXTEND for mobile)
- **ObsidianKnowledgeService**: Vault file access (USE for exports)

---

## Subagent Implementation Strategy

### Task Distribution for Rapid Development

**Subagent 1: Database & Backend** (Python Expert)
- Create migration script for new tables
- Implement Mode API endpoints
- Extend conversation export logic
- Integrate with existing services

**Subagent 2: Frontend Mobile** (JavaScript/CSS Expert)
- Implement responsive layout
- Create hamburger menu system
- Handle touch interactions
- Viewport and keyboard management

**Subagent 3: Mode System** (Full-Stack)
- Build mode management UI
- Implement mode selection logic
- Token counting integration
- System prompt hierarchy

**Subagent 4: Testing & Validation** (QA Expert)
- Create comprehensive test suite
- Mobile device testing
- API endpoint validation
- Export format verification

### Parallel Development Approach
1. Subagents 1 & 2 work simultaneously on backend/frontend
2. Subagent 3 builds mode system after database ready
3. Subagent 4 validates throughout process

---

## Implementation Specifications

### STEP 1: Database Migration

#### File: `web-interface/migrations/v030_migration.py`
```python
#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Migration script for v0.3.0 - RUN THIS FIRST"""

import sqlite3
from datetime import datetime
from pathlib import Path

def migrate_database():
    db_path = Path(__file__).parent.parent / 'data' / 'claude.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")

        # Create conversation_modes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_modes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                icon VARCHAR(50) DEFAULT '💬',
                is_default BOOLEAN DEFAULT FALSE,
                is_deleted BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create mode_configuration table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mode_configuration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode_id INTEGER NOT NULL,
                model VARCHAR(50) DEFAULT 'claude-3-5-sonnet-20241022',
                temperature FLOAT DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 4096,
                system_prompt TEXT,
                system_prompt_tokens INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mode_id) REFERENCES conversation_modes(id)
            )
        """)

        # Create mode_knowledge_files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mode_knowledge_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                vault VARCHAR(50) DEFAULT 'private',
                tokens INTEGER DEFAULT 0,
                auto_include BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mode_id) REFERENCES conversation_modes(id)
            )
        """)

        # Add columns to conversations table
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'mode_id' not in columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN mode_id INTEGER")
        if 'auto_title' not in columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN auto_title VARCHAR(255)")
        if 'exported_at' not in columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN exported_at TIMESTAMP")

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mode_conversation ON conversations(mode_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mode_config ON mode_configuration(mode_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mode_knowledge ON mode_knowledge_files(mode_id)")

        # Insert default "General" mode
        cursor.execute("""
            INSERT OR IGNORE INTO conversation_modes (name, description, icon, is_default)
            VALUES ('General', 'General purpose assistant', '💬', TRUE)
        """)

        # Get the General mode ID
        cursor.execute("SELECT id FROM conversation_modes WHERE name = 'General'")
        general_mode_id = cursor.fetchone()[0]

        # Insert configuration for General mode
        cursor.execute("""
            INSERT OR IGNORE INTO mode_configuration (mode_id, model, system_prompt, system_prompt_tokens)
            VALUES (?, 'claude-3-5-sonnet-20241022', 'You are a helpful assistant.', 5)
        """, (general_mode_id,))

        # Update existing conversations to use General mode
        cursor.execute("UPDATE conversations SET mode_id = ? WHERE mode_id IS NULL", (general_mode_id,))

        # Commit transaction
        cursor.execute("COMMIT")
        print("✅ Database migration completed successfully")

    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
```

### STEP 2: Update Models

#### File: `web-interface/models/models.py`
**ADD to existing file (DO NOT remove existing models):**
```python
# Add these imports at the top
from datetime import datetime

# Add these models at the end of file
class ConversationMode(db.Model):
    """Conversation modes with configurations"""
    __tablename__ = 'conversation_modes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50), default='💬')
    is_default = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    configuration = db.relationship('ModeConfiguration', backref='mode', uselist=False, cascade='all, delete-orphan')
    knowledge_files = db.relationship('ModeKnowledgeFile', backref='mode', cascade='all, delete-orphan')
    conversations = db.relationship('Conversation', backref='mode')

class ModeConfiguration(db.Model):
    """Configuration settings for each mode"""
    __tablename__ = 'mode_configuration'

    id = db.Column(db.Integer, primary_key=True)
    mode_id = db.Column(db.Integer, db.ForeignKey('conversation_modes.id'), nullable=False)
    model = db.Column(db.String(50), default='claude-3-5-sonnet-20241022')
    temperature = db.Column(db.Float, default=0.7)
    max_tokens = db.Column(db.Integer, default=4096)
    system_prompt = db.Column(db.Text)
    system_prompt_tokens = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ModeKnowledgeFile(db.Model):
    """Knowledge files auto-included for modes"""
    __tablename__ = 'mode_knowledge_files'

    id = db.Column(db.Integer, primary_key=True)
    mode_id = db.Column(db.Integer, db.ForeignKey('conversation_modes.id'), nullable=False)
    file_path = db.Column(db.Text, nullable=False)
    vault = db.Column(db.String(50), default='private')
    tokens = db.Column(db.Integer, default=0)
    auto_include = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Update Conversation model (ADD these lines to existing model)
# In the Conversation class, add these columns:
# mode_id = db.Column(db.Integer, db.ForeignKey('conversation_modes.id'))
# auto_title = db.Column(db.String(255))
# exported_at = db.Column(db.DateTime)
```

### STEP 3: Mode Service

#### File: `web-interface/services/mode_service.py` (NEW FILE)
```python
#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Conversation Mode management service"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from flask import current_app

from models.models import db, ConversationMode, ModeConfiguration, ModeKnowledgeFile
from services.token_service import get_token_service

logger = logging.getLogger(__name__)

class ModeService:
    """Handles all mode-related operations"""

    def __init__(self):
        self.token_service = get_token_service()
        self._cache = {}  # Simple mode cache

    def get_all_modes(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Get all conversation modes"""
        query = ConversationMode.query
        if not include_deleted:
            query = query.filter_by(is_deleted=False)

        modes = query.order_by(ConversationMode.is_default.desc(), ConversationMode.name).all()

        return [{
            'id': mode.id,
            'name': mode.name,
            'description': mode.description,
            'icon': mode.icon,
            'is_default': mode.is_default,
            'model': mode.configuration.model if mode.configuration else 'claude-3-5-sonnet-20241022',
            'knowledge_files_count': len(mode.knowledge_files),
            'system_tokens': mode.configuration.system_prompt_tokens if mode.configuration else 0
        } for mode in modes]

    def get_mode_details(self, mode_id: int) -> Optional[Dict[str, Any]]:
        """Get complete mode details including configuration"""
        mode = ConversationMode.query.get(mode_id)
        if not mode or mode.is_deleted:
            return None

        # Calculate total tokens
        total_tokens = 0
        if mode.configuration:
            total_tokens += mode.configuration.system_prompt_tokens

        knowledge_files = []
        for kf in mode.knowledge_files:
            if kf.auto_include:
                total_tokens += kf.tokens
                knowledge_files.append({
                    'id': kf.id,
                    'file_path': kf.file_path,
                    'vault': kf.vault,
                    'tokens': kf.tokens,
                    'auto_include': kf.auto_include
                })

        return {
            'id': mode.id,
            'name': mode.name,
            'description': mode.description,
            'icon': mode.icon,
            'is_default': mode.is_default,
            'configuration': {
                'model': mode.configuration.model if mode.configuration else 'claude-3-5-sonnet-20241022',
                'temperature': mode.configuration.temperature if mode.configuration else 0.7,
                'max_tokens': mode.configuration.max_tokens if mode.configuration else 4096,
                'system_prompt': mode.configuration.system_prompt if mode.configuration else '',
                'system_prompt_tokens': mode.configuration.system_prompt_tokens if mode.configuration else 0
            },
            'knowledge_files': knowledge_files,
            'total_system_tokens': total_tokens
        }

    def create_mode(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new conversation mode"""
        try:
            # Validate name uniqueness
            existing = ConversationMode.query.filter_by(name=data['name']).first()
            if existing:
                raise ValueError(f"Mode with name '{data['name']}' already exists")

            # Create mode
            mode = ConversationMode(
                name=data['name'],
                description=data.get('description', ''),
                icon=data.get('icon', '💬')
            )
            db.session.add(mode)
            db.session.flush()  # Get the ID

            # Create configuration
            system_prompt = data.get('configuration', {}).get('system_prompt', '')
            system_tokens = self.token_service.estimate_tokens(system_prompt)

            config = ModeConfiguration(
                mode_id=mode.id,
                model=data.get('configuration', {}).get('model', 'claude-3-5-sonnet-20241022'),
                temperature=data.get('configuration', {}).get('temperature', 0.7),
                max_tokens=data.get('configuration', {}).get('max_tokens', 4096),
                system_prompt=system_prompt,
                system_prompt_tokens=system_tokens
            )
            db.session.add(config)

            # Add knowledge files
            for kf_data in data.get('knowledge_files', []):
                tokens = self.token_service.estimate_file_tokens(kf_data['file_path'])
                kf = ModeKnowledgeFile(
                    mode_id=mode.id,
                    file_path=kf_data['file_path'],
                    vault=kf_data.get('vault', 'private'),
                    tokens=tokens,
                    auto_include=kf_data.get('auto_include', True)
                )
                db.session.add(kf)

            db.session.commit()

            return {'id': mode.id, 'success': True}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create mode: {e}")
            raise

    def update_mode(self, mode_id: int, data: Dict[str, Any]) -> bool:
        """Update an existing mode"""
        try:
            mode = ConversationMode.query.get(mode_id)
            if not mode or mode.is_deleted:
                raise ValueError(f"Mode {mode_id} not found")

            # Don't allow editing default mode name
            if mode.is_default and 'name' in data and data['name'] != mode.name:
                raise ValueError("Cannot rename the default mode")

            # Update mode fields
            if 'name' in data:
                mode.name = data['name']
            if 'description' in data:
                mode.description = data['description']
            if 'icon' in data:
                mode.icon = data['icon']

            mode.updated_at = datetime.utcnow()

            # Update configuration
            if 'configuration' in data:
                config = mode.configuration
                if not config:
                    config = ModeConfiguration(mode_id=mode.id)
                    db.session.add(config)

                cfg_data = data['configuration']
                if 'model' in cfg_data:
                    config.model = cfg_data['model']
                if 'temperature' in cfg_data:
                    config.temperature = cfg_data['temperature']
                if 'max_tokens' in cfg_data:
                    config.max_tokens = cfg_data['max_tokens']
                if 'system_prompt' in cfg_data:
                    config.system_prompt = cfg_data['system_prompt']
                    config.system_prompt_tokens = self.token_service.estimate_tokens(cfg_data['system_prompt'])

            # Update knowledge files (replace all)
            if 'knowledge_files' in data:
                # Remove existing
                ModeKnowledgeFile.query.filter_by(mode_id=mode.id).delete()

                # Add new ones
                for kf_data in data['knowledge_files']:
                    tokens = self.token_service.estimate_file_tokens(kf_data['file_path'])
                    kf = ModeKnowledgeFile(
                        mode_id=mode.id,
                        file_path=kf_data['file_path'],
                        vault=kf_data.get('vault', 'private'),
                        tokens=tokens,
                        auto_include=kf_data.get('auto_include', True)
                    )
                    db.session.add(kf)

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update mode: {e}")
            raise

    def delete_mode(self, mode_id: int) -> bool:
        """Soft delete a mode"""
        try:
            mode = ConversationMode.query.get(mode_id)
            if not mode:
                raise ValueError(f"Mode {mode_id} not found")

            if mode.is_default:
                raise ValueError("Cannot delete the default mode")

            # Soft delete
            mode.is_deleted = True
            mode.updated_at = datetime.utcnow()

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete mode: {e}")
            raise

    def duplicate_mode(self, mode_id: int) -> Dict[str, Any]:
        """Create a copy of an existing mode"""
        try:
            original = self.get_mode_details(mode_id)
            if not original:
                raise ValueError(f"Mode {mode_id} not found")

            # Create new mode with "Copy of" prefix
            copy_name = f"Copy of {original['name']}"
            counter = 1
            while ConversationMode.query.filter_by(name=copy_name).first():
                counter += 1
                copy_name = f"Copy of {original['name']} ({counter})"

            new_data = {
                'name': copy_name,
                'description': original['description'],
                'icon': original['icon'],
                'configuration': original['configuration'],
                'knowledge_files': original['knowledge_files']
            }

            return self.create_mode(new_data)

        except Exception as e:
            logger.error(f"Failed to duplicate mode: {e}")
            raise

    def get_system_prompt_for_conversation(self, conversation_id: int) -> str:
        """Build complete system prompt for a conversation"""
        from models.models import Conversation

        conversation = Conversation.query.get(conversation_id)
        if not conversation or not conversation.mode:
            # Use default mode
            default_mode = ConversationMode.query.filter_by(is_default=True).first()
            mode = default_mode if default_mode else None
        else:
            mode = conversation.mode

        # Build hierarchical prompt
        prompt_parts = []

        # Global system prompt
        prompt_parts.append("""You are Claude, an AI assistant created by Anthropic.
You are viewing this conversation in the context of an Obsidian Second Brain system.""")

        # Mode-specific prompt
        if mode and mode.configuration and mode.configuration.system_prompt:
            prompt_parts.append(mode.configuration.system_prompt)

        # Knowledge files context
        if mode and mode.knowledge_files:
            files_list = [kf.file_path for kf in mode.knowledge_files if kf.auto_include]
            if files_list:
                prompt_parts.append(f"The following files have been added as context:\n" +
                                  "\n".join(f"- {f}" for f in files_list))

        return "\n\n".join(prompt_parts)

# Singleton pattern
_mode_service = None

def get_mode_service():
    """Get singleton mode service instance"""
    global _mode_service
    if _mode_service is None:
        _mode_service = ModeService()
    return _mode_service
```

### STEP 4: API Endpoints

#### File: `web-interface/app.py`
**ADD these routes to existing app.py:**
```python
from services.mode_service import get_mode_service
from services.export_service import get_export_service

mode_service = get_mode_service()
export_service = get_export_service()

# Mode Management Endpoints
@app.route('/api/modes', methods=['GET'])
@login_required
def get_modes():
    """Get all conversation modes"""
    try:
        modes = mode_service.get_all_modes()
        return jsonify({'modes': modes})
    except Exception as e:
        logger.error(f"Failed to get modes: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/modes/<int:mode_id>', methods=['GET'])
@login_required
def get_mode_details(mode_id):
    """Get complete mode details"""
    try:
        details = mode_service.get_mode_details(mode_id)
        if not details:
            return jsonify({'error': 'Mode not found'}), 404
        return jsonify(details)
    except Exception as e:
        logger.error(f"Failed to get mode details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/modes', methods=['POST'])
@login_required
def create_mode():
    """Create new conversation mode"""
    try:
        data = request.json
        result = mode_service.create_mode(data)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create mode: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/modes/<int:mode_id>', methods=['PUT'])
@login_required
def update_mode(mode_id):
    """Update existing mode"""
    try:
        data = request.json
        success = mode_service.update_mode(mode_id, data)
        return jsonify({'success': success})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to update mode: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/modes/<int:mode_id>', methods=['DELETE'])
@login_required
def delete_mode(mode_id):
    """Delete a mode"""
    try:
        success = mode_service.delete_mode(mode_id)
        return jsonify({'success': success})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to delete mode: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/modes/<int:mode_id>/duplicate', methods=['POST'])
@login_required
def duplicate_mode(mode_id):
    """Duplicate an existing mode"""
    try:
        result = mode_service.duplicate_mode(mode_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to duplicate mode: {e}")
        return jsonify({'error': str(e)}), 500

# Export Endpoints
@app.route('/api/conversations/<int:conversation_id>/export', methods=['POST'])
@login_required
def export_conversation(conversation_id):
    """Export conversation to Obsidian inbox"""
    try:
        vault = request.json.get('vault', 'private')
        filepath = export_service.export_to_inbox(conversation_id, vault)

        # Update conversation exported_at timestamp
        conversation = Conversation.query.get(conversation_id)
        if conversation:
            conversation.exported_at = datetime.utcnow()
            db.session.commit()

        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        logger.error(f"Failed to export conversation: {e}")
        return jsonify({'error': str(e)}), 500

# Mobile UI Detection
@app.route('/api/ui/mode', methods=['GET'])
def get_ui_mode():
    """Get current UI mode (mobile/desktop)"""
    user_agent = request.headers.get('User-Agent', '')
    is_mobile = any(device in user_agent.lower() for device in ['iphone', 'android', 'ipad'])

    # Check for user override in session
    override = session.get('ui_mode_override')
    if override:
        return jsonify({'mode': override, 'user_override': True})

    return jsonify({'mode': 'mobile' if is_mobile else 'desktop', 'user_override': False})

@app.route('/api/ui/mode', methods=['POST'])
def set_ui_mode():
    """Set UI mode override"""
    mode = request.json.get('mode', 'auto')
    if mode == 'auto':
        session.pop('ui_mode_override', None)
    else:
        session['ui_mode_override'] = mode
    return jsonify({'success': True})
```

### STEP 5: Export Service

#### File: `web-interface/services/export_service.py` (NEW FILE)
```python
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
        self.vault_paths = {
            'private': Path(current_app.config.get('OBSIDIAN_PRIVATE_PATH', '')),
            'poa': Path(current_app.config.get('OBSIDIAN_POA_PATH', ''))
        }

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
        total_tokens = sum(msg.token_count or 0 for msg in messages)

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
```

### STEP 6: Frontend JavaScript Implementation

#### File: `web-interface/static/js/mobile.js` (NEW FILE)
```javascript
/**
 * Mobile Responsive Manager for v0.3.0
 */
class MobileResponsiveManager {
    constructor() {
        this.isMobile = false;
        this.sidebarOpen = false;
        this.touchStartX = 0;
        this.touchStartY = 0;
        this.longPressTimer = null;

        this.init();
    }

    init() {
        this.detectDevice();
        this.setupHamburgerMenu();
        this.setupTouchHandlers();
        this.setupKeyboardHandlers();
        this.applyLayout();
    }

    detectDevice() {
        // Check user agent for iPhone 15 Pro Max and other mobile devices
        const userAgent = navigator.userAgent.toLowerCase();
        const isIPhone = /iphone/.test(userAgent);
        const isAndroid = /android/.test(userAgent);
        const isIPad = /ipad/.test(userAgent);

        // Check for user override from settings
        const savedMode = localStorage.getItem('claude-web-ui');
        if (savedMode) {
            const settings = JSON.parse(savedMode);
            if (settings.uiMode === 'mobile') {
                this.isMobile = true;
            } else if (settings.uiMode === 'desktop') {
                this.isMobile = false;
            } else {
                // Auto-detect
                this.isMobile = isIPhone || isAndroid || (isIPad && window.innerWidth < 768);
            }
        } else {
            this.isMobile = isIPhone || isAndroid || (isIPad && window.innerWidth < 768);
        }

        // Add mobile class to body
        if (this.isMobile) {
            document.body.classList.add('mobile');
            document.body.classList.remove('desktop');
        } else {
            document.body.classList.add('desktop');
            document.body.classList.remove('mobile');
        }
    }

    setupHamburgerMenu() {
        // Create hamburger button if it doesn't exist
        if (!document.getElementById('hamburgerMenu')) {
            const hamburger = document.createElement('button');
            hamburger.id = 'hamburgerMenu';
            hamburger.className = 'hamburger-menu';
            hamburger.innerHTML = `
                <span class="hamburger-line"></span>
                <span class="hamburger-line"></span>
                <span class="hamburger-line"></span>
            `;
            document.body.appendChild(hamburger);

            // Create backdrop
            const backdrop = document.createElement('div');
            backdrop.id = 'sidebarBackdrop';
            backdrop.className = 'sidebar-backdrop';
            document.body.appendChild(backdrop);

            // Event handlers
            hamburger.addEventListener('click', () => this.toggleSidebar());
            backdrop.addEventListener('click', () => this.closeSidebar());
        }

        // Hide sidebar on mobile by default
        if (this.isMobile) {
            const sidebar = document.getElementById('sidebar');
            if (sidebar) {
                sidebar.classList.add('collapsed');
            }
        }
    }

    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        const backdrop = document.getElementById('sidebarBackdrop');
        const hamburger = document.getElementById('hamburgerMenu');

        if (!sidebar) return;

        this.sidebarOpen = !this.sidebarOpen;

        if (this.sidebarOpen) {
            sidebar.classList.add('active');
            backdrop.classList.add('active');
            hamburger.classList.add('active');
        } else {
            sidebar.classList.remove('active');
            backdrop.classList.remove('active');
            hamburger.classList.remove('active');
        }
    }

    closeSidebar() {
        if (this.sidebarOpen) {
            this.toggleSidebar();
        }
    }

    setupTouchHandlers() {
        if (!this.isMobile) return;

        // Long press for message actions
        document.addEventListener('touchstart', (e) => {
            const messageEl = e.target.closest('.message');
            if (!messageEl) return;

            this.touchStartX = e.touches[0].clientX;
            this.touchStartY = e.touches[0].clientY;

            this.longPressTimer = setTimeout(() => {
                this.showMessageActions(messageEl, e.touches[0]);
            }, 300);
        });

        document.addEventListener('touchend', () => {
            if (this.longPressTimer) {
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
            }
        });

        document.addEventListener('touchmove', (e) => {
            if (this.longPressTimer) {
                const deltaX = Math.abs(e.touches[0].clientX - this.touchStartX);
                const deltaY = Math.abs(e.touches[0].clientY - this.touchStartY);

                if (deltaX > 10 || deltaY > 10) {
                    clearTimeout(this.longPressTimer);
                    this.longPressTimer = null;
                }
            }
        });
    }

    showMessageActions(messageEl, touch) {
        // Haptic feedback (if supported)
        if (navigator.vibrate) {
            navigator.vibrate(50);
        }

        // Create context menu
        const existingMenu = document.querySelector('.message-context-menu');
        if (existingMenu) {
            existingMenu.remove();
        }

        const menu = document.createElement('div');
        menu.className = 'message-context-menu';

        const isUserMessage = messageEl.classList.contains('user-message');
        const actions = isUserMessage
            ? ['Copy', 'Edit', 'Delete']
            : ['Copy', 'Retry', 'Continue'];

        actions.forEach(action => {
            const button = document.createElement('button');
            button.textContent = action;
            button.onclick = () => {
                this.handleMessageAction(messageEl, action);
                menu.remove();
            };
            menu.appendChild(button);
        });

        // Position menu
        menu.style.position = 'fixed';
        let x = touch.clientX;
        let y = touch.clientY;

        // Adjust position if near edges
        document.body.appendChild(menu);
        const rect = menu.getBoundingClientRect();

        if (x + rect.width > window.innerWidth) {
            x = window.innerWidth - rect.width - 10;
        }
        if (y + rect.height > window.innerHeight) {
            y = window.innerHeight - rect.height - 10;
        }

        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;

        // Close on outside click
        setTimeout(() => {
            document.addEventListener('click', function closeMenu() {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            });
        }, 100);
    }

    handleMessageAction(messageEl, action) {
        const messageId = messageEl.dataset.messageId;
        const content = messageEl.querySelector('.message-content')?.textContent;

        switch(action) {
            case 'Copy':
                navigator.clipboard.writeText(content);
                window.showToast('Message copied to clipboard');
                break;
            case 'Edit':
                window.messageManager?.editMessage(messageId);
                break;
            case 'Delete':
                window.messageManager?.deleteMessage(messageId);
                break;
            case 'Retry':
                window.messageManager?.retryMessage(messageId);
                break;
            case 'Continue':
                window.messageManager?.continueFromMessage(messageId);
                break;
        }
    }

    setupKeyboardHandlers() {
        if (!this.isMobile) return;

        const inputField = document.getElementById('messageInput');
        if (!inputField) return;

        // Handle keyboard show/hide
        let initialHeight = window.innerHeight;

        window.addEventListener('resize', () => {
            const currentHeight = window.innerHeight;
            const inputContainer = document.querySelector('.input-container');

            if (currentHeight < initialHeight * 0.75) {
                // Keyboard is shown
                inputContainer?.classList.add('keyboard-visible');
            } else {
                // Keyboard is hidden
                inputContainer?.classList.remove('keyboard-visible');
            }
        });
    }

    applyLayout() {
        // Handle file chips on mobile
        if (this.isMobile) {
            this.setupMobileFileChips();
        }
    }

    setupMobileFileChips() {
        const fileDisplay = document.getElementById('selectedFilesDisplay');
        if (!fileDisplay) return;

        // Replace full chips with badge on mobile
        if (this.isMobile) {
            const chipsContainer = document.getElementById('fileChipsContainer');
            const fileCount = chipsContainer?.querySelectorAll('.file-chip').length || 0;

            if (fileCount > 0) {
                // Create badge
                const badge = document.createElement('div');
                badge.className = 'file-count-badge';
                badge.innerHTML = `📎 ${fileCount}`;
                badge.onclick = () => this.showFileModal();

                // Hide original chips, show badge
                chipsContainer.style.display = 'none';

                const badgeContainer = document.createElement('div');
                badgeContainer.id = 'mobileBadgeContainer';
                badgeContainer.appendChild(badge);
                fileDisplay.appendChild(badgeContainer);
            }
        }
    }

    showFileModal() {
        // Create modal to show file list
        const modal = document.createElement('div');
        modal.className = 'file-list-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Attached Files</h3>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="modal-body">
                    <div id="modalFileList"></div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Populate file list
        const fileList = document.getElementById('modalFileList');
        const chips = document.querySelectorAll('.file-chip');

        chips.forEach(chip => {
            const fileItem = document.createElement('div');
            fileItem.className = 'modal-file-item';
            fileItem.innerHTML = `
                <span class="file-name">${chip.querySelector('.chip-text').textContent}</span>
                <span class="file-tokens">${chip.querySelector('.chip-tokens').textContent}</span>
            `;
            fileList.appendChild(fileItem);
        });

        // Close handler
        modal.querySelector('.close-modal').onclick = () => {
            modal.remove();
        };

        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        };
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    window.mobileManager = new MobileResponsiveManager();
});
```

### STEP 7: Mobile CSS Styles

#### File: `web-interface/static/css/mobile.css` (NEW FILE)
```css
/* Mobile-specific styles for v0.3.0 */

/* Hamburger Menu */
.hamburger-menu {
    display: none;
    position: fixed;
    top: 1rem;
    left: 1rem;
    z-index: 1001;
    width: 40px;
    height: 40px;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    cursor: pointer;
    padding: 0;
    justify-content: center;
    align-items: center;
    flex-direction: column;
    gap: 4px;
}

.mobile .hamburger-menu {
    display: flex;
}

.hamburger-line {
    width: 24px;
    height: 2px;
    background: var(--text-primary);
    transition: all 0.3s ease;
}

.hamburger-menu.active .hamburger-line:nth-child(1) {
    transform: rotate(45deg) translate(5px, 5px);
}

.hamburger-menu.active .hamburger-line:nth-child(2) {
    opacity: 0;
}

.hamburger-menu.active .hamburger-line:nth-child(3) {
    transform: rotate(-45deg) translate(5px, -5px);
}

/* Sidebar for Mobile */
.mobile .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    height: 100vh;
    width: 280px;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    z-index: 1000;
    background: var(--bg-primary);
}

.mobile .sidebar.active {
    transform: translateX(0);
    box-shadow: 2px 0 10px rgba(0,0,0,0.1);
}

/* Backdrop */
.sidebar-backdrop {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    z-index: 999;
}

.sidebar-backdrop.active {
    display: block;
}

/* Main content adjustments */
.mobile .main-content {
    margin-left: 0;
    padding-top: 60px;  /* Space for hamburger */
    width: 100%;
}

/* Input container */
.mobile .input-container {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-primary);
    border-top: 1px solid var(--border-color);
    padding: 0.75rem;
    z-index: 100;
}

.mobile .input-container.keyboard-visible {
    /* Will be positioned above keyboard */
    position: fixed;
    bottom: 0;
}

/* File count badge */
.file-count-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: transform 0.2s ease;
}

.file-count-badge:hover {
    transform: scale(1.05);
}

/* File modal */
.file-list-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    z-index: 2000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
}

.file-list-modal .modal-content {
    background: var(--bg-primary);
    border-radius: 12px;
    max-width: 90%;
    max-height: 70vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.file-list-modal .modal-header {
    padding: 1rem;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.file-list-modal .modal-body {
    padding: 1rem;
    overflow-y: auto;
}

.modal-file-item {
    display: flex;
    justify-content: space-between;
    padding: 0.75rem;
    border-radius: 8px;
    background: var(--bg-secondary);
    margin-bottom: 0.5rem;
}

/* Message context menu */
.message-context-menu {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    padding: 0.5rem;
    z-index: 2001;
}

.message-context-menu button {
    display: block;
    width: 100%;
    padding: 0.5rem 1rem;
    text-align: left;
    background: none;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    border-radius: 4px;
}

.message-context-menu button:hover {
    background: var(--bg-secondary);
}

/* iPhone 15 Pro Max specific */
@media screen and (max-width: 430px) {
    .mobile .sidebar {
        width: 85%;  /* Take most of screen on phone */
    }

    .mobile .chat-header {
        padding: 0.5rem;
        font-size: 14px;
    }

    .mobile .message {
        padding: 0.75rem;
        font-size: 15px;  /* Optimal for iPhone reading */
    }

    .mobile .input-field {
        font-size: 16px;  /* Prevent zoom on iOS */
    }
}

/* Landscape mode */
@media screen and (max-width: 932px) and (orientation: landscape) {
    .mobile .input-container {
        padding: 0.5rem;
    }

    .mobile .messages-container {
        padding-bottom: 4rem;
    }
}

/* Mode header for mobile */
.mobile .conversation-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 0.5rem;
}

.mobile .mode-badge {
    font-size: 12px;
    padding: 2px 8px;
}

/* Touch feedback */
.mobile .message:active {
    background: var(--bg-hover);
}

/* Prevent text selection on long press */
.mobile .message {
    -webkit-user-select: none;
    user-select: none;
    -webkit-touch-callout: none;
}
```

---

## Implementation Order & Testing

### Implementation Steps (CRITICAL ORDER)

1. **FIRST: Run Database Migration**
   ```bash
   cd web-interface
   python migrations/v030_migration.py
   ```

2. **Update Backend Files**
   - Add models to `models/models.py`
   - Create `services/mode_service.py`
   - Create `services/export_service.py`
   - Update `app.py` with new routes

3. **Update Frontend Files**
   - Create `static/js/mobile.js`
   - Create `static/css/mobile.css`
   - Update `templates/base.html` to include new files
   - Update `templates/index.html` for mode display

4. **Test Each Component**
   - Test database migration
   - Test API endpoints with curl/Postman
   - Test mobile detection
   - Test mode CRUD operations
   - Test export functionality

### Testing Checklist

```python
# File: web-interface/tests/test_v030.py
#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test suite for v0.3.0 features"""

import unittest
import json
from pathlib import Path
from app import app, db

class TestV030Features(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def test_database_migration(self):
        """Verify all new tables exist"""
        with app.app_context():
            # Check tables exist
            cursor = db.session.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor]

            self.assertIn('conversation_modes', tables)
            self.assertIn('mode_configuration', tables)
            self.assertIn('mode_knowledge_files', tables)

    def test_default_mode_exists(self):
        """Verify General mode was created"""
        response = self.app.get('/api/modes')
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(m['name'] == 'General' for m in data['modes']))

    def test_mobile_detection(self):
        """Test mobile device detection"""
        # Test iPhone user agent
        response = self.app.get('/api/ui/mode', headers={
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'
        })
        data = json.loads(response.data)
        self.assertEqual(data['mode'], 'mobile')

    def test_mode_crud_operations(self):
        """Test creating, updating, deleting modes"""
        # Create mode
        response = self.app.post('/api/modes', json={
            'name': 'Test Mode',
            'description': 'Testing',
            'icon': '🧪',
            'configuration': {
                'model': 'claude-3-5-sonnet-20241022',
                'system_prompt': 'You are a test assistant'
            }
        })
        self.assertEqual(response.status_code, 200)
        mode_id = json.loads(response.data)['id']

        # Update mode
        response = self.app.put(f'/api/modes/{mode_id}', json={
            'description': 'Updated description'
        })
        self.assertEqual(response.status_code, 200)

        # Delete mode
        response = self.app.delete(f'/api/modes/{mode_id}')
        self.assertEqual(response.status_code, 200)

    def test_export_conversation(self):
        """Test exporting conversation to inbox"""
        # Create test conversation first
        # ... setup code ...

        response = self.app.post('/api/conversations/1/export', json={
            'vault': 'private'
        })
        self.assertEqual(response.status_code, 200)

        # Verify file was created
        data = json.loads(response.data)
        filepath = Path(data['filepath'])
        self.assertTrue(filepath.exists())
        self.assertTrue(filepath.name.startswith('[CHAT]'))

    def tearDown(self):
        self.app_context.pop()

if __name__ == '__main__':
    unittest.main()
```

---

## Common Pitfalls to Avoid

### ❌ DO NOT:
1. **Modify existing v0.2.0 tables** - Only add new columns/tables
2. **Change permission system** - Write permissions must stay disabled
3. **Break token caching** - Reuse existing TokenService
4. **Create new auth system** - Use existing user management
5. **Modify Claude SDK integration** - Extend, don't replace
6. **Hardcode paths** - Use config values for vault paths
7. **Skip migration** - Database migration MUST run first
8. **Ignore mobile testing** - Test on actual iPhone/simulator

### ✅ DO:
1. **Reuse existing services** - TokenService, PermissionManager, etc.
2. **Follow singleton patterns** - For service instances
3. **Use transactions** - For database operations
4. **Add error handling** - Comprehensive try/catch blocks
5. **Log everything** - Use existing logging system
6. **Test incrementally** - Test each component before moving on
7. **Preserve backwards compatibility** - Existing features must work
8. **Use existing UI patterns** - Match v0.2.0 styling

---

## Rollback Plan

### If Issues Occur:
```bash
# 1. Restore database backup
cp data/claude.db.backup data/claude.db

# 2. Revert code changes
git checkout v0.2.0

# 3. Clear caches
rm -rf __pycache__
rm -rf static/cache

# 4. Restart application
./restart_app.sh
```

### Database Backup Before Migration:
```bash
cp data/claude.db data/claude.db.v020.backup
```

---

## Dependencies to Install

```bash
# No new dependencies required!
# All functionality uses existing packages:
# - Flask (existing)
# - SQLAlchemy (existing)
# - tiktoken (existing from v0.2.0)
# - Claude Agent SDK (existing)
```

---

## Success Criteria

### v0.3.0 is complete when:
- [ ] Database migration runs without errors
- [ ] Mobile layout works on iPhone 15 Pro Max
- [ ] Hamburger menu functions properly
- [ ] All mode CRUD operations work
- [ ] Export creates valid markdown files
- [ ] Token counting includes mode system prompts
- [ ] Long press shows context menu
- [ ] File badge shows on mobile
- [ ] Mode persists with conversations
- [ ] Settings page has mode management
- [ ] All v0.2.0 features still work

---

## Final Notes for Subagent Implementation

1. **Start with database migration** - This is critical
2. **Test API endpoints with curl** before frontend
3. **Use iPhone simulator** for mobile testing
4. **Preserve all v0.2.0 functionality**
5. **Follow existing code patterns** from v0.2.0
6. **Use existing services** wherever possible
7. **Document any deviations** from this spec

This specification provides **complete implementation details** with zero ambiguity. Follow the steps exactly as specified for successful v0.3.0 deployment.
