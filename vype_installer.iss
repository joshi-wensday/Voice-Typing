; Inno Setup Script for Vype
; Requires Inno Setup 6.0 or later
; Download from: https://jrsoftware.org/isdl.php

#define MyAppName "Vype"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Vype Team"
#define MyAppURL "https://github.com/yourusername/vype"
#define MyAppExeName "Vype.exe"

[Setup]
; Basic application information
AppId={{B8F3C9D1-4E2A-4F1B-9C3D-7A5E8F9B2C1D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
LicenseFile=LICENSE
InfoBeforeFile=README.md
OutputDir=installer_output
OutputBaseFilename=vype-setup-v{#MyAppVersion}
SetupIconFile=logo-1280.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; Visual settings - use Inno Setup defaults
; WizardImageFile=compiler:WizModernImage-IS.bmp
; WizardSmallImageFile=compiler:WizModernSmallImage-IS.bmp

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Launch Vype on system startup"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable and all files from PyInstaller build
Source: "dist\Vype\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Documentation
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

; Config example
Source: "config.example.yaml"; DestDir: "{app}"; Flags: ignoreversion

; Launcher scripts
Source: "launch_vype.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "launch_vype_silent.vbs"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} Settings"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--settings"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

; Desktop icon
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; Quick Launch
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

; Startup
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\launch_vype_silent.vbs"; Tasks: startupicon

[Run]
; Option to launch after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Check if .NET Framework or other prerequisites are installed
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Add any prerequisite checks here
end;

// Custom wizard page for additional options
procedure InitializeWizard();
begin
  // Could add custom pages here for model selection, etc.
end;

// Post-install actions
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Create config directory in user's AppData
    CreateDir(ExpandConstant('{userappdata}\vype'));
    
    // Could download default model here if needed
    // MsgBox('Vype has been installed successfully!', mbInformation, MB_OK);
  end;
end;

[UninstallDelete]
; Clean up config files on uninstall (ask user first)
Type: filesandordirs; Name: "{userappdata}\vype"

