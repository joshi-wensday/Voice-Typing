# 🚀 Voice Typing - Launcher Guide

## Quick Start

### Option 1: Desktop Shortcut (Recommended)

Create a desktop shortcut in one step:

```powershell
powershell -ExecutionPolicy Bypass -File create_desktop_shortcut.ps1
```

Then double-click **"Voice Typing"** on your desktop!

### Option 2: Silent Launch (No Console)

Double-click: **`launch_voice_typing_silent.vbs`**

- ✅ No console window
- ✅ Launches in background
- ✅ Clean and professional

### Option 3: Batch File (With Console)

Double-click: **`launch_voice_typing.bat`**

- ✅ Shows console (useful for debugging)
- ✅ See error messages
- ✅ Keep window open on error

---

## Launcher Files

| File | What It Does |
|------|--------------|
| `launch_voice_typing_silent.vbs` | Launch without console (recommended) |
| `launch_voice_typing.bat` | Launch with console window |
| `create_desktop_shortcut.ps1` | Create desktop shortcut |
| `BUILD_EXE.md` | Build standalone .exe (advanced) |

---

## Creating Desktop Shortcut

### Method 1: PowerShell Script (Automatic)

```powershell
powershell -ExecutionPolicy Bypass -File create_desktop_shortcut.ps1
```

### Method 2: Manual

1. Right-click `launch_voice_typing_silent.vbs`
2. Click "Create shortcut"
3. Drag shortcut to desktop
4. Rename to "Voice Typing"

---

## Building a Standalone Application

Want a `.exe` that doesn't need Python? See **`BUILD_EXE.md`** for:

- **PyInstaller** (recommended) - Creates standalone executable
- **Auto-py-to-exe** - GUI tool for PyInstaller
- **cx_Freeze** - Alternative builder
- **Inno Setup** - Professional installer

### Quick Build

```bash
pip install pyinstaller
pyinstaller voice_typing.spec
# Your .exe will be in dist/voice_typing/
```

---

## Troubleshooting

### "Virtual environment not found"

Run the setup script first:

```bash
python scripts\setup_dev.py
```

### Desktop shortcut doesn't work

1. Make sure you're in the Voice-Typing directory
2. Run the PowerShell script from the correct location
3. Check that `launch_voice_typing_silent.vbs` exists

### Want to see errors?

Use the batch file launcher instead:
```bash
launch_voice_typing.bat
```

---

## What Each Launcher Does

### VBS Launcher (Silent)
```vbs
' Launches Python in background
' No console window
' Returns immediately
```

### Batch Launcher
```batch
REM Shows console
REM Activates venv
REM Runs Python
REM Pauses on error
```

### Desktop Shortcut
```powershell
# Creates .lnk file on desktop
# Points to VBS launcher
# Uses microphone icon
```

---

## Next Steps

1. **Create desktop shortcut**: Run the PowerShell script
2. **Launch Voice Typing**: Double-click the shortcut
3. **Build standalone exe** (optional): See BUILD_EXE.md

---

*All launchers are ready to use!* 🎉

