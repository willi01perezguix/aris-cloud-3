@echo off
setlocal
if "%PACKAGING_APP_VERSION%"=="" if not "%ARIS_APP_VERSION%"=="" set PACKAGING_APP_VERSION=%ARIS_APP_VERSION%
powershell -ExecutionPolicy Bypass -File "%~dp0build_core.ps1" %*
