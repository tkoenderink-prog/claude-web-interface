#!/bin/bash

# Claude Clone - Quick Start

echo "🚀 Starting Claude Clone..."
echo ""

# Create necessary directories
mkdir -p data static/uploads

# Start the app with proper host binding
echo "✅ Server starting on multiple addresses:"
echo "   • http://localhost:5000"
echo "   • http://127.0.0.1:5000"
echo "   • http://0.0.0.0:5000"
echo ""
echo "📝 Try all URLs if one doesn't work!"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start with explicit host binding
/opt/homebrew/opt/python@3.11/bin/python3.11 -c "
import sys
sys.path.insert(0, '.')
from app_simple import app, socketio

# Override host to ensure it works
app.config['SERVER_HOST'] = '0.0.0.0'

print('Starting server on 0.0.0.0:5000...')
socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
"