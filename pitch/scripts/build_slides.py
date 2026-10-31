"""Build a portable three-slide HTML deck using the README's exact Excalidraw PNG."""
from pathlib import Path
import base64
import hashlib

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT.parent / "docs" / "architecture.png"


def build_slides() -> Path:
    html = (ROOT / "slides.template.html").read_text(encoding="utf-8")
    for token, filename in [
        ("FONT_REGULAR", "OpenAISans-Regular.woff2"),
        ("FONT_MEDIUM", "OpenAISans-Medium.woff2"),
        ("FONT_SEMIBOLD", "OpenAISans-Semibold.woff2"),
    ]:
        data = (ROOT / "dist" / "vendor" / filename).read_bytes()
        html = html.replace(f"@@{token}@@", base64.b64encode(data).decode("ascii"))
    image = ARCHITECTURE.read_bytes()
    html = html.replace("@@ARCHITECTURE@@", base64.b64encode(image).decode("ascii"))
    html = html.replace("@@ARCHITECTURE_SHA@@", hashlib.sha256(image).hexdigest())
    if "@@" in html:
        raise ValueError("Unresolved slide template token")
    target = ROOT / "dist" / "slides.html"
    target.write_text(html, encoding="utf-8")
    return target


if __name__ == "__main__":
    path = build_slides()
    print(f"Three-slide HTML ready: {path} ({path.stat().st_size:,} bytes)")
