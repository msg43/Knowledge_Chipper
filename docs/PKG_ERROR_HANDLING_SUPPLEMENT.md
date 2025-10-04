# PKG Migration Plan - Error Handling & Testing Supplement

## **Error Handling & Recovery Mechanisms**

### **1. Fallback Mechanisms for Download Failures**

#### **Multi-Source Download Strategy**
```bash
# Primary → Secondary → Tertiary sources
DOWNLOAD_SOURCES=(
    "https://github.com/your-repo/releases/latest/download/"
    "https://cdn.skipthepodcast.com/releases/"
    "https://backup.skipthepodcast.com/releases/"
)

download_with_fallback() {
    local file="$1"
    local max_retries=3
    
    for source in "${DOWNLOAD_SOURCES[@]}"; do
        for attempt in $(seq 1 $max_retries); do
            echo "Attempting download from $source (attempt $attempt/$max_retries)"
            
            if curl -L --fail --retry 2 --retry-delay 5 \
                   --connect-timeout 30 --max-time 1800 \
                   -o "/tmp/$file" "${source}${file}"; then
                echo "✅ Successfully downloaded $file from $source"
                return 0
            fi
            
            echo "❌ Download failed, retrying in 10 seconds..."
            sleep 10
        done
        echo "⚠️ All attempts failed for $source, trying next source..."
    done
    
    echo "❌ CRITICAL: All download sources failed for $file"
    return 1
}
```

#### **Partial Download Resume**
```bash
# Resume interrupted downloads
download_with_resume() {
    local url="$1"
    local output="$2"
    local expected_size="$3"
    
    # Check if partial file exists
    if [ -f "$output.partial" ]; then
        local current_size=$(stat -f%z "$output.partial" 2>/dev/null || echo "0")
        echo "Resuming download from byte $current_size"
        
        curl -L -C "$current_size" -o "$output.partial" "$url"
    else
        curl -L -o "$output.partial" "$url"
    fi
    
    # Verify download completed
    local final_size=$(stat -f%z "$output.partial" 2>/dev/null || echo "0")
    if [ "$final_size" -eq "$expected_size" ]; then
        mv "$output.partial" "$output"
        return 0
    else
        echo "❌ Download incomplete: $final_size/$expected_size bytes"
        return 1
    fi
}
```

#### **Degraded Installation Mode**
```bash
# Install with minimal components if full install fails
install_minimal_mode() {
    echo "🔄 Entering minimal installation mode..."
    echo "Installing core components only:"
    echo "  ✅ App skeleton"
    echo "  ✅ Python framework"
    echo "  ✅ Essential models only"
    echo "  ⚠️ Advanced features will download on first use"
    
    # Install only critical components
    install_python_framework || return 1
    install_whisper_base_model || return 1
    install_essential_dependencies || return 1
    
    # Mark as minimal install
    touch "/Applications/Skip the Podcast Desktop.app/Contents/Resources/minimal_install"
    
    echo "✅ Minimal installation complete"
    echo "💡 Additional components will download when first needed"
}
```

### **2. Checksum Verification Implementation**

#### **SHA256 Verification System**
```bash
# Create checksums.sha256 file for each release
create_checksums() {
    cd dist/
    
    # Generate checksums for all components
    shasum -a 256 *.pkg *.tar.gz *.dmg > checksums.sha256
    
    # Sign checksums file
    gpg --detach-sign --armor checksums.sha256
    
    echo "✅ Checksums created and signed"
}

# Verify downloads during installation
verify_checksum() {
    local file="$1"
    local expected_hash="$2"
    
    echo "🔍 Verifying $file..."
    local actual_hash=$(shasum -a 256 "$file" | awk '{print $1}')
    
    if [ "$actual_hash" = "$expected_hash" ]; then
        echo "✅ Checksum verified: $file"
        return 0
    else
        echo "❌ CRITICAL: Checksum mismatch for $file"
        echo "   Expected: $expected_hash"
        echo "   Actual:   $actual_hash"
        echo "   File may be corrupted or tampered with"
        return 1
    fi
}

# Download and verify checksums file
download_and_verify_checksums() {
    local base_url="$1"
    
    # Download checksums file
    curl -L -o /tmp/checksums.sha256 "${base_url}/checksums.sha256"
    curl -L -o /tmp/checksums.sha256.asc "${base_url}/checksums.sha256.asc"
    
    # Verify GPG signature (optional but recommended)
    if command -v gpg >/dev/null 2>&1; then
        if gpg --verify /tmp/checksums.sha256.asc /tmp/checksums.sha256 2>/dev/null; then
            echo "✅ Checksums file signature verified"
        else
            echo "⚠️ Unable to verify checksums signature (continuing anyway)"
        fi
    fi
    
    # Load checksums into associative array
    while IFS=' ' read -r hash filename; do
        CHECKSUMS["$filename"]="$hash"
    done < /tmp/checksums.sha256
}
```

