@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
echo Trabajando... (el detalle se guarda en log_ejecucion.txt)
call :principal > log_ejecucion.txt 2>&1
type log_ejecucion.txt
echo.
echo ===== FIN =====
pause
exit /b

:principal
echo === %date% %time% ===
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
  echo [1/4] Instalando Python...
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-source-agreements --accept-package-agreements
  set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
echo PY=%PY%
%PY% --version

echo [2/4] Instalando edge-tts...
%PY% -m pip install --upgrade --quiet edge-tts

echo [3/4] Comprobando ffmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo Instalando ffmpeg...
  winget install -e --id Gyan.FFmpeg --silent --accept-source-agreements --accept-package-agreements
)
where ffmpeg
if errorlevel 1 (
  for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*") do for /d %%E in ("%%D\ffmpeg-*") do set "PATH=%%E\bin;%PATH%"
)
ffmpeg -version | findstr /b "ffmpeg version"

echo [4/4] Abriendo la app...
where pythonw >nul 2>&1 && (start "" pythonw app.pyw) || (start "" %PY% app.pyw)
exit /b
