#!/bin/bash
# post-install.sh - First run setup for users

echo "================================"
echo "   Titan Assistant Setup"
echo "================================"
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    RESOURCES_PATH="/Applications/Titan.app/Contents/Resources"
    ENV_FILE="$RESOURCES_PATH/server/.env"
else
    echo "This script is for macOS. Windows users see README."
    exit 1
fi

echo "This is your first time running Titan!"
echo "We need to set up your Claude API key."
echo ""

# Check if .env already exists
if [ -f "$ENV_FILE" ]; then
    echo "✅ API key already configured!"
    echo ""
    read -p "Do you want to update it? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

echo "Step 1: Get Your API Key"
echo "  1. Visit: https://console.anthropic.com/"
echo "  2. Sign up or log in"
echo "  3. Go to API Keys"
echo "  4. Create a new key"
echo ""

read -p "Paste your API key here: " api_key

if [ -z "$api_key" ]; then
    echo "❌ No API key provided. Setup cancelled."
    exit 1
fi

# Validate key format
if [[ ! $api_key =~ ^sk-ant- ]]; then
    echo "⚠️  Warning: API key should start with 'sk-ant-'"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create .env file
echo "ANTHROPIC_API_KEY=$api_key" > "$ENV_FILE"
echo "PORT=3000" >> "$ENV_FILE"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Titan is ready to use!"
echo "Say 'Hey Titan' to get started."
echo ""