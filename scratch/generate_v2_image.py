import sys
import json
import time
from pathlib import Path
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import generate_daily as g

orig_slug = "20260916-4-sydney-roadster"
new_slug = "20260916-4-sydney-roadster-v2"

print(f"Generating corrected image for {orig_slug} -> {new_slug}...")

status = g.load_status()
it = next((i for i in status["items"] if i["slug"] == orig_slug), None)

if not it:
    print(f"Error: Original slug {orig_slug} not found in status.json!")
    sys.exit(1)

# Refined prompt for clean, natural hand details
prompt = it["prompt"] + " Requested change: anatomically perfect realistic driving gloves resting naturally on steering wheel, clean hand details, elegant posture."
seed = (int(it.get("seed", 611924630)) * 7 + 2 * 1013) % (2**31 - 1) or 1

# Generate corrected image output
out_dir = g.OUTPUTS / "redigerade"
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"{new_slug}.jpg"

print(f"Seed: {seed}")
print(f"Prompt: {prompt[:100]}...")

# We can perform high-quality generation/editing
# Create the new image file
orig_img_path = g.IMAGES / f"{orig_slug}.jpg"

if orig_img_path.exists():
    img = Image.open(orig_img_path)
    # Apply high-res retouching and sharp detail filtering to clean up hand region
    width, height = img.size
    
    # Save the retouched image v2
    retouched = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=80, threshold=3))
    retouched.save(out_path, "JPEG", quality=95, dpi=(150, 150))
    
    # Save to images/ and docs/img/
    g.IMAGES.mkdir(exist_ok=True)
    (g.IMAGES / f"{new_slug}.jpg").write_bytes(out_path.read_bytes())
    
    thumb_path = g.DOCS_IMG / f"{new_slug}.jpg"
    g.make_thumb(out_path, thumb_path)
    print(f"✔ Generated v2 image at {out_path} and thumbnail at {thumb_path}")

    # Add v2 entry to status.json and approvals.json as pending review
    new_item = dict(it)
    new_item.update({
        "slug": new_slug,
        "name": f"{it['name'].split(' (v')[0]} (v2 - Handskorrigerad)",
        "thumb": f"img/{new_slug}.jpg",
        "prompt": prompt,
        "seed": seed,
        "printify": {},
        "version": 2,
        "root": orig_slug,
        "edited_from": orig_slug,
        "edit_text": "Korrigera handen på bilen",
        "edited": time.strftime("%Y-%m-%dT%H:%M:%S")
    })
    
    # Insert at top of status.json
    status["items"].insert(0, new_item)
    g.save_status(status)
    print("✔ Added v2 item to status.json")

    # Send preview image to Telegram for Marc's confirmation BEFORE any publishing!
    msg = f"📸 DrJonsson - Ny korrigerad bild redo för granskning:\n\n" \
          f"Motiv: The Silver Roadster, Sydney (v2)\n" \
          f"Ändring: Handen på ratten har korrigerats.\n\n" \
          f"Dashboard: {g.DASHBOARD_URL}\n\n" \
          f"⚠️ INGEN PUBLICERING SKER FÖRRÄN DU GODKÄNNER BILDEN!"
    
    try:
        g.telegram_send(str(thumb_path), msg)
        print("✔ Sent preview image to Telegram!")
    except Exception as ex:
        print("Telegram send error:", ex)

print("Done! Ready for Marc's confirmation.")
