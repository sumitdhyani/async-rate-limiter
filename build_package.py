# build_package.py
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent

def main() -> int:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "build"])
    subprocess.check_call([sys.executable, "-m", "build"], cwd=ROOT)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
