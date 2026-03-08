@echo off
echo Building TF Pilot Console...
pip install -r requirements.txt
pyinstaller --onefile --windowed --name TF_Pilot_Console console.py
echo Build Complete! Check the dist folder.
pause
