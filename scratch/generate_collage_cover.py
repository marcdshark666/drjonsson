import subprocess
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "brand"
DOCS_IMG = ROOT / "docs" / "img"
SCRATCH_DIR = ROOT / "scratch"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# Select 6 top motifs for the collage
imgs = [
    (DOCS_IMG / "20260915-1-riviera-garden-cream-suit.jpg").as_uri(),
    (DOCS_IMG / "20260915-3-capri-speedboat.jpg").as_uri(),
    (DOCS_IMG / "20260916-3-lake-como-high-board.jpg").as_uri(),
    (DOCS_IMG / "20260915-2-cortina-silk-robe.jpg").as_uri(),
    (DOCS_IMG / "20260916-1-palm-springs-the-trio.jpg").as_uri(),
    (DOCS_IMG / "20260916-2-cannes-caftans.jpg").as_uri(),
]

collage_html = f"""<!DOCTYPE html>
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
    padding: 0 90px;
    border: 16px solid #111111;
    overflow: hidden;
    position: relative;
  }}
  .inner-border {{
    position: absolute;
    top: 28px; left: 28px; right: 28px; bottom: 28px;
    border: 3px solid #C9A227;
    pointer-events: none;
    z-index: 10;
  }}
  .brand-left {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    max-width: 1400px;
    z-index: 2;
  }}
  .brand-header {{
    display: flex;
    align-items: center;
    gap: 45px;
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
    font-size: 155px;
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
    margin-top: 25px;
  }}
  .gold-rule {{
    height: 4px;
    width: 140px;
    background: #C9A227;
  }}
  .slogan {{
    font-size: 38px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    font-weight: 600;
    color: #111111;
  }}
  .announcement {{
    font-size: 30px;
    color: #5B5449;
    letter-spacing: 0.12em;
    margin-top: 40px;
    text-transform: uppercase;
    font-weight: 500;
  }}
  .collage-right {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: repeat(2, 1fr);
    gap: 20px;
    z-index: 2;
    padding: 20px;
  }}
  .frame {{
    background: #FFFFFF;
    padding: 10px 10px 14px;
    box-shadow: 0 15px 35px rgba(0,0,0,0.18);
    border: 2px solid #D6CCB8;
    border-radius: 3px;
  }}
  .frame:nth-child(1) {{ transform: rotate(-2deg); }}
  .frame:nth-child(2) {{ transform: rotate(1.5deg) translateY(-8px); }}
  .frame:nth-child(3) {{ transform: rotate(-1deg); }}
  .frame:nth-child(4) {{ transform: rotate(2deg); }}
  .frame:nth-child(5) {{ transform: rotate(-1.5deg); }}
  .frame:nth-child(6) {{ transform: rotate(1deg); }}
  .frame img {{
    width: 260px;
    height: 340px;
    object-fit: cover;
    display: block;
    border-radius: 2px;
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

<div class="collage-right">
  <div class="frame"><img src="{imgs[0]}"></div>
  <div class="frame"><img src="{imgs[1]}"></div>
  <div class="frame"><img src="{imgs[2]}"></div>
  <div class="frame"><img src="{imgs[3]}"></div>
  <div class="frame"><img src="{imgs[4]}"></div>
  <div class="frame"><img src="{imgs[5]}"></div>
</div>

</body>
</html>
"""

(SCRATCH_DIR / "collage_temp.html").write_text(collage_html, encoding="utf-8")
cover_png = BRAND_DIR / "etsy_cover_collage_3360x840.png"

print("Rendering Collage Cover Banner (3360x840)...")
subprocess.run([EDGE_EXE, "--headless", "--disable-gpu", "--hide-scrollbars", "--window-size=3360,840",
                f"--screenshot={cover_png}", str((SCRATCH_DIR / "collage_temp.html").resolve())], check=True)

print("Done! Collage generated successfully in brand/")
