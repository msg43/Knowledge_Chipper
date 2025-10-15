#!/bin/bash
# deploy_release.sh - Simple script to deploy a new release
# Usage: ./scripts/deploy_release.sh [version]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ️${NC} $1"
}

echo -e "${BLUE}${BOLD}🚀 Release Deployment Script${NC}"
echo "=============================="
echo ""

# Get current version
CURRENT_VERSION=$(grep -o 'version = "[^"]*"' pyproject.toml | cut -d'"' -f2)
print_info "Current version: $CURRENT_VERSION"

# Determine new version
if [ -n "$1" ]; then
    NEW_VERSION="$1"
    print_info "Using provided version: $NEW_VERSION"
else
    echo ""
    echo "What type of release?"
    echo "1) Patch (${CURRENT_VERSION} → increment last number)"
    echo "2) Minor (${CURRENT_VERSION} → increment middle number)"
    echo "3) Custom version"
    echo ""
    read -p "Choose (1/2/3): " choice

    case $choice in
        1)
            # Increment patch version
            NEW_VERSION=$(echo $CURRENT_VERSION | awk -F. '{$NF = $NF + 1;} 1' | sed 's/ /./g')
            ;;
        2)
            # Increment minor version, reset patch
            NEW_VERSION=$(echo $CURRENT_VERSION | awk -F. '{$(NF-1) = $(NF-1) + 1; $NF = 0;} 1' | sed 's/ /./g')
            ;;
        3)
            read -p "Enter new version: " NEW_VERSION
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
fi

print_info "New version will be: $NEW_VERSION"
echo ""

# Confirm deployment
echo -e "${YELLOW}This will:${NC}"
echo "  1. Update pyproject.toml to version $NEW_VERSION"
echo "  2. Commit the version change"
echo "  3. Create and push git tag v$NEW_VERSION"
echo "  4. Trigger automated build, sign, and release"
echo "  5. Release will appear at: https://github.com/msg43/skipthepodcast.com/releases"
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Deployment cancelled"
    exit 0
fi

# Update version in pyproject.toml
print_info "Updating version in pyproject.toml..."
sed -i '' "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml

# Verify the change
UPDATED_VERSION=$(grep -o 'version = "[^"]*"' pyproject.toml | cut -d'"' -f2)
if [ "$UPDATED_VERSION" != "$NEW_VERSION" ]; then
    print_error "Failed to update version in pyproject.toml"
    exit 1
fi

print_status "Version updated to $NEW_VERSION"

# Commit the version change
print_info "Committing version change..."
git add pyproject.toml
git commit -m "Bump version to $NEW_VERSION"

print_status "Version change committed"

# Create and push tag
print_info "Creating and pushing tag v$NEW_VERSION..."
git tag "v$NEW_VERSION"
git push origin main
git push origin "v$NEW_VERSION"

print_status "Tag pushed - deployment initiated!"

echo ""
echo -e "${GREEN}${BOLD}🎉 Release Deployment Started!${NC}"
echo "================================================"
echo ""
echo "The automated pipeline is now:"
echo "  1. Building your application"
echo "  2. Signing with Apple Developer certificates"
echo "  3. Submitting for notarization (~5-15 minutes)"
echo "  4. Creating release at https://github.com/msg43/skipthepodcast.com/releases"
echo ""
echo "Monitor progress at:"
echo "  https://github.com/msg43/Knowledge_Chipper/actions"
echo ""
echo "Expected completion: 15-20 minutes"
