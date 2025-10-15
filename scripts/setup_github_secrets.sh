#!/bin/bash
# setup_github_secrets.sh - Help set up GitHub repository secrets for Apple code signing

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}🔐 GitHub Secrets Setup Helper${NC}"
echo "=================================="
echo ""

print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ️${NC} $1"
}

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    print_error "GitHub CLI (gh) is not installed"
    echo "Install it with: brew install gh"
    echo "Then run: gh auth login"
    exit 1
fi

# Check if user is authenticated
if ! gh auth status &> /dev/null; then
    print_error "Not authenticated with GitHub CLI"
    echo "Run: gh auth login"
    exit 1
fi

echo -e "${BLUE}This script will help you set up GitHub repository secrets for Apple code signing.${NC}"
echo ""
echo "You'll need:"
echo "1. Your Apple ID email"
echo "2. Your Team ID"
echo "3. Your app-specific password"
echo "4. Your Developer ID certificates (exported as .p12 files)"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

# Get repository info
REPO_OWNER=$(gh repo view --json owner --jq '.owner.login')
REPO_NAME=$(gh repo view --json name --jq '.name')

echo ""
echo "Setting up secrets for repository: ${REPO_OWNER}/${REPO_NAME}"
echo ""

# Collect Apple ID
echo -e "${BLUE}1. Apple ID Email${NC}"
read -p "Enter your Apple ID email: " APPLE_ID
if [ -z "$APPLE_ID" ]; then
    print_error "Apple ID is required"
    exit 1
fi

# Collect Team ID
echo ""
echo -e "${BLUE}2. Team ID${NC}"
echo "Find your Team ID at: https://developer.apple.com/account"
read -p "Enter your Team ID (10 characters): " APPLE_TEAM_ID
if [ -z "$APPLE_TEAM_ID" ]; then
    print_error "Team ID is required"
    exit 1
fi

# Collect app-specific password
echo ""
echo -e "${BLUE}3. App-Specific Password${NC}"
echo "Create one at: https://appleid.apple.com/account/manage"
read -s -p "Enter your app-specific password: " APPLE_APP_PASSWORD
echo
if [ -z "$APPLE_APP_PASSWORD" ]; then
    print_error "App-specific password is required"
    exit 1
fi

# Certificate export instructions
echo ""
echo -e "${BLUE}4. Export Certificates${NC}"
echo ""
echo "You need to export your certificates as .p12 files:"
echo ""
echo "📋 Steps to export certificates:"
echo "1. Open Keychain Access"
echo "2. Find 'Developer ID Application' certificate"
echo "3. Right-click → Export"
echo "4. Save as .p12 format"
echo "5. Set a password (you'll enter it below)"
echo "6. Repeat for 'Developer ID Installer' certificate"
echo ""

read -p "Have you exported both certificates as .p12 files? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Please export your certificates first, then run this script again."
    exit 0
fi

# Get certificate paths
echo ""
read -p "Path to Developer ID Application .p12 file: " APP_CERT_PATH
if [ ! -f "$APP_CERT_PATH" ]; then
    print_error "Application certificate file not found: $APP_CERT_PATH"
    exit 1
fi

read -p "Path to Developer ID Installer .p12 file: " INSTALLER_CERT_PATH
if [ ! -f "$INSTALLER_CERT_PATH" ]; then
    print_error "Installer certificate file not found: $INSTALLER_CERT_PATH"
    exit 1
fi

# Get certificate password
echo ""
read -s -p "Enter the password for your .p12 certificates: " CERT_PASSWORD
echo
if [ -z "$CERT_PASSWORD" ]; then
    print_error "Certificate password is required"
    exit 1
fi

# Convert certificates to base64
echo ""
echo -e "${BLUE}📤 Uploading secrets to GitHub...${NC}"

APP_CERT_BASE64=$(base64 -i "$APP_CERT_PATH")
INSTALLER_CERT_BASE64=$(base64 -i "$INSTALLER_CERT_PATH")

# Set GitHub secrets
echo "Setting APPLE_ID..."
echo "$APPLE_ID" | gh secret set APPLE_ID

echo "Setting APPLE_TEAM_ID..."
echo "$APPLE_TEAM_ID" | gh secret set APPLE_TEAM_ID

echo "Setting APPLE_APP_PASSWORD..."
echo "$APPLE_APP_PASSWORD" | gh secret set APPLE_APP_PASSWORD

echo "Setting APPLE_CERTIFICATE_APPLICATION..."
echo "$APP_CERT_BASE64" | gh secret set APPLE_CERTIFICATE_APPLICATION

echo "Setting APPLE_CERTIFICATE_INSTALLER..."
echo "$INSTALLER_CERT_BASE64" | gh secret set APPLE_CERTIFICATE_INSTALLER

echo "Setting APPLE_CERTIFICATE_PASSWORD..."
echo "$CERT_PASSWORD" | gh secret set APPLE_CERTIFICATE_PASSWORD

print_status "All secrets uploaded successfully!"

echo ""
echo -e "${GREEN}${BOLD}🎉 Setup Complete!${NC}"
echo "=============================="
echo ""
echo "Repository secrets configured:"
echo "✅ APPLE_ID"
echo "✅ APPLE_TEAM_ID"
echo "✅ APPLE_APP_PASSWORD"
echo "✅ APPLE_CERTIFICATE_APPLICATION"
echo "✅ APPLE_CERTIFICATE_INSTALLER"
echo "✅ APPLE_CERTIFICATE_PASSWORD"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Push a version tag to trigger the build: git tag v1.0.0 && git push origin v1.0.0"
echo "2. Or manually trigger the workflow in GitHub Actions"
echo "3. Monitor the build at: https://github.com/${REPO_OWNER}/${REPO_NAME}/actions"
echo ""
echo "🔒 Security notes:"
echo "- Your certificates are stored as encrypted secrets"
echo "- Only GitHub Actions can access these secrets"
echo "- Secrets are automatically masked in logs"
