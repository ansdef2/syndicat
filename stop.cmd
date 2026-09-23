@echo off
rem Остановка фоновой платформы «Синдикат»: снимает процесс, слушающий порт.
rem Использование:  stop.cmd [порт]   (по умолчанию 8777)
setlocal enabledelayedexpansion
set PORT=%1
if "%PORT%"=="" set PORT=8777
set FOUND=

for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"TCP .*:%PORT% .*LISTENING"') do (
  taskkill /PID %%p /F >nul 2>&1
  if !errorlevel!==0 set FOUND=1
)

if defined FOUND (
  echo Платформа остановлена, порт %PORT% свободен.
) else (
  echo На порту %PORT% ничего не слушает.
)
