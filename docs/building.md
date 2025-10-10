# Building Vype Executables

This guide covers how to build Vype executables for distribution.

## Prerequisites

### Required Software

1. **Python 3.10+** - Make sure it's in your PATH
2. **PyInstaller** - Will be installed automatically by build script
3. **Inno Setup 6.0+** (for Windows installer) - Download from [jrsoftware.org](https://jrsoftware.org/isdl.php)

### Install Dependencies

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install PyInstaller specifically
pip install pyinstaller
```

## Building the Portable Executable

The portable executable is a standalone version that doesn't require installation.

### Quick Build

```bash
# Run the build script
python scripts/build_portable.py
```

This will:
1. Check for PyInstaller and install if needed
2. Clean previous builds
3. Run PyInstaller with the `vype.spec` configuration
4. Create executable in `dist/Vype/Vype.exe`

### Manual Build

If you prefer to run PyInstaller manually:

```bash
pyinstaller vype.spec --clean --noconfirm
```

### Output

- **Location**: `dist/Vype/`
- **Main executable**: `Vype.exe`
- **Size**: ~100-150 MB (without models)
- **Contents**: All Python dependencies bundled

### Testing the Portable Build

```bash
# Run from dist directory
cd dist/Vype
Vype.exe
```

**Test checklist:**
- [ ] Application launches without errors
- [ ] System tray icon appears
- [ ] Hotkey registration works
- [ ] Settings window opens
- [ ] Audio capture works
- [ ] Model download works
- [ ] Transcription works
- [ ] Configuration persists after restart

## Building the Installer

The installer provides a complete installation experience with shortcuts and optional components.

### Prerequisites

1. Build the portable executable first (see above)
2. Install [Inno Setup](https://jrsoftware.org/isdl.php)
3. Add Inno Setup to your PATH or note the installation directory

### Build Installer

```bash
# Using Inno Setup from command line
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" vype_installer.iss
```

Or open `vype_installer.iss` in Inno Setup and click "Compile".

### Output

- **Location**: `installer_output/`
- **Filename**: `vype-setup-v1.0.0.exe`
- **Size**: ~100-150 MB
- **Type**: Windows Installer

### Installer Features

The installer includes:
- ✓ Complete application installation
- ✓ Start Menu shortcuts
- ✓ Desktop icon (optional)
- ✓ Quick Launch icon (optional)
- ✓ Startup on boot (optional)
- ✓ Uninstaller
- ✓ Config directory creation

### Testing the Installer

Test on a **clean Windows installation** (VM recommended):

1. Run the installer
2. Test all installation options
3. Verify shortcuts work
4. Launch application
5. Test all features
6. Uninstall and verify cleanup

## Build Configuration

### PyInstaller Spec File

The `vype.spec` file controls the executable build:

**Key settings:**
- `console=False` - No console window
- `icon='logo-1280.ico'` - Application icon
- `upx=True` - UPX compression
- Hidden imports for Whisper, sounddevice, etc.

**Customizing:**
```python
# Edit vype.spec to:
# - Add/remove hidden imports
# - Include additional data files
# - Change compression settings
# - Modify executable name
```

### Inno Setup Script

The `vype_installer.iss` file controls the installer:

**Key settings:**
- Version number
- Application ID (GUID)
- Installation directory
- Optional components
- File associations

## Distribution

### Portable Distribution

1. Zip the `dist/Vype` directory:
   ```bash
   cd dist
   tar -a -c -f vype-portable-v1.0.0.zip Vype
   ```

2. Upload to GitHub Releases

3. Include README with:
   - Minimum system requirements
   - First-run instructions
   - Model download info

### Installer Distribution

1. Test the installer thoroughly
2. Sign the executable (optional but recommended)
3. Upload to GitHub Releases
4. Create checksums:
   ```bash
   certutil -hashfile vype-setup-v1.0.0.exe SHA256
   ```

## Versioning

Update version in multiple files before building:

1. `pyproject.toml` - `version = "1.0.0"`
2. `vype_installer.iss` - `#define MyAppVersion "1.0.0"`
3. `src/vype/__init__.py` - `__version__ = "1.0.0"`
4. `CHANGELOG.md` - Add release notes

## Code Signing (Optional)

For trusted installations, sign the executables:

```bash
# Using signtool (Windows SDK)
signtool sign /f cert.pfx /p password /t http://timestamp.digicert.com Vype.exe
```

## Troubleshooting

### Missing DLL Errors

If users report missing DLLs:
1. Check hidden imports in `vype.spec`
2. Add to `binaries` list if needed
3. Test on clean Windows install

### Large File Size

To reduce executable size:
1. Review `excludes` in `vype.spec`
2. Remove unnecessary dependencies
3. Use UPX compression
4. Consider lazy loading for large libraries

### Import Errors

If modules aren't found:
1. Add to `hiddenimports` in `vype.spec`
2. Use `collect_submodules()` for packages
3. Test with `--debug all` flag

### Antivirus False Positives

PyInstaller executables may trigger antivirus:
1. Submit to antivirus vendors for whitelisting
2. Sign the executable with a certificate
3. Build with `--debug bootloader` to investigate
4. Add exceptions for common AVs in documentation

## Release Checklist

Before releasing:

- [ ] Update version numbers
- [ ] Update CHANGELOG.md
- [ ] Build portable executable
- [ ] Test portable on clean Windows
- [ ] Build installer
- [ ] Test installer on clean Windows
- [ ] Create release notes
- [ ] Tag release in git
- [ ] Upload to GitHub Releases
- [ ] Update documentation
- [ ] Announce release

## GitHub Release Template

```markdown
# Vype v1.0.0 - Release Name

## 🎉 New Features
- Feature 1
- Feature 2

## 🐛 Bug Fixes  
- Fix 1
- Fix 2

## 📥 Downloads

- **Installer** (Recommended): `vype-setup-v1.0.0.exe` (150 MB)
  - Includes shortcuts, uninstaller, and auto-updates
  
- **Portable**: `vype-portable-v1.0.0.zip` (100 MB)
  - No installation required, extract and run

## 💻 System Requirements
- Windows 10/11 (64-bit)
- 4GB RAM minimum
- 500MB free disk space (more for models)

## 📝 Installation

**Installer:** Run the `.exe` and follow the wizard.

**Portable:** Extract the `.zip` and run `Vype.exe`.

## ⚠️ Known Issues
- Issue 1
- Issue 2

## 📋 Checksums
```
SHA256: [hash here]
```
```

## Support

For build issues:
1. Check this documentation
2. Review PyInstaller docs
3. Check Inno Setup docs
4. Open an issue on GitHub

