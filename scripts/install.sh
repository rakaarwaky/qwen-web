#!/usr/bin/env bash
# Installation & environment setup script for qwen-web-automation & MCP server.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 [install] Setting up qwen-web-automation environment..."

cd "${PROJECT_ROOT}"

# 1. Install python package & dependencies
echo "📦 [install] Installing Python package in editable mode (qwen-cli)..."
pip install -e .

# 2. Install Playwright Chromium browser
echo "🌐 [install] Installing Playwright Chromium browser binary..."
python3 -m playwright install chromium

# 3. Create required XDG runtime directories
echo "📁 [install] Creating default XDG runtime directories..."
XDG_DATA="${XDG_DATA_HOME:-${HOME}/.local/share}/qwen-web-automation"
XDG_STATE="${XDG_STATE_HOME:-${HOME}/.local/state}/qwen-web-automation"
XDG_CACHE="${XDG_CACHE_HOME:-${HOME}/.cache}/qwen-web-automation"
XDG_CONFIG="${XDG_CONFIG_HOME:-${HOME}/.config}/qwen-web-automation"

mkdir -p "${XDG_DATA}/input/done" "${XDG_DATA}/input/failed" "${XDG_DATA}/output" "${XDG_DATA}/qwen_session"
mkdir -p "${XDG_STATE}/log"
mkdir -p "${XDG_CACHE}/.processing"
mkdir -p "${XDG_CONFIG}"

# Also keep local repo fallback dirs for local testing
mkdir -p input/done input/failed input/.processing output log qwen_session

# 4. Make entrypoints executable
echo "🔑 [install] Setting executable permissions..."
chmod +x src/main.py "${SCRIPT_DIR}/install.sh" 2>/dev/null || true

# 5. Ensure ~/.local/bin is in PATH in ~/.bashrc
BASHRC="${HOME}/.bashrc"
PATH_LINE='export PATH="${HOME}/.local/bin:${PATH}"'

if [ -f "${BASHRC}" ]; then
    if ! grep -q "\.local/bin" "${BASHRC}"; then
        echo "📝 [install] Adding ~/.local/bin to PATH in ~/.bashrc..."
        echo "" >> "${BASHRC}"
        echo "# qwen-web-automation global CLI PATH" >> "${BASHRC}"
        echo "${PATH_LINE}" >> "${BASHRC}"
    fi
fi

echo "✅ [install] Setup complete!"
echo "👉 You can now run 'qwen-cli' from anywhere in your terminal!"
echo "👉 To perform initial session login: qwen-cli --login"
echo "👉 To start MCP server: qwen-cli --mcp"