### **3. Disk Space Management**

#### **Pre-Installation Space Check**
```bash
check_disk_space() {
    local required_space_gb="$1"  # e.g., 8 for maximum installation
    local install_path="/Applications"
    
    # Get available space in GB
    local available_space=$(df -g "$install_path" | awk 'NR==2 {print $4}')
    
    echo "💾 Disk space check:"
    echo "   Required: ${required_space_gb}GB"
    echo "   Available: ${available_space}GB"
    
    if [ "$available_space" -lt "$required_space_gb" ]; then
        echo "❌ CRITICAL: Insufficient disk space"
        echo ""
        echo "🧹 Free up space options:"
        echo "1. Run: sudo rm -rf ~/Library/Caches/* (safe cache cleanup)"
        echo "2. Empty Trash"
        echo "3. Remove old Downloads"
        echo "4. Use Storage Management in About This Mac"
        echo ""
        echo "🔄 Alternative: Choose minimal installation (requires 2GB)"
        
        # Offer minimal installation
        read -p "Install minimal version? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            INSTALL_MODE="minimal"
            return 0
        else
            return 1
        fi
    fi
    
    return 0
}

# Progressive space monitoring during install
monitor_disk_space() {
    local threshold_gb=1  # Warn if less than 1GB remaining
    
    while true; do
        local available=$(df -g /Applications | awk 'NR==2 {print $4}')
        
        if [ "$available" -lt "$threshold_gb" ]; then
            echo "⚠️ WARNING: Low disk space ($available GB remaining)"
            echo "Installation may fail. Consider canceling and freeing space."
        fi
        
        sleep 30
    done &
    
    SPACE_MONITOR_PID=$!
}

cleanup_on_space_failure() {
    echo "🧹 Cleaning up partial installation due to disk space..."
    
    # Remove partially downloaded files
    rm -f /tmp/python-framework.tar.gz*
    rm -f /tmp/ai-models.tar.gz*
    rm -f /tmp/ollama-model-*
    
    # Remove partial app if installed
    if [ -d "/Applications/Skip the Podcast Desktop.app" ]; then
        rm -rf "/Applications/Skip the Podcast Desktop.app"
    fi
    
    echo "✅ Cleanup complete"
}
```

### **4. Permission Failure Recovery**

#### **Admin Privilege Verification**
```bash
verify_admin_privileges() {
    echo "🔐 Verifying administrator privileges..."
    
    # Test write access to /Applications
    if ! touch "/Applications/.test_write_$$" 2>/dev/null; then
        echo "❌ CRITICAL: Cannot write to /Applications directory"
        echo "This installer must be run with administrator privileges"
        return 1
    fi
    rm -f "/Applications/.test_write_$$"
    
    # Test ability to change ownership
    if ! chown root:wheel "/tmp" 2>/dev/null; then
        echo "❌ CRITICAL: Cannot change file ownership"
        echo "Installation requires full administrator access"
        return 1
    fi
    
    echo "✅ Administrator privileges verified"
    return 0
}

# Handle permission failures during operation
handle_permission_failure() {
    local operation="$1"
    local target="$2"
    local error_code="$3"
    
    echo "❌ Permission failure during: $operation"
    echo "Target: $target"
    echo "Error code: $error_code"
    
    case "$operation" in
        "app_install")
            echo "🔧 Attempting permission repair..."
            
            # Try to fix /Applications permissions
            sudo chown root:admin /Applications
            sudo chmod 775 /Applications
            
            # Retry the operation
            echo "🔄 Retrying app installation..."
            return 0
            ;;
            
        "framework_install")
            echo "🔧 Attempting framework permission fix..."
            
            # Remove any conflicting installations
            sudo rm -rf "/Applications/Skip the Podcast Desktop.app/Contents/Frameworks"
            mkdir -p "/Applications/Skip the Podcast Desktop.app/Contents/Frameworks"
            
            return 0
            ;;
            
        *)
            echo "❌ Unknown permission failure type"
            echo "Please run installer as administrator"
            return 1
            ;;
    esac
}
```

