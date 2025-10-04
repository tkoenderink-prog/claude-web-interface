#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Main Flask application for Claude Clone."""

import os
import sys
import json
import uuid
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config.config import get_config
from models.models import db, User, Conversation, Message, ProjectKnowledge, ConversationKnowledge, FileAttachment, TokenCache, UserPermissions
from services.claude_service import ClaudeService, ObsidianKnowledgeService
from services.token_service import get_token_service, TokenEstimationError
from services.permission_service import get_permission_manager
from services.streaming_service import get_streaming_service, ContentType
from services.mode_service import get_mode_service
from services.export_service import get_export_service
from services.download_service import get_download_service

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(get_config())

# Initialize logging
logger = logging.getLogger(__name__)

# Initialize extensions
db.init_app(app)
CORS(app, origins=app.config['CORS_ORIGINS'])
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize services
claude_service = ClaudeService(working_directory=Path.cwd())
obsidian_service = ObsidianKnowledgeService({
    'private': Path(app.config['OBSIDIAN_PRIVATE_PATH']),
    'poa': Path(app.config['OBSIDIAN_POA_PATH'])
})
token_service = get_token_service()
permission_manager = get_permission_manager()
streaming_service = get_streaming_service()
mode_service = get_mode_service()
export_service = get_export_service()
download_service = get_download_service()

# Create database tables
with app.app_context():
    db.create_all()
    # Create default user if none exists (for simplified auth)
    if not User.query.first():
        default_user = User(username='default', email='user@example.com')
        db.session.add(default_user)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.query.get(int(user_id))

def async_to_sync(f):
    """Decorator to run async functions in Flask routes."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    return wrapper

# Routes

@app.route('/')
def index():
    """Main chat interface."""
    return render_template('index.html')

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Simple login endpoint."""
    # For simplified demo, auto-login the default user
    user = User.query.first()
    if user:
        login_user(user, remember=True)
        return jsonify({'success': True, 'user': {'id': user.id, 'username': user.username}})
    return jsonify({'success': False, 'error': 'No user found'}), 404

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """Logout endpoint."""
    logout_user()
    return jsonify({'success': True})

# Permission Management Endpoints
@app.route('/api/permissions', methods=['GET'])
@login_required
def get_permissions():
    """Get current user permissions."""
    try:
        permissions = permission_manager.get_user_permissions(current_user.id)
        permission_info = permission_manager.get_permission_info()

        return jsonify({
            'success': True,
            'permissions': permissions,
            'permission_info': permission_info
        })
    except Exception as e:
        logger.error(f"Failed to get permissions for user {current_user.id}: {e}")
        return jsonify({'success': False, 'error': 'Failed to load permissions'}), 500

@app.route('/api/permissions', methods=['PUT'])
@login_required
def update_permissions():
    """Update user permissions with validation."""
    try:
        data = request.json
        if not data or 'permissions' not in data:
            return jsonify({'success': False, 'error': 'Invalid request data'}), 400

        permissions = data['permissions']

        # CRITICAL SAFETY CHECK: Block any attempt to enable write permissions
        if permissions.get('writeFiles', False):
            logger.warning(f"User {current_user.id} attempted to enable write permissions - BLOCKED")
            return jsonify({
                'success': False,
                'error': 'Write permissions cannot be enabled for security reasons'
            }), 403

        # Update permissions
        success = permission_manager.update_user_permissions(current_user.id, permissions)

        if success:
            # Return updated permissions
            updated_permissions = permission_manager.get_user_permissions(current_user.id)
            return jsonify({
                'success': True,
                'permissions': updated_permissions,
                'message': 'Permissions updated successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update permissions'}), 500

    except Exception as e:
        logger.error(f"Failed to update permissions for user {current_user.id}: {e}")
        return jsonify({'success': False, 'error': 'Failed to update permissions'}), 500

