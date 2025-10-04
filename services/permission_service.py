#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Permission management service for Claude AI web interface."""

import json
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from flask import current_app
from models.models import db, UserPermissions, User

# Set up logging
logger = logging.getLogger(__name__)

class PermissionManager:
    """Manages user permissions and tool access for Claude AI interface."""

    # CRITICAL: Maps user-friendly permissions to Claude Agent SDK tools
    # SAFETY: Write/Edit tools are NEVER included to prevent file modifications
    PERMISSION_MAPPING = {
        'webSearch': ['WebSearch', 'WebFetch'],
        'vaultSearch': ['Grep', 'Glob', 'Task'],
        'readFiles': ['Read'],
        'writeFiles': []  # ALWAYS EMPTY - NEVER ALLOW WRITES FOR SAFETY
    }

    # Default safe permissions for new users
    DEFAULT_PERMISSIONS = {
        'webSearch': False,        # Disabled by default (external access)
        'vaultSearch': True,       # Enabled by default (safe local search)
        'readFiles': True,         # Enabled by default (safe read access)
        'writeFiles': False        # ALWAYS FALSE - HARDCODED FOR SAFETY
    }

    # Tools that are NEVER allowed regardless of permissions
    FORBIDDEN_TOOLS = [
        'Write', 'Edit', 'MultiEdit', 'NotebookEdit',  # File modification tools
        'Bash',                                         # System execution
        'KillShell', 'BashOutput'                      # Shell management
    ]

    # Core tools that are always available (safe, essential tools)
    CORE_TOOLS = [
        'TodoWrite'  # Task management is always safe
    ]

    def __init__(self):
        """Initialize permission manager."""
        self.cache = {}  # Simple in-memory cache for performance

    def get_user_permissions(self, user_id: int) -> Dict[str, bool]:
        """
        Get current permissions for a user.

        Args:
            user_id: User ID to get permissions for

        Returns:
            Dictionary of permission names to boolean values
        """
        # Check cache first
        cache_key = f"user_perms_{user_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Get from database
        user_perms = UserPermissions.query.filter_by(user_id=user_id).first()

        if not user_perms:
            # Create default permissions for new user
            user_perms = self._create_default_permissions(user_id)

        permissions = {
            'webSearch': user_perms.web_search,
            'vaultSearch': user_perms.vault_search,
            'readFiles': user_perms.read_files,
            'writeFiles': user_perms.write_files  # Always False due to database constraint
        }

        # Cache the result
        self.cache[cache_key] = permissions
        logger.info(f"Loaded permissions for user {user_id}: {permissions}")

        return permissions

    def update_user_permissions(self, user_id: int, permissions: Dict[str, bool]) -> bool:
        """
        Update user permissions with validation.

        Args:
            user_id: User ID to update permissions for
            permissions: Dictionary of permission names to boolean values

        Returns:
            True if update successful, False otherwise
        """
        try:
            # CRITICAL SAFETY CHECK: Never allow write permissions
            if permissions.get('writeFiles', False):
                logger.warning(f"Attempt to enable write permissions for user {user_id} - BLOCKED")
                return False  # Reject the entire update if write permissions are requested

            # Validate permission keys
            valid_perms = set(self.DEFAULT_PERMISSIONS.keys())
            provided_perms = set(permissions.keys())

            if not provided_perms.issubset(valid_perms):
                invalid_perms = provided_perms - valid_perms
                logger.error(f"Invalid permissions provided: {invalid_perms}")
                return False

            # Get or create user permissions record
            user_perms = UserPermissions.query.filter_by(user_id=user_id).first()
            if not user_perms:
                user_perms = UserPermissions(user_id=user_id)
                db.session.add(user_perms)

            # Update permissions (writeFiles always forced to False)
            user_perms.web_search = permissions.get('webSearch', False)
            user_perms.vault_search = permissions.get('vaultSearch', True)
            user_perms.read_files = permissions.get('readFiles', True)
            user_perms.write_files = False  # HARDCODED FOR SAFETY
            user_perms.updated_at = datetime.utcnow()

            db.session.commit()

            # Clear cache
            cache_key = f"user_perms_{user_id}"
            if cache_key in self.cache:
                del self.cache[cache_key]

            logger.info(f"Updated permissions for user {user_id}: {permissions}")
            self._audit_permission_change(user_id, permissions)

            return True

        except Exception as e:
            logger.error(f"Failed to update permissions for user {user_id}: {e}")
            db.session.rollback()
            return False

    def get_allowed_tools(self, user_id: int) -> List[str]:
        """
        Get list of tools allowed for a user based on their permissions.

        Args:
            user_id: User ID to get allowed tools for

        Returns:
            List of tool names that the user is allowed to use
        """
        permissions = self.get_user_permissions(user_id)
        allowed_tools = set(self.CORE_TOOLS)  # Always include core tools

        # Add tools based on permissions
        for perm_name, enabled in permissions.items():
            if enabled and perm_name in self.PERMISSION_MAPPING:
                allowed_tools.update(self.PERMISSION_MAPPING[perm_name])

        # Remove any forbidden tools (safety check)
        allowed_tools = allowed_tools - set(self.FORBIDDEN_TOOLS)

        # Convert to sorted list for consistency
        tool_list = sorted(list(allowed_tools))

        logger.debug(f"Allowed tools for user {user_id}: {tool_list}")
        return tool_list

    def validate_tool_usage(self, user_id: int, tool_name: str) -> bool:
        """
        Validate if a user is allowed to use a specific tool.

        Args:
            user_id: User ID to check permissions for
            tool_name: Name of the tool to validate

        Returns:
            True if tool usage is allowed, False otherwise
        """
        # Check if tool is forbidden
        if tool_name in self.FORBIDDEN_TOOLS:
            logger.warning(f"User {user_id} attempted to use forbidden tool: {tool_name}")
            return False

        # Check if tool is in allowed list
        allowed_tools = self.get_allowed_tools(user_id)
        is_allowed = tool_name in allowed_tools

        if not is_allowed:
            logger.warning(f"User {user_id} attempted to use unauthorized tool: {tool_name}")

        return is_allowed

    def get_permission_info(self) -> Dict:
        """
        Get information about available permissions and their descriptions.

        Returns:
            Dictionary with permission metadata
        """
        return {
            'permissions': {
                'webSearch': {
                    'name': 'Web Search',
                    'description': 'Allow Claude to search the internet and fetch web content',
                    'icon': '🌐',
                    'risk_level': 'medium',
                    'tools': self.PERMISSION_MAPPING['webSearch']
                },
                'vaultSearch': {
                    'name': 'Vault Search',
                    'description': 'Allow Claude to search through your Obsidian vault',
                    'icon': '🔍',
                    'risk_level': 'low',
                    'tools': self.PERMISSION_MAPPING['vaultSearch']
                },
                'readFiles': {
                    'name': 'Read Files',
                    'description': 'Allow Claude to read files from your system',
                    'icon': '📖',
                    'risk_level': 'low',
                    'tools': self.PERMISSION_MAPPING['readFiles']
                },
                'writeFiles': {
                    'name': 'Write Files',
                    'description': 'File writing is permanently disabled for safety',
                    'icon': '🚫',
                    'risk_level': 'high',
                    'tools': [],
                    'disabled': True,
                    'disabled_reason': 'File writing is disabled for security and safety reasons'
                }
            },
            'forbidden_tools': self.FORBIDDEN_TOOLS,
            'core_tools': self.CORE_TOOLS
        }

    def _create_default_permissions(self, user_id: int) -> UserPermissions:
        """
        Create default permissions for a new user.

        Args:
            user_id: User ID to create permissions for

        Returns:
            UserPermissions object
        """
        user_perms = UserPermissions(
            user_id=user_id,
            web_search=self.DEFAULT_PERMISSIONS['webSearch'],
            vault_search=self.DEFAULT_PERMISSIONS['vaultSearch'],
            read_files=self.DEFAULT_PERMISSIONS['readFiles'],
            write_files=False,  # ALWAYS FALSE
            updated_at=datetime.utcnow()
        )

        db.session.add(user_perms)
        db.session.commit()

        logger.info(f"Created default permissions for user {user_id}")
        return user_perms

    def _audit_permission_change(self, user_id: int, new_permissions: Dict[str, bool]):
        """
        Log permission changes for audit purposes.

        Args:
            user_id: User ID whose permissions changed
            new_permissions: New permission values
        """
        user = User.query.get(user_id)
        username = user.username if user else f"user_{user_id}"

        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'username': username,
            'action': 'permission_update',
            'permissions': new_permissions,
            'safety_check': 'writeFiles blocked' if new_permissions.get('writeFiles') else 'passed'
        }

        # Log to application logs (can be extended to write to audit table)
        logger.info(f"AUDIT: {json.dumps(audit_entry)}")

    def clear_cache(self, user_id: Optional[int] = None):
        """
        Clear permission cache.

        Args:
            user_id: Specific user ID to clear, or None to clear all
        """
        if user_id:
            cache_key = f"user_perms_{user_id}"
            if cache_key in self.cache:
                del self.cache[cache_key]
        else:
            self.cache.clear()

        logger.debug(f"Cleared permission cache for user: {user_id or 'all'}")


# Global instance
permission_manager = PermissionManager()


def get_permission_manager() -> PermissionManager:
    """Get the global permission manager instance."""
    return permission_manager