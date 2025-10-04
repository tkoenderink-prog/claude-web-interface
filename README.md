# Claude Agent SDK Web Interface for Obsidian Vaults

A Flask-based web application that provides a Claude-powered interface for interacting with Obsidian vaults using the official Claude Agent SDK (October 2025).

## Features

- **Official Claude Agent SDK**: Uses the `claude-agent-sdk` Python package (v0.1.0)
- **Chat Interface**: Clean, modern UI similar to Claude.AI
- **Streaming Responses**: Real-time response generation
- **Project Knowledge**: Integration with Obsidian vaults (Private & POA)
- **Conversation Management**: Save, load, and export conversations
- **Claude Tools Support**: Enable Read, Write, WebFetch tools
- **Session Management**: Persistent conversation sessions
- **Dark Mode**: Toggle between light and dark themes

## Installation

### Prerequisites
- Python 3.11 (at `/opt/homebrew/opt/python@3.11/bin/python3.11`)
- Node.js (for Claude Code CLI - optional)
- PostgreSQL or SQLite for database

### Install Dependencies
```bash
# Install Claude Agent SDK and Flask dependencies
/opt/homebrew/opt/python@3.11/bin/python3.11 -m pip install --break-system-packages \
    claude-agent-sdk flask flask-cors flask-socketio flask-login flask-sqlalchemy

# Optional: Install Claude Code CLI
npm install -g @anthropic-ai/claude-code
```

## Quick Start

1. **Configure environment**:
   ```bash
   # Create .env file
   cp .env.example .env

   # For Claude subscription (recommended):
   # Leave ANTHROPIC_API_KEY unset

   # For API billing:
   # Set ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

2. **Run the application**:
   ```bash
   /opt/homebrew/opt/python@3.11/bin/python3.11 app.py
   ```

3. **Open in browser**:
   Navigate to http://localhost:5000

## Project Structure

```
web-interface/
├── app.py                 # Main Flask application
├── config/
│   └── config.py         # Configuration management
├── models/
│   └── models.py         # Database models
├── services/
│   └── claude_service.py # Claude Agent SDK integration
├── static/
│   ├── css/             # Stylesheets
│   ├── js/              # JavaScript application
│   └── uploads/         # File uploads directory
├── templates/           # HTML templates
├── data/               # SQLite database storage
└── requirements.txt    # Python dependencies
```

## Obsidian Vault Integration

The application automatically connects to your Obsidian vaults:

- **Obsidian-Private**: Personal knowledge management vault
- **Obsidian-POA**: Professional work vault

Files are organized using the PARA method:
- 01-PROJECTS: Active projects
- 02-AREAS: Ongoing responsibilities
- 03-RESOURCES: Reference materials
- 04-ARCHIVE: Completed items

## Using Project Knowledge

1. Click the book icon in the chat header
2. Select a vault (Private or POA)
3. Search for files or browse by category
4. Select files to add as context
5. Claude will use these files to enhance responses

## API Configuration

The app uses your Claude Max 20 subscription via the Anthropic API. Features:

- Automatic fallback between models
- Token usage tracking
- Rate limiting protection
- Error handling and retries

## Docker Deployment

For production deployment:

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

## Development

To modify the application:

1. Frontend: Edit `static/js/app.js` and `static/css/style.css`
2. Backend: Modify `app.py` and `services/claude_service.py`
3. Database: Update models in `models/models.py`

## Advanced Features

### Custom Instructions
Set per-conversation instructions to guide Claude's behavior

### Export Conversations
Download conversations as JSON for backup or analysis

### WebSocket Streaming
Real-time message streaming for instant feedback

### Multi-Agent Support
Leverage specialized agents for different tasks:
- Research agents for information gathering
- Coding agents for development tasks
- Review agents for analysis
- Organization agents for structuring data

## Troubleshooting

**API Key Issues**: Ensure your ANTHROPIC_API_KEY is correctly set in .env

**Database Errors**: Delete `data/claude_clone.db` to reset

**Connection Issues**: Check firewall settings for port 5000

**Vault Access**: Ensure Obsidian vault paths are correct in .env

## Security Notes

- Never commit .env file with real API keys
- Use strong SECRET_KEY in production
- Enable HTTPS for production deployment
- Regularly backup your database

## Support

For issues or questions about:
- Claude Agent SDK: See `claude-agent-sdk.md`
- Requirements: See `needed-from-user.md`
- Obsidian integration: Check vault CLAUDE.md files