@echo off
echo Building TF Pilot Console...
python -m pip install -r requirements.txt
python -m PyInstaller --onefile --windowed --name TF_Pilot_Console console.py
echo Build Complete! Check the dist folder.
pause
