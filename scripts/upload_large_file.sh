#!/bin/bash
# upload_large_file.sh - Upload large files to GitHub releases using resumable uploads

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"

# GitHub configuration
GITHUB_REPO="msg43/Knowledge_Chipper"
RELEASE_TAG="v3.2.35"
FILE_PATH="$DIST_DIR/ollama-models-bundle.tar.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📤 Large File Uploader for GitHub Releases${NC}"
echo "============================================="

# Function to print status
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
    print_error "File not found: $FILE_PATH"
    exit 1
fi

FILE_SIZE=$(stat -f%z "$FILE_PATH")
FILE_NAME=$(basename "$FILE_PATH")

echo "File: $FILE_NAME"
echo "Size: $(du -h "$FILE_PATH" | cut -f1)"

# Check if file is larger than 2GB
if [ $FILE_SIZE -le 2147483648 ]; then
    echo "File is under 2GB, using standard upload..."
    gh release upload "$RELEASE_TAG" "$FILE_PATH" --repo "$GITHUB_REPO"
    print_status "File uploaded successfully"
    exit 0
fi

echo "File is over 2GB, attempting large file upload..."

# Get release ID
RELEASE_ID=$(gh api repos/$GITHUB_REPO/releases/tags/$RELEASE_TAG --jq .id)

if [ -z "$RELEASE_ID" ]; then
    print_error "Could not find release $RELEASE_TAG"
    exit 1
fi

echo "Release ID: $RELEASE_ID"

# Use GitHub CLI to upload with large file support
print_status "Uploading large file using GitHub CLI..."

# Try using gh release upload with --clobber flag
if gh release upload "$RELEASE_TAG" "$FILE_PATH" --repo "$GITHUB_REPO" --clobber; then
    print_status "Large file uploaded successfully!"
else
    print_error "Failed to upload large file"
    echo "GitHub has a 2GB limit for release assets"
    echo "Consider splitting the file or using alternative hosting"
    exit 1
fi
