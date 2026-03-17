#!/usr/bin/env bash
# Defty one-line installer — Linux & macOS
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/asd125202/defty/main/install.sh | bash
#
# What this does:
#   1. Installs uv (the fast Python package manager)
#   2. Installs Python 3.12 via uv
#   3. Installs the `defty` CLI tool via uv
#   4. Adds the defty command to your PATH

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[defty]${RESET} $*"; }
success() { echo -e "${GREEN}[defty]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[defty]${RESET} $*"; }
die()     { echo -e "${RED}[defty] ERROR:${RESET} $*" >&2; exit 1; }

DEFTY_REPO="https://github.com/asd125202/defty.git"
PYTHON_VERSION="3.12"

echo -e "${BOLD}"
echo "  ██████╗ ███████╗███████╗████████╗██╗   ██╗"
echo "  ██╔══██╗██╔════╝██╔════╝╚══██╔══╝╚██╗ ██╔╝"
echo "  ██║  ██║█████╗  █████╗     ██║    ╚████╔╝ "
echo "  ██║  ██║██╔══╝  ██╔══╝     ██║     ╚██╔╝  "
echo "  ██████╔╝███████╗██║        ██║      ██║   "
echo "  ╚═════╝ ╚══════╝╚═╝        ╚═╝      ╚═╝   "
echo -e "${RESET}"
echo -e "${BOLD}  Physical AI IDE — one-line installer${RESET}"
echo ""

# ── Detect OS + arch ─────────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Linux)  PLATFORM="linux" ;;
    Darwin) PLATFORM="macos" ;;
    *)      die "Unsupported OS: $OS. Use install.ps1 on Windows." ;;
esac

case "$ARCH" in
    x86_64)          ARCH_LABEL="x86_64" ;;
    aarch64|arm64)   ARCH_LABEL="arm64" ;;
    *)               die "Unsupported architecture: $ARCH" ;;
esac

info "Detected: $OS ($ARCH_LABEL)"

# ── Check prerequisites ───────────────────────────────────────────────────────
for cmd in curl; do
    command -v "$cmd" >/dev/null 2>&1 || die "'$cmd' is required but not found. Please install it."
done

# ── Step 1: Install uv ───────────────────────────────────────────────────────
info "Step 1/3 — Installing uv (Python package manager)..."

if command -v uv >/dev/null 2>&1; then
    UV_VERSION="$(uv --version 2>&1 | awk '{print $2}')"
    info "uv already installed (${UV_VERSION}), skipping download."
else
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source the uv environment
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        die "uv installation failed. Please install manually: https://docs.astral.sh/uv/"
    fi
    success "uv installed successfully."
fi

# Ensure uv is on PATH for this script
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# ── Step 2: Install Python 3.12 ──────────────────────────────────────────────
info "Step 2/3 — Installing Python ${PYTHON_VERSION} via uv..."
uv python install "${PYTHON_VERSION}"
success "Python ${PYTHON_VERSION} ready."

# ── Step 3: Install defty ─────────────────────────────────────────────────────
info "Step 3/3 — Installing defty CLI..."
uv tool install "git+${DEFTY_REPO}" --python "${PYTHON_VERSION}" --force
success "defty installed."

# ── PATH setup ────────────────────────────────────────────────────────────────
UV_TOOLS_BIN="$(uv tool dir 2>/dev/null)/bin"
if [[ ":$PATH:" != *":${UV_TOOLS_BIN}:"* ]]; then
    warn "Adding ${UV_TOOLS_BIN} to PATH..."
    SHELL_RC=""
    if [[ -n "${BASH_VERSION:-}" ]] || [[ "$(basename "${SHELL:-}")" == "bash" ]]; then
        SHELL_RC="$HOME/.bashrc"
    elif [[ -n "${ZSH_VERSION:-}" ]] || [[ "$(basename "${SHELL:-}")" == "zsh" ]]; then
        SHELL_RC="$HOME/.zshrc"
    fi
    if [[ -n "$SHELL_RC" ]]; then
        echo "" >> "$SHELL_RC"
        echo "# Added by defty installer" >> "$SHELL_RC"
        echo "export PATH=\"${UV_TOOLS_BIN}:\$PATH\"" >> "$SHELL_RC"
        warn "Restart your terminal or run: export PATH=\"${UV_TOOLS_BIN}:\$PATH\""
    fi
    export PATH="${UV_TOOLS_BIN}:$PATH"
fi

# ── Verify ───────────────────────────────────────────────────────────────────
echo ""
if command -v defty >/dev/null 2>&1; then
    DEFTY_VER="$(defty --version 2>&1)"
    success "Installation complete!  ${DEFTY_VER}"
    echo ""
    echo -e "  ${BOLD}Quick start:${RESET}"
    echo "    mkdir my-robot && cd my-robot"
    echo "    defty init"
    echo "    defty scan ports"
    echo "    defty scan cameras"
    echo ""
else
    warn "defty installed but not yet on PATH."
    warn "Run: export PATH=\"${UV_TOOLS_BIN}:\$PATH\""
    warn "Then try: defty --version"
fi