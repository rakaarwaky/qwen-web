#!/usr/bin/env bash
# Installation & environment setup script for qwen-web-cli & MCP server.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 [install] Setting up qwen-web-cli environment..."

cd "${PROJECT_ROOT}"

# 0. Clean uninstall of any previous install so stale copies (with old code) do not linger
echo "🧹 [install] Removing any previous qwen-web installation..."
pip uninstall -y qwen-web 2>/dev/null || true
python3 -m pip uninstall -y qwen-web 2>/dev/null || true
rm -f "${HOME}/.local/bin/qwen-web-cli" "${HOME}/.local/bin/qwc" 2>/dev/null || true

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

# 4b. Ensure the real browser session directory used by the app has correct
#     permissions. Chromium needs the execute bit on the profile dir; a missing
#     bit causes "Failed to create a ProcessSingleton ... Permission denied".
#     Derive the path from the app config (DEFAULT_SESSION) so it stays in sync
#     with cfg.session_path; fall back to the documented default if the venv
#     python is not available yet.
APP_SESSION_DIR="$("${VENV_DIR}/bin/python" -c 'from modules.shared.src.taxonomy_core_constant import DEFAULT_SESSION; print(DEFAULT_SESSION)' 2>/dev/null || true)"
if [ -z "${APP_SESSION_DIR}" ]; then
    APP_SESSION_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/qwen-web/qwen_session"
fi
echo "🔐 [install] Repairing browser session dir permissions: ${APP_SESSION_DIR}"
mkdir -p "${APP_SESSION_DIR}"
chmod 700 "${APP_SESSION_DIR}" 2>/dev/null || true

if [ -f "${PROJECT_ROOT}/SKILL.md" ]; then
    echo "📄 [install] Copying SKILL.md template to XDG data directory (${XDG_DATA}/SKILL.md)..."
    cp "${PROJECT_ROOT}/SKILL.md" "${XDG_DATA}/SKILL.md"
fi

# 5. Link entrypoints into ~/.local/bin (so the freshly installed venv copy runs,
#    not a stale system-python copy left behind by a previous install)
echo "🔑 [install] Linking entry points into ~/.local/bin..."
chmod +x "${SCRIPT_DIR}/install.sh" 2>/dev/null || true
mkdir -p "${HOME}/.local/bin"
ln -sf "${VENV_DIR}/bin/qwen-web-cli" "${HOME}/.local/bin/qwen-web-cli"
ln -sf "${VENV_DIR}/bin/qwc" "${HOME}/.local/bin/qwc" 2>/dev/null || true

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