### **5. Component Verification System**

#### **Comprehensive Component Testing**
```bash
verify_python_framework() {
    local framework_path="/Applications/Skip the Podcast Desktop.app/Contents/Frameworks/Python.framework"
    
    echo "🔍 Verifying Python framework..."
    
    # Check framework structure
    local required_paths=(
        "Versions/3.13/bin/python3.13"
        "Versions/3.13/lib/python3.13"
        "Versions/3.13/include/python3.13"
    )
    
    for path in "${required_paths[@]}"; do
        if [ ! -e "$framework_path/$path" ]; then
            echo "❌ Missing framework component: $path"
            return 1
        fi
    done
    
    # Test Python execution
    local python_exe="$framework_path/Versions/3.13/bin/python3.13"
    if ! "$python_exe" -c "import sys; print(f'Python {sys.version}'); sys.exit(0)" 2>/dev/null; then
        echo "❌ Python framework cannot execute"
        return 1
    fi
    
    echo "✅ Python framework verified"
    return 0
}

verify_ollama_installation() {
    echo "🔍 Verifying Ollama installation..."
    
    # Check Ollama binary
    if ! command -v ollama >/dev/null 2>&1; then
        echo "❌ Ollama binary not found in PATH"
        return 1
    fi
    
    # Test Ollama service
    if ! ollama list >/dev/null 2>&1; then
        echo "🔄 Starting Ollama service..."
        ollama serve &
        sleep 5
    fi
    
    # Verify model installation
    local model_name="$1"  # e.g., "qwen2.5:7b"
    if ! ollama list | grep -q "$model_name"; then
        echo "❌ Model $model_name not properly installed"
        return 1
    fi
    
    # Test model response
    local test_response=$(echo "Hello" | ollama run "$model_name" 2>/dev/null | head -1)
    if [ -z "$test_response" ]; then
        echo "❌ Model $model_name not responding"
        return 1
    fi
    
    echo "✅ Ollama and model $model_name verified"
    return 0
}

verify_obsidian_configuration() {
    echo "🔍 Verifying Obsidian configuration..."
    
    # Check Obsidian installation
    if [ ! -d "/Applications/Obsidian.app" ]; then
        echo "❌ Obsidian not installed"
        return 1
    fi
    
    # Check vault configuration
    local vault_path="$HOME/Documents/SkipThePodcast_Knowledge"
    if [ ! -d "$vault_path" ]; then
        echo "❌ Obsidian vault not created"
        return 1
    fi
    
    # Check Obsidian configuration file
    local config_file="$HOME/Library/Application Support/obsidian/obsidian.json"
    if [ ! -f "$config_file" ]; then
        echo "❌ Obsidian configuration not set"
        return 1
    fi
    
    # Verify vault is configured as default
    if ! grep -q "SkipThePodcast_Knowledge" "$config_file"; then
        echo "❌ Vault not configured as default"
        return 1
    fi
    
    echo "✅ Obsidian configuration verified"
    return 0
}
```

## **Comprehensive Testing Strategy**

### **1. Test Environments Specification**

#### **Primary Test Environments**
```yaml
test_environments:
  clean_macos:
    - macOS_monterey_12.7:
        hardware: "MacBook Air M1 (8GB RAM)"
        python: "None (fresh install)"
        purpose: "Minimum viable system test"
    
    - macOS_ventura_13.6:
        hardware: "MacBook Pro M2 Pro (16GB RAM)" 
        python: "System Python 3.9"
        purpose: "Standard user environment"
    
    - macOS_sonoma_14.4:
        hardware: "Mac Studio M2 Ultra (64GB RAM)"
        python: "Homebrew Python 3.12 + conda"
        purpose: "Complex Python environment conflicts"
    
    - macOS_sequoia_15.0:
        hardware: "MacBook Pro M3 Max (32GB RAM)"
        python: "Multiple Python versions"
        purpose: "Latest OS compatibility"
  
  corporate_environments:
    - locked_down_corporate:
        restrictions: "Admin restrictions, firewall, no homebrew"
        network: "Corporate proxy required"
        purpose: "Enterprise deployment test"
    
    - educational_institution:
        restrictions: "Limited admin access, shared accounts"
        network: "Filtered internet access"
        purpose: "Educational deployment test"
  
  edge_cases:
    - low_storage:
        disk_space: "< 2GB available"
        purpose: "Minimal installation testing"
    
    - slow_network:
        bandwidth: "< 1Mbps connection"
        purpose: "Download timeout and resume testing"
    
    - offline_mode:
        network: "No internet after PKG download"
        purpose: "Offline installation verification"
```

