#!/usr/bin/env python3
"""
token_qr.py - flyttar dashboard-nyckeln till mobilen UTAN att den gar over natet.

Marc klickar "kopiera" pa GitHubs token-sida. Det har skriptet laser urklippet,
bygger lanken https://marcdshark666.github.io/drjonsson/#gh=<token>, visar den
som QR-kod pa skarmen (Marc skannar med mobilkameran -> sidan sparar nyckeln i
mobilens webblasare) och oppnar samma lank i datorns standardwebblasare.
Sedan toms urklippet och QR-bilden raderas efter 10 minuter.

Nyckeln loggas inte, skrivs inte i repot och skickas ingenstans. Fragmentet
(#gh=...) nar aldrig GitHubs server; sidan laser det och tar bort det ur adressen.

  .venv\\Scripts\\python.exe pipeline\\token_qr.py
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "outputs" / "private"      # outputs/ ar gitignorat
DASH = "https://marcdshark666.github.io/drjonsson/"


def clipboard() -> str:
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def clear_clipboard() -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ' '"], capture_output=True)


def main() -> int:
    tok = clipboard()
    if not re.fullmatch(r"(github_pat_|ghp_)[A-Za-z0-9_]{20,}", tok):
        print("Urklippet innehaller ingen GitHub-token. Klicka kopiera-ikonen pa token-sidan och kor igen.")
        return 1
    link = DASH + "#gh=" + quote(tok, safe="")
    try:
        import qrcode
    except ImportError:
        print("saknar paketet qrcode: pip install qrcode")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "dashboard-nyckel-qr.png"
    img = qrcode.make(link, box_size=10, border=3)
    img.save(png)
    print(f"QR sparad ({img.size[0]}x{img.size[1]}), oppnar bild och lank")
    subprocess.Popen(["cmd.exe", "/c", "start", "", str(png)], creationflags=0x08000000)
    subprocess.Popen(["cmd.exe", "/c", "start", "", link], creationflags=0x08000000)
    clear_clipboard()
    # QR-bilden raderas efter 10 minuter
    time.sleep(600)
    try:
        png.unlink()
    except OSError:
        pass
    print("QR raderad")
    return 0


if __name__ == "__main__":
    sys.exit(main())
