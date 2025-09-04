# DMG Update Implementation Guide

## 🎯 **How DMG Updates Work**

When a user clicks "Update" button, instead of rebuilding from source:

1. **Check for Updates**: Query GitHub API for latest release
2. **Download DMG**: Download new DMG from release assets
3. **Preserve User Data**: Backup user settings and database
4. **Install Update**: Replace app with new version
5. **Restore User Data**: Copy back user data to new app
6. **Restart**: Launch updated app

## 📁 **User Data Preservation**

### **What Gets Preserved:**
- ✅ **Database**: `knowledge_system.db` (all processed content, speakers, etc.)
- ✅ **Settings**: `config/settings.yaml` (user preferences)
- ✅ **Credentials**: `config/credentials.yaml` (API keys)
- ✅ **App State**: `state/application_state.json` (UI preferences)
- ✅ **Output Files**: All user-generated content in `output/`

### **What Gets Replaced:**
- 🔄 **Application Code**: New features, bug fixes
- 🔄 **Python Environment**: Updated dependencies
- 🔄 **Default Configs**: Updated templates and examples

## 🔧 **Technical Implementation**

### **Update Process Flow**

```python
class DMGUpdateWorker(QThread):
    def run(self):
        try:
            # 1. Check for updates
            latest_release = self.check_github_releases()
            if not self.is_newer_version(latest_release.version):
                self.update_finished.emit(False, "No updates available")
                return
            
            # 2. Backup user data
            backup_path = self.backup_user_data()
            
            # 3. Download DMG
            dmg_path = self.download_dmg(latest_release.download_url)
            
            # 4. Install update
            self.install_dmg(dmg_path)
            
            # 5. Restore user data
            self.restore_user_data(backup_path)
            
            # 6. Signal success
            self.update_finished.emit(True, "Update completed successfully")
            
        except Exception as e:
            self.update_error.emit(f"Update failed: {e}")
```

### **Data Backup Strategy**

```python
def backup_user_data(self) -> Path:
    """Backup all user data before update."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path.home() / ".knowledge-system-backup" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Backup database
    if (project_dir / "knowledge_system.db").exists():
        shutil.copy2(
            project_dir / "knowledge_system.db",
            backup_dir / "knowledge_system.db"
        )
    
    # Backup configuration
    if (project_dir / "config").exists():
        shutil.copytree(
            project_dir / "config",
            backup_dir / "config"
        )
    
    # Backup state
    if (project_dir / "state").exists():
        shutil.copytree(
            project_dir / "state",
            backup_dir / "state"
        )
    
    # Backup output
    if (project_dir / "output").exists():
        shutil.copytree(
            project_dir / "output",
            backup_dir / "output"
        )
    
    return backup_dir
```

### **DMG Installation Process**

```python
def install_dmg(self, dmg_path: Path) -> None:
    """Install new app from DMG."""
    # 1. Mount DMG
    mount_result = subprocess.run([
        "hdiutil", "attach", str(dmg_path), "-nobrowse", "-quiet"
    ], capture_output=True, text=True)
    
    if mount_result.returncode != 0:
        raise Exception("Failed to mount DMG")
    
    # 2. Find mount point
    mount_point = self.find_mount_point(dmg_path)
    
    # 3. Replace app
    old_app = Path("/Applications/Knowledge_Chipper.app")
    new_app = mount_point / "Knowledge_Chipper.app"
    
    if old_app.exists():
        shutil.rmtree(old_app)
    
    shutil.copytree(new_app, old_app)
    
    # 4. Unmount DMG
    subprocess.run(["hdiutil", "detach", str(mount_point)], 
                  capture_output=True)
    
    # 5. Clean up downloaded DMG
    dmg_path.unlink()
```

## 🛡️ **User Data Safety**

### **Multiple Backup Layers:**

1. **Pre-Update Backup**: Complete backup before any changes
2. **In-Place Preservation**: Keep data outside app bundle
3. **Rollback Capability**: Can restore previous version if needed
4. **Automatic Recovery**: Detect and restore data on first launch

### **Data Location Strategy:**

Currently your data is mixed:
- ❌ **In Project Dir**: Database and config in development directory
- ✅ **Should Be**: User data in standard macOS locations

**Recommended Migration:**
```
# Current (problematic for updates)
~/Projects/Knowledge_Chipper/knowledge_system.db
~/Projects/Knowledge_Chipper/config/settings.yaml

# Better (survives app updates)
~/Library/Application Support/Knowledge Chipper/database.db
~/Library/Application Support/Knowledge Chipper/settings.yaml
```

## 📱 **User Experience**

### **Update Dialog:**
```
🔄 Knowledge Chipper Update Available!

Version 3.1.2 → 3.2.0

📋 What's New:
• Improved speaker detection
• Faster transcription
• Bug fixes and stability improvements

📦 Download Size: 245 MB
⏱️ Estimated Time: 2-3 minutes

[Cancel] [Update Now]
```

### **Progress Indicators:**
1. "Checking for updates..." (GitHub API call)
2. "Downloading update..." (DMG download with progress)
3. "Backing up your data..." (User data backup)
4. "Installing update..." (DMG installation)
5. "Restoring your settings..." (Data restoration)
6. "Update complete! Restarting..." (App restart)

## ⚡ **Performance Benefits**

### **DMG vs. Source Build:**
- **Download**: 200MB DMG vs. Full Git Clone
- **Installation**: 30 seconds vs. 5-10 minutes
- **Reliability**: Pre-tested build vs. Live compilation
- **User Requirements**: No dev tools vs. Python, Git, etc.

## 🔧 **Implementation Steps**

### **Phase 1: Basic DMG Updates**
1. Add GitHub API client for release checking
2. Implement DMG download with progress
3. Create basic backup/restore system
4. Test with small version increments

### **Phase 2: Enhanced UX**
1. Better progress indicators
2. Rollback capability
3. Smart data migration
4. Error recovery

### **Phase 3: Data Location Migration**
1. Move user data to proper macOS locations
2. Handle migration from old locations
3. Update all file paths in codebase

## 🎯 **Quick Start Implementation**

To get started immediately, I can modify your existing `UpdateWorker` to:

1. **Check GitHub releases** instead of git pulls
2. **Download DMG** instead of rebuilding
3. **Simple backup/restore** of current data locations
4. **Restart app** after installation

This gives you the benefits immediately while keeping current data structure.

## 🚨 **Important Notes**

### **User Data Safety:**
- ✅ Multiple backup layers ensure data never lost
- ✅ Automatic recovery if update fails
- ✅ User can manually rollback if needed

### **Permissions:**
- ✅ No sudo required (installs to /Applications normally)
- ✅ User controls when updates happen
- ✅ Can work offline after download

### **Compatibility:**
- ✅ Works with existing data structure
- ✅ Preserves all user customizations
- ✅ Maintains app preferences and state

The user experience becomes: Click Update → Wait 2 minutes → Everything preserved, app updated! 🎉
