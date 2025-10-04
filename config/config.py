#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Configuration module for Claude Clone Flask application."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # Database
    BASE_DIR = Path(__file__).parent.parent
    DATABASE_PATH = BASE_DIR / 'data' / 'claude_clone.db'
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Use absolute path for SQLite (spaces in path are OK without encoding)
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f'sqlite:///{DATABASE_PATH}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Claude Configuration (No API key needed - uses browser auth)
    DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'sonnet-4.5')
    AVAILABLE_MODELS = ['sonnet-4.5', 'opus-4.1', 'haiku']
    MAX_TOKENS = int(os.getenv('MAX_TOKENS', '4096'))
    TEMPERATURE = float(os.getenv('TEMPERATURE', '0.7'))
    USE_BROWSER_AUTH = True  # Uses Claude Max 20 subscription

    # Obsidian Vault Paths
    OBSIDIAN_PRIVATE_PATH = Path(os.getenv('OBSIDIAN_PRIVATE_PATH', '../Obsidian-Private'))
    OBSIDIAN_POA_PATH = Path(os.getenv('OBSIDIAN_POA_PATH', '../Obsidian-POA'))

    # Server
    SERVER_HOST = os.getenv('SERVER_HOST', '127.0.0.1')
    SERVER_PORT = int(os.getenv('SERVER_PORT', '5000'))

    # Session
    SESSION_LIFETIME_MINUTES = int(os.getenv('SESSION_LIFETIME_MINUTES', '1440'))
    PERMANENT_SESSION_LIFETIME = SESSION_LIFETIME_MINUTES * 60

    # Upload
    UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'md', 'py', 'js', 'html', 'css', 'json', 'yaml', 'yml'}

    # Feature Flags
    ENABLE_WEBSOCKET = os.getenv('ENABLE_WEBSOCKET', 'true').lower() == 'true'
    ENABLE_FILE_UPLOAD = os.getenv('ENABLE_FILE_UPLOAD', 'true').lower() == 'true'
    ENABLE_PROJECT_KNOWLEDGE = os.getenv('ENABLE_PROJECT_KNOWLEDGE', 'true').lower() == 'true'
    ENABLE_CONVERSATION_EXPORT = os.getenv('ENABLE_CONVERSATION_EXPORT', 'true').lower() == 'true'

    # CORS
    CORS_ORIGINS = ['http://localhost:5000', 'http://127.0.0.1:5000', 'http://0.0.0.0:5000', '*']

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("FLASK_SECRET_KEY must be set in production")

    # Use PostgreSQL in production if available
    DATABASE_URL = os.getenv('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or Config.SQLALCHEMY_DATABASE_URI

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment."""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])