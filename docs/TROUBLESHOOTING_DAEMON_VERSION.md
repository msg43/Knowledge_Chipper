# Troubleshooting Daemon Version Issues

**Last Updated:** January 12, 2026  
**Status:** Active troubleshooting guide

---

## Problem: Installed PKG Shows Wrong Version

### Symptoms

- Install daemon v1.1.18 PKG
- Website shows "Daemon: Running" but displays v1.1.15 or older
- Restarting doesn't update the version
- Multiple restarts still show old version

### Root Causes

The daemon version mismatch can stem from multiple caching layers:

1. **PyInstaller build cache** - Reuses old compiled Python modules from `build/` directory
2. **Python bytecode cache** - Stale `__pycache__/*.pyc` files with old version embedded
3. **Development daemon** - `python -m daemon.main` running separately, blocks port 8765
4. **Weak restart mechanism** - `launchctl stop/start` doesn't force-kill stubborn processes
5. **Cached binary** - PKG installer packaged old binary from previous build

---

## Solution: Nuclear Clean Build

Use this procedure when you see version mismatches:

### Step 1: Kill ALL Daemon Processes

```bash
# Kill any Python processes running daemon
pkill -9 -f "python.*daemon"
pkill -9 -f "daemon.main"

# Kill the daemon binary
pkill -9 -f "GetReceiptsDaemon"

# Kill anything on port 8765
PORT_PID=$(lsof -ti:8765 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    kill -9 $PORT_PID
fi

# Verify nothing is running
sleep 2
lsof -ti:8765 || echo "✅ Port 8765 is free"
```

### Step 2: Clean ALL Caches

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper

# Use Makefile clean (now enhanced with aggressive cleaning)
make clean

# Or manual deep clean:
rm -rf build/ dist/
find daemon/ -name "__pycache__" -exec rm -rf {} +
find daemon/ -name "*.pyc" -delete
find src/ -name "__pycache__" -exec rm -rf {} +
rm -rf ~/.pyinstaller_cache
```

### Step 3: Rebuild from Scratch

```bash
# Build with fresh artifacts
bash scripts/release_daemon.sh

# The script will now:
# ✓ Check for and kill development daemons
# ✓ Prompt to clean stale build/ dist/ directories
# ✓ Clean Python bytecode cache
# ✓ Clear PyInstaller cache
# ✓ Verify version in built binary
```

### Step 4: Install and Force-Restart

```bash
# Install the newly built PKG
open dist/GetReceipts-Daemon-{version}.pkg

# After installation, FORCE restart (don't use the desktop button yet)
launchctl bootout gui/$(id -u)/org.getreceipts.daemon
sleep 2
launchctl load ~/Library/LaunchAgents/org.getreceipts.daemon.plist
sleep 3

# Verify version
curl -s http://localhost:8765/api/config | python3 -c "import sys, json; print('Version:', json.load(sys.stdin)['version'])"
```

---

## Prevention Checklist

### Before Building a Release

- [ ] Kill all development daemon processes: `pkill -9 -f "python.*daemon"`
- [ ] Run `make clean` to clear all caches
- [ ] Remove build artifacts: `rm -rf build/ dist/`
- [ ] Verify no daemon on port 8765: `lsof -ti:8765` (should be empty)

### During Development

- [ ] **NEVER run** `python -m daemon.main` for production testing
- [ ] **ALWAYS test** using the PKG-installed daemon at `/Applications/GetReceipts Daemon.app`
- [ ] If you need to test code changes, rebuild and reinstall the PKG

### After Installation

- [ ] Use the enhanced restart button: `~/Desktop/Restart GetReceipts.command`
- [ ] Button now force-kills processes and shows version after restart
- [ ] Verify version on website matches installed version

---

## Diagnostic Commands

### Check What's Running

```bash
# Find daemon processes
ps aux | grep -i getreceipts | grep -v grep

# Check port 8765
lsof -i:8765

# Check LaunchAgent status
launchctl list | grep getreceipts
```

### Check Installed Version

```bash
# Check binary timestamp
ls -la "/Applications/GetReceipts Daemon.app/Contents/MacOS/"

# Check running daemon version
curl -s http://localhost:8765/api/config | python3 -c "import sys, json; data = json.load(sys.stdin); print(f\"Version: {data['version']}\nUptime: {data['uptime_seconds']:.0f}s\")"

# Extract version from binary (may not work if obfuscated)
strings "/Applications/GetReceipts Daemon.app/Contents/MacOS/GetReceiptsDaemon" | grep "__version__"
```

### Check Source Code Version

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 -c "from daemon import __version__; print(__version__)"
```

---

## Common Scenarios

### Scenario 1: Development Daemon Blocking Port

**Symptom:** PKG installs correctly but old version still responds

**Cause:** You ran `python -m daemon.main` and it's still running

**Solution:**
```bash
pkill -9 -f "python.*daemon"
launchctl start org.getreceipts.daemon
```

### Scenario 2: Cached PyInstaller Build

**Symptom:** Built PKG has old version despite updated source code

**Cause:** PyInstaller reused cached compiled modules

**Solution:**
```bash
make clean
rm -rf ~/.pyinstaller_cache
bash scripts/release_daemon.sh
```

### Scenario 3: Weak Restart

**Symptom:** Restart button doesn't actually change version

**Cause:** Old restart script only did `launchctl stop/start`

**Solution:** Use enhanced restart button (included in v1.1.18+):
```bash
~/Desktop/Restart\ GetReceipts.command
```

---

## Version History of Fixes

- **v1.1.18** - Enhanced restart scripts with force-kill
- **v1.1.18** - Build script cache cleaning
- **v1.1.18** - Post-build version verification
- **v1.1.18** - Pre-flight checks in release script
- **v1.1.18** - Enhanced Makefile clean target

---

## Still Having Issues?

If you've followed all steps and still see version mismatches:

1. **Check for multiple Python installations:**
   ```bash
   which python3
   python3 --version
   ```

2. **Verify LaunchAgent plist:**
   ```bash
   cat ~/Library/LaunchAgents/org.getreceipts.daemon.plist | grep ProgramArguments -A2
   ```

3. **Check daemon logs:**
   ```bash
   tail -50 /tmp/getreceipts-daemon.stdout.log
   tail -50 /tmp/getreceipts-daemon.stderr.log
   ```

4. **Nuclear option - Complete reinstall:**
   ```bash
   # Uninstall completely
   launchctl unload ~/Library/LaunchAgents/org.getreceipts.daemon.plist
   rm ~/Library/LaunchAgents/org.getreceipts.daemon.plist
   rm -rf "/Applications/GetReceipts Daemon.app"
   pkill -9 -f "daemon"
   
   # Clean and rebuild
   cd /Users/matthewgreer/Projects/Knowledge_Chipper
   make clean
   rm -rf build/ dist/
   bash scripts/release_daemon.sh
   
   # Install fresh
   open dist/GetReceipts-Daemon-{version}.pkg
   ```

---

## Contact

If issues persist, check:
- GitHub Issues: https://github.com/msg43/Knowledge_Chipper/issues
- CHANGELOG.md for version-specific notes
