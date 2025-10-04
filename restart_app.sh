#!/bin/bash

# Quick restart script for applying changes

echo "🔄 Restarting Claude Agent SDK Web Interface..."
echo ""

# Kill any existing servers
echo "Stopping existing servers..."
lsof -ti:5000 | xargs kill -9 2>/dev/null
lsof -ti:5001 | xargs kill -9 2>/dev/null

sleep 1

echo "Starting fresh instance..."
echo ""

# Run the launch script
./launch.sh