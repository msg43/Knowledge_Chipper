#!/bin/bash
# setup_obsidian_integration.sh - Automatic Obsidian installation and vault setup for PKG installer
# Configures Obsidian with Skip the Podcast Desktop integration

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Obsidian configuration
VAULT_PATH="$HOME/Documents/SkipThePodcast_Knowledge"
OBSIDIAN_CONFIG_DIR="$HOME/Library/Application Support/obsidian"
OBSIDIAN_APP="/Applications/Obsidian.app"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}📝 Obsidian Integration Setup for PKG Installer${NC}"
echo "==============================================="
echo "Automatic Obsidian installation and vault configuration"
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

# Check if Obsidian is already installed
check_obsidian_installation() {
    if [ -d "$OBSIDIAN_APP" ]; then
        print_status "Obsidian already installed"
        return 0
    else
        return 1
    fi
}

# Download and install Obsidian
install_obsidian() {
    echo -e "\n${BLUE}📦 Installing Obsidian...${NC}"
    report_progress 10 "Downloading Obsidian"

    # Get latest Obsidian download URL
    OBSIDIAN_URL=$(curl -s https://api.github.com/repos/obsidianmd/obsidian-releases/releases/latest | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(next(asset['browser_download_url'] for asset in data['assets'] if asset['name'].endswith('.dmg')))")

    if [ -z "$OBSIDIAN_URL" ]; then
        print_error "Failed to get Obsidian download URL"
        return 1
    fi

    local temp_dmg="/tmp/obsidian.dmg"

    # Download Obsidian
    if ! curl -L -o "$temp_dmg" "$OBSIDIAN_URL"; then
        print_error "Failed to download Obsidian"
        return 1
    fi

    report_progress 40 "Installing Obsidian"

    # Mount DMG
    local mount_point
    mount_point=$(hdiutil attach "$temp_dmg" | grep Volumes | awk '{print $3}')

    if [ -z "$mount_point" ]; then
        print_error "Failed to mount Obsidian DMG"
        return 1
    fi

    # Copy Obsidian to Applications
    if ! cp -R "$mount_point/Obsidian.app" "/Applications/"; then
        print_error "Failed to copy Obsidian to Applications"
        hdiutil detach "$mount_point" 2>/dev/null || true
        return 1
    fi

    # Unmount DMG
    hdiutil detach "$mount_point" 2>/dev/null || true

    # Cleanup
    rm -f "$temp_dmg"

    print_status "Obsidian installed successfully"
    return 0
}

# Create Skip the Podcast vault
create_vault() {
    echo -e "\n${BLUE}📁 Creating Skip the Podcast knowledge vault...${NC}"
    report_progress 60 "Setting up knowledge vault"

    # Create vault directory
    mkdir -p "$VAULT_PATH"

    # Create vault structure
    mkdir -p "$VAULT_PATH/Transcripts"
    mkdir -p "$VAULT_PATH/Summaries"
    mkdir -p "$VAULT_PATH/People"
    mkdir -p "$VAULT_PATH/Concepts"
    mkdir -p "$VAULT_PATH/Templates"
    mkdir -p "$VAULT_PATH/Archive"
    mkdir -p "$VAULT_PATH/.obsidian"

    print_status "Vault structure created"

    # Create welcome note
    cat > "$VAULT_PATH/Welcome to Skip the Podcast Knowledge.md" << 'EOF'
# Welcome to Skip the Podcast Knowledge

This vault is automatically configured for your Skip the Podcast Desktop knowledge management.

## Folder Structure

- **Transcripts**: Raw transcripts from videos and audio files
- **Summaries**: Processed summaries and knowledge extracts
- **People**: Notes about people mentioned in content
- **Concepts**: Key concepts and ideas
- **Templates**: Note templates for consistent formatting
- **Archive**: Older or less relevant content

## Getting Started

1. Use Skip the Podcast Desktop to process your first video or audio file
2. Files will automatically appear in the appropriate folders
3. Use Obsidian's graph view to explore connections
4. Create your own notes and link them to the processed content

## Features Enabled

- Automatic wikilink creation
- Graph view for relationship visualization
- Search across all content
- Tag-based organization
- Template system for consistent notes

## Support

For help with Skip the Podcast Desktop, visit:
- [GitHub Repository](https://github.com/msg43/Knowledge_Chipper)
- [Documentation](https://github.com/msg43/Knowledge_Chipper/blob/main/README.md)

Happy knowledge building! 🧠✨
EOF

    print_status "Welcome note created"
}

# Create Obsidian configuration
configure_obsidian() {
    echo -e "\n${BLUE}⚙️ Configuring Obsidian...${NC}"
    report_progress 70 "Configuring Obsidian settings"

    # Create Obsidian config directory
    mkdir -p "$OBSIDIAN_CONFIG_DIR"

    # Create main Obsidian configuration
    cat > "$OBSIDIAN_CONFIG_DIR/obsidian.json" << EOF
{
  "vaults": {
    "$(basename "$VAULT_PATH")": {
      "path": "$VAULT_PATH",
      "ts": $(date +%s)000
    }
  },
  "open": "$(basename "$VAULT_PATH")"
}
EOF

    print_status "Main Obsidian configuration created"

    # Create vault-specific configuration
    local vault_config_dir="$VAULT_PATH/.obsidian"
    mkdir -p "$vault_config_dir"

    # App configuration
    cat > "$vault_config_dir/app.json" << 'EOF'
{
  "legacyEditor": false,
  "livePreview": true,
  "showLineNumber": true,
  "spellcheck": true,
  "useTab": false,
  "tabSize": 2,
  "readableLineLength": true,
  "strictLineBreaks": false,
  "foldHeading": true,
  "foldIndent": true,
  "showUnsupportedFiles": false,
  "newLinkFormat": "shortest",
  "attachmentFolderPath": "Archive/Attachments",
  "newFileLocation": "current",
  "promptDelete": true,
  "alwaysUpdateLinks": true
}
EOF

    # Core plugins configuration
    cat > "$vault_config_dir/core-plugins.json" << 'EOF'
[
  "file-explorer",
  "global-search",
  "switcher",
  "graph",
  "backlink",
  "canvas",
  "outgoing-link",
  "tag-pane",
  "properties",
  "page-preview",
  "templates",
  "note-composer",
  "command-palette",
  "markdown-importer",
  "outline",
  "word-count"
]
EOF

    # Appearance configuration
    cat > "$vault_config_dir/appearance.json" << 'EOF'
{
  "accentColor": "#1d4ed8",
  "theme": "obsidian",
  "cssTheme": "",
  "baseFontSize": 16,
  "enabledCssSnippets": [],
  "interfaceFontFamily": "",
  "textFontFamily": "",
  "monospaceFontFamily": "",
  "foldHeading": true,
  "leftRibbonHiddenItems": {},
  "rightRibbonHiddenItems": {},
  "hiddenViewTypes": [],
  "nativeMenus": true
}
EOF

    # Graph configuration for better knowledge visualization
    cat > "$vault_config_dir/graph.json" << 'EOF'
{
  "collapse-filter": false,
  "search": "",
  "showTags": true,
  "showAttachments": false,
  "hideUnresolved": false,
  "showOrphans": true,
  "collapse-color-groups": false,
  "colorGroups": [
    {
      "query": "path:Transcripts",
      "color": {
        "a": 1,
        "rgb": 5817472
      }
    },
    {
      "query": "path:Summaries",
      "color": {
        "a": 1,
        "rgb": 11621088
      }
    },
    {
      "query": "path:People",
      "color": {
        "a": 1,
        "rgb": 16056320
      }
    },
    {
      "query": "path:Concepts",
      "color": {
        "a": 1,
        "rgb": 5395026
      }
    }
  ],
  "collapse-display": false,
  "showArrow": true,
  "textFadeMultiplier": -1,
  "nodeSizeMultiplier": 1.2,
  "lineSizeMultiplier": 1,
  "collapse-forces": false,
  "centerStrength": 0.3,
  "repelStrength": 8,
  "linkStrength": 0.7,
  "linkDistance": 200
}
EOF

    print_status "Vault configuration created"
}

# Create templates for Skip the Podcast content
create_templates() {
    echo -e "\n${BLUE}📝 Creating content templates...${NC}"
    report_progress 80 "Creating note templates"

    local templates_dir="$VAULT_PATH/Templates"

    # Transcript template
    cat > "$templates_dir/Transcript Template.md" << 'EOF'
# {{title}}

## Metadata
- **Source**: {{source_url}}
- **Duration**: {{duration}}
- **Processed**: {{date}}
- **Type**: {{content_type}}

## Summary
{{summary}}

## Key People
{{people}}

## Key Concepts
{{concepts}}

## Transcript
{{transcript}}

## Notes
<!-- Add your personal notes here -->

## Related
<!-- Link to related content -->

---
Tags: #transcript #{{content_type}}
EOF

    # Summary template
    cat > "$templates_dir/Summary Template.md" << 'EOF'
# {{title}} - Summary

## Overview
{{overview}}

## Key Points
{{key_points}}

## People Mentioned
{{people}}

## Mental Models & Frameworks
{{mental_models}}

## Jargon & Technical Terms
{{jargon}}

## Actionable Insights
{{insights}}

## Questions & Follow-up
{{questions}}

## Source
- **Original**: [[{{transcript_link}}]]
- **Processed**: {{date}}

---
Tags: #summary #knowledge #{{topic_tags}}
EOF

    # Person template
    cat > "$templates_dir/Person Template.md" << 'EOF'
# {{name}}

## Background
{{background}}

## Expertise
{{expertise}}

## Key Ideas
{{key_ideas}}

## Mentioned In
{{mentioned_in}}

## Quotes
{{quotes}}

## Links & References
{{references}}

---
Tags: #person #expert
EOF

    # Concept template
    cat > "$templates_dir/Concept Template.md" << 'EOF'
# {{concept}}

## Definition
{{definition}}

## Context
{{context}}

## Applications
{{applications}}

## Related Concepts
{{related}}

## Sources
{{sources}}

## Personal Notes
<!-- Your thoughts and connections -->

---
Tags: #concept #{{domain}}
EOF

    print_status "Content templates created"

    # Configure templates plugin
    cat > "$VAULT_PATH/.obsidian/templates.json" << 'EOF'
{
  "folder": "Templates"
}
EOF

    print_status "Templates plugin configured"
}

# Create Skip the Podcast Desktop integration
create_integration_config() {
    echo -e "\n${BLUE}🔗 Creating Skip the Podcast integration...${NC}"
    report_progress 90 "Configuring application integration"

    # Create integration configuration file
    local config_dir="$HOME/.config/skip_the_podcast"
    mkdir -p "$config_dir"

    cat > "$config_dir/obsidian_integration.json" << EOF
{
  "enabled": true,
  "vault_path": "$VAULT_PATH",
  "output_paths": {
    "transcripts": "$VAULT_PATH/Transcripts",
    "summaries": "$VAULT_PATH/Summaries",
    "people": "$VAULT_PATH/People",
    "concepts": "$VAULT_PATH/Concepts"
  },
  "templates": {
    "transcript": "$VAULT_PATH/Templates/Transcript Template.md",
    "summary": "$VAULT_PATH/Templates/Summary Template.md",
    "person": "$VAULT_PATH/Templates/Person Template.md",
    "concept": "$VAULT_PATH/Templates/Concept Template.md"
  },
  "auto_link": true,
  "use_wikilinks": true,
  "create_index": true
}
EOF

    print_status "Integration configuration created"
}

# Main execution
main() {
    echo -e "${BLUE}🔍 Checking Obsidian installation...${NC}"
    report_progress 5 "Checking Obsidian installation"

    # Check if Obsidian is installed
    if ! check_obsidian_installation; then
        if ! install_obsidian; then
            print_error "Obsidian installation failed"
            exit 1
        fi
    fi

    # Create vault
    if ! create_vault; then
        print_error "Vault creation failed"
        exit 1
    fi

    # Configure Obsidian
    if ! configure_obsidian; then
        print_error "Obsidian configuration failed"
        exit 1
    fi

    # Create templates
    if ! create_templates; then
        print_error "Template creation failed"
        exit 1
    fi

    # Create integration
    if ! create_integration_config; then
        print_error "Integration configuration failed"
        exit 1
    fi

    report_progress 100 "Obsidian integration complete"

    echo -e "\n${GREEN}${BOLD}🎉 Obsidian Integration Complete!${NC}"
    echo "=============================================="
    echo "Vault Location: $VAULT_PATH"
    echo "Obsidian App: $OBSIDIAN_APP"
    echo "Status: Configured and ready"
    echo ""
    echo "Features configured:"
    echo "• Skip the Podcast knowledge vault"
    echo "• Organized folder structure"
    echo "• Content templates"
    echo "• Graph visualization"
    echo "• Automatic linking"
    echo ""
    echo "Next time you launch Obsidian, it will open your knowledge vault automatically."
}

# Command-line interface
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    case "${1:-setup}" in
        "setup")
            main
            ;;
        "vault-only")
            create_vault
            create_templates
            create_integration_config
            ;;
        "test")
            if [ -d "$OBSIDIAN_APP" ] && [ -d "$VAULT_PATH" ]; then
                print_status "Obsidian and vault are properly configured"
            else
                print_error "Obsidian integration is not complete"
                exit 1
            fi
            ;;
        *)
            echo "Usage: $0 [setup|vault-only|test]"
            echo "  setup      - Full Obsidian installation and configuration"
            echo "  vault-only - Create vault and templates without installing Obsidian"
            echo "  test       - Test if integration is working"
            exit 1
            ;;
    esac
fi
