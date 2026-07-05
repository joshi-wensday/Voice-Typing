; Inno Setup script for Vype V2.
; Build after PyInstaller:  ISCC vype_installer.iss

#define AppVersion "2.0.0-beta.1"

[Setup]
AppId={{8E2F1B7A-9C43-4D6B-A1E0-VYPE00000002}
AppName=Vype
AppVersion={#AppVersion}
AppPublisher=Josh
AppPublisherURL=https://github.com/joshi-wensday/Voice-Typing
DefaultDirName={autopf}\Vype
DefaultGroupName=Vype
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer_output
OutputBaseFilename=vype-setup-v{#AppVersion}
SetupIconFile=logo-1280.ico
UninstallDisplayIcon={app}\vype.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"
Name: "startupicon"; Description: "Start Vype when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "dist\vype\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Vype"; Filename: "{app}\vype.exe"
Name: "{autodesktop}\Vype"; Filename: "{app}\vype.exe"; Tasks: desktopicon
Name: "{userstartup}\Vype"; Filename: "{app}\vype.exe"; Tasks: startupicon

[Run]
Filename: "{app}\vype.exe"; Description: "Launch Vype now"; Flags: nowait postinstall skipifsilent
