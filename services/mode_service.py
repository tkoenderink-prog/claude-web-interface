#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Conversation Mode management service"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
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
            # Handle both False and NULL values
            from sqlalchemy import or_
            query = query.filter(or_(ConversationMode.is_deleted == False, ConversationMode.is_deleted == None))

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
        if not mode or (mode.is_deleted == True):  # Only exclude if explicitly True
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
            system_tokens = self.token_service.estimate_text_tokens(system_prompt)['token_count']

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
                try:
                    tokens_result = self.token_service.estimate_file_tokens(Path(kf_data['file_path']))
                    tokens = tokens_result['token_count']
                except:
                    tokens = 0
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
                    config.system_prompt_tokens = self.token_service.estimate_text_tokens(cfg_data['system_prompt'])['token_count']

            # Update knowledge files (replace all)
            if 'knowledge_files' in data:
                # Remove existing
                ModeKnowledgeFile.query.filter_by(mode_id=mode.id).delete()

                # Add new ones
                for kf_data in data['knowledge_files']:
                    try:
                        tokens_result = self.token_service.estimate_file_tokens(Path(kf_data['file_path']))
                        tokens = tokens_result['token_count']
                    except:
                        tokens = 0
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
