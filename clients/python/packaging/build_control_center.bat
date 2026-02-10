@echo off
setlocal
if "%ARIS_APP_VERSION%"=="" set ARIS_APP_VERSION=0.6.2
pyinstaller --clean --noconfirm control_center.spec.template
