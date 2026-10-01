@echo off
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where pythonw >nul 2>&1 && (start "" pythonw app.pyw) || python app.pyw
