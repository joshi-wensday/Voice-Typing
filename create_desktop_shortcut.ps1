# PowerShell Script to Create Desktop Shortcut for Voice Typing
# Run this with: powershell -ExecutionPolicy Bypass -File create_desktop_shortcut.ps1

Write-Host "Creating Voice Typing Desktop Shortcut..." -ForegroundColor Green

# Get the current directory (where Voice Typing is installed)
$voiceTypingPath = $PSScriptRoot

# Path to the silent launcher
$launcherPath = Join-Path $voiceTypingPath "launch_voice_typing_silent.vbs"

# Check if launcher exists
if (-not (Test-Path $launcherPath)) {
    Write-Host "Error: Launcher not found at $launcherPath" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create shortcut on desktop
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Voice Typing.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $launcherPath
$Shortcut.WorkingDirectory = $voiceTypingPath
$Shortcut.Description = "Voice Typing - Local Speech-to-Text"
$Shortcut.IconLocation = "shell32.dll,222"  # Microphone icon
$Shortcut.Save()

Write-Host ""
Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "  Location: $shortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now double-click 'Voice Typing' on your desktop to launch the app!" -ForegroundColor Yellow
Write-Host ""

Read-Host "Press Enter to exit"

