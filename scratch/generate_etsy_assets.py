import subprocess
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "brand"
SCRATCH_DIR = ROOT / "scratch"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# 1. Profile Icon HTML (500x500)
profile_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; padding: 0; width: 500px; height: 500px; background: #F4EFE6; display: flex; align-items: center; justify-content: center; overflow: hidden; }
  svg { width: 420px; height: 420px; }
</style>
</head>
<body>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240">
  <rect width="240" height="240" fill="#F4EFE6"/>
  <rect x="6" y="6" width="228" height="228" fill="none" stroke="#111111" stroke-width="5"/>
  <rect x="18" y="18" width="204" height="204" fill="none" stroke="#C9A227" stroke-width="2"/>
  <path d="M62 60 V196 H112 A68 68 0 0 0 112 60 Z" fill="none" stroke="#111111" stroke-width="12" stroke-linejoin="miter"/>
  <path d="M196 60 V160 A34 34 0 0 1 128 160" fill="none" stroke="#C9A227" stroke-width="12" stroke-linecap="square"/>
  <path d="M166 60 H226" stroke="#C9A227" stroke-width="12" stroke-linecap="square"/>
</svg>
</body>
</html>
"""

# 2. Cover Banner HTML (3360x840)
img1 = (ROOT / "docs" / "img" / "20260915-1-riviera-garden-cream-suit.jpg").as_uri()
img2 = (ROOT / "docs" / "img" / "20260915-3-capri-speedboat.jpg").as_uri()
img3 = (ROOT / "docs" / "img" / "20260916-3-lake-como-high-board.jpg").as_uri()

cover_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0; width: 3360px; height: 840px;
    background: #F4EFE6;
    color: #111111;
    font-family: 'IBM Plex Sans', sans-serif;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 120px;
    border: 16px solid #111111;
    overflow: hidden;
    position: relative;
  }}
  .inner-border {{
    position: absolute;
    top: 28px; left: 28px; right: 28px; bottom: 28px;
    border: 3px solid #C9A227;
    pointer-events: none;
  }}
  .brand-left {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    max-width: 1700px;
    z-index: 2;
  }}
  .brand-header {{
    display: flex;
    align-items: center;
    gap: 50px;
  }}
  .logo-svg {{
    width: 220px;
    height: 220px;
    flex: none;
  }}
  .title-group {{
    display: flex;
    flex-direction: column;
  }}
  h1 {{
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 160px;
    font-weight: 500;
    margin: 0;
    line-height: 0.95;
    letter-spacing: 0.02em;
  }}
  h1 span {{ color: #C9A227; }}
  .slogan-line {{
    display: flex;
    align-items: center;
    gap: 24px;
    margin-top: 30px;
  }}
  .gold-rule {{
    height: 4px;
    width: 140px;
    background: #C9A227;
  }}
  .slogan {{
    font-size: 42px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    font-weight: 600;
    color: #111111;
  }}
  .announcement {{
    font-size: 32px;
    color: #5B5449;
    letter-spacing: 0.12em;
    margin-top: 45px;
    text-transform: uppercase;
    font-weight: 500;
  }}
  .gallery-right {{
    display: flex;
    gap: 40px;
    align-items: center;
    z-index: 2;
  }}
  .frame {{
    background: #FFFFFF;
    padding: 18px 18px 24px;
    box-shadow: 0 20px 45px rgba(0,0,0,0.15);
    border: 2px solid #D6CCB8;
    transform: rotate(-1.5deg);
    transition: transform 0.3s;
  }}
  .frame:nth-child(2) {{
    transform: rotate(2deg) translateY(-20px);
  }}
  .frame:nth-child(3) {{
    transform: rotate(-1deg);
  }}
  .frame img {{
    width: 380px;
    height: 570px;
    object-fit: cover;
    display: block;
  }}
</style>
</head>
<body>
<div class="inner-border"></div>

<div class="brand-left">
  <div class="brand-header">
    <svg class="logo-svg" viewBox="0 0 240 240">
      <rect width="240" height="240" fill="#F4EFE6"/>
      <rect x="6" y="6" width="228" height="228" fill="none" stroke="#111111" stroke-width="5"/>
      <rect x="18" y="18" width="204" height="204" fill="none" stroke="#C9A227" stroke-width="2"/>
      <path d="M62 60 V196 H112 A68 68 0 0 0 112 60 Z" fill="none" stroke="#111111" stroke-width="12"/>
      <path d="M196 60 V160 A34 34 0 0 1 128 160" fill="none" stroke="#C9A227" stroke-width="12" stroke-linecap="square"/>
      <path d="M166 60 H226" stroke="#C9A227" stroke-width="12" stroke-linecap="square"/>
    </svg>
    <div class="title-group">
      <h1>Dr<span>J</span>onsson</h1>
      <div class="slogan-line">
        <div class="gold-rule"></div>
        <div class="slogan">Rich in every frame</div>
      </div>
    </div>
  </div>
  <div class="announcement">Fine Art Photography Prints · Shipped Worldwide</div>
</div>

<div class="gallery-right">
  <div class="frame"><img src="{img1}"></div>
  <div class="frame"><img src="{img2}"></div>
  <div class="frame"><img src="{img3}"></div>
</div>

</body>
</html>
"""

(SCRATCH_DIR / "profile_temp.html").write_text(profile_html, encoding="utf-8")
(SCRATCH_DIR / "cover_temp.html").write_text(cover_html, encoding="utf-8")

prof_png = BRAND_DIR / "etsy_profile_500x500.png"
cover_png = BRAND_DIR / "etsy_cover_3360x840.png"

print("Rendering Profile Icon (500x500)...")
subprocess.run([EDGE_EXE, "--headless", "--disable-gpu", "--hide-scrollbars", "--window-size=500,500",
                f"--screenshot={prof_png}", str((SCRATCH_DIR / "profile_temp.html").resolve())], check=True)

print("Rendering Cover Banner (3360x840)...")
subprocess.run([EDGE_EXE, "--headless", "--disable-gpu", "--hide-scrollbars", "--window-size=3360,840",
                f"--screenshot={cover_png}", str((SCRATCH_DIR / "cover_temp.html").resolve())], check=True)

print("Done! Images generated successfully in brand/")
