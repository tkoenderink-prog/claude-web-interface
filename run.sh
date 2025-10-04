#!/bin/bash

# Claude Clone - Run Script

echo "🚀 Starting Claude Clone Flask Application..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env file and add your ANTHROPIC_API_KEY"
    echo "   Then run this script again."
    exit 1
fi

# Check if API key is set
if grep -q "your_api_key_here" .env; then
    echo "❌ Error: Please set your ANTHROPIC_API_KEY in the .env file"
    exit 1
fi

# Create necessary directories
mkdir -p data static/uploads

# Install dependencies if needed
echo "📦 Checking dependencies..."
/opt/homebrew/opt/python@3.11/bin/python3.11 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    /opt/homebrew/bin/pip3 install --break-system-packages -r requirements.txt
fi

# Run the application
echo "✅ Starting Flask application..."
echo "🌐 Open http://localhost:5000 in your browser"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

/opt/homebrew/opt/python@3.11/bin/python3.11 app.py