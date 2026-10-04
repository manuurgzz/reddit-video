@echo off
cd /d "%~dp0Texto_Voz"
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
python server.py
