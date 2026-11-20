@echo off
setlocal
title 1 - Is the J2534 cable detected?
set "FLASHER="
for %%f in ("%~dp0..\tools\VolvoFlasher*.exe") do set "FLASHER=%%~ff"
if not defined FLASHER goto :noflasher
echo ===== J2534 adapters seen by VolvoFlasher =====
"%FLASHER%" devices
echo.
echo If your adapter (for example "MongoosePro JLR") is listed above, the driver and cable work.
echo Nothing listed: install the 32-bit J2534 driver of your cable and use the x86 VolvoFlasher build.
pause
exit /b 0
:noflasher
echo VolvoFlasher*.exe not found in the "tools" folder. See README section 2.
pause
exit /b 1
