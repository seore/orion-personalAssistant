#!/bin/bash
# build.sh - Automated Orion build script

set -e  # Exit on error

echo "🚀 Building Orion Assistant..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if electron-builder is installed
if ! npm list electron-builder &> /dev/null; then
    echo -e "${YELLOW}Installing electron-builder...${NC}"
    npm install --save-dev electron-builder
fi

# Verify build directory exists
if [ ! -d "build" ]; then
    echo -e "${RED}Error: build/ directory not found!${NC}"
    echo "Please create build/ and add:"
    echo "  - icon.icns (macOS icon)"
    echo "  - entitlements.mac.plist"
    exit 1
fi

# Check for icon
if [ ! -f "build/icon.icns" ]; then
    echo -e "${YELLOW}Warning: build/icon.icns not found${NC}"
    echo "App will use default Electron icon"
fi

# Check for entitlements
if [ ! -f "build/entitlements.mac.plist" ]; then
    echo -e "${YELLOW}Warning: build/entitlements.mac.plist not found${NC}"
    echo "Creating default entitlements..."
    cat > build/entitlements.mac.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.device.audio-input</key>
    <true/>
    <key>com.apple.security.automation.apple-events</key>
    <true/>
  </dict>
</plist>
PLIST
fi

# Clean previous builds
echo -e "${GREEN}Cleaning previous builds...${NC}"
rm -rf dist/

# Install dependencies
echo -e "${GREEN}Installing dependencies...${NC}"
npm install

# Build for current platform
echo ""
echo -e "${GREEN}Building Orion for macOS...${NC}"
echo "This may take a few minutes..."
echo ""

npm run dist:mac

# Check if build succeeded
if [ -d "dist" ] && [ "$(ls -A dist)" ]; then
    echo ""
    echo -e "${GREEN}✅ Build completed successfully!${NC}"
    echo ""
    echo "Built files:"
    ls -lh dist/
    echo ""
    echo "To test the app:"
    echo "  1. Open dist/mac/Orion.app"
    echo "  2. Or install from dist/Orion-*.dmg"
    echo ""
    echo "To distribute:"
    echo "  - Share the DMG file with users"
    echo "  - Include USER_SETUP_GUIDE.md"
    echo "  - Include the orion-server folder"
else
    echo -e "${RED}❌ Build failed!${NC}"
    echo "Check the output above for errors"
    exit 1
fi
