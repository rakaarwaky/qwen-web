#!/usr/bin/env bash
# Installation & environment setup script for qwen-web-automation & MCP server.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 [install] Setting up qwen-web-automation environment..."

cd "${PROJECT_ROOT}"

# 1. Install python requirements
if [ -f "requirements.txt" ]; then
    echo "📦 [install] Installing Python dependencies from requirements.txt..."
    pip install -r requirements.txt
fi

# 2. Install Playwright Chromium browser
echo "🌐 [install] Installing Playwright Chromium browser binary..."
python3 -m playwright install chromium

# 3. Create required runtime directories
echo "📁 [install] Creating default runtime directories..."
mkdir -p input/done input/failed input/.processing output log qwen_session

# 4. Make entrypoints executable
echo "🔑 [install] Setting executable permissions..."
chmod +x src/main.py "${SCRIPT_DIR}/install.sh" "${SCRIPT_DIR}/postinstall.sh" 2>/dev/null || true

echo "✅ [install] Setup complete!"
echo "👉 To perform initial session login, run: python3 src/main.py --login"
echo "👉 To start MCP server, run: python3 src/main.py --mcp"
