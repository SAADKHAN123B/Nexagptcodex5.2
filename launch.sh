#!/bin/bash
# ╔═══════════════════════════════════════════════════════════╗
# ║                  NexaCode Launcher                        ║
# ║          AI-Powered Terminal Coding Assistant              ║
# ╚═══════════════════════════════════════════════════════════╝

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

# Force UTF-8 encoding (fixes UnicodeEncodeError on Termux/Android)
export PYTHONIOENCODING=utf-8
export LANG="${LANG:-en_US.UTF-8}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ███╗   ██╗███████╗██╗  ██╗ █████╗  ██████╗ ██████╗ ██████╗ ███████╗"
echo "  ████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝"
echo "  ██╔██╗ ██║█████╗   ╚███╔╝ ███████║██║     ██║   ██║██║  ██║█████╗  "
echo "  ██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║██║     ██║   ██║██║  ██║██╔══╝  "
echo "  ██║ ╚████║███████╗██╔╝ ╚██╗██║  ██║╚██████╗╚██████╔╝██████╔╝███████╗"
echo "  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝"
echo -e "${NC}"

# Check Python version
if ! command -v $PYTHON &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed.${NC}"
    echo "Install Python 3.9+ to use NexaCode."
    exit 1
fi

PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$($PYTHON -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PYTHON -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]); then
    echo -e "${RED}Error: Python 3.9+ required (found $PY_VERSION)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $PY_VERSION detected${NC}"

# Check & install dependencies
check_deps() {
    $PYTHON -c "import rich, prompt_toolkit, httpx, aiosqlite, yaml" 2>/dev/null
    return $?
}

if ! check_deps; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r "$SCRIPT_DIR/requirements.txt" --quiet 2>/dev/null || \
    $PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

echo ""

# Handle command line args
if [ "$1" = "--setup" ]; then
    echo -e "${CYAN}Running setup wizard...${NC}"
    $PYTHON "$SCRIPT_DIR/nexacode.py" --setup "${@:2}"
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    $PYTHON "$SCRIPT_DIR/nexacode.py" --help
elif [ "$1" = "--version" ] || [ "$1" = "-v" ]; then
    $PYTHON "$SCRIPT_DIR/nexacode.py" --version
else
    # Launch NexaCode
    cd "${WORKSPACE:-$(pwd)}"
    $PYTHON "$SCRIPT_DIR/nexacode.py" "$@"
fi
