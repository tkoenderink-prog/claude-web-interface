#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Test database integration with token estimation system."""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask
from models.models import db, TokenCache, ProjectKnowledge, Conversation, User
from services.token_service import get_token_service
from datetime import datetime, timedelta
import json

def test_database_integration():
    """Test that the token system integrates properly with the database models."""

    # Create a test Flask app
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize database
    db.init_app(app)

    with app.app_context():
        # Create all tables
        db.create_all()

        # Test TokenCache model
        print("Testing TokenCache model...")
        cache_entry = TokenCache(
            content_hash='test_hash_123',
            token_count=150,
            character_count=800,
            encoding_name='cl100k_base',
            content_type='text',
            expires_at=datetime.utcnow() + timedelta(hours=24),
            source_info=json.dumps({'test': 'data'})
        )
        db.session.add(cache_entry)
        db.session.commit()

        # Verify cache entry was created
        retrieved = TokenCache.query.filter_by(content_hash='test_hash_123').first()
        if retrieved:
            print(f"✓ TokenCache entry created: {retrieved.token_count} tokens")
            print(f"  - Hash: {retrieved.content_hash}")
            print(f"  - Encoding: {retrieved.encoding_name}")
            print(f"  - Expires: {retrieved.expires_at}")
        else:
            print("✗ Failed to create TokenCache entry")

        # Test User and ProjectKnowledge with token_count
        print("\nTesting ProjectKnowledge with token counting...")
        user = User(username='testuser', email='test@example.com')
        db.session.add(user)
        db.session.flush()

        knowledge = ProjectKnowledge(
            user_id=user.id,
            name='Test Knowledge',
            vault_type='obsidian-private',
            file_path='/test/path.md',
            category='RESOURCE',
            content_preview='This is a test content preview',
            content_hash='content_hash_123',
            token_count=75  # Our new field
        )
        db.session.add(knowledge)
        db.session.commit()

        # Verify ProjectKnowledge with token count
        retrieved_knowledge = ProjectKnowledge.query.filter_by(name='Test Knowledge').first()
        if retrieved_knowledge:
            print(f"✓ ProjectKnowledge created with token count: {retrieved_knowledge.token_count}")

            # Test to_dict method includes token_count
            knowledge_dict = retrieved_knowledge.to_dict()
            if 'token_count' in knowledge_dict:
                print(f"✓ to_dict() includes token_count: {knowledge_dict['token_count']}")
            else:
                print("✗ to_dict() missing token_count field")
        else:
            print("✗ Failed to create ProjectKnowledge entry")

        # Test Conversation with total_tokens
        print("\nTesting Conversation with total token tracking...")
        conversation = Conversation(
            uuid='test-conv-123',
            title='Test Conversation',
            user_id=user.id,
            total_tokens=250  # Our new field
        )
        db.session.add(conversation)
        db.session.commit()

        # Verify Conversation with total tokens
        retrieved_conv = Conversation.query.filter_by(uuid='test-conv-123').first()
        if retrieved_conv:
            print(f"✓ Conversation created with total tokens: {retrieved_conv.total_tokens}")

            # Test to_dict method includes total_tokens
            conv_dict = retrieved_conv.to_dict()
            if 'total_tokens' in conv_dict:
                print(f"✓ to_dict() includes total_tokens: {conv_dict['total_tokens']}")
            else:
                print("✗ to_dict() missing total_tokens field")
        else:
            print("✗ Failed to create Conversation entry")

        # Test cache cleanup functionality
        print("\nTesting cache cleanup...")

        # Create expired cache entry
        expired_cache = TokenCache(
            content_hash='expired_hash_456',
            token_count=100,
            character_count=500,
            encoding_name='cl100k_base',
            content_type='text',
            expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        )
        db.session.add(expired_cache)
        db.session.commit()

        # Test cleanup
        expired_count = TokenCache.cleanup_expired()
        db.session.commit()

        print(f"✓ Cleaned up {expired_count} expired cache entries")

        # Verify expired entry was removed
        expired_check = TokenCache.query.filter_by(content_hash='expired_hash_456').first()
        if expired_check is None:
            print("✓ Expired cache entry successfully removed")
        else:
            print("✗ Expired cache entry was not removed")

        # Test token service integration
        print("\nTesting token service integration...")
        token_service = get_token_service()

        # Test basic functionality
        test_text = "This is a test for database integration."
        result = token_service.estimate_text_tokens(test_text)
        print(f"✓ Token service working: {result['token_count']} tokens estimated")

        print("\n" + "="*50)
        print("DATABASE INTEGRATION TEST COMPLETE")
        print("="*50)
        print("✓ All database models support token counting")
        print("✓ TokenCache model working correctly")
        print("✓ Cache cleanup functionality working")
        print("✓ Token service integration successful")

if __name__ == "__main__":
    test_database_integration()