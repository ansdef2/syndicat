@echo off
rem Поднимает платформу, если она не слушает порт. Если работает - ничего не делает.
rem Использование:  ensure-running.cmd [порт]   (по умолчанию 8777)
setlocal
cd /d "%~dp0"
set PORT=%1
if "%PORT%"=="" set PORT=8777

netstat -ano | findstr /r /c:"TCP .*:%PORT% .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo Платформа уже работает на порту %PORT%.
  exit /b 0
)
call "%~dp0run-background.cmd" %PORT%
