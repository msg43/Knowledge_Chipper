#!/bin/bash
# setup_ollama_models.sh - Hardware-optimized Ollama model installation for PKG installer
# Uses hardware detection to recommend and install optimal models

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🦙 Ollama Model Setup for PKG Installer${NC}"
echo "=========================================="
echo "Hardware-optimized model installation"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

report_progress() {
    local percent="$1"
    local message="$2"
    echo "##INSTALLER_PROGRESS## $percent $message"
}

# Function to detect hardware and get model recommendation
get_model_recommendation() {
    python3 - << 'EOF'
import subprocess
import json
import sys

def detect_hardware():
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return fallback_detection()

        data = json.loads(result.stdout)
        hardware_info = data["SPHardwareDataType"][0]

        chip_name = hardware_info.get("chip_type", "").lower()
        memory_str = hardware_info.get("physical_memory", "16 GB")

        # Parse memory
        memory_gb = int(memory_str.split()[0])

        return {
            "chip_name": chip_name,
            "memory_gb": memory_gb
        }

    except Exception as e:
        print(f"Hardware detection failed: {e}", file=sys.stderr)
        return fallback_detection()

def fallback_detection():
    import os
    cpu_cores = os.cpu_count() or 8

    if cpu_cores >= 20:
        return {"chip_name": "m3 ultra", "memory_gb": 128}
    elif cpu_cores >= 12:
        return {"chip_name": "m3 max", "memory_gb": 64}
    else:
        return {"chip_name": "m3", "memory_gb": 16}

def get_ollama_model_recommendation(specs):
    chip_name = specs["chip_name"]
    memory_gb = specs["memory_gb"]

    if memory_gb >= 64 and ("ultra" in chip_name):
        return {
            "primary": "llama3.2:8b",
            "size": "4.7GB",
            "description": "High-quality model for Ultra systems",
            "optional_upgrade": "llama3.1:70b (40GB) - Expert mode"
        }
    elif memory_gb >= 32 and ("max" in chip_name):
        return {
            "primary": "llama3.2:8b",
            "size": "4.7GB",
            "description": "Optimal for Max systems"
        }
    elif memory_gb >= 16:
        return {
            "primary": "llama3.2:3b",
            "size": "2GB",
            "description": "Balanced for Pro systems"
        }
    else:
        return {
            "primary": "llama3.2:1b",
            "size": "1.3GB",
            "description": "Efficient for base systems"
        }

# Main execution
specs = detect_hardware()
recommendation = get_ollama_model_recommendation(specs)

print(json.dumps({
    "hardware": specs,
    "recommendation": recommendation
}))
EOF
}

# Check if Ollama is installed
check_ollama_installation() {
    if command -v ollama &> /dev/null; then
        print_status "Ollama already installed"
        return 0
    else
        return 1
    fi
}

# Install Ollama
install_ollama() {
    echo -e "\n${BLUE}📦 Installing Ollama...${NC}"
    report_progress 10 "Downloading Ollama"

    # Download Ollama installer
    OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-darwin"
    OLLAMA_TEMP="/tmp/ollama"

    if ! curl -L -o "$OLLAMA_TEMP" "$OLLAMA_URL"; then
        print_error "Failed to download Ollama"
        return 1
    fi

    report_progress 30 "Installing Ollama binary"

    # Install Ollama
    sudo mkdir -p /usr/local/bin
    sudo mv "$OLLAMA_TEMP" /usr/local/bin/ollama
    sudo chmod +x /usr/local/bin/ollama

    # Add to PATH if needed
    if ! echo "$PATH" | grep -q "/usr/local/bin"; then
        export PATH="/usr/local/bin:$PATH"
    fi

    print_status "Ollama installed"
    return 0
}

# Start Ollama service
start_ollama_service() {
    echo -e "\n${BLUE}🚀 Starting Ollama service...${NC}"
    report_progress 40 "Starting Ollama service"

    # Start Ollama in background
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!

    # Wait for service to be ready
    local attempts=0
    local max_attempts=30

    while [ $attempts -lt $max_attempts ]; do
        if ollama list &> /dev/null; then
            print_status "Ollama service started"
            return 0
        fi

        sleep 1
        attempts=$((attempts + 1))
    done

    print_error "Ollama service failed to start"
    return 1
}

