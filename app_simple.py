#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Simple Flask app using session key authentication."""

import os
import sys
import json
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

sys.path.insert(0, str(Path(__file__).parent))

from config.config import get_config
from models.models import db, User, Conversation, Message, ProjectKnowledge, ConversationKnowledge, FileAttachment
from services.claude_api_service import ClaudeAPIService
from services.claude_service import ObsidianKnowledgeService

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(get_config())

# Initialize extensions
db.init_app(app)
CORS(app, origins=app.config['CORS_ORIGINS'])
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager(app)
login_manager.login_view = 'auth'

# Initialize services
claude_service = ClaudeAPIService()
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
    return User.query.get(int(user_id))

def async_to_sync(f):
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
    if not claude_service.is_authenticated():
        return redirect(url_for('auth'))

    # Auto-login the default user if not logged in
    if not current_user.is_authenticated:
        user = User.query.first()
        if user:
            login_user(user, remember=True)

    return render_template('index.html')

@app.route('/auth')
def auth():
    """Simple authentication page."""
    return render_template('simple_auth.html')

@app.route('/api/auth/session', methods=['POST'])
@async_to_sync
async def set_session():
    """Set Claude session key."""
    data = request.json
    session_key = data.get('session_key')
    organization_id = data.get('organization_id')

    if not session_key:
        return jsonify({'success': False, 'error': 'Session key required'}), 400

    # Set the session key
    await claude_service.set_session_key(session_key, organization_id)

    # Auto-login the default user
    user = User.query.first()
    if user:
        login_user(user, remember=True)
    return jsonify({'success': True, 'message': 'Session key saved successfully'})

@app.route('/api/auth/session/status', methods=['GET'])
def session_status():
    """Check session authentication status."""
    return jsonify({
        'authenticated': claude_service.is_authenticated()
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout and clear session."""
    claude_service.clear_session()
    logout_user()
    return jsonify({'success': True})

@app.route('/api/test', methods=['POST'])
@async_to_sync
async def test_message():
    """Test Claude connection."""
    if not claude_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.json
    message = data.get('message', 'Hello')

    response = ""
    async for chunk in claude_service.create_message('test-conversation', message):
        response += chunk

    return jsonify({'response': response})

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

    # Create conversation in Claude
    claude_conv = await claude_service.create_conversation()

    # Save to local database
    conversation = Conversation(
        uuid=claude_conv.get('uuid', str(uuid.uuid4())),
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
    if not claude_service.is_authenticated():
        return jsonify({'error': 'Claude session expired. Please re-authenticate.'}), 401

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

    # Get Claude's response
    assistant_content = ""
    start_time = datetime.utcnow()

    # Determine model
    model = conversation.model
    if model == 'claude-3-5-sonnet-20241022':
        model = 'sonnet-4.5'
    elif model == 'claude-3-opus-20240229':
        model = 'opus-4.1'

    async for chunk in claude_service.create_message(
        conversation_id=conversation.uuid,
        prompt=message_content
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

    link = ConversationKnowledge(
        conversation_id=conversation.id,
        knowledge_id=knowledge.id,
        added_by_user=True
    )
    db.session.add(link)
    db.session.commit()

    return jsonify({'success': True, 'knowledge': knowledge.to_dict()})

# WebSocket Events

@socketio.on('connect')
def handle_connect():
    print("WebSocket client connected")
    if not claude_service.is_authenticated():
        print("Claude not authenticated in WebSocket")
        emit('error', {'error': 'Claude not authenticated'})
        return
    print("Claude authenticated, WebSocket ready")
    emit('connected', {'data': 'Connected to Claude Clone'})

@socketio.on('join_conversation')
def handle_join_conversation(data):
    """Join a conversation room for WebSocket events."""
    conversation_id = data.get('conversation_id')
    if conversation_id:
        join_room(conversation_id)
        print(f"Client joined conversation room: {conversation_id}")
        emit('joined', {'conversation_id': conversation_id}, room=conversation_id)

@socketio.on('stream_message')
@async_to_sync
async def handle_stream_message(data):
    """Stream a message response via WebSocket."""
    print(f"Received stream_message: {data}")

    if not claude_service.is_authenticated():
        print("Claude not authenticated")
        emit('error', {'error': 'Claude session expired'})
        return

    conversation_id = data['conversation_id']
    content = data['content']
    room = conversation_id

    conversation = Conversation.query.filter_by(uuid=conversation_id).first()
    if not conversation:
        print(f"Conversation not found: {conversation_id}")
        emit('error', {'error': 'Conversation not found'}, room=room)
        return

    print(f"Found conversation: {conversation.id}, uuid: {conversation.uuid}")

    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role='user',
        content=content
    )
    db.session.add(user_message)
    db.session.commit()

    # Get conversation history
    messages = []
    for msg in conversation.messages.order_by(Message.created_at).all():
        messages.append({
            'role': msg.role,
            'content': msg.content
        })

    emit('stream_start', room=room)
    assistant_content = ""
    start_time = datetime.utcnow()

    try:
        print(f"Calling Claude API with conversation_id: {conversation.uuid}, content: {content[:50]}...")
        async for chunk in claude_service.create_message(conversation_id=conversation.uuid, prompt=content):
            assistant_content += chunk
            emit('stream_chunk', {'chunk': chunk}, room=room)
        print(f"Claude response complete: {len(assistant_content)} characters")
    except Exception as e:
        print(f"Error calling Claude API: {e}")
        emit('error', {'error': str(e)}, room=room)
        return

    emit('stream_end', room=room)

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
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    socketio.run(app, host=app.config['SERVER_HOST'], port=app.config['SERVER_PORT'],
                 debug=app.config['DEBUG'], allow_unsafe_werkzeug=True)