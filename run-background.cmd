@echo off
rem Фоновый запуск платформы «Синдикат» в Windows: окно не открывается,
rem вывод пишется в syndicat.log рядом со скриптом.
rem Использование:  run-background.cmd [порт]   (по умолчанию 8777)
setlocal
cd /d "%~dp0"
set PORT=%1
if "%PORT%"=="" set PORT=8777

where pythonw >nul 2>&1
if %errorlevel%==0 (
  start "" /b pythonw -m syndicat --port %PORT% >>"%~dp0syndicat.log" 2>&1
  goto started
)
where pyw >nul 2>&1
if %errorlevel%==0 (
  start "" /b pyw -3 -m syndicat --port %PORT% >>"%~dp0syndicat.log" 2>&1
  goto started
)
where python >nul 2>&1
if %errorlevel%==0 (
  start "" /min python -m syndicat --port %PORT% >>"%~dp0syndicat.log" 2>&1
  goto started
)
echo Python 3 не найден. Установите его с https://www.python.org/downloads/
echo и отметьте при установке "Add python.exe to PATH".
exit /b 1

:started
echo Панель работает в фоне: http://127.0.0.1:%PORT%/
echo Журнал:     %~dp0syndicat.log
echo Остановить: stop.cmd %PORT%
