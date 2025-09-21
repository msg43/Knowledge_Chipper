# Setting Up Packages.app for Skip the Podcast Desktop

## Installation

1. Download Packages.app from: http://s.sudre.free.fr/Software/Packages/about.html
2. Install by dragging to Applications
3. Launch Packages.app

## Creating the Installer Package

### 1. Create New Project
- Open Packages.app
- File → New
- Choose "Distribution" (for a full installer with UI)
- Save as `SkipThePodcast.pkgproj` in your project root

### 2. Project Settings
- **Project** tab:
  - Name: Skip the Podcast Desktop
  - Identifier: com.knowledgechipper.skipthepodcast

### 3. Settings Tab
- **Options**:
  - ✅ Require admin password for installation
  - ✅ Relocatable (uncheck if you want to force /Applications)
  - Authorization: Admin

### 4. Payload Tab
- Add your app:
  - Click "+" → Add Files
  - Select your built .app bundle
  - Destination: /Applications
  - Set permissions: root:admin 755

### 5. Scripts Tab
If you have pre/post install scripts:
- Add scripts with proper permissions
- Set "Run as: root" for scripts that need elevation

### 6. Requirements & Resources Tab
- Add any system requirements
- Customize welcome, license, conclusion screens

### 7. Build
- Build → Build
- Output will be a .pkg file that WILL prompt for authentication

## Key Settings for Authentication

In Packages.app, these settings ensure authentication:

1. **Project Settings → Options**:
   ```
   Authorization Action: Admin Password Required
   ```

2. **For each component**:
   ```
   Authentication: Administrator
   ```

3. **For scripts**:
   ```
   Authorization Level: Root Authorization
   ```

## Command Line Build

You can also build from command line:
```bash
/usr/local/bin/packagesbuild SkipThePodcast.pkgproj
```

## Advantages Over Native Tools

1. **Consistent Behavior**: Always prompts when configured to
2. **Visual Configuration**: No need to hand-edit XML
3. **Better Debugging**: Clear error messages
4. **Professional UI**: Matches Apple's installer style
5. **Signing Support**: Easy integration with codesigning

## Integration with Current Build

To integrate with your current build process:

1. Create the .pkgproj file once (GUI)
2. Update version programmatically:
   ```bash
   # Update version in pkgproj
   /usr/libexec/PlistBuddy -c "Set :PROJECT:PROJECT_SETTINGS:VERSION $VERSION" SkipThePodcast.pkgproj
   ```
3. Build via command line in your scripts

This approach gives you a reliable installer that will always prompt for authentication when needed.
