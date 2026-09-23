@echo off
rem Снимает автозапуск платформы при входе в систему.
schtasks /delete /tn "Syndicat" /f >nul 2>&1
if %errorlevel%==0 (echo Автозапуск снят.) else (echo Задание "Syndicat" не найдено.)