### **2. Automated Testing for PKG Installation**

#### **Automated Test Suite**
```bash
#!/bin/bash
# automated_pkg_test_suite.sh

run_automated_tests() {
    local test_results_dir="test_results/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$test_results_dir"
    
    echo "🧪 Starting automated PKG installation test suite..."
    echo "Results will be saved to: $test_results_dir"
    
    # Test 1: Clean installation
    test_clean_installation "$test_results_dir"
    
    # Test 2: Installation with existing Python
    test_existing_python_conflict "$test_results_dir"
    
    # Test 3: Low disk space scenario
    test_low_disk_space "$test_results_dir"
    
    # Test 4: Network interruption during download
    test_network_interruption "$test_results_dir"
    
    # Test 5: Component verification
    test_component_verification "$test_results_dir"
    
    # Test 6: Uninstallation
    test_uninstallation "$test_results_dir"
    
    # Generate test report
    generate_test_report "$test_results_dir"
}

test_clean_installation() {
    local results_dir="$1"
    local test_name="clean_installation"
    
    echo "🧪 Test: Clean Installation"
    
    # Remove any existing installation
    sudo rm -rf "/Applications/Skip the Podcast Desktop.app"
    
    # Record start time
    local start_time=$(date +%s)
    
    # Run installation
    if installer -pkg "dist/Skip_the_Podcast_Desktop-test.pkg" -target /; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        echo "✅ Installation completed in ${duration}s" | tee "$results_dir/${test_name}.log"
        
        # Verify installation
        verify_complete_installation >> "$results_dir/${test_name}.log"
        
    else
        echo "❌ Installation failed" | tee "$results_dir/${test_name}.log"
        return 1
    fi
}

test_network_interruption() {
    local results_dir="$1"
    local test_name="network_interruption"
    
    echo "🧪 Test: Network Interruption During Download"
    
    # Start installation
    installer -pkg "dist/Skip_the_Podcast_Desktop-test.pkg" -target / &
    local installer_pid=$!
    
    # Wait for downloads to start, then simulate network failure
    sleep 30
    
    # Block network access temporarily
    sudo pfctl -e
    echo "block all" | sudo pfctl -f -
    
    # Wait 60 seconds then restore network
    sleep 60
    sudo pfctl -f /etc/pf.conf
    
    # Check if installation recovered
    wait $installer_pid
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ Installation recovered from network interruption" | tee "$results_dir/${test_name}.log"
    else
        echo "❌ Installation failed to recover from network interruption" | tee "$results_dir/${test_name}.log"
    fi
}
```

### **3. Regression Testing Procedures**

#### **Regression Test Matrix**
```yaml
regression_tests:
  core_functionality:
    - python_framework_isolation:
        test: "Verify framework Python doesn't conflict with system Python"
        platforms: ["M1", "M2", "M3", "Intel"]
        frequency: "Every build"
    
    - app_launch_verification:
        test: "App launches without errors after installation"
        scenarios: ["fresh_install", "upgrade", "reinstall"]
        frequency: "Every build"
    
    - component_integration:
        test: "All components work together properly"
        components: ["python", "ollama", "ffmpeg", "models", "obsidian"]
        frequency: "Every release candidate"
  
  installation_scenarios:
    - clean_system_install:
        test: "Installation on system with no prior Python/ML tools"
        automation: "automated_pkg_test_suite.sh --clean"
        frequency: "Weekly"
    
    - upgrade_from_dmg:
        test: "Upgrade from existing DMG installation"
        automation: "test_dmg_to_pkg_upgrade.sh"
        frequency: "Release candidates only"
    
    - corporate_environment:
        test: "Installation in restricted corporate environment"
        automation: "Manual with corporate test VM"
        frequency: "Before major releases"
  
  performance_regression:
    - installation_time:
        test: "Installation completes within reasonable time"
        baseline: "< 20 minutes on standard broadband"
        automation: "measure_install_time.sh"
        frequency: "Every build"
    
    - download_efficiency:
        test: "Downloads use optimal bandwidth and resume properly"
        baseline: "90% of available bandwidth utilization"
        automation: "test_download_performance.sh"
        frequency: "Weekly"
```

