#ifndef SourceRoot
  #define SourceRoot "..\.."
#endif
#define AppVersion "2.0.0"
[Setup]
AppId={{87CCF3A0-93D8-43E1-9D27-4CF124BD5A80}
AppName=مخازن التعيينات
AppVersion={#AppVersion}
AppPublisher=Logistics Workspace
DefaultDirName={localappdata}\Programs\Logistics
DefaultGroupName=مخازن التعيينات
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#SourceRoot}\dist
OutputBaseFilename=Logistics-Setup-{#AppVersion}
SetupIconFile={#SourceRoot}\static\img\app.ico
UninstallDisplayIcon={app}\Logistics.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex=LogisticsDesktopV2
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce
[Files]
Source: "{#SourceRoot}\dist\Logistics\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\runtime\installer\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; DestDir: "{tmp}"; Flags: dontcopy
[Icons]
Name: "{group}\مخازن التعيينات"; Filename: "{app}\Logistics.exe"
Name: "{autodesktop}\مخازن التعيينات"; Filename: "{app}\Logistics.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\Logistics.exe"; Description: "Open Logistics Workspace"; Flags: nowait postinstall skipifsilent
[Code]
function HasWebViewAt(Root: Integer): Boolean;
var Names: TArrayOfString; I: Integer; Name, Version: String;
begin
  Result := False;
  if RegGetSubkeyNames(Root, 'SOFTWARE\Microsoft\EdgeUpdate\Clients', Names) then
    for I := 0 to GetArrayLength(Names)-1 do
      if RegQueryStringValue(Root, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + Names[I], 'name', Name) then
        if Pos('WebView2', Name) > 0 then
          if RegQueryStringValue(Root, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + Names[I], 'pv', Version) then
            if (Version <> '') and (Version <> '0.0.0.0') then Result := True;
end;
function PrepareToInstall(var NeedsRestart: Boolean): String;
var ResultCode: Integer;
begin
  Result := '';
  if HasWebViewAt(HKCU) or HasWebViewAt(HKLM32) or HasWebViewAt(HKLM64) then Exit;
  ExtractTemporaryFile('MicrosoftEdgeWebView2RuntimeInstallerX64.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebView2RuntimeInstallerX64.exe'),
    '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := 'Could not start the bundled Microsoft WebView2 installer.'
  else if (ResultCode <> 0) and (ResultCode <> 3010) then
    Result := 'Microsoft WebView2 setup failed. Code: ' + IntToStr(ResultCode);
end;
// User database lives outside {app}. No [UninstallDelete] entry is allowed for it.
