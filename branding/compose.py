from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from pathlib import Path
B=Path(__file__).parent; R=B/"raw"
ban=Image.open(R/"banner_8.png").convert("RGB").resize((3360,840),Image.LANCZOS); ban.save(B/"etsy-banner-3360x840.jpg",quality=92)
hero=Image.open(R/"hero_7.png").convert("RGB")
D=B.parent/"docs"/"img"; D.mkdir(exist_ok=True)
hero.resize((1600,857),Image.LANCZOS).save(D/"hero.jpg",quality=85); hero.resize((1600,857),Image.LANCZOS).save(B/"site-hero.jpg",quality=90)
w,h=hero.size; ch=int(w*630/1200); t=(h-ch)//2
og=hero.crop((0,t,w,t+ch)).resize((1200,630),Image.LANCZOS)
d=ImageDraw.Draw(og); ov=Image.new("RGBA",og.size,(0,0,0,0)); ImageDraw.Draw(ov).rectangle((0,430,1200,630),fill=(0,0,0,150))
og=Image.alpha_composite(og.convert("RGBA"),ov).convert("RGB"); d=ImageDraw.Draw(og)
f=lambda s:ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf",s)
d.text((50,460),"DrJonsson 3D Prints",font=f(72),fill="white"); d.text((52,550),"Egna 3D-printade föremål, gjorda i Sverige",font=f(34),fill=(232,112,42))
og.save(B/"og-1200x630.jpg",quality=90); og.save(D/"og.jpg",quality=88)
ic=Image.open(R/"icon_bg_7.png").convert("RGB").resize((500,500),Image.LANCZOS)
ic=ImageEnhance.Brightness(ic).enhance(.45); d=ImageDraw.Draw(ic)
def ctext(txt,y,size,fill):
    ft=f(size); bw=d.textlength(txt,font=ft); d.text(((500-bw)/2,y),txt,font=ft,fill=fill)
ctext("DJ",90,190,"white"); ctext("3D",285,130,(232,112,42))
ic.save(B/"etsy-icon-500x500.png")
