@echo off
setlocal
echo ======================================================
echo TERMINAL FRONTIER - PILOT CONSOLE AUTO-UPDATER
echo ======================================================
echo.

:: 1. Give the main window time to close and release file handles
echo [Step 1/4] Waiting for Pilot Console to shutdown...
timeout /t 3 /nobreak > nul

:: 2. Pull latest code from GitHub
echo [Step 2/4] Pulling latest changes from GitHub...
git pull
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Git pull failed. Please ensure Git is installed and you have no local conflicts.
    pause
    exit /b %errorlevel%
)

:: 3. Update dependencies
echo [Step 3/4] Updating Python dependencies...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Pip install encountered issues. Continuing to build regardless...
)

:: 4. Rebuild the executable
echo [Step 4/4] Building new TF_Pilot_Console executable...
python -m PyInstaller --onefile --windowed --name TF_Pilot_Console console.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller failed to build the console.
    pause
    exit /b %errorlevel%
)

echo.
echo ======================================================
echo UPDATE COMPLETE!
echo The new version is available in the 'dist' folder.
echo You can now restart the TF_Pilot_Console.
echo ======================================================
echo.
pause
exit /b 0
