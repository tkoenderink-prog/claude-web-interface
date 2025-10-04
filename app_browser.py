#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Main Flask application for Claude Clone with browser-based authentication."""

import os
import sys
import json
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config.config import get_config
from models.models import db, User, Conversation, Message, ProjectKnowledge, ConversationKnowledge, FileAttachment
from services.claude_browser_service import ClaudeBrowserService, ClaudeSubscriptionManager
from services.claude_service import ObsidianKnowledgeService

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(get_config())

# Initialize extensions
db.init_app(app)
CORS(app, origins=app.config['CORS_ORIGINS'])
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize services
claude_service = ClaudeBrowserService()
subscription_manager = ClaudeSubscriptionManager(claude_service)
obsidian_service = ObsidianKnowledgeService({
    'private': Path(app.config['OBSIDIAN_PRIVATE_PATH']),
    'poa': Path(app.config['OBSIDIAN_POA_PATH'])
})

# Create database tables
with app.app_context():
    db.create_all()
    # Create default user if none exists
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
    # Check if Claude is authenticated
    if not claude_service.is_authenticated():
        return redirect(url_for('claude_auth'))
    return render_template('index.html')

@app.route('/auth/claude')
def claude_auth():
    """Claude authentication page."""
    return render_template('claude_auth.html')

@app.route('/api/auth/claude/start', methods=['POST'])
@async_to_sync
async def start_claude_auth():
    """Start Claude browser authentication."""
    success = await claude_service.authenticate(headless=False)
    if success:
        # Auto-login the default user
        user = User.query.first()
        if user:
            login_user(user, remember=True)
        return jsonify({'success': True, 'message': 'Claude authentication successful!'})
    return jsonify({'success': False, 'error': 'Authentication failed'}), 401