@app.route('/api/permissions/info', methods=['GET'])
@login_required
def get_permission_info():
    """Get information about available permissions."""
    try:
        permission_info = permission_manager.get_permission_info()
        return jsonify({
            'success': True,
            'info': permission_info
        })
    except Exception as e:
        logger.error(f"Failed to get permission info: {e}")
        return jsonify({'success': False, 'error': 'Failed to load permission info'}), 500

@app.route('/api/permissions/tools', methods=['GET'])
@login_required
def get_allowed_tools():
    """Get list of tools allowed for current user."""
    try:
        allowed_tools = permission_manager.get_allowed_tools(current_user.id)
        return jsonify({
            'success': True,
            'allowed_tools': allowed_tools
        })
    except Exception as e:
        logger.error(f"Failed to get allowed tools for user {current_user.id}: {e}")
        return jsonify({'success': False, 'error': 'Failed to load allowed tools'}), 500

@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get all conversations for current user."""
    conversations = current_user.conversations.filter_by(is_archived=False).order_by(Conversation.updated_at.desc()).all()
    return jsonify([c.to_dict() for c in conversations])

@app.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation():
    """Create a new conversation."""
    data = request.json
    conversation = Conversation(
        uuid=str(uuid.uuid4()),
        title=data.get('title', 'New Conversation'),
        user_id=current_user.id,
        model=data.get('model', app.config['DEFAULT_MODEL']),
        custom_instructions=data.get('custom_instructions'),
        mode_id=data.get('mode_id', 1)  # Default to General mode
    )
    db.session.add(conversation)
    db.session.commit()
    return jsonify(conversation.to_dict())

@app.route('/api/conversations/<conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    """Get a specific conversation with messages."""
    conversation = Conversation.query.filter_by(uuid=conversation_id, user_id=current_user.id).first_or_404()
    response = conversation.to_dict()
    response['messages'] = [m.to_dict() for m in conversation.messages]
    return jsonify(response)

@app.route('/api/conversations/<conversation_id>', methods=['PUT'])
@login_required
def update_conversation(conversation_id):
    """Update a conversation."""
    conversation = Conversation.query.filter_by(uuid=conversation_id, user_id=current_user.id).first_or_404()
    data = request.json

    # Update allowed fields
    if 'title' in data:
        conversation.title = data['title']
    if 'mode_id' in data:
        conversation.mode_id = data['mode_id']
    if 'model' in data:
        conversation.model = data['model']
    if 'custom_instructions' in data:
        conversation.custom_instructions = data['custom_instructions']

    db.session.commit()
    return jsonify(conversation.to_dict())

@app.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
@login_required
@async_to_sync
async def send_message(conversation_id):
    """Send a message in a conversation."""
    conversation = Conversation.query.filter_by(uuid=conversation_id, user_id=current_user.id).first_or_404()
    data = request.json

    # Extract file information from request
    knowledge_files = data.get('knowledge_files', [])
    upload_files = data.get('upload_files', [])
    total_tokens = data.get('total_tokens', 0)

    # Save user message with file associations
    user_message = Message(
        conversation_id=conversation.id,
        role='user',
        content=data['content']
    )
    db.session.add(user_message)
    db.session.commit()

    # Log file information for debugging
    if knowledge_files or upload_files:
        app.logger.info(f"Message includes {len(knowledge_files)} knowledge files and {len(upload_files)} uploads (Total tokens: {total_tokens})")

    # Get conversation history
    messages = []
    for msg in conversation.messages.limit(20):  # Limit context to last 20 messages
        messages.append({
            'role': msg.role,
            'content': msg.content
        })

    # Get project knowledge if enabled
    project_knowledge = []
    if app.config['ENABLE_PROJECT_KNOWLEDGE']:
        knowledge_links = conversation.knowledge_links.all()
        for link in knowledge_links:
            knowledge = link.knowledge
            content = await obsidian_service.get_file_content(knowledge.vault_type, knowledge.file_path)
            if content:
                project_knowledge.append(f"# {knowledge.name}\n\n{content}")

    # Get Claude's response with streaming
    assistant_content = ""
    start_time = datetime.utcnow()

    # Get allowed tools from frontend (based on user permissions) with fallback
    allowed_tools = data.get('allowed_tools', [])

    # If no tools provided, get from permission manager as fallback
    if not allowed_tools:
        allowed_tools = permission_manager.get_allowed_tools(current_user.id)

    # Log permission-based tool usage
    logger.info(f"User {current_user.id} message using tools: {allowed_tools}")

    # Debug: Log project knowledge status
    print(f"Project knowledge enabled: {app.config.get('ENABLE_PROJECT_KNOWLEDGE', True)}")
    print(f"Knowledge links found: {len(knowledge_links) if 'knowledge_links' in locals() else 0}")
    if project_knowledge:
        print(f"Sending {len(project_knowledge)} knowledge items to Claude")
        for idx, pk in enumerate(project_knowledge):
            print(f"  Knowledge {idx+1}: {pk[:100]}...")
    else:
        print("No project knowledge being sent")

    # Get the system prompt from the mode if available
    system_prompt = conversation.custom_instructions or ""
    if conversation.mode_id:
        mode_prompt = mode_service.get_system_prompt_for_conversation(conversation.id)
        if mode_prompt:
            system_prompt = mode_prompt
            print(f"Using mode system prompt from mode_id {conversation.mode_id}")

    async for chunk in claude_service.create_message(
        messages=messages,
        system_prompt=system_prompt,
        project_knowledge=project_knowledge,
        stream=True,  # Enable streaming
        tools=allowed_tools
    ):
        assistant_content += chunk

    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    # Save assistant message
    assistant_message = Message(
        conversation_id=conversation.id,
        role='assistant',
        content=assistant_content,
        processing_time_ms=processing_time,
        model_used=conversation.model
    )
    db.session.add(assistant_message)

    # Update conversation
    conversation.updated_at = datetime.utcnow()
    if conversation.title == 'New Conversation' and len(messages) <= 2:
        # Auto-generate title from first exchange
        conversation.title = data['content'][:50] + ('...' if len(data['content']) > 50 else '')

    db.session.commit()

    return jsonify(assistant_message.to_dict())

@app.route('/api/knowledge/search', methods=['POST'])
@login_required
@async_to_sync
async def search_knowledge():
    """Search Obsidian vaults for knowledge."""
    data = request.json
    vault = data.get('vault', 'private')
    query = data.get('query', '')
    category = data.get('category')
    select_all = data.get('select_all', False)

    # If select_all is requested, return all available files
    if select_all:
        results = await obsidian_service.get_all_files(vault, category)
    else:
        results = await obsidian_service.search_vault(vault, query, category)

    # Get current conversation ID from request
    conversation_id = data.get('conversation_id')

    # Enhance results with token estimates and current selection status
    enhanced_results = []
    for item in results:
        # Check if this file exists in ProjectKnowledge
        existing_knowledge = ProjectKnowledge.query.filter_by(
            user_id=current_user.id,
            vault_type=vault,
            file_path=item['path']
        ).first()

        # Check if it's added to the CURRENT conversation (not any conversation)
        is_added_to_current = False
        if existing_knowledge and conversation_id:
            # Get the conversation
            conversation = Conversation.query.filter_by(
                uuid=conversation_id,
                user_id=current_user.id
            ).first()

            if conversation:
                # Check if this knowledge is linked to the current conversation
                conversation_knowledge = ConversationKnowledge.query.filter_by(
                    conversation_id=conversation.id,
                    knowledge_id=existing_knowledge.id
                ).first()
                is_added_to_current = conversation_knowledge is not None

        # Get or estimate token count
        token_count = None
        if existing_knowledge and existing_knowledge.token_count and existing_knowledge.token_count > 0:
            token_count = existing_knowledge.token_count
        else:
            # Try to estimate tokens for new files or files with 0 tokens
            try:
                content = await obsidian_service.get_file_content(vault, item['path'])
                if content:
                    token_estimation = token_service.estimate_text_tokens(content)
                    token_count = token_estimation['token_count']

                    # Update the database if we have an existing record with 0 tokens
                    if existing_knowledge and (not existing_knowledge.token_count or existing_knowledge.token_count == 0):
                        existing_knowledge.token_count = token_count
                        db.session.commit()
            except Exception as e:
                app.logger.warning(f"Failed to estimate tokens for {item['path']}: {e}")

        enhanced_item = {
            **item,
            'token_count': token_count,
            'is_added': is_added_to_current,  # Now checks current conversation only
            'knowledge_id': existing_knowledge.id if existing_knowledge else None
        }
        enhanced_results.append(enhanced_item)

    return jsonify(enhanced_results)

@app.route('/api/knowledge/structure', methods=['GET'])
@login_required
@async_to_sync
async def get_vault_structure():
    """Get structure of Obsidian vaults."""
    vault = request.args.get('vault', 'private')
    structure = await obsidian_service.get_vault_structure(vault)
    return jsonify(structure)

@app.route('/api/knowledge/add', methods=['POST'])
@login_required
@async_to_sync
async def add_knowledge_to_conversation():
    """Add project knowledge to a conversation."""
    data = request.json
    conversation = Conversation.query.filter_by(uuid=data['conversation_id'], user_id=current_user.id).first_or_404()

    # Check if knowledge exists in DB, create if not
    knowledge = ProjectKnowledge.query.filter_by(
        user_id=current_user.id,
        vault_type=data['vault'],
        file_path=data['file_path']
    ).first()

    if not knowledge:
        content = await obsidian_service.get_file_content(data['vault'], data['file_path'])
        if not content:
            return jsonify({'error': 'File not found'}), 404

        # Estimate token count for the content
        try:
            token_estimation = token_service.estimate_text_tokens(content)
            token_count = token_estimation['token_count']
        except TokenEstimationError as e:
            app.logger.warning(f"Failed to estimate tokens for knowledge file {data['file_path']}: {e}")
            token_count = None

        knowledge = ProjectKnowledge(
            user_id=current_user.id,
            name=Path(data['file_path']).stem,
            vault_type=data['vault'],
            file_path=data['file_path'],
            category=data.get('category', 'RESOURCE'),
            content_preview=content[:500] if content else "",
            content_hash=obsidian_service.calculate_content_hash(content),
            token_count=token_count
        )
        db.session.add(knowledge)
        db.session.flush()  # Flush to get the ID

    # Link to conversation
    link = ConversationKnowledge(
        conversation_id=conversation.id,
        knowledge_id=knowledge.id,
        added_by_user=True
    )
    db.session.add(link)
    db.session.commit()

    return jsonify({'success': True, 'knowledge': knowledge.to_dict()})

@app.route('/api/knowledge/add-bulk', methods=['POST'])
@login_required
@async_to_sync
async def add_bulk_knowledge_to_conversation():
    """Add multiple project knowledge files to a conversation in a single transaction."""
    data = request.json
    conversation = Conversation.query.filter_by(uuid=data['conversation_id'], user_id=current_user.id).first_or_404()
    files = data.get('files', [])

    if not files:
        return jsonify({'error': 'No files provided'}), 400

    results = {
        'succeeded': [],
        'failed': [],
        'total_tokens': 0,
        'duplicate_count': 0
    }

    try:
        # Process files in a single database transaction
        for file_data in files:
            vault = file_data.get('vault')
            file_path = file_data.get('file_path')
            category = file_data.get('category', 'RESOURCE')

            if not vault or not file_path:
                results['failed'].append({
                    'file_path': file_path or 'unknown',
                    'vault': vault or 'unknown',
                    'error': 'Missing vault or file_path'
                })
                continue

            try:
                # Check if knowledge already exists
                knowledge = ProjectKnowledge.query.filter_by(
                    user_id=current_user.id,
                    vault_type=vault,
                    file_path=file_path
                ).first()

                if not knowledge:
                    # Create new knowledge entry
                    content = await obsidian_service.get_file_content(vault, file_path)
                    if not content:
                        results['failed'].append({
                            'file_path': file_path,
                            'vault': vault,
                            'error': 'File not found or empty'
                        })
                        continue

                    # Estimate token count
                    try:
                        token_estimation = token_service.estimate_text_tokens(content)
                        token_count = token_estimation['token_count']
                    except TokenEstimationError as e:
                        app.logger.warning(f"Failed to estimate tokens for {file_path}: {e}")
                        token_count = None

                    knowledge = ProjectKnowledge(
                        user_id=current_user.id,
                        name=Path(file_path).stem,
                        vault_type=vault,
                        file_path=file_path,
                        category=category,
                        content_preview=content[:500] if content else "",
                        content_hash=obsidian_service.calculate_content_hash(content),
                        token_count=token_count
                    )
                    db.session.add(knowledge)
                    db.session.flush()  # Flush to get the ID

                # Check if already linked to this conversation
                existing_link = ConversationKnowledge.query.filter_by(
                    conversation_id=conversation.id,
                    knowledge_id=knowledge.id
                ).first()

                if existing_link:
                    results['duplicate_count'] += 1
                    continue

                # Create conversation link
                link = ConversationKnowledge(
                    conversation_id=conversation.id,
                    knowledge_id=knowledge.id,
                    added_by_user=True
                )
                db.session.add(link)

                # Track success
                results['succeeded'].append({
                    'file_path': file_path,
                    'vault': vault,
                    'knowledge_id': knowledge.id,
                    'token_count': knowledge.token_count,
                    'name': knowledge.name
                })

                if knowledge.token_count:
                    results['total_tokens'] += knowledge.token_count

            except Exception as e:
                app.logger.error(f"Error processing file {file_path}: {e}")
                results['failed'].append({
                    'file_path': file_path,
                    'vault': vault,
                    'error': str(e)
                })

        # Commit all changes at once
        db.session.commit()

        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_files': len(files),
                'succeeded': len(results['succeeded']),
                'failed': len(results['failed']),
                'duplicates': results['duplicate_count'],
                'total_tokens': results['total_tokens']
            }
        })

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Bulk knowledge addition failed: {e}")
        return jsonify({'error': 'Bulk operation failed', 'details': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """Handle file uploads."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = app.config['UPLOAD_FOLDER'] / filename
        file.save(filepath)

        # Calculate token count for the uploaded file
        try:
            # Read file content to estimate tokens
            file_content = ""
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            except UnicodeDecodeError:
                # For binary files, use filename as content
                file_content = f"[Binary file: {filename}]"

            tokens = token_service.estimate_tokens(file_content)
        except Exception as e:
            app.logger.warning(f"Failed to estimate tokens for uploaded file {filename}: {e}")
            tokens = 0

        # Generate unique file ID
        file_id = str(uuid.uuid4())

        return jsonify({
            'success': True,
            'filename': filename,
            'size': os.path.getsize(filepath),
            'tokens': tokens,
            'file_id': file_id
        })

    return jsonify({'error': 'File type not allowed'}), 400

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Token Estimation API Endpoints