### **4. User Acceptance Testing Criteria**

#### **UAT Success Criteria**
```yaml
user_acceptance_criteria:
  installation_experience:
    seamless_installation:
      - criteria: "User can install with single PKG double-click"
      - measurement: "100% of testers complete installation without assistance"
      - pass_threshold: "95%"
    
    clear_progress_indication:
      - criteria: "User understands installation progress at all times"
      - measurement: "Progress bar and messages are clear and accurate"
      - pass_threshold: "90% user satisfaction in survey"
    
    reasonable_installation_time:
      - criteria: "Installation completes in acceptable timeframe"
      - measurement: "Average installation time < 15 minutes"
      - pass_threshold: "100% of installations complete within 30 minutes"
  
  post_installation_functionality:
    immediate_app_launch:
      - criteria: "App launches immediately after installation without additional setup"
      - measurement: "App opens and displays main interface"
      - pass_threshold: "100% success rate"
    
    all_features_working:
      - criteria: "All core features work without additional downloads"
      - measurement: "Transcription, diarization, HCE, and LLM features functional"
      - pass_threshold: "100% of core features operational"
    
    obsidian_integration:
      - criteria: "Obsidian vault is configured and accessible"
      - measurement: "Vault opens in Obsidian, files save to correct location"
      - pass_threshold: "95% success rate"
  
  user_experience_quality:
    professional_installer_feel:
      - criteria: "Installation feels professional and trustworthy"
      - measurement: "User survey rating on 1-10 scale"
      - pass_threshold: "Average rating >= 8.0"
    
    error_handling_clarity:
      - criteria: "Any errors are clearly explained with actionable solutions"
      - measurement: "Error message comprehensibility survey"
      - pass_threshold: "85% of users understand error messages"
    
    minimal_user_intervention:
      - criteria: "Installation requires minimal user input after password entry"
      - measurement: "Number of user prompts/decisions required"
      - pass_threshold: "≤ 3 user interactions total"
  
  reliability_standards:
    consistent_success_rate:
      - criteria: "Installation succeeds consistently across different environments"
      - measurement: "Success rate across test matrix"
      - pass_threshold: "98% success rate"
    
    graceful_failure_handling:
      - criteria: "Failures are handled gracefully with clear recovery options"
      - measurement: "Failure recovery success rate"
      - pass_threshold: "80% of failures can be resolved by user following provided instructions"
```

#### **UAT Test Protocol**
```bash
# User Acceptance Test Protocol
conduct_uat_session() {
    local tester_id="$1"
    local session_date="$(date +%Y%m%d)"
    local results_file="uat_results/${tester_id}_${session_date}.log"
    
    echo "👤 UAT Session: $tester_id"
    echo "📅 Date: $session_date"
    echo "📝 Results: $results_file"
    
    # Pre-test setup
    echo "🔧 Setting up test environment..."
    setup_clean_test_environment
    
    # Test execution with timing
    local start_time=$(date +%s)
    
    echo "▶️ Starting timed installation test..."
    
    # Monitor user actions
    record_user_interactions &
    local monitor_pid=$!
    
    # Execute installation
    open "dist/Skip_the_Podcast_Desktop-${VERSION}.pkg"
    
    # Wait for completion or timeout (30 minutes)
    wait_for_installation_completion 1800
    local install_result=$?
    
    kill $monitor_pid 2>/dev/null
    
    local end_time=$(date +%s)
    local total_time=$((end_time - start_time))
    
    # Record results
    {
        echo "Installation Time: ${total_time}s"
        echo "Installation Result: $install_result"
        echo "User Interactions: $(count_user_interactions)"
        echo "Error Encountered: $(check_for_errors)"
    } >> "$results_file"
    
    # Post-installation testing
    test_app_functionality >> "$results_file"
    
    # User satisfaction survey
    conduct_user_survey "$tester_id" >> "$results_file"
    
    echo "✅ UAT session complete: $results_file"
}
```

## **Implementation Priority**

### **Phase 0: Error Handling & Testing Infrastructure (1 week)**
1. Implement fallback download mechanisms
2. Create checksum verification system
3. Build disk space management
4. Set up permission failure recovery
5. Develop component verification system
6. Create automated test suite
7. Define UAT criteria and protocols

This comprehensive error handling and testing strategy ensures the PKG migration will be robust, reliable, and user-friendly.
