@echo off
setlocal
title 4 - FLASH a file to the ECU (pre-flight, dry run, write, read-back)
rem Usage: drag a .bin file onto this script, or run it and type the path.
set "FLASHER="
for %%f in ("%~dp0..\tools\VolvoFlasher*.exe") do set "FLASHER=%%~ff"
if not defined FLASHER goto :noflasher
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && set "PY=py"
if not defined PY goto :nopython
set "SRC=%~1"
if not defined SRC set /p "SRC=Full path of the .bin to flash: "
set "SRC=%SRC:"=%"
if not exist "%SRC%" goto :nofile
if not exist "%~dp0..\work" mkdir "%~dp0..\work"
copy /y "%SRC%" "%~dp0..\work\to_flash.bin" >nul
pushd "%~dp0..\work"
if exist expected.bin del expected.bin
if exist dryrun_image.bin del dryrun_image.bin

echo ===== 1. PRE-FLIGHT (size, ID, both checksum tables, changes vs your stock read) =====
set "STOCKARG="
if exist "..\backups\stock_read.bin" set "STOCKARG=--stock ..\backups\stock_read.bin"
if not defined STOCKARG echo NOTE: backups\stock_read.bin not found, so changes are not compared to stock.
%PY% "..\tools\preflight.py" to_flash.bin %STOCKARG% --expected expected.bin
if errorlevel 1 goto :preflightbad
echo.

echo ===== 2. DRY RUN (no contact with the car) =====
"%FLASHER%" -f P1 -e 7A --cm-info me9_p1 --json flash -i to_flash.bin --dry-run --emit-image dryrun_image.bin 1>dryrun_plan.json 2>dryrun_errors.txt
if not exist dryrun_image.bin goto :drybad
fc /b expected.bin dryrun_image.bin >nul
if errorlevel 1 goto :drybad
echo Dry run OK: the flasher would write exactly this file, boot area untouched.
echo.

echo ==================================================================
echo  This ERASES and REWRITES the engine ECU with:
echo    %SRC%
echo  ALL must be true before you continue:
echo   - Battery charger connected and ON
echo   - Ignition ON, engine OFF, lights / fan / radio OFF
echo   - Laptop on mains power, sleep and Windows Update paused
echo   - Cable firmly in, nobody touches the car or the laptop
echo  If it stops halfway: do NOT turn the ignition off, do NOT unplug.
echo  Run this script again, or flash backups\stock_read.bin with it.
echo ==================================================================
set "CONFIRM="
set /p "CONFIRM=Type FLASH in capitals and press Enter to start, anything else cancels: "
if not "%CONFIRM%"=="FLASH" goto :cancel

echo.
echo ===== 3. WRITING (about 3 minutes, NOTHING shows until it ends) =====
rem The flasher's exit code is 0 even on errors, so the output is saved and searched.
rem Plain redirect on purpose: a pipe could interrupt the flasher mid-write.
set "FLASHERR=0"
"%FLASHER%" -f P1 -e 7A --cm-info me9_p1 -v flash -i to_flash.bin > flash_output.txt 2>&1
type flash_output.txt
findstr /c:"Flashing error" /c:"Write flash failed" /c:"Erase flash failed" flash_output.txt >nul && set "FLASHERR=1"
if "%FLASHERR%"=="1" echo *** The flasher printed an error. The read-back below decides. ***

echo.
echo ===== 4. READING BACK TO VERIFY (about 6 minutes) =====
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
"%FLASHER%" -f P1 -e 7A --cm-info me9_p1 -v read -o readback_%TS%.bin -s 0 -sz 200000
if not exist readback_%TS%.bin goto :noreadback
fc /b to_flash.bin readback_%TS%.bin >nul
if errorlevel 1 goto :different
echo.
echo ******************************************************************
echo  SUCCESS: the ECU now holds exactly this file (full 2 MB read-back).
if "%FLASHERR%"=="1" echo  The flasher printed an error, but the read-back proves the data is right.
echo  Ignition OFF, wait 30 seconds, start the engine, check for fault codes.
echo ******************************************************************
popd
pause
exit /b 0

:different
echo *** READ-BACK DIFFERS FROM THE FILE. Do NOT start the engine. Keep ignition ON. ***
echo *** Run this script again. If it differs again, flash backups\stock_read.bin.     ***
popd
pause
exit /b 1
:noreadback
echo *** Read-back failed. Keep ignition ON, do not start. Run the read-back again. ***
popd
pause
exit /b 1
:drybad
echo *** Dry run failed or differs from the expected image. Nothing was written. ***
echo *** See work\dryrun_plan.json and work\dryrun_errors.txt                     ***
popd
pause
exit /b 1
:preflightbad
echo *** Pre-flight FAILED. Nothing was written to the car. ***
popd
pause
exit /b 1
:cancel
echo Cancelled. Nothing was written to the car.
popd
pause
exit /b 1
:nofile
echo *** File not found: %SRC% ***
pause
exit /b 1
:nopython
echo Python 3 not found. Install it from python.org (tick "Add to PATH").
pause
exit /b 1
:noflasher
echo VolvoFlasher*.exe not found in the "tools" folder. See README section 2.
pause
exit /b 1
