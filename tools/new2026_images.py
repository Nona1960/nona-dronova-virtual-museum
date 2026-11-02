# -*- coding: utf-8 -*-
"""Prepare images for the «New acquisitions 2026» page: WebP, no cropping, EXIF authorship.
Usage: python3 -I tools/new2026_images.py <src1.jpg> <src2.jpg> ...   (in the order of content_new2026.SECTIONS)"""
import os, sys
from PIL import Image, ImageOps
HERE = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(os.path.dirname(HERE), "public")
sys.path.insert(0, HERE)
import content_new2026 as N

works = [w for s in N.SECTIONS for w in s["works"]]
srcs = sys.argv[1:]
assert len(srcs) == len(works), f"{len(srcs)} files for {len(works)} works"
out_dir = os.path.join(PUB, "img", "new-2026"); os.makedirs(out_dir, exist_ok=True)
for src, (name, ru, en, oil, mru, men) in zip(srcs, works):
    ex = Image.Exif()
    ex[0x013B] = "Nona Dronova"
    ex[0x8298] = "(c) Nona Dronova. All rights reserved."
    ex[0x010E] = f"Nona Dronova - {en}, {'oil on canvas, ' if oil else ''}{men + ' ' if men else ''}2026"
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im.save(os.path.join(out_dir, name + ".webp"), "WEBP", quality=90, method=6, exif=ex.tobytes())
    t = im.copy(); t.thumbnail((640, 640), Image.LANCZOS)
    t.save(os.path.join(out_dir, name + "-640.webp"), "WEBP", quality=80, method=6, exif=ex.tobytes())
    print(name, im.size)
