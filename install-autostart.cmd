@echo off
rem Сторож платформы: задание планировщика каждые 5 минут пробует поднять сервер.
rem Если платформа уже работает, новый процесс видит занятый порт и молча выходит,
rem поэтому второго экземпляра не возникает, а упавшая платформа поднимается сама.
rem Окон при этом не появляется: запуск идёт через pythonw.exe.
rem Использование:  install-autostart.cmd [порт]   (по умолчанию 8777)
setlocal
cd /d "%~dp0"
set PORT=%1
if "%PORT%"=="" set PORT=8777

set LAUNCHER=
for /f "delims=" %%i in ('where pythonw 2^>nul') do if not defined LAUNCHER set LAUNCHER=%%i
if not defined LAUNCHER (
  for /f "delims=" %%i in ('where pyw 2^>nul') do if not defined LAUNCHER set LAUNCHER=%%i -3
)
if not defined LAUNCHER (
  echo Не найден pythonw.exe - запуск без окна невозможен.
  echo Установите Python с python.org или настройте автозапуск вручную:
  echo Win+R, shell:startup, ярлык на run-background.cmd
  exit /b 1
)

schtasks /create /tn "Syndicat" /f /sc minute /mo 5 ^
  /tr "\"%LAUNCHER%\" -m syndicat --port %PORT% --log \"%~dp0syndicat.log\"" >nul
if %errorlevel% neq 0 (
  echo Не удалось создать задание планировщика.
  echo Попробуйте запустить этот файл от имени администратора либо настройте
  echo автозапуск вручную: Win+R, shell:startup, ярлык на run-background.cmd
  exit /b 1
)

echo Задание "Syndicat" создано: проверка каждые 5 минут, порт %PORT%.
echo Платформа поднимется сама после перезагрузки и после любого падения.
echo Снять автозапуск: uninstall-autostart.cmd
call "%~dp0ensure-running.cmd" %PORT%
