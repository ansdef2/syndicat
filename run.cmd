@echo off
rem Запуск локальной платформы «Синдикат» из проводника или командной строки Windows.
cd /d "%~dp0"
where py >nul 2>&1 && (py -3 -m syndicat %* & goto :eof)
where python >nul 2>&1 && (python -m syndicat %* & goto :eof)
echo Python 3 не найден. Установите его с https://www.python.org/downloads/
echo и отметьте при установке "Add python.exe to PATH".
pause
