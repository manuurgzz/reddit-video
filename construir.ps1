# Crea el instalador:  .\construir.ps1   ->  dist\RedditVideo-Setup-<versión>.exe
# Necesita Python con PyInstaller (pip install pyinstaller edge-tts) e Inno Setup (winget install JRSoftware.InnoSetup).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$version = (Select-String -Path version.py -Pattern 'VERSION = "(.+)"').Matches[0].Groups[1].Value

# 1 · ffmpeg (el instalador lo lleva dentro; se descarga una vez y se guarda en build\)
$ffmpeg = "build\ffmpeg"
if (-not (Test-Path "$ffmpeg\ffmpeg.exe")) {
    Write-Host "Descargando ffmpeg..."
    New-Item -ItemType Directory -Force build | Out-Null
    $zip = "build\ffmpeg.zip"
    Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip
    Expand-Archive $zip "build\ffmpeg-zip" -Force
    New-Item -ItemType Directory -Force $ffmpeg | Out-Null
    Get-ChildItem "build\ffmpeg-zip" -Recurse -Include ffmpeg.exe, ffprobe.exe, LICENSE* | Copy-Item -Destination $ffmpeg
    Remove-Item $zip, "build\ffmpeg-zip" -Recurse -Force
}

# 2 · La app (carpeta dist\Reddit Video)
python -m PyInstaller RedditVideo.spec --noconfirm --distpath dist --workpath build\pyinstaller
if ($LASTEXITCODE) { throw "PyInstaller falló" }

# 3 · El instalador
$iscc = @((Get-Command iscc -ErrorAction SilentlyContinue).Source,
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) { throw "Falta Inno Setup: winget install JRSoftware.InnoSetup" }
& $iscc "/DVersion=$version" instalador.iss
if ($LASTEXITCODE) { throw "Inno Setup falló" }
Write-Host "Listo: dist\RedditVideo-Setup-$version.exe"
