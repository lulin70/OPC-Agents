#!/usr/bin/env bash
# OPC-Agents One-Click Launcher v0.5.9
# Usage: ./scripts/start.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     🚀 OPC-Agents v0.5.9 Launcher       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Check Python
echo -e "📋 ${YELLOW}Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.10+${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "   ✅ Python $PYTHON_VERSION"

# Step 2: Check/create virtual environment
if [ ! -d "venv" ]; then
    echo -e "📦 ${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi
source venv/bin/activate
echo -e "   ✅ Virtual environment activated"

# Step 3: Install dependencies (with progress)
echo -e "📦 ${YELLOW}Installing dependencies...${NC}"
pip install --quiet --upgrade pip 2>/dev/null || true

# Install core dependencies first (required)
if ! pip install -q -r requirements.txt 2>/dev/null; then
    echo -e "${RED}❌ Failed to install core dependencies.${NC}"
    echo -e "   Try manually: pip install -r requirements.txt"
    exit 1
fi
echo -e "   ✅ Dependencies installed"

# Step 4: Check .env file
echo -e "⚙️  ${YELLOW}Checking configuration...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "   📝 Created .env from template (please edit your API key)"
    else
        # Generate a proper encryption key for the user
        GEN_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
        if [ -n "$GEN_KEY" ]; then
            cat > .env << EOF
# OPC-Agents Configuration
OPC_ENCRYPTION_KEY=${GEN_KEY}
OPC_LOCALE=zh_CN
OPC_DATA_DIR=./data
EOF
            echo -e "   📝 Created default .env with generated encryption key"
        else
            cat > .env << 'EOF'
# OPC-Agents Configuration
# WARNING: Without OPC_ENCRYPTION_KEY, encrypted data will be lost on restart!
# Run: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Then paste the output as OPC_ENCRYPTION_KEY below.
OPC_ENCRYPTION_KEY=
OPC_LOCALE=zh_CN
OPC_DATA_DIR=./data
EOF
            echo -e "   ⚠️  Created .env WITHOUT encryption key — please add one!"
        fi
        # Write encryption key to .env.local (separate from .env template)
        if [ -n "$GEN_KEY" ]; then
            echo "OPC_ENCRYPTION_KEY=$GEN_KEY" >> .env.local
        fi
    fi
else
    echo -e "   ✅ .env found"
fi

# Step 5: Create data directory
mkdir -p data
echo -e "   ✅ Data directory ready"

echo ""
echo -e "🔍 ${YELLOW}Running pre-flight checks...${NC}"

# Check 1: Port availability
if lsof -i :8501 >/dev/null 2>&1; then
    echo -e "   ⚠️  Port 8501 is already in use. Trying 8502..."
    ALT_PORT=8502
else
    ALT_PORT=8501
fi

# Check 2: Disk space (need at least 100MB)
FREE_SPACE=$(df -k "$SCRIPT_DIR" | awk 'NR==2{print $4}')
if [ "$FREE_SPACE" -lt 102400 ]; then
    echo -e "   ⚠️  Low disk space: ${FREE_SPACE}KB available"
else
    echo -e "   ✅ Disk space OK ($(( FREE_SPACE / 1024 ))MB available)"
fi

# Check 3: Memory (warn if < 512MB free)
if command -v vm_stat &> /dev/null; then
    FREE_MEM=$(vm_stat | awk '/pages free/ {print $3}' | tr -d '.')
    FREE_MB=$(( FREE_MEM * 4096 / 1024 / 1024 ))
    if [ "$FREE_MB" -lt 512 ]; then
        echo -e "   ⚠️  Low memory: ${FREE_MB}MB free"
    else
        echo -e "   ✅ Memory OK (${FREE_MB}MB free)"
    fi
fi

echo ""

# Step 6: Auto-detect and open browser
AUTO_OPEN=""
if command -v open &> /dev/null; then
    # macOS
    AUTO_OPEN="macos"
elif command -v xdg-open &> /dev/null; then
    # Linux
    AUTO_OPEN="linux"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ Ready! Starting OPC-Agents...      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "🌐 Opening browser at http://localhost:8501 ..."
echo -e "Press Ctrl+C to stop"
echo ""

# Start Streamlit with auto-browser-open
STREAMLIT_SERVER_PORT=8501 streamlit run frontend/app.py \
    --server.port 8501 \
    --server.headless true \
    &

SERVER_PID=$!

# Open browser after a short delay
sleep 2
if [ "$AUTO_OPEN" = "macos" ]; then
    open "http://localhost:8501" 2>/dev/null || true
elif [ "$AUTO_OPEN" = "linux" ]; then
    xdg-open "http://localhost:8501" 2>/dev/null || true
fi

# Wait for server
wait $SERVER_PID 2>/dev/null