@app.route('/api/tokens/estimate', methods=['POST'])
@login_required
def estimate_text_tokens():
    """Estimate tokens for text content."""
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({'error': 'Text content is required'}), 400

        text = data['text']
        if not isinstance(text, str):
            return jsonify({'error': 'Text must be a string'}), 400

        result = token_service.estimate_text_tokens(text)
        return jsonify({
            'success': True,
            'estimation': result
        })

    except TokenEstimationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error estimating text tokens: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/tokens/file', methods=['POST'])
@login_required
def estimate_file_tokens():
    """Estimate tokens for a file."""
    try:
        data = request.json
        if not data or 'file_path' not in data:
            return jsonify({'error': 'File path is required'}), 400

        file_path = data['file_path']
        use_cache = data.get('use_cache', True)

        # Validate file path
        file_path_obj = Path(file_path)
        if not file_path_obj.is_absolute():
            # If relative path, make it relative to upload folder
            file_path_obj = app.config.get('UPLOAD_FOLDER', Path.cwd()) / file_path

        result = token_service.estimate_file_tokens(file_path_obj, use_cache=use_cache)
        return jsonify({
            'success': True,
            'estimation': result
        })

    except TokenEstimationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error estimating file tokens: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/tokens/conversation', methods=['POST'])
@login_required
def estimate_conversation_tokens():
    """Estimate tokens for an entire conversation context."""
    try:
        data = request.json
        if not data or 'conversation_id' not in data:
            return jsonify({'error': 'Conversation ID is required'}), 400

        conversation = Conversation.query.filter_by(
            uuid=data['conversation_id'],
            user_id=current_user.id
        ).first_or_404()

        # Build message list
        messages = []
        for msg in conversation.messages.order_by(Message.created_at):
            messages.append({
                'role': msg.role,
                'content': msg.content
            })

        # Get project knowledge if enabled
        project_knowledge = []
        if app.config.get('ENABLE_PROJECT_KNOWLEDGE', True):
            knowledge_links = conversation.knowledge_links.all()
            for link in knowledge_links:
                knowledge = link.knowledge
                # For estimation, use content preview or fetch actual content
                if knowledge.content_preview:
                    project_knowledge.append(f"# {knowledge.name}\n\n{knowledge.content_preview}")

        result = token_service.estimate_conversation_tokens(
            messages=messages,
            system_prompt=conversation.custom_instructions,
            project_knowledge=project_knowledge
        )

        # Update conversation with estimated tokens
        conversation.total_tokens = result['total_tokens']
        db.session.commit()

        return jsonify({
            'success': True,
            'estimation': result
        })

    except TokenEstimationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error estimating conversation tokens: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/tokens/cache/stats', methods=['GET'])
