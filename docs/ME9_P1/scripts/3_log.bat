@echo off
setlocal
title 3 - Log engine data (read only)
set "LOGGER="
for %%f in ("%~dp0..\tools\VolvoLogger*.exe") do set "LOGGER=%%~ff"
if not defined LOGGER goto :nologger
if not exist "%~dp0..\logs" mkdir "%~dp0..\logs"
echo Logging only READS data. The RAM addresses in the logger folder are for software P010D600.
echo On another software version they must be ported first (README section 6).
echo.
echo Variable files available:
dir /b "%~dp0..\logger\*.ecu"
echo.
set "VARS=P010D600_log_full_40.ecu"
set /p "VARS=File to use (Enter = P010D600_log_full_40.ecu): "
if not exist "%~dp0..\logger\%VARS%" goto :novars
set "NOTE=log"
set /p "NOTE=One word to name this log (idle, cruise, pull3rd...): "
for /f %%n in ('powershell -NoProfile -Command "$n='%NOTE%' -replace '[^A-Za-z0-9_-]',''; if(-not $n){$n='log'}; $n"') do set "NOTE=%%n"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
copy /y "%~dp0..\logger\%VARS%" "%~dp0..\logs\vars.ecu" >nul
pushd "%~dp0..\logs"
set "OUT=%TS%_%NOTE%.csv"
echo Start the engine first, then press a key. Ctrl+C once to stop (answer N to "Terminate batch job").
pause
"%LOGGER%" -f P1 -e 7A --variables vars.ecu -o %OUT% -p 8
if not exist %OUT% goto :nofile
echo *** Log saved: logs\%OUT% ***
popd
pause
exit /b 0
:nofile
echo *** No log file was created. ***
popd
pause
exit /b 1
:novars
echo *** %VARS% not found in the logger folder. ***
pause
exit /b 1
:nologger
echo VolvoLogger*.exe not found in the "tools" folder. See README section 2.
pause
exit /b 1
