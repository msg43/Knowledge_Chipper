#!/bin/bash
# Auto-fixing commit script for Knowledge_Chipper
# This script automatically handles pre-commit auto-fixes and re-commits if needed

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔧 Starting auto-fixing commit process...${NC}"

# Stage all changes
echo -e "${YELLOW}📦 Staging all changes...${NC}"
git add .

# Get commit message from arguments or prompt
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}💬 Enter commit message:${NC}"
    read -r COMMIT_MSG
else
    COMMIT_MSG="$*"
fi

echo -e "${GREEN}📝 Committing with message: ${COMMIT_MSG}${NC}"

# Try to commit - if pre-commit hooks auto-fix files, they'll "fail" but fix the issues
if git commit -m "$COMMIT_MSG"; then
    echo -e "${GREEN}✅ Commit successful on first try!${NC}"
else
    # Pre-commit hooks likely auto-fixed files, so stage the fixes and commit again
    echo -e "${YELLOW}🔄 Pre-commit hooks auto-fixed files. Re-staging and committing...${NC}"
    git add .

    if git commit -m "$COMMIT_MSG"; then
        echo -e "${GREEN}✅ Commit successful after auto-fixes!${NC}"
    else
        echo -e "${RED}❌ Commit failed even after auto-fixes. Please check the errors above.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}🎉 Commit process complete!${NC}"

# Ask if user wants to push
echo -e "${YELLOW}🚀 Push to GitHub? (y/N):${NC}"
read -r -n 1 PUSH_RESPONSE
echo

if [[ $PUSH_RESPONSE =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}📤 Pushing to GitHub...${NC}"
    if git push origin main; then
        echo -e "${GREEN}✅ Successfully pushed to GitHub!${NC}"
    else
        echo -e "${RED}❌ Push failed. You may need to pull first or resolve conflicts.${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}📝 Skipped push. You can push later with: git push origin main${NC}"
fi

echo -e "${GREEN}🎯 All done!${NC}"
