; =====================================================================
; Inno Setup Script for QwikPrint Desktop Print Agent & Spooler
; App Name: QwikPrint Desktop Spooler
; Version: 2.4.0
; =====================================================================

[Setup]
AppId={{D37B4A11-48C9-4F90-84E1-9B5A3D730C82}
AppName=QwikPrint Desktop Spooler
AppVersion=2.4.0
AppPublisher=QwikPrint Inc.
AppPublisherURL=https://qwikprint.onrender.com
DefaultDirName={autopf}\QwikPrint
DefaultGroupName=QwikPrint
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=QwikPrint_Setup
SetupIconFile=gui\app_icon.ico
UninstallDisplayIcon={app}\PrintAgent.exe
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkablealone
Name: "autostart"; Description: "Automatically launch QwikPrint when Windows starts"; GroupDescription: "System Startup:"; Flags: checkablealone

[Files]
Source: "..\dist\PrintAgent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "gui\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "gui\qwikprint_logo.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\QwikPrint Desktop Spooler"; Filename: "{app}\PrintAgent.exe"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,QwikPrint}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\QwikPrint Desktop Spooler"; Filename: "{app}\PrintAgent.exe"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "QwikPrintAgent"; ValueData: """{app}\PrintAgent.exe"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "net"; Parameters: "start spoolsv"; Flags: runhidden
Filename: "{app}\PrintAgent.exe"; Description: "{cm:LaunchProgram,QwikPrint Desktop Spooler}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM PrintAgent.exe"; Flags: runhidden; RunOnceId: "KillQwikPrintAgent"

[UninstallDelete]
Type: files; Name: "{userappdata}\Microsoft\Windows\Start Menu\Programs\Startup\QwikPrintAgent.lnk"
Type: filesandordirs; Name: "{userappdata}\QwikPrint"
Type: filesandordirs; Name: "{userappdata}\QwikPrintAgent"
Type: filesandordirs; Name: "{localappdata}\QwikPrint"
Type: filesandordirs; Name: "{app}"

[Code]
// Pascal Scripting for Pre-install / Pre-uninstall process management and dependency checks

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Kill running instance before installing/updating
  Exec('taskkill', '/F /IM PrintAgent.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill', '/F /IM QwikPrintAgent.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  // Ensure Windows Print Spooler service is active
  Exec('net', 'start spoolsv', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Kill running instance before uninstalling
  Exec('taskkill', '/F /IM PrintAgent.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill', '/F /IM QwikPrintAgent.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