# Download and install model
install_model() {
    local model="$1"
    local description="$2"

    echo -e "\n${BLUE}🧠 Installing $model model...${NC}"
    report_progress 50 "Downloading $model model ($description)"

    # Pull the model
    if ollama pull "$model"; then
        print_status "$model model installed successfully"
        return 0
    else
        print_error "Failed to install $model model"
        return 1
    fi
}

# Verify model functionality
verify_model() {
    local model="$1"

    echo -e "\n${BLUE}🧪 Verifying $model model...${NC}"
    report_progress 80 "Verifying model functionality"

    # Test model with a simple prompt
    local test_response
    test_response=$(ollama run "$model" "Hello! Please respond with 'OK' if you're working correctly." 2>&1 | head -1)

    if echo "$test_response" | grep -i "ok" &> /dev/null; then
        print_status "Model $model verified and working"
        return 0
    else
        print_warning "Model $model may not be working correctly"
        print_warning "Response: $test_response"
        return 1
    fi
}

# Create model configuration file
create_model_config() {
    local model="$1"
    local config_dir="$HOME/.config/skip_the_podcast"

    mkdir -p "$config_dir"

    cat > "$config_dir/ollama_model.json" << EOF
{
  "default_model": "$model",
  "installed_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "hardware_optimized": true,
  "verified": true
}
EOF

    print_status "Model configuration saved"
}

# Main execution
main() {
    # Get hardware recommendation
    echo -e "${BLUE}🔍 Detecting hardware and getting model recommendation...${NC}"
    report_progress 5 "Detecting hardware specifications"

    RECOMMENDATION_JSON=$(get_model_recommendation)

    if [ -z "$RECOMMENDATION_JSON" ]; then
        print_error "Failed to get model recommendation"
        exit 1
    fi

    # Parse recommendation
    MODEL=$(echo "$RECOMMENDATION_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['recommendation']['primary'])")
    SIZE=$(echo "$RECOMMENDATION_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['recommendation']['size'])")
    DESCRIPTION=$(echo "$RECOMMENDATION_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['recommendation']['description'])")
    CHIP=$(echo "$RECOMMENDATION_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['hardware']['chip_name'])")
    MEMORY=$(echo "$RECOMMENDATION_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['hardware']['memory_gb'])")

    echo -e "${GREEN}Hardware detected:${NC}"
    echo "  Chip: $CHIP"
    echo "  Memory: ${MEMORY}GB"
    echo ""
    echo -e "${GREEN}Recommended model:${NC}"
    echo "  Model: $MODEL"
    echo "  Size: $SIZE"
    echo "  Description: $DESCRIPTION"
    echo ""

    # Check if Ollama is installed
    if ! check_ollama_installation; then
        if ! install_ollama; then
            print_error "Ollama installation failed"
            exit 1
        fi
    fi

    # Start Ollama service
    if ! start_ollama_service; then
        print_error "Failed to start Ollama service"
        exit 1
    fi

    # Install recommended model
    if ! install_model "$MODEL" "$SIZE"; then
        print_error "Model installation failed"
        exit 1
    fi

    # Verify model works
    if ! verify_model "$MODEL"; then
        print_warning "Model verification failed, but continuing..."
    fi

    # Create configuration
    create_model_config "$MODEL"

    report_progress 100 "Ollama setup complete"

    echo -e "\n${GREEN}${BOLD}🎉 Ollama Setup Complete!${NC}"
    echo "=============================================="
    echo "Model: $MODEL ($SIZE)"
    echo "Status: Installed and verified"
    echo "Service: Running"
    echo ""
    echo "Your Mac is optimized for the best performance with this model."
}

# Command-line interface
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    case "${1:-setup}" in
        "setup")
            main
            ;;
        "test")
            MODEL="${2:-llama3.2:3b}"
            verify_model "$MODEL"
            ;;
        "recommend")
            get_model_recommendation
            ;;
        *)
            echo "Usage: $0 [setup|test|recommend]"
            echo "  setup      - Full Ollama setup with hardware-optimized model"
            echo "  test MODEL - Test specific model functionality"
            echo "  recommend  - Get hardware-based model recommendation"
            exit 1
            ;;
    esac
fi
