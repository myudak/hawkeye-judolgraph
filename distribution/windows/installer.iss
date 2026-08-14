#ifndef MyAppVersion
  #define MyAppVersion "1.0.1"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\windows\HAWK-EYE"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{D2F6B05D-E8CD-44AA-AF27-74C26A51FEA3}
AppName=HAWK-EYE
AppVersion={#MyAppVersion}
AppPublisher=JudolGraph
AppPublisherURL=https://github.com/myudak/hawkeye-judolgraph
AppSupportURL=https://github.com/myudak/hawkeye-judolgraph/issues
DefaultDirName={localappdata}\Programs\HAWK-EYE
DefaultGroupName=HAWK-EYE
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=HAWK-EYE-Setup-{#MyAppVersion}-windows-x64
SetupIconFile=..\..\apps\web\src\assets\favicon.ico
UninstallDisplayIcon={app}\HAWK-EYE.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany=JudolGraph
VersionInfoDescription=HAWK-EYE Windows Installer
VersionInfoProductName=HAWK-EYE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\HAWK-EYE"; Filename: "{app}\HAWK-EYE.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\HAWK-EYE"; Filename: "{app}\HAWK-EYE.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\HAWK-EYE.exe"; Description: "Launch HAWK-EYE"; Flags: nowait postinstall skipifsilent
