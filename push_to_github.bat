@echo off
setlocal
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "PUSH_SCRIPT=%SCRIPT_DIR%scripts\push_to_github.ps1"

if not exist "%PUSH_SCRIPT%" (
  echo Missing script: %PUSH_SCRIPT%
  echo Please keep this .bat file together with the scripts folder.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PUSH_SCRIPT%"

echo.
pause
