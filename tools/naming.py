# -*- coding: utf-8 -*-
"""SEO-friendly image file names shared by build.py and stamp_images.py."""
import re

def slug(t, n=60):
    t = (t or "").lower().replace("’", "").replace("'", "")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:n].rstrip("-")

def author_slug(o):
    return "sergey-dronov" if o.get("author") == "sergey" else "nona-dronova"

def fname(o, src_title=None):
    k = o["kind"]
    if k == "garden": base = "garden-ferns-and-moss"
    elif k == "interior": base = "painting-in-the-artist-home"
    elif k == "illustration":
        base = slug(re.sub(r",?\s*(by|of)\s+(nona|sergey)\s+dronov[a]?", "", o.get("desc_alt_en") or "photo", flags=re.I), 44) or "photo"
    else:
        base = slug(o.get("title_en") or src_title or "") or slug((o.get("collection") or "work").replace("-", " "))
    return f"{author_slug(o)}-{base}-{o['id'].lower()}"
