"""Windows-only setup for Kayal/MARK LIV.""" 
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_PY = (3, 11)
MAX_PY = (3, 13)

def _run(label, args):
    print(f"\n▶ {label}")
    subprocess.run(args, check=True)

def _check_python():
    v = sys.version_info[:2]
    if v < MIN_PY:
        print(f"Python {v[0]}.{v[1]} detected — requires Python {MIN_PY[0]}.{MIN_PY[1]} or newer.")
        sys.exit(1)
    if v > MAX_PY:
        print(f"⚠ Python {v[0]}.{v[1]} is newer than the tested {MAX_PY[0]}.{MAX_PY[1]}; continuing.")

def main():
    print(f"Windows setup — Python {sys.version_info[0]}.{sys.version_info[1]}")
    _check_python()
    _run("Installing dependencies", [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    try:
        _run("Installing Playwright browsers", [sys.executable, "-m", "playwright", "install", "chromium", "firefox"])
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"⚠ Browser install failed ({exc}); retry: {sys.executable} -m playwright install chromium firefox")
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        postinstall = Path(sys.executable).parent / "Scripts" / "pywin32_postinstall.py"
        print("⚠ pywin32 registration incomplete; shortcut creation may use fallback.")
        print(f'   "{sys.executable}" -m pip install --force-reinstall pywin32')
        print(f'   "{sys.executable}" "{postinstall}" -install')
    print("\n✅ Setup complete!")
    print("   1) Launch: python main.py")
    print("   2) Enter your Gemini API key when prompted.")
    print("   3) Optional: enable Hey Jarvis from Settings → Wake Word.")

if __name__ == "__main__":
    main()
