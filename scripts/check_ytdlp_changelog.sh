#!/bin/bash
# Check yt-dlp releases and show changelog for risk assessment
# Helps determine if an update is safe or potentially breaking

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}         yt-dlp Release Checker & Risk Assessment${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Get current version
CURRENT=$(pip show yt-dlp 2>/dev/null | grep Version | awk '{print $2}')
if [ -z "$CURRENT" ]; then
    echo -e "${RED}❌ yt-dlp not installed${NC}"
    exit 1
fi

echo -e "${BLUE}📌 Current version:${NC} $CURRENT"

# Get latest version
echo -e "\n${BLUE}🔍 Checking for updates...${NC}"
LATEST=$(pip index versions yt-dlp 2>/dev/null | grep "LATEST:" | awk '{print $2}')

if [ -z "$LATEST" ]; then
    echo -e "${RED}❌ Could not fetch latest version (network issue?)${NC}"
    exit 1
fi

echo -e "${BLUE}🆕 Latest version:${NC}  $LATEST"

if [ "$CURRENT" = "$LATEST" ]; then
    echo -e "\n${GREEN}✅ Already on latest version!${NC}"
    echo ""
    echo "Still showing recent releases for awareness..."
    echo ""
fi

# Fetch recent releases from GitHub API
echo -e "\n${BLUE}📋 Fetching recent releases from GitHub...${NC}"
echo ""

RELEASES=$(curl -s -H "Accept: application/vnd.github.v3+json" "https://api.github.com/repos/yt-dlp/yt-dlp/releases?per_page=5")

if [ $? -ne 0 ] || [ -z "$RELEASES" ]; then
    echo -e "${YELLOW}⚠️  Could not fetch from GitHub API (rate limit or network issue)${NC}"
    echo ""
    echo "Alternative: Check releases manually at:"
    echo "https://github.com/yt-dlp/yt-dlp/releases"
    echo ""
    echo "Or use RSS feed:"
    echo "https://github.com/yt-dlp/yt-dlp/releases.atom"
    exit 0
fi

# Check if we got an error response
if echo "$RELEASES" | grep -q "API rate limit exceeded"; then
    echo -e "${YELLOW}⚠️  GitHub API rate limit exceeded${NC}"
    echo ""
    echo "Alternative: Check releases manually at:"
    echo "https://github.com/yt-dlp/yt-dlp/releases"
    exit 0
fi

# Parse and display releases
echo "$RELEASES" | python3 - "$CURRENT" "$LATEST" <<'PYTHON'
import sys
import json
from datetime import datetime

releases_json = sys.stdin.read()
current_version = sys.argv[1]
latest_version = sys.argv[2]

try:
    releases = json.loads(releases_json)
except json.JSONDecodeError:
    print("❌ Failed to parse GitHub API response")
    sys.exit(1)

# Risk keywords to watch for
HIGH_RISK = ['breaking', 'incompatible', 'removed', 'deprecated']
MEDIUM_RISK = ['changed', 'modified', 'refactor', 'rewrite']
YOUTUBE_FIX = ['youtube', 'signature', 'extractor', 'format', 'throttl']
SECURITY = ['security', 'vulnerability', 'cve', 'exploit']

def assess_risk(body):
    """Assess risk level based on release notes"""
    if not body:
        return "UNKNOWN", "⚠️"

    body_lower = body.lower()

    # Check for security issues (critical)
    if any(keyword in body_lower for keyword in SECURITY):
        return "CRITICAL", "🔴"

    # Check for breaking changes
    if any(keyword in body_lower for keyword in HIGH_RISK):
        return "HIGH", "🟠"

    # Check for YouTube fixes (important but usually safe)
    if any(keyword in body_lower for keyword in YOUTUBE_FIX):
        return "SAFE", "🟢"

    # Check for significant changes
    if any(keyword in body_lower for keyword in MEDIUM_RISK):
        return "MEDIUM", "🟡"

    return "LOW", "🟢"

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

for i, release in enumerate(releases[:5]):
    version = release['tag_name']
    name = release['name'] or version
    published = release['published_at']
    body = release['body'] or "No release notes"
    url = release['html_url']

    # Parse date
    pub_date = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
    date_str = pub_date.strftime("%Y-%m-%d")

    # Check if this is current or newer
    is_current = (version == current_version)
    is_newer = (version == latest_version)

    # Assess risk
    risk_level, risk_icon = assess_risk(body)

    # Header
    if is_current:
        print(f"\n📌 {version} (YOUR VERSION) - {date_str}")
    elif is_newer and version != current_version:
        print(f"\n🆕 {version} (LATEST) - {date_str}")
    else:
        print(f"\n   {version} - {date_str}")

    print(f"   Risk: {risk_icon} {risk_level}")

    # Show key points from release notes (first 5 bullet points or 300 chars)
    lines = body.split('\n')
    bullet_points = [line for line in lines if line.strip().startswith(('-', '*', '+'))]

    if bullet_points:
        print(f"   Key changes:")
        for point in bullet_points[:5]:
            cleaned = point.strip().lstrip('-*+ ').strip()
            if cleaned and len(cleaned) > 10:  # Skip empty or very short lines
                # Truncate long lines
                if len(cleaned) > 70:
                    cleaned = cleaned[:67] + "..."
                print(f"     • {cleaned}")
    else:
        # No bullet points, show first 200 chars
        summary = body[:200].replace('\n', ' ').strip()
        if summary:
            print(f"   Summary: {summary}...")

    print(f"   URL: {url}")

    if i < len(releases) - 1:
        print()

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

# Decision recommendation
print("\n🎯 RECOMMENDATION:")

if current_version == latest_version:
    print("   ✅ You're on the latest version. No action needed.")
elif current_version > latest_version:
    print("   ⚠️  You're ahead of the published latest? This is unusual.")
else:
    # Check if there are any high-risk releases between current and latest
    high_risk_count = 0
    youtube_fix_count = 0
    security_count = 0

    for release in releases:
        version = release['tag_name']
        # Simple version comparison (works for most cases)
        if version > current_version and version <= latest_version:
            risk_level, _ = assess_risk(release['body'])
            if risk_level == "CRITICAL":
                security_count += 1
            elif risk_level == "HIGH":
                high_risk_count += 1
            elif risk_level == "SAFE":
                youtube_fix_count += 1

    if security_count > 0:
        print(f"   🔴 URGENT: {security_count} security update(s) available!")
        print("   ACTION: Update immediately and test")
    elif youtube_fix_count > 0:
        print(f"   🟢 SAFE: {youtube_fix_count} YouTube fix(es) available")
        print("   ACTION: Safe to update - run: make test-ytdlp-update")
    elif high_risk_count > 0:
        print(f"   🟠 CAUTION: {high_risk_count} potentially breaking change(s)")
        print("   ACTION: Test carefully - run: make test-ytdlp-update")
    else:
        print("   🟢 LOW RISK: Maintenance updates")
        print("   ACTION: Safe to update - run: make test-ytdlp-update")

print("\n📚 More info: https://github.com/yt-dlp/yt-dlp/releases")
print()

PYTHON

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
