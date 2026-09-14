; Inno Setup Script for QwikPrint Desktop Print Agent
; App Name: QwikPrint

[Setup]
AppId={{D37B4A11-48C9-4F90-84E1-9B5A3D730C82}
AppName=QwikPrint
AppVersion=4.0.5
AppPublisher=QwikPrint
AppPublisherURL=https://github.com/akmtechofficial/QwikPrint
DefaultDirName={autopf}\QwikPrint
DefaultGroupName=QwikPrint
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=QwikPrint_Setup
SetupIconFile=gui\app_icon.ico
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\PrintAgent.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PrintAgent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "gui\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "gui\qwikprint_logo.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\QwikPrint"; Filename: "{app}\PrintAgent.exe"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,QwikPrint}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\QwikPrint"; Filename: "{app}\PrintAgent.exe"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\PrintAgent.exe"; Description: "{cm:LaunchProgram,QwikPrint}"; Flags: nowait postinstall skipifsilent
