@echo off
:: Windows NSSM Service Installer for LinkedIn Cold Email Bot
:: Runs the bot 24/7 as a background Windows service

echo ==================================================
echo 🛠️ Windows Service Setup for LinkedIn Cold Email Bot
echo ==================================================
echo.

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ ERROR: Please run this script as an Administrator!
    echo Right-click this file and select "Run as administrator".
    pause
    exit /b 1
)

:: Get current folder
set "PROJECT_DIR=%~dp0.."
cd /d "%PROJECT_DIR%"

echo 📁 Project folder: %CD%

:: 1. Setup Python venv
echo 📦 Setting up Python virtual environment...
if not exist "venv" (
    python -m venv venv
    echo ✅ Created virtual environment.
) else (
    echo ✅ Virtual environment already exists.
)

call venv\Scripts\activate.bat
echo 📥 Installing dependencies from requirements.txt...
pip install -r requirements.txt
echo ✅ Dependencies installed.

:: 2. Download and Setup NSSM (Non-Sucking Service Manager)
echo.
echo 📥 Downloading NSSM process manager...
mkdir "%PROJECT_DIR%\bin" 2>nul
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://nssm.cc/release/nssm-2.24.zip' -OutFile '%PROJECT_DIR%\bin\nssm.zip'"
if %errorLevel% neq 0 (
    echo ❌ Failed to download NSSM. Please install manually from https://nssm.cc
    pause
    exit /b 1
)

echo 📦 Extracting NSSM...
powershell -Command "Expand-Archive -Path '%PROJECT_DIR%\bin\nssm.zip' -DestinationPath '%PROJECT_DIR%\bin' -Force"

:: Copy the correct architecture binary (win64) to the bin root
copy /y "%PROJECT_DIR%\bin\nssm-2.24\win64\nssm.exe" "%PROJECT_DIR%\bin\nssm.exe" >nul
rd /s /q "%PROJECT_DIR%\bin\nssm-2.24" 2>nul
del /q "%PROJECT_DIR%\bin\nssm.zip" 2>nul

echo ✅ NSSM setup completed.

:: 3. Setup the Windows Service
echo.
echo 🛠️ Registering Windows Service 'ColdEmailBot' using NSSM...
set "NSSM=%PROJECT_DIR%\bin\nssm.exe"
set "PYTHON_EXE=%PROJECT_DIR%\venv\Scripts\python.exe"
set "SCRIPT_PY=%PROJECT_DIR%\main.py"
set "LOGS_DIR=%PROJECT_DIR%\logs"

mkdir "%LOGS_DIR%" 2>nul

:: Remove existing service if it exists
"%NSSM%" remove ColdEmailBot confirm >nul 2>&1

:: Install service
"%NSSM%" install ColdEmailBot "%PYTHON_EXE%" "%SCRIPT_PY%"
"%NSSM%" set ColdEmailBot AppDirectory "%PROJECT_DIR%"
"%NSSM%" set ColdEmailBot Start SERVICE_AUTO_START

:: Redirect output logs
"%NSSM%" set ColdEmailBot AppStdout "%LOGS_DIR%\service_out.log"
"%NSSM%" set ColdEmailBot AppStderr "%LOGS_DIR%\service_err.log"

:: Configure restart on crash
"%NSSM%" set ColdEmailBot AppExit Default Restart
"%NSSM%" set ColdEmailBot AppThrottle 1500

echo.
echo ✅ Service registered successfully!
echo 🎬 Starting the service...
net start ColdEmailBot

echo.
echo ==================================================
echo 🎉 Setup Complete! The bot is now running in the background.
echo.
echo 📊 Service Control Commands (from Admin Command Prompt):
echo   • Start service:   net start ColdEmailBot
echo   • Stop service:    net stop ColdEmailBot
echo   • Restart service: nssm restart ColdEmailBot (or net stop + net start)
echo   • Delete service:  sc delete ColdEmailBot
echo ==================================================
pause
