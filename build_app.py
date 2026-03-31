# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import shutil

def run_cmd(cmd, cwd=None):
    # 將列表轉為字串以相容 shell=True
    full_cmd = " ".join(f'"{c}"' if ' ' in c else c for c in cmd) if isinstance(cmd, list) else cmd
    print(f"[RUNNING] {full_cmd}")
    # 在 Windows 上執行 npm/pip 必須使用 shell=True
    result = subprocess.run(full_cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}")
    return result.returncode

def main():
    project_root = os.path.abspath(".")
    frontend_dir = os.path.join(project_root, "frontend")
    
    print("==========================================")
    print("   COLA PIG STANDALONE BUILDER (PYTHON)")
    print("==========================================")

    # 1. Frontend Build
    print("\n[STEP 1/3] Building Frontend (Static Export)...")
    
    # Save original config
    config_path = os.path.join(frontend_dir, "next.config.ts")
    config_bak = config_path + ".bak"
    if os.path.exists(config_path):
        shutil.copy2(config_path, config_bak)
    
    # Write temp export config
    export_config = 'import type { NextConfig } from "next"; const nextConfig: NextConfig = { output: "export", images: { unoptimized: true } }; export default nextConfig;'
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(export_config)
    
    # Build
    try:
        run_cmd("npm run build", cwd=frontend_dir)
    finally:
        # Restore original config
        if os.path.exists(config_bak):
            shutil.move(config_bak, config_path)

    # 2. PyInstaller
    print("\n[STEP 2/3] Installing PyInstaller...")
    run_cmd([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 3. Bundling
    print("\n[STEP 3/3] Bundling EXE...")
    
    # We use list to avoid escaping issues
    # Note: Using English name to avoid encoding issues in shell during bundle
    exe_name = "ColaPigTradingApp"
    
    pyinstall_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        f"--name={exe_name}",
        '--add-data=frontend/out;frontend/out',
        '--add-data=股票代號表.csv;.',
        '--add-data=watchlist_groups.json;.',
        '--collect-all=pandas',
        "standalone_server.py"
    ]
    
    run_cmd(pyinstall_cmd)

    print("\n==========================================")
    print(f"   BUILD COMPLETE!")
    print(f"   Target: dist/{exe_name}.exe")
    print("==========================================")
    print("Step 4: You can now rename the EXE to '冰可樂加熱_交易版.exe'")

if __name__ == "__main__":
    main()
