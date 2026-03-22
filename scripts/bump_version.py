import os
import re
import json

def bump_version():
    with open("version.json", "r") as f:
        version_data = json.load(f)
    
    version = version_data["version"]
    print(f"Bumping codebase to version: {version}")

    # 1. Update backend/main.py (version field)
    main_py_path = "backend/main.py"
    if os.path.exists(main_py_path):
        with open(main_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Update app version
        content = re.sub(r'version="[0-9.]+"', f'version="{version}"', content)
        # Update metadata version
        content = re.sub(r'"version": "[0-9.]+"', f'"version": "{version}"', content)
        
        with open(main_py_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated {main_py_path}")

    # 2. Update frontend files
    frontend_dir = "frontend"
    for filename in os.listdir(frontend_dir):
        if filename.endswith(".html") or filename.endswith(".js"):
            path = os.path.join(frontend_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Fallback to latin-1 if utf-8 fails
                with open(path, "r", encoding="latin-1") as f:
                    content = f.read()

            # Update VERSION comment in HTML
            content = re.sub(r'<!-- VERSION: [0-9._A-Z]+ -->', f'<!-- VERSION: {version} -->', content)
            
            # Update cache busting ?v= in HTML/JS
            content = re.sub(r'\?v=[0-9.]+', f'?v={version}', content)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated {path}")

if __name__ == "__main__":
    bump_version()