@login_required
def get_token_cache_stats():
    """Get token cache statistics."""
    try:
        stats = token_service.get_cache_stats()

        # Add database cache stats
        db_cache_count = TokenCache.query.count()
        expired_db_count = TokenCache.query.filter(
            TokenCache.expires_at <= datetime.utcnow()
        ).count()

        stats.update({
            'database_cached_items': db_cache_count,
            'database_expired_items': expired_db_count
        })

        return jsonify({
            'success': True,
            'cache_stats': stats
        })

    except Exception as e:
        app.logger.error(f"Error getting cache stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/tokens/cache/clear', methods=['POST'])
@login_required
def clear_token_cache():
    """Clear token cache (memory and database)."""
    try:
        # Clear memory cache
        memory_cleared = token_service.clear_cache()

        # Clear database cache
        db_cleared = TokenCache.query.count()
        TokenCache.query.delete()
        db.session.commit()

        return jsonify({
            'success': True,
            'cleared': {
                'memory_cache': memory_cleared,
                'database_cache': db_cleared
            }
        })

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error clearing cache: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/tokens/cache/cleanup', methods=['POST'])
@login_required
def cleanup_expired_cache():
    """Clean up expired cache entries."""
    try:
        # Cleanup database cache
        expired_count = TokenCache.cleanup_expired()
        db.session.commit()

        return jsonify({
            'success': True,
            'expired_removed': expired_count
        })

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error cleaning up cache: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# WebSocket Events

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('connected', {'data': 'Connected to Claude Clone'})

@socketio.on('disconnect')
def handle_disconnect(reason=None):
    """Handle client disconnection."""
    print(f'Client disconnected: {request.sid}')

    # Clean up any active streams for this client
    # Note: We need to handle this synchronously or in a proper async context
    try:
        active_streams = streaming_service.get_active_streams()
        for stream_id in active_streams:
            # Cancel streams synchronously since we're not in an async context
            # The streaming service will handle cleanup internally
            pass  # Streams will timeout naturally
    except Exception as e:
        logger.error(f"Error during disconnect cleanup: {e}")

@socketio.on('join_conversation')
def handle_join_conversation(data):
    """Join a conversation room for real-time updates."""
    room = data['conversation_id']
    join_room(room)
    emit('joined', {'room': room}, room=room)

@socketio.on('leave_conversation')
def handle_leave_conversation(data):
    """Leave a conversation room."""
    room = data['conversation_id']
    leave_room(room)
    emit('left', {'room': room}, room=room)

@socketio.on('cancel_stream')
@async_to_sync
async def handle_cancel_stream(data):
    """Cancel an active stream."""
    stream_id = data.get('stream_id')
    if stream_id:
        await streaming_service.cancel_stream(stream_id)
        logger.info(f"Stream {stream_id} cancelled by user request")
    else:
        logger.warning("Cancel stream request without stream_id")

@socketio.on('stream_status')
def handle_stream_status(data):
    """Get status of a stream."""
    stream_id = data.get('stream_id')
    if stream_id:
        status = streaming_service.get_stream_status(stream_id)
        emit('stream_status_response', {
            'stream_id': stream_id,
            'status': status
        })
    else:
        emit('stream_status_response', {
            'error': 'No stream_id provided'
        })

@socketio.on('stream_message')
@async_to_sync
async def handle_stream_message(data):
    """Stream a message response via WebSocket with enhanced streaming."""
    try:
        conversation_id = data['conversation_id']
        content = data['content']
        room = conversation_id
        stream_id = f"stream_{conversation_id}_{int(time.time() * 1000)}"

        # Extract file information from request
        knowledge_files = data.get('knowledge_files', [])
        upload_files = data.get('upload_files', [])
        total_tokens = data.get('total_tokens', 0)

        logger.info(f"Starting stream {stream_id} for conversation {conversation_id}")
        logger.info(f"Includes {len(knowledge_files)} knowledge files, {len(upload_files)} uploads")
    except Exception as e:
        logger.error(f"Error in stream_message setup: {e}")
        emit('error', {'error': str(e)}, room=request.sid)
        return

    # Save user message
    conversation = Conversation.query.filter_by(uuid=conversation_id).first()
    if not conversation:
        emit('error', {'error': 'Conversation not found'}, room=room)
        return

    user_message = Message(
        conversation_id=conversation.id,
        role='user',
        content=content
    )
    db.session.add(user_message)
    db.session.commit()

    # Create emit function for streaming service
    def create_emit_func(room):
        async def emit_func(event, data):
            emit(event, data, room=room)
        return emit_func

    emit_func = create_emit_func(room)

    try:
        # Initialize streaming service
        await streaming_service.start_stream(stream_id, emit_func)

        # Get conversation history
        messages = []
        for msg in conversation.messages.limit(20):
            messages.append({
                'role': msg.role,
                'content': msg.content
            })

        # Get project knowledge if enabled
        project_knowledge = []
        if conversation and app.config.get('ENABLE_PROJECT_KNOWLEDGE', True):
            knowledge_links = conversation.knowledge_links.all()
            for link in knowledge_links:
                knowledge = link.knowledge
                knowledge_content = await obsidian_service.get_file_content(knowledge.vault_type, knowledge.file_path)
                if knowledge_content:
                    project_knowledge.append(f"# {knowledge.name}\n\n{knowledge_content}")

        # Get allowed tools (from permission system or request)
        allowed_tools = data.get('allowed_tools', [])
        if not allowed_tools:
            # In WebSocket context, current_user might not be available
            # Use conversation owner's ID instead
            user_id = conversation.user_id if conversation else 1
            allowed_tools = permission_manager.get_allowed_tools(user_id)

        logger.info(f"Streaming with tools: {allowed_tools}")

        # Create Claude response generator
        async def claude_generator():
            # Get the system prompt from the mode if available
            system_prompt = ""
            if conversation:
                system_prompt = conversation.custom_instructions or ""
                if conversation.mode_id:
                    mode_prompt = mode_service.get_system_prompt_for_conversation(conversation.id)
                    if mode_prompt:
                        system_prompt = mode_prompt

            async for chunk in claude_service.create_message(
                messages=messages,
                system_prompt=system_prompt,
                project_knowledge=project_knowledge,
                stream=True,  # Enable streaming
                tools=allowed_tools
            ):
                yield chunk

        # Stream response with intelligent buffering
        start_time = datetime.utcnow()
        await streaming_service.stream_with_buffering(
            stream_id,
            claude_generator(),
            ContentType.MARKDOWN
        )

        # Get final content from streaming service
        stream_status = streaming_service.get_stream_status(stream_id)
        assistant_content = stream_status.get('total_content', '') if stream_status else ''

        # For fallback, collect content manually if needed
        if not assistant_content:
            assistant_content = ""
            async for chunk in claude_generator():
                assistant_content += chunk

        # Save assistant message
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        assistant_message = Message(
            conversation_id=conversation.id,
            role='assistant',
            content=assistant_content,
            processing_time_ms=processing_time,
            model_used=conversation.model
        )
        db.session.add(assistant_message)
        conversation.updated_at = datetime.utcnow()
        db.session.commit()

        # Emit message saved event
        emit('message_saved', assistant_message.to_dict(), room=room)
        logger.info(f"Stream {stream_id} completed successfully")

    except Exception as e:
        logger.error(f"Error in stream {stream_id}: {str(e)}")
        emit('error', {
            'error': f'Streaming error: {str(e)}',
            'stream_id': stream_id
        }, room=room)

        # Cancel the stream
        await streaming_service.cancel_stream(stream_id)

# v0.3.0 - Mode Management Endpoints

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

# v0.3.0 - Export Endpoints

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

# v0.3.0 - Mobile UI Detection

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

# Download Endpoints

@app.route('/api/conversations/<uuid>/download/<format>', methods=['GET'])
@login_required
def download_conversation(uuid, format):
    """Download conversation in specified format"""
    try:
        # Get conversation
        conversation = Conversation.query.filter_by(
            uuid=uuid,
            user_id=current_user.id
        ).first()

        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        # Validate format
        if format not in ['json', 'markdown', 'pdf']:
            return jsonify({'error': 'Invalid format. Use json, markdown, or pdf'}), 400

        # Export conversation
        result = download_service.export_conversation(conversation.id, format)

        # Return as download
        from flask import Response

        if result.get('is_base64'):
            # For PDF (base64 encoded)
            import base64
            content = base64.b64decode(result['content'])
        else:
            # For JSON and Markdown
            content = result['content'].encode('utf-8')

        response = Response(
            content,
            mimetype=result['mime_type'],
            headers={
                'Content-Disposition': f'attachment; filename="{result["filename"]}"'
            }
        )
        return response

    except Exception as e:
        logger.error(f"Failed to download conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<uuid>/download-options', methods=['GET'])
@login_required
def get_download_options(uuid):
    """Get available download formats and conversation info"""
    try:
        conversation = Conversation.query.filter_by(
            uuid=uuid,
            user_id=current_user.id
        ).first()

        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        # Count messages
        message_count = Message.query.filter_by(
            conversation_id=conversation.id
        ).count()

        return jsonify({
            'title': conversation.title or 'Untitled Conversation',
            'message_count': message_count,
            'formats': [
                {
                    'format': 'markdown',
                    'label': 'Markdown (.md)',
                    'description': 'Best for reading and editing',
                    'icon': '📝'
                },
                {
                    'format': 'pdf',
                    'label': 'PDF Document',
                    'description': 'Best for sharing and printing',
                    'icon': '📄'
                },
                {
                    'format': 'json',
                    'label': 'JSON Data',
                    'description': 'Best for data processing',
                    'icon': '📊'
                }
            ]
        })
    except Exception as e:
        logger.error(f"Failed to get download options: {e}")
        return jsonify({'error': str(e)}), 500

# Error handlers

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    socketio.run(app, host=app.config['SERVER_HOST'], port=app.config['SERVER_PORT'], debug=app.config['DEBUG'])