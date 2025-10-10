# Vype v1.0.0 Release Guide

## ✅ Git Commit Complete

**Commit Hash:** Check with `git log -1`  
**Files Changed:** 62 files  
**Lines Added:** 5,736  
**Status:** Ready for release

---

## 📋 Pre-Release Checklist

Before building the installer, verify these items:

### 1. Code Quality ✅
- [x] All linter errors fixed
- [x] No debug print statements (except intentional logging)
- [x] All imports updated to `vype`
- [x] Tests updated and passing

### 2. Version Check ✅
- [x] `pyproject.toml` version: `1.0.0`
- [x] `vype_installer.iss` version: `1.0.0`
- [x] README.md references correct version

### 3. Documentation ✅
- [x] README.md updated with Vype branding
- [x] CHANGELOG.md exists
- [x] LICENSE file present
- [x] Release checklist created

---

## 🔨 Building the Installer

### Prerequisites

1. **Install Python Dependencies**
   ```powershell
   # Activate your virtual environment first
   .\venv\Scripts\activate
   
   # Verify installation
   pip list | findstr faster-whisper
   ```

2. **Install PyInstaller**
   ```powershell
   pip install pyinstaller
   ```

3. **Install Inno Setup**
   - Download from: https://jrsoftware.org/isdl.php
   - Use Inno Setup 6.0 or later
   - Install to default location: `C:\Program Files (x86)\Inno Setup 6`

### Step 1: Build Portable Executable

```powershell
# Run the build script
python scripts\build_portable.py
```

This will:
- Clean previous builds
- Run PyInstaller with `vype.spec`
- Create `dist\Vype\Vype.exe`
- Display executable size and location

**Expected Output:**
```
✓ PyInstaller X.X.X found
✓ Spec file found: C:\...\vype.spec
Building executable...
✓ Build successful!

Executable: dist\Vype\Vype.exe
Size: ~150-200 MB
```

### Step 2: Test the Executable

```powershell
# Test the portable executable
cd dist\Vype
.\Vype.exe
```

**Test Checklist:**
- [ ] Application launches without errors
- [ ] System tray icon appears
- [ ] Visualizer displays correctly
- [ ] Settings window opens
- [ ] Hotkey works
- [ ] Can record and transcribe
- [ ] Model management works
- [ ] No missing DLL errors

### Step 3: Build Windows Installer

```powershell
# Return to project root
cd ..\..

# Compile installer with Inno Setup
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" vype_installer.iss
```

**Expected Output:**
```
Inno Setup 6.x.x
Compiling: vype_installer.iss
...
Successful compile (XX warnings)

Output: installer_output\vype-setup-v1.0.0.exe
```

### Step 4: Test the Installer

```powershell
# Run the installer
.\installer_output\vype-setup-v1.0.0.exe
```

**Test Checklist:**
- [ ] Installer UI displays correctly
- [ ] License and README show properly
- [ ] Installation completes successfully
- [ ] Desktop shortcut created (if selected)
- [ ] Start Menu shortcuts work
- [ ] Application runs from installed location
- [ ] Uninstaller works completely

---

## 📦 Creating Release Assets

### 1. Create Portable ZIP

```powershell
# Create a zip of the portable executable
Compress-Archive -Path dist\Vype\* -DestinationPath vype-portable-v1.0.0.zip
```

### 2. Generate Checksums

```powershell
# Calculate SHA256 checksums
Get-FileHash .\installer_output\vype-setup-v1.0.0.exe -Algorithm SHA256 | Format-List
Get-FileHash .\vype-portable-v1.0.0.zip -Algorithm SHA256 | Format-List

# Save to file
@"
SHA256 Checksums for Vype v1.0.0
================================

vype-setup-v1.0.0.exe
$(Get-FileHash .\installer_output\vype-setup-v1.0.0.exe -Algorithm SHA256 | Select-Object -ExpandProperty Hash)

vype-portable-v1.0.0.zip
$(Get-FileHash .\vype-portable-v1.0.0.zip -Algorithm SHA256 | Select-Object -ExpandProperty Hash)
"@ | Out-File SHA256SUMS.txt
```

### 3. Create Source Archive

```powershell
# Create source code archive
git archive --format=zip --prefix=vype-1.0.0/ -o vype-v1.0.0-source.zip HEAD
```

---

## 🚀 Publishing the Release

### Option 1: GitHub Release (Recommended)

1. **Push to GitHub**
   ```powershell
   git push origin main
   ```

2. **Create Tag**
   ```powershell
   git tag -a v1.0.0 -m "Vype v1.0.0 - Initial Release"
   git push origin v1.0.0
   ```

3. **Create GitHub Release**
   - Go to: https://github.com/yourusername/vype/releases/new
   - Select tag: `v1.0.0`
   - Title: `Vype v1.0.0 - Initial Release`
   - Description: Use content from CHANGELOG.md
   
4. **Upload Assets**
   - `vype-setup-v1.0.0.exe` (Installer)
   - `vype-portable-v1.0.0.zip` (Portable)
   - `vype-v1.0.0-source.zip` (Source)
   - `SHA256SUMS.txt` (Checksums)

### Option 2: Direct Distribution

Simply share the files:
- **For most users**: `vype-setup-v1.0.0.exe`
- **For portable use**: `vype-portable-v1.0.0.zip`
- **For developers**: `vype-v1.0.0-source.zip`

---

## 📊 Release Verification

### Final Checks

1. **File Sizes**
   - Installer: ~150-200 MB
   - Portable ZIP: ~100-150 MB
   - Source: ~1-5 MB

2. **Virus Scanning**
   - Upload installer to VirusTotal
   - Verify no false positives
   - Include scan link in release notes

3. **Clean Install Test**
   - Test on a fresh Windows 10 VM
   - Test on a fresh Windows 11 VM
   - Verify first-run experience
   - Check model download functionality

---

## 📢 Announcement Template

```markdown
# Vype v1.0.0 Released! 🎉

**Vype** (Voice + Type) - Local voice dictation that respects your privacy.

## 🎯 What is Vype?

Vype is a voice dictation tool that runs entirely on your PC using OpenAI Whisper.
No cloud, no subscriptions, no privacy concerns.

## ✨ Key Features

- 🎤 Real-time voice dictation with 99%+ accuracy
- 🎨 Beautiful circular audio spectrum visualizer
- 🔧 Comprehensive model management (10+ Whisper models)
- 🌈 Full theme customization
- 💻 100% local processing - your audio never leaves your machine

## 📥 Download

**Installer (Recommended):** [vype-setup-v1.0.0.exe](link) - 150 MB  
**Portable:** [vype-portable-v1.0.0.zip](link) - 100 MB

## 💻 Requirements

- Windows 10/11 (64-bit)
- 4GB RAM minimum (8GB recommended)
- 500MB free disk space

## 📖 Quick Start

1. Download and install
2. Press Ctrl+Alt+Space to start dictating
3. Speak naturally
4. Watch your words appear!

## 🙏 Feedback

Found a bug? Have a feature request?  
Open an issue: https://github.com/yourusername/vype/issues

## ⭐ Support

If you like Vype, give it a star on GitHub!
```

---

## 🔄 Post-Release

### Immediate Actions

1. **Monitor Issues**
   - Watch for bug reports
   - Respond within 24 hours
   - Fix critical issues immediately

2. **Gather Feedback**
   - Track download statistics
   - Read user reviews
   - Note feature requests

3. **Plan Next Release**
   - Prioritize bug fixes
   - Evaluate new features
   - Set timeline for v1.1.0

### Documentation Updates

1. Update project README with download links
2. Add installation guide screenshots
3. Create video tutorials (optional)
4. Update documentation website

---

## 🛠️ Troubleshooting Build Issues

### PyInstaller Fails

```powershell
# Clean everything and rebuild
Remove-Item -Recurse -Force dist, build
pip install --upgrade pyinstaller
python scripts\build_portable.py
```

### Inno Setup Can't Find Files

- Verify `dist\Vype\Vype.exe` exists
- Check all paths in `vype_installer.iss`
- Ensure working directory is project root

### Executable Won't Run

- Test on clean Windows install
- Check for missing DLLs with Dependency Walker
- Verify PyInstaller spec file includes all dependencies

### Installer Size Too Large

- Normal for applications with ML models
- 150-200 MB is expected
- Models are not included (downloaded separately)

---

## 📝 Notes

- **First Release**: This is v1.0.0, expect some user feedback
- **Model Downloads**: Users download models on first use
- **GPU Support**: Works on both CPU and CUDA devices
- **Updates**: Plan for auto-update mechanism in v1.1.0

---

## ✅ You're Ready!

Your release is ready to ship! 🚀

**Next Command:**
```powershell
# Build the executable
python scripts\build_portable.py

# Then build the installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" vype_installer.iss
```

Good luck with your release! 🎉

