# Building Voice Typing as a Standalone Executable

This guide shows you how to build Voice Typing as a standalone Windows application (`.exe`) that doesn't require Python to be installed.

## Quick Start

```bash
# 1. Install PyInstaller
pip install pyinstaller

# 2. Build the executable
pyinstaller voice_typing.spec

# 3. Find your executable
# dist\voice_typing\voice_typing.exe
```

## Method 1: Using PyInstaller (Recommended)

### Step 1: Install PyInstaller

```bash
pip install pyinstaller
```

### Step 2: Create Build Spec File

Save this as `voice_typing.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src\\voice_typing\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/voice_typing/ui/assets', 'voice_typing/ui/assets'),  # If you have assets
    ],
    hiddenimports=[
        'faster_whisper',
        'tkinter',
        'PIL',
        'numpy',
        'pydantic',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='voice_typing',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window!
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # Add your icon here
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='voice_typing',
)
```

### Step 3: Build

```bash
pyinstaller voice_typing.spec
```

Your executable will be in `dist\voice_typing\voice_typing.exe`

### Step 4: Create an Icon (Optional)

1. Create or download a microphone icon (256x256 PNG)
2. Convert to .ico using an online converter
3. Save as `icon.ico` in the root directory

## Method 2: Using Auto-py-to-exe (GUI Tool)

Auto-py-to-exe provides a graphical interface for PyInstaller:

```bash
# Install
pip install auto-py-to-exe

# Launch GUI
auto-py-to-exe
```

Settings to use:
- **Script Location**: `src/voice_typing/__main__.py`
- **Onefile**: No (use "One Directory")
- **Console Window**: No
- **Icon**: Your icon file
- **Additional Files**: Any config files or assets

## Method 3: Using cx_Freeze

```bash
# Install
pip install cx_Freeze

# Create setup.py
```

Save as `setup_exe.py`:

```python
from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["faster_whisper", "tkinter", "PIL", "numpy"],
    "includes": ["pydantic", "yaml"],
    "excludes": ["matplotlib", "scipy"],
}

setup(
    name="Voice Typing",
    version="1.0",
    description="Local Speech-to-Text Application",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "src/voice_typing/__main__.py",
            base="Win32GUI",  # No console
            target_name="voice_typing.exe",
            icon="icon.ico",
        )
    ],
)
```

Build:

```bash
python setup_exe.py build
```

## Creating an Installer

### Using Inno Setup (Professional Installer)

1. Download Inno Setup: https://jrsoftware.org/isdl.php
2. Create `installer.iss`:

```iss
[Setup]
AppName=Voice Typing
AppVersion=1.0
DefaultDirName={pf}\Voice Typing
DefaultGroupName=Voice Typing
OutputDir=installer
OutputBaseFilename=VoiceTypingSetup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\voice_typing\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\Voice Typing"; Filename: "{app}\voice_typing.exe"
Name: "{commondesktop}\Voice Typing"; Filename: "{app}\voice_typing.exe"

[Run]
Filename: "{app}\voice_typing.exe"; Description: "Launch Voice Typing"; Flags: postinstall nowait skipifsilent
```

3. Compile with Inno Setup Compiler

## Current Launcher Options (No Build Required)

For now, you can use the launchers included:

### Option 1: Silent VBS Launcher (Recommended)
- **File**: `launch_voice_typing_silent.vbs`
- **Benefits**: No console window, clean launch
- **Usage**: Double-click to run

### Option 2: Batch File Launcher
- **File**: `launch_voice_typing.bat`
- **Benefits**: Shows console (useful for debugging)
- **Usage**: Double-click to run

### Option 3: Desktop Shortcut
```bash
# Create a desktop shortcut automatically:
powershell -ExecutionPolicy Bypass -File create_desktop_shortcut.ps1
```

## Comparison

| Method | Size | Speed | Complexity | Console |
|--------|------|-------|------------|---------|
| VBS Launcher | Small | Fast | Easy | No |
| Batch Launcher | Small | Fast | Easy | Yes |
| PyInstaller | ~500MB | Medium | Medium | No |
| cx_Freeze | ~400MB | Medium | Medium | No |
| Auto-py-to-exe | ~500MB | Medium | Easy | No |

## Recommendations

**For Development**: Use VBS launcher (no build needed)

**For Distribution**: Use PyInstaller with Inno Setup installer

**For Simplicity**: Use the desktop shortcut script

## Troubleshooting

### PyInstaller Issues

**Missing modules**:
```bash
# Add to hiddenimports in spec file
hiddenimports=['missing_module']
```

**Large file size**:
```bash
# Use UPX compression
upx=True
```

**DLL errors**:
```bash
# Include in binaries
binaries=[('path/to/file.dll', '.')]
```

### Running the Built Executable

1. First run may be slow (extracting)
2. Ensure models are downloaded
3. Check config file exists
4. Run from command line to see errors

## Next Steps

1. **Try the VBS launcher** (easiest option)
2. **Create desktop shortcut** using the PowerShell script
3. **Build with PyInstaller** if you need a standalone .exe
4. **Create installer** for professional distribution

---

*Current Status: VBS launcher and shortcut creator are ready to use!*