@app.route('/api/auth/claude/status', methods=['GET'])
def claude_auth_status():
    """Check Claude authentication status."""
    return jsonify({
        'authenticated': claude_service.is_authenticated(),
        'subscription': 'Claude Max 20' if claude_service.is_authenticated() else None
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Simple login endpoint."""
    # Check if Claude is authenticated first
    if not claude_service.is_authenticated():
        return jsonify({'success': False, 'error': 'Please authenticate with Claude first'}), 401

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

@app.route('/api/subscription', methods=['GET'])
@login_required
@async_to_sync
async def get_subscription():
    """Get Claude subscription information."""
    info = await subscription_manager.get_subscription_info()
    usage = await subscription_manager.get_usage_stats()
    return jsonify({
        'subscription': info,
        'usage': usage
    })

@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get all conversations for current user."""
    conversations = current_user.conversations.filter_by(is_archived=False).order_by(Conversation.updated_at.desc()).all()
    return jsonify([c.to_dict() for c in conversations])

@app.route('/api/conversations', methods=['POST'])
@login_required
@async_to_sync
async def create_conversation():
    """Create a new conversation."""
    data = request.json

    # Create conversation in Claude.AI
    claude_conversation = await claude_service.create_conversation()

    # Save to local database
    conversation = Conversation(
        uuid=claude_conversation.get('id', str(uuid.uuid4())),
        title=data.get('title', 'New Conversation'),
        user_id=current_user.id,
        model=data.get('model', app.config['DEFAULT_MODEL']),
        custom_instructions=data.get('custom_instructions')
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

@app.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
@login_required
@async_to_sync
async def send_message(conversation_id):
    """Send a message in a conversation."""
    conversation = Conversation.query.filter_by(uuid=conversation_id, user_id=current_user.id).first_or_404()
    data = request.json

    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role='user',
        content=data['content']
    )
    db.session.add(user_message)
    db.session.commit()

    # Get project knowledge if enabled
    project_knowledge = []
    if app.config['ENABLE_PROJECT_KNOWLEDGE']:
        knowledge_links = conversation.knowledge_links.all()
        for link in knowledge_links:
            knowledge = link.knowledge
            content = await obsidian_service.get_file_content(knowledge.vault_type, knowledge.file_path)
            if content:
                project_knowledge.append(f"# {knowledge.name}\n\n{content}")

    # Prepare message with knowledge context
    message_content = data['content']
    if project_knowledge:
        context = "\n\n---\n\n".join(project_knowledge)
        message_content = f"Context from my knowledge base:\n{context}\n\nQuestion: {message_content}"

    # Get Claude's response using browser service
    assistant_content = ""
    start_time = datetime.utcnow()

    # Determine model to use
    model = conversation.model
    if model == 'claude-3-5-sonnet-20241022':
        model = 'sonnet-4.5'
    elif model == 'claude-3-opus-20240229':
        model = 'opus-4.1'

    async for chunk in claude_service.send_message(
        conversation_id=conversation.uuid,
        message=message_content,
        model=model
    ):
        assistant_content += chunk

    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    # Save assistant message
    assistant_message = Message(
        conversation_id=conversation.id,
        role='assistant',
        content=assistant_content,
        processing_time_ms=processing_time,
        model_used=model
    )
    db.session.add(assistant_message)

    # Update conversation
    conversation.updated_at = datetime.utcnow()
    if conversation.title == 'New Conversation' and len(conversation.messages.all()) <= 2:
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

    results = await obsidian_service.search_vault(vault, query, category)
    return jsonify(results)

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

        knowledge = ProjectKnowledge(
            user_id=current_user.id,
            name=Path(data['file_path']).stem,
            vault_type=data['vault'],
            file_path=data['file_path'],
            category=data.get('category', 'RESOURCE'),
            content_preview=content[:500],
            content_hash=obsidian_service.calculate_content_hash(content)
        )
        db.session.add(knowledge)

    # Link to conversation
    link = ConversationKnowledge(
        conversation_id=conversation.id,
        knowledge_id=knowledge.id,
        added_by_user=True
    )
    db.session.add(link)
    db.session.commit()

    return jsonify({'success': True, 'knowledge': knowledge.to_dict()})

@app.route('/api/upload', methods=['POST'])
@login_required
@async_to_sync
async def upload_file():
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

        # Upload to Claude if needed
        attachment = await claude_service.upload_file(filepath)

        return jsonify({
            'success': True,
            'filename': filename,
            'size': os.path.getsize(filepath),
            'claude_attachment': attachment
        })

    return jsonify({'error': 'File type not allowed'}), 400

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# WebSocket Events

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    if not claude_service.is_authenticated():
        emit('error', {'error': 'Claude not authenticated'})
        return
    emit('connected', {'data': 'Connected to Claude Clone'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f'Client disconnected: {request.sid}')

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

@socketio.on('stream_message')
@async_to_sync
async def handle_stream_message(data):
    """Stream a message response via WebSocket."""
    conversation_id = data['conversation_id']
    content = data['content']
    room = conversation_id

    # Check Claude authentication
    if not claude_service.is_authenticated():
        emit('error', {'error': 'Claude not authenticated'}, room=room)
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

    # Stream Claude's response
    emit('stream_start', room=room)
    assistant_content = ""
    start_time = datetime.utcnow()

    model = data.get('model', conversation.model)
    if model == 'claude-3-5-sonnet-20241022':
        model = 'sonnet-4.5'
    elif model == 'claude-3-opus-20240229':
        model = 'opus-4.1'

    async for chunk in claude_service.send_message(conversation.uuid, content, model=model):
        assistant_content += chunk
        emit('stream_chunk', {'chunk': chunk}, room=room)

    emit('stream_end', room=room)

    # Save assistant message
    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    assistant_message = Message(
        conversation_id=conversation.id,
        role='assistant',
        content=assistant_content,
        processing_time_ms=processing_time,
        model_used=model
    )
    db.session.add(assistant_message)
    conversation.updated_at = datetime.utcnow()
    db.session.commit()

    emit('message_saved', assistant_message.to_dict(), room=room)

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
    socketio.run(app, host=app.config['SERVER_HOST'], port=app.config['SERVER_PORT'],
                 debug=app.config['DEBUG'], allow_unsafe_werkzeug=True)