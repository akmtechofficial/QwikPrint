import os
import sys
import subprocess
import shutil

def build_exe():
    print("==========================================================")
    print("     BUILDING STANDALONE PYTHON PRINT AGENT (.EXE)        ")
    print("==========================================================")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(current_dir, "dist")
    build_dir = os.path.join(current_dir, "build")

    # Clean build dirs
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=PrintAgent",
        "--onefile",
        "--windowed",
        "--clean",
        f"--paths={current_dir}",
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtNetwork",
        "--hidden-import=win32print",
        "--hidden-import=win32api",
        "--hidden-import=requests",
        "--hidden-import=winsound",
        os.path.join(current_dir, "main.py")
    ]

    print(f"[Build] Executing command: {' '.join(pyinstaller_cmd)}\n")
    result = subprocess.run(pyinstaller_cmd)

    if result.returncode == 0:
        exe_path = os.path.join(dist_dir, "PrintAgent.exe")
        print("\n==========================================================")
        print("✅ SUCCESS! Standalone Executable built at:")
        print(f"👉 {exe_path}")
        print("==========================================================")
    else:
        print(f"\n❌ PyInstaller build failed with exit code {result.returncode}")

if __name__ == "__main__":
    build_exe()
