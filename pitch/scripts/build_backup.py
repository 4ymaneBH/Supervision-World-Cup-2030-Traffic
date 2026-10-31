"""Package the static demo and a small launcher for an offline presentation."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
TARGET = DIST / "offline-demo.zip"

LAUNCHER = '''@echo off
cd /d "%~dp0"
echo Rabat Flow - http://127.0.0.1:8080
echo Keep this window open during the demo. Press Ctrl+C to stop.
python -m http.server 8080 --bind 127.0.0.1 --directory site
if errorlevel 1 pause
'''.replace("\n", "\r\n")
README = '''RABAT FLOW / DEMO HORS LIGNE / OFFLINE DEMO

Francais : lancez START-DEMO.cmd sous Windows, puis ouvrez
http://127.0.0.1:8080/?lang=fr . Python 3 doit etre installe.

English: run START-DEMO.cmd on Windows, then open
http://127.0.0.1:8080/?lang=en . Python 3 must be installed.

macOS / Linux / Windows terminal:
python -m http.server 8080 --bind 127.0.0.1 --directory site

Keep the terminal open during the presentation. Ctrl+C stops the server.
All fonts and Three.js assets are included. No internet or API keys needed.
Vehicles, routes, traffic and improvements are illustrative simulations.
Use FR / EN to change language. Play the story or choose the three stages.
Space: pause. R: reset. F: fullscreen. A 2D fallback supports no-WebGL devices.
'''


def build_backup() -> Path:
    with ZipFile(TARGET, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        def add(name: str, data: bytes) -> None:
            info = ZipInfo("rabat-flow/" + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data)
        for path in sorted(DIST.rglob("*")):
            if path.is_file() and path != TARGET and path.suffix != ".zip":
                add("site/" + path.relative_to(DIST).as_posix(), path.read_bytes())
        add("START-DEMO.cmd", LAUNCHER.encode("utf-8"))
        add("README.txt", README.encode("utf-8"))
    return TARGET


if __name__ == "__main__":
    path = build_backup()
    print(f"Offline backup ready: {path.name} ({path.stat().st_size:,} bytes)")
