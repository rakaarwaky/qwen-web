#!/usr/bin/env bash
# Installation & environment setup script for qwen-web-cli & MCP server.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 [install] Setting up qwen-web-cli environment..."

cd "${PROJECT_ROOT}"

# 1. Virtual environment setup
VENV_DIR="${PROJECT_ROOT}/venv"
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ ! -d "${VENV_DIR}" ]; then
        echo "🐍 [install] Creating virtual environment at ${VENV_DIR}..."
        python3 -m venv "${VENV_DIR}"
    fi
    echo "⚡ [install] Activating virtual environment..."
    source "${VENV_DIR}/bin/activate"
fi

# 2. Install python package & dependencies
echo "📦 [install] Installing Python package in editable mode (qwen-web-cli / qwc)..."
pip install -e .

# 3. Install Playwright Chromium browser
echo "🌐 [install] Installing Playwright Chromium browser binary..."
python3 -m playwright install chromium

# 4. Create required XDG runtime directories
echo "📁 [install] Creating default XDG runtime directories..."
XDG_DATA="${XDG_DATA_HOME:-${HOME}/.local/share}/qwen-web-automation"
XDG_STATE="${XDG_STATE_HOME:-${HOME}/.local/state}/qwen-web-automation"
XDG_CACHE="${XDG_CACHE_HOME:-${HOME}/.cache}/qwen-web-automation"
XDG_CONFIG="${XDG_CONFIG_HOME:-${HOME}/.config}/qwen-web-automation"

ROLES="role-architect role-business-analyst role-tech-lead"
for role in $ROLES; do
    mkdir -p "${XDG_DATA}/input/${role}/done" "${XDG_DATA}/input/${role}/failed"
done
mkdir -p "${XDG_DATA}/output" "${XDG_DATA}/qwen_session"
mkdir -p "${XDG_STATE}/log"
mkdir -p "${XDG_CACHE}/.processing"
mkdir -p "${XDG_CONFIG}"

if [ -f "${PROJECT_ROOT}/SKILL.md" ]; then
    echo "📄 [install] Copying SKILL.md template to XDG data directory (${XDG_DATA}/SKILL.md)..."
    cp "${PROJECT_ROOT}/SKILL.md" "${XDG_DATA}/SKILL.md"
fi

# 5. Make entrypoints executable
echo "🔑 [install] Setting executable permissions..."
chmod +x "${SCRIPT_DIR}/install.sh" 2>/dev/null || true

# 6. Ensure ~/.local/bin is in PATH in ~/.bashrc
BASHRC="${HOME}/.bashrc"
PATH_LINE='export PATH="${HOME}/.local/bin:${PATH}"'

if [ -f "${BASHRC}" ]; then
    if ! grep -q "\.local/bin" "${BASHRC}"; then
        echo "📝 [install] Adding ~/.local/bin to PATH in ~/.bashrc..."
        echo "" >> "${BASHRC}"
        echo "# qwen-web-cli global CLI PATH" >> "${BASHRC}"
        echo "${PATH_LINE}" >> "${BASHRC}"
    fi
fi

echo "✅ [install] Setup complete!"
echo "👉 You can now run 'qwc' or 'qwen-web-cli' from anywhere in your terminal!"
echo "👉 To perform initial session login: qwc --login"
echo "👉 To start MCP server: qwc --mcp"
