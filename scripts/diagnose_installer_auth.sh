#!/bin/bash
# diagnose_installer_auth.sh - Diagnose why installer isn't prompting for password

echo "🔍 Diagnosing Installer Authentication Issue"
echo "==========================================="

# Get the latest PKG
PKG=$(ls -t /Users/matthewgreer/Projects/Knowledge_Chipper/dist/Skip_the_Podcast_Desktop-*.pkg | head -1)
echo "Analyzing: $(basename "$PKG")"
echo ""

# 1. Check current user permissions
echo "📋 Current User Info:"
echo "User: $(whoami)"
echo "Groups: $(groups)"
echo "Admin status: $(dscl . -read /Groups/admin | grep $(whoami) > /dev/null && echo "YES" || echo "NO")"
echo ""

# 2. Check /Applications permissions
echo "📁 /Applications Directory Permissions:"
ls -ld /Applications
echo "Can write without sudo: $([ -w /Applications ] && echo "YES" || echo "NO")"
echo ""

# 3. Analyze package structure
echo "📦 Package Structure:"
pkgutil --payload-files "$PKG" | head -20
echo "..."
echo ""

# 4. Check if package contains system-level files
echo "🔍 Checking for system-level paths in package:"
pkgutil --payload-files "$PKG" | grep -E "^(Library|System|private|usr/local)" | head -10 || echo "No system-level files found"
echo ""

# 5. Test CLI installer behavior
echo "🖥️ Testing CLI installer (will prompt for password if needed):"
echo "Command: sudo installer -pkg \"$PKG\" -target / -verbose"
echo ""
echo "Expected behavior:"
echo "- Should require sudo/password"
echo "- Should install to /Applications"
echo ""

# 6. Check package receipt requirements
echo "📋 Package Info:"
pkgutil --check-signature "$PKG" 2>&1 | head -10
echo ""

# 7. Create a test package with guaranteed root requirement
echo "🧪 Creating test package that MUST require root..."
TEST_DIR="/tmp/test_root_pkg"
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR/payload/usr/local/bin"
mkdir -p "$TEST_DIR/scripts"

# Create a dummy file that requires root
echo '#!/bin/bash' > "$TEST_DIR/payload/usr/local/bin/test_root_file"
chmod 755 "$TEST_DIR/payload/usr/local/bin/test_root_file"

# Create postinstall that requires root
cat > "$TEST_DIR/scripts/postinstall" << 'EOF'
#!/bin/bash
echo "Running as: $(whoami)"
echo "Creating root-owned file..."
touch /private/var/log/skip_the_podcast_test.log
chown root:wheel /private/var/log/skip_the_podcast_test.log
exit 0
EOF
chmod 755 "$TEST_DIR/scripts/postinstall"

# Build test package
pkgbuild --root "$TEST_DIR/payload" \
         --scripts "$TEST_DIR/scripts" \
         --identifier "com.test.root" \
         --version "1.0" \
         --install-location "/" \
         --ownership preserve \
         "/tmp/test_root.pkg" 2>&1

echo ""
echo "Test package created: /tmp/test_root.pkg"
echo "This package MUST require root because it:"
echo "1. Installs to /usr/local/bin"
echo "2. Creates files in /private/var/log"
echo ""
echo "Try opening this in Installer.app to see if it prompts for password."

# Cleanup
rm -rf "$TEST_DIR"

echo ""
echo "🔎 Analysis Complete"
echo ""
echo "Common reasons for 'Done or Trash' instead of password prompt:"
echo "1. User is admin AND has write access to all target locations"
echo "2. Package doesn't contain files that require elevated permissions"
echo "3. macOS Sequoia may have changed Installer.app behavior"
echo ""
echo "Recommendations:"
echo "1. Include system-level files (LaunchDaemons, /usr/local/bin, etc.)"
echo "2. Use a third-party installer wrapper"
echo "3. Create a notarized installer (may trigger different behavior)"
