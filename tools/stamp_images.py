# -*- coding: utf-8 -*-
"""Re-export images with SEO file names and EXIF authorship (Artist / Copyright / Description).
Usage: python3 -I tools/stamp_images.py <raw source dir>"""
import os, sys, json, re
from PIL import Image, ImageOps
HERE = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(os.path.dirname(HERE), "public")
sys.path.insert(0, HERE)
from naming import fname
RAW = sys.argv[1]
raw = {os.path.splitext(f)[0]: os.path.join(RAW, f) for f in os.listdir(RAW)}
cat = json.load(open(os.path.join(PUB, "data", "catalog.json"), encoding="utf-8"))["objects"]
SRC_RE = re.compile(r"^(.+?),\s*(textile art|jewellery|painting) by Nona Dronova$", re.I)
keep = {"l": set(), "s": set()}
for o in cat:
    if o["kind"] == "excluded": continue
    m = SRC_RE.match(o.get("desc_alt_en") or "")
    st = m.group(1) if m and not re.search(r"collection|detail|interior", m.group(1), re.I) else None
    name = fname(o, st)
    who = "Sergey Dronov" if o.get("author") == "sergey" else "Nona Dronova"
    title = o.get("title_en") or st or (o.get("desc_alt_en") or "")
    ex = Image.Exif()
    ex[0x013B] = who                                   # Artist
    ex[0x8298] = f"(c) {who}. All rights reserved."       # Copyright
    desc = f"{who}{' - ' + title if title else ''}"
    ex[0x010E] = desc.encode("ascii", "ignore").decode()[:250]  # ImageDescription
    im = ImageOps.exif_transpose(Image.open(raw[o["img_md5"]])).convert("RGB")
    for d, mx, q in (("l", 1600, 82), ("s", 640, 76)):
        out = os.path.join(PUB, "img", d, name + ".webp")
        t = im.copy(); t.thumbnail((mx, mx), Image.LANCZOS)
        t.save(out, "WEBP", quality=q, method=5, exif=ex.tobytes())
        keep[d].add(name + ".webp")
for d in ("l", "s"):
    for f in os.listdir(os.path.join(PUB, "img", d)):
        if f not in keep[d]: os.remove(os.path.join(PUB, "img", d, f))
print({d: len(v) for d, v in keep.items()})
