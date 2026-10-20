; Inno Setup: instalador de Reddit Video para un solo usuario (no pide permisos de administrador).
; Se compila desde construir.ps1:  ISCC /DVersion=1.0.0 instalador.iss
#ifndef Version
  #define Version "1.0.0"
#endif

[Setup]
AppId={{8F3C6B52-4E0A-4D7B-9C1E-52A7D0B1E4A1}
AppName=Reddit Video
AppVersion={#Version}
AppPublisher=Manuel Rodriguez
AppPublisherURL=https://github.com/manuurgzz/reddit-video
DefaultDirName={autopf}\Reddit Video
DefaultGroupName=Reddit Video
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=RedditVideo-Setup-{#Version}
SetupIconFile=assets\icono.ico
UninstallDisplayIcon={app}\Reddit Video.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un icono en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\Reddit Video\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Reddit Video"; Filename: "{app}\Reddit Video.exe"
Name: "{autodesktop}\Reddit Video"; Filename: "{app}\Reddit Video.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Reddit Video.exe"; Description: "Abrir Reddit Video"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; si el piloto automático estaba activado, se da de baja su tarea de Windows
Filename: "schtasks.exe"; Parameters: "/Delete /TN ""Reddit Video - Piloto automatico"" /F"; Flags: runhidden; RunOnceId: "QuitarTareaPiloto"
