@echo off
setlocal
chcp 65001 >nul

set "ROOT_DIR=%~dp0"
set "APP=%ROOT_DIR%tools\github_push_web\server.js"

if not exist "%APP%" (
  echo Missing web helper: %APP%
  echo Please keep github_push_web.bat in the project root.
  pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Please install Node.js 18+ first.
  pause
  exit /b 1
)

echo Starting local GitHub push web helper...
echo Keep this window open while using the web page.
echo.

node "%APP%" "%ROOT_DIR%" --open

echo.
pause
