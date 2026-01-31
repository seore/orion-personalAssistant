#!/bin/bash
# prepare-server.sh - Prepare the server for bundling

echo "📦 Preparing Claude server for bundling..."

# Check if orion-server exists
if [ ! -d "../orion-server" ]; then
    echo "❌ Error: orion-server directory not found!"
    echo "Expected location: ../orion-server"
    echo ""
    echo "Please create the orion-server folder at the same level as orion-assistant:"
    echo "  parent-folder/"
    echo "    ├── orion-assistant/    (this project)"
    echo "    └── orion-server/       (Claude API server)"
    exit 1
fi

cd ../orion-server

# Install server dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing server dependencies..."
    npm install --production
else
    echo "✅ Server dependencies already installed"
fi

# Create .env.example if it doesn't exist
if [ ! -f ".env.example" ]; then
    echo "📝 Creating .env.example..."
    cat > .env.example << 'ENVEOF'
# Anthropic Claude API Key
# Get yours from: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Server Port
PORT=3000
ENVEOF
fi

# Check if .env exists (for development)
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "For testing, create a .env file with your API key"
fi

cd ../orion-assistant

echo "✅ Server prepared for bundling!"
echo ""
echo "Next steps:"
echo "  1. Make sure you have an API key"
echo "  2. Update server/.env with your key for testing"
echo "  3. Run: ./build.sh"
