"""Genererar DrJonsson 3D Prints-branding lokalt med Z-Image-Turbo (gratis)."""
import os, sys
os.environ.setdefault("HF_HOME", r"E:\CHAT-RTX\hf-cache")
import torch, diffusers
from pathlib import Path
OUT = Path(__file__).parent / "raw"; OUT.mkdir(exist_ok=True)
pipe = diffusers.ZImagePipeline.from_pretrained("Tongyi-MAI/Z-Image-Turbo", torch_dtype=torch.bfloat16)
pipe.to('cuda')
STYLE = "clean bright Scandinavian studio, soft daylight, off-white and light oak wood surface, minimalist product photography, shallow depth of field, no text, no people, no logos"
OBJ = "3D-printed objects in multicolour PLA: a geometric desk organizer, a small vase with layered ridges, a cable holder, a pen cup, in matte black, white, silver-grey and one warm orange accent"
jobs = {
 "banner": (1792, 448, f"ultra wide panoramic banner, {OBJ} arranged along a wooden shelf with empty space on the left, {STYLE}"),
 "hero": (1792, 960, f"wide hero photo, {OBJ} on a pale wooden table next to a window, {STYLE}"),
 "icon_bg": (1024, 1024, "abstract layered 3D-printed texture, fine horizontal print layer lines in matte black and silver-grey PLA with a thin warm orange stripe, macro, soft light, no text, no letters"),
}
for name, (w, h, p) in jobs.items():
    for seed in (7, 8):
        g = torch.Generator("cpu").manual_seed(seed)
        im = pipe(prompt=p, width=w, height=h, num_inference_steps=8, guidance_scale=0.0, generator=g).images[0]
        im.save(OUT / f"{name}_{seed}.png"); print(name, seed, flush=True)
