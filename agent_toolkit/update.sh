#!/bin/bash

echo "======================================================"
echo "TERMINAL FRONTIER - PILOT CONSOLE AUTO-UPDATER"
echo "======================================================"
echo ""

# 1. Give the main window time to close
echo "[Step 1/4] Waiting for Pilot Console to shutdown..."
sleep 3

# 2. Pull latest code from GitHub
echo "[Step 2/4] Pulling latest changes from GitHub..."
git pull
if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Git pull failed. Please ensure Git is installed and you have no local conflicts."
    read -p "Press enter to exit"
    exit 1
fi

# 3. Update dependencies
echo "[Step 3/4] Updating Python dependencies..."
python3 -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo ""
    echo "[WARNING] Pip install encountered issues. Continuing to build regardless..."
fi

# 4. Rebuild the executable
echo "[Step 4/4] Building new TF_Pilot_Console executable..."
# Note: On Mac/Linux, we might not always want PyInstaller to run automatically
# as many users run from source, but we'll include it for consistency with the .bat.
if command -v pyinstaller &> /dev/null
then
    pyinstaller --onefile --windowed --name TF_Pilot_Console console.py
else
    python3 -m PyInstaller --onefile --windowed --name TF_Pilot_Console console.py
fi

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] PyInstaller failed to build the console."
    read -p "Press enter to exit"
    exit 1
fi

echo ""
echo "======================================================"
echo "UPDATE COMPLETE!"
echo "The new version is available in the 'dist' folder."
echo "======================================================"
echo ""
read -p "Press enter to exit"
exit 0
