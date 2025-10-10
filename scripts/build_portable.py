"""Build portable executable for Vype using PyInstaller."""

import sys
import subprocess
from pathlib import Path
import shutil

def main():
    """Build the portable executable."""
    print("=" * 70)
    print("Vype Portable Build Script")
    print("=" * 70)
    print()
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"[OK] PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("[INFO] PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("[OK] PyInstaller installed")
    
    # Get project root
    project_root = Path(__file__).parent.parent
    spec_file = project_root / "vype.spec"
    
    if not spec_file.exists():
        print(f"[ERROR] Spec file not found: {spec_file}")
        return 1
    
    print(f"[OK] Spec file found: {spec_file}")
    print()
    
    # Clean previous builds
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    
    if dist_dir.exists():
        print("Cleaning previous dist/...")
        shutil.rmtree(dist_dir)
    
    if build_dir.exists():
        print("Cleaning previous build/...")
        shutil.rmtree(build_dir)
    
    print()
    print("Building executable...")
    print("-" * 70)
    
    # Run PyInstaller
    try:
        subprocess.check_call([
            sys.executable,
            "-m",
            "PyInstaller",
            str(spec_file),
            "--clean",
            "--noconfirm",
        ])
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build failed with error code {e.returncode}")
        return 1
    
    print("-" * 70)
    print()
    
    # Check output
    exe_path = dist_dir / "Vype" / "Vype.exe"
    
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("[SUCCESS] Build successful!")
        print()
        print(f"Executable: {exe_path}")
        print(f"Size: {size_mb:.1f} MB")
        print()
        print("=" * 70)
        print("Portable build complete!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Test the executable: dist\\Vype\\Vype.exe")
        print("2. Create a zip archive for distribution")
        print("3. Test on a clean Windows installation")
        print()
        return 0
    else:
        print("[ERROR] Build completed but executable not found!")
        return 1

if __name__ == "__main__":
    sys.exit(main())

