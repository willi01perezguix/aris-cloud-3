@echo off
setlocal
if "%ARIS_APP_VERSION%"=="" set ARIS_APP_VERSION=0.6.2
pyinstaller --clean --noconfirm core_app.spec.template
