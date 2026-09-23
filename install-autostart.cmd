@echo off
rem Регистрирует задание, которое поднимает платформу при входе в систему.
rem Использование:  install-autostart.cmd [порт]   (по умолчанию 8777)
setlocal
cd /d "%~dp0"
set PORT=%1
if "%PORT%"=="" set PORT=8777

schtasks /create /tn "Syndicat" /f /sc onlogon ^
  /tr "\"%~dp0ensure-running.cmd\" %PORT%" >nul
if %errorlevel% neq 0 (
  echo Не удалось создать задание. Запустите этот файл от имени администратора
  echo либо настройте автозапуск вручную: Win+R, shell:startup, ярлык на run-background.cmd
  exit /b 1
)
echo Задание "Syndicat" создано: платформа поднимается при входе в систему.
echo Порт: %PORT%.  Снять автозапуск: uninstall-autostart.cmd
call "%~dp0ensure-running.cmd" %PORT%
