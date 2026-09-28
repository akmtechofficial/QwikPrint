import os
import sys
import subprocess
import shutil

def build_exe():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("==========================================================")
    print("  BUILDING SIGNED PRODUCTION QWIKPRINT DESKTOP SPOOLER   ")
    print("==========================================================")

    # Kill running PrintAgent process if open
    try:
        subprocess.run(["taskkill", "/F", "/IM", "PrintAgent.exe"], capture_output=True)
    except Exception:
        pass

    current_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(current_dir, "dist")
    build_dir = os.path.join(current_dir, "build")
    version_file = os.path.join(current_dir, "file_version_info.txt")

    # Clean build dirs
    if os.path.exists(dist_dir):
        try:
            shutil.rmtree(dist_dir)
        except Exception as err:
            print(f"[Warning] Could not clean dist dir: {err}")
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
        except Exception as err:
            print(f"[Warning] Could not clean build dir: {err}")

    os.makedirs(dist_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)

    icon_path = os.path.join(current_dir, "gui", "app_icon.ico")
    logo_path = os.path.join(current_dir, "gui", "qwikprint_logo.png")

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=PrintAgent",
        "--onefile",
        "--windowed",
        "--clean",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--specpath={current_dir}",
        f"--icon={icon_path}",
        f"--version-file={version_file}",
        f"--add-data={logo_path};gui",
        f"--paths={current_dir}",
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtNetwork",
        "--hidden-import=win32print",
        "--hidden-import=win32api",
        "--hidden-import=requests",
        "--hidden-import=winsound",
        os.path.join(current_dir, "main.py")
    ]

    print(f"[Build 1/4] Executing PyInstaller build command...\n")
    result = subprocess.run(pyinstaller_cmd)

    if result.returncode != 0:
        print(f"\n[ERROR] PyInstaller build failed with exit code {result.returncode}")
        return

    exe_path = os.path.join(dist_dir, "PrintAgent.exe")
    if not os.path.exists(exe_path):
        print(f"\n[ERROR] Built binary not found at: {exe_path}")
        return

    main_dist = os.path.join(os.path.dirname(current_dir), "dist")
    os.makedirs(main_dist, exist_ok=True)
    shutil.copy(exe_path, os.path.join(main_dist, "PrintAgent.exe"))

    # 2. Sign PyInstaller binary
    print("\n[Build 2/4] Authenticode Code-Signing PrintAgent.exe...")
    sign_script = os.path.join(current_dir, "sign_binary.ps1")
    if os.path.exists(sign_script):
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", sign_script, "-FilePath", exe_path])
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", sign_script, "-FilePath", os.path.join(main_dist, "PrintAgent.exe")])

    # 3. Build Inno Setup Installer
    iscc_path = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    iss_file = os.path.join(current_dir, "setup_script.iss")
    if os.path.exists(iscc_path) and os.path.exists(iss_file):
        print("\n[Build 3/4] Compiling Production Inno Setup Installer...")
        subprocess.run([iscc_path, iss_file])

    # 4. Sign Final Setup Executable in static/downloads
    downloads_dir = os.path.join(os.path.dirname(current_dir), "web_server", "static", "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    final_setup_exe = os.path.join(downloads_dir, "QwikPrint_Desktop_Spooler_v2.4.exe")
    if os.path.exists(final_setup_exe):
        print("\n[Build 4/4] Authenticode Code-Signing final QwikPrint_Desktop_Spooler_v2.4.exe...")
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", sign_script, "-FilePath", final_setup_exe])
        # Also mirror to main dist folder
        shutil.copy(final_setup_exe, os.path.join(main_dist, "QwikPrint_Desktop_Spooler_v2.4.exe"))

    print("\n==========================================================")
    print("[SUCCESS] Production Signed QwikPrint Desktop Spooler Built!")
    print(f"-> Installer: {final_setup_exe}")
    print("==========================================================")

if __name__ == "__main__":
    build_exe()
