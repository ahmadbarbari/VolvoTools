@echo off
setlocal
title 2 - Back up the ECU (read twice, compare) - READ ONLY
set "FLASHER="
for %%f in ("%~dp0..\tools\VolvoFlasher*.exe") do set "FLASHER=%%~ff"
if not defined FLASHER goto :noflasher
if not exist "%~dp0..\backups" mkdir "%~dp0..\backups"
pushd "%~dp0..\backups"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
echo Reading only. Nothing is written to the car.
echo Battery charger ON, ignition ON, engine OFF, laptop on mains power, sleep off.
echo Each read takes about 6 minutes.
pause
echo ===== READ 1 =====
"%FLASHER%" -f P1 -e 7A --cm-info me9_p1 -v read -o read_%TS%_1.bin -s 0 -sz 200000
if not exist read_%TS%_1.bin goto :readfail
echo.
echo Turn the ignition OFF, wait 10 seconds, turn it back ON (engine off), then press a key.
pause
echo ===== READ 2 =====
"%FLASHER%" -f P1 -e 7A --cm-info me9_p1 -v read -o read_%TS%_2.bin -s 0 -sz 200000
if not exist read_%TS%_2.bin goto :readfail
fc /b read_%TS%_1.bin read_%TS%_2.bin >nul
if errorlevel 1 goto :differ
for %%A in (read_%TS%_1.bin) do set "SZ=%%~zA"
if not "%SZ%"=="2097152" goto :badsize
powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 read_%TS%_1.bin).Hash"
if not exist stock_read.bin copy /y read_%TS%_1.bin stock_read.bin >nul
echo.
echo ******************************************************************
echo  Both reads are identical and 2 MB: read_%TS%_1.bin
echo  Saved as backups\stock_read.bin (only if no stock_read.bin existed).
echo  COPY IT OFF THIS PC NOW (USB key + cloud). It is your way back.
echo ******************************************************************
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && set "PY=py"
if defined PY %PY% "%~dp0..\tools\preflight.py" read_%TS%_1.bin
popd
pause
exit /b 0
:differ
echo *** The two reads are DIFFERENT. Do not use them. Check cable and power, run this again. ***
popd
pause
exit /b 1
:badsize
echo *** The read is not 2,097,152 bytes. Do not use it. ***
popd
pause
exit /b 1
:readfail
echo *** Read failed, no file. Turn ignition off for 30 s, check the cable, try again. ***
popd
pause
exit /b 1
:noflasher
echo VolvoFlasher*.exe not found in the "tools" folder. See README section 2.
pause
exit /b 1
