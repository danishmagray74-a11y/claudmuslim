; Claude Muslim Windows installer
#define MyAppName "Claude Muslim"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Claude Muslim"
#define MyAppExeName "ClaudeMuslim.exe"

[Setup]
AppId={{D5B23B80-6F8C-4E2B-9A2E-1B3D9E7F61A4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\ClaudeMuslim
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\output
OutputBaseFilename=ClaudeMuslim-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\ClaudeMuslim.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Claude Muslim"; Filename: "{app}\ClaudeMuslim.exe"
Name: "{autodesktop}\Claude Muslim"; Filename: "{app}\ClaudeMuslim.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ClaudeMuslim.exe"; Description: "Launch Claude Muslim"; Flags: postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C schtasks /Delete /TN ""ClaudeMuslim-Interval"" /F"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/C schtasks /Delete /TN ""ClaudeMuslim-Logon"" /F"; Flags: runhidden
