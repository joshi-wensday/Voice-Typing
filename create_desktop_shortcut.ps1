# PowerShell Script to Create Desktop Shortcut for Vype
# Run this with: powershell -ExecutionPolicy Bypass -File create_desktop_shortcut.ps1

Write-Host "Creating Vype Desktop Shortcut..." -ForegroundColor Green

# Get the current directory (where Vype is installed)
$vypePath = $PSScriptRoot

# Path to the silent launcher
$launcherPath = Join-Path $vypePath "launch_vype_silent.vbs"

# Check if launcher exists
if (-not (Test-Path $launcherPath)) {
    Write-Host "Error: Launcher not found at $launcherPath" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create shortcut on desktop
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Vype.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $launcherPath
$Shortcut.WorkingDirectory = $vypePath
$Shortcut.Description = "Vype - Local Voice Dictation"

# Try to use custom icon, fall back to default if not found
$iconPath = Join-Path $vypePath "logo-1280.ico"
if (-not (Test-Path $iconPath)) {
    # Try in src/vype/ui/assets/
    $iconPath = Join-Path $vypePath "src\vype\ui\assets\logo-1280.ico"
}

if (Test-Path $iconPath) {
    $Shortcut.IconLocation = $iconPath
} else {
    $Shortcut.IconLocation = "shell32.dll,222"  # Microphone icon fallback
}

$Shortcut.Save()

Write-Host ""
Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "  Location: $shortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now double-click 'Vype' on your desktop to launch the app!" -ForegroundColor Yellow
Write-Host ""

Read-Host "Press Enter to exit"

