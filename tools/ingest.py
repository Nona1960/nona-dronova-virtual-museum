"""Stage 1: build catalog.json + optimized images from extracted repo images.
Usage: python3 -I ingest.py <museum-src dir> <site repo dir>
"""
import sys, os, re, json, collections
from PIL import Image, ImageOps

SRC, SITE = sys.argv[1], sys.argv[2]
recs = json.load(open(f"{SRC}/images.json"))
RAW = f"{SRC}/raw"

# ---------------------------------------------------------------- mapping
GARDEN_ROOMS = {  # garden-as-art room number -> (slug, collection)
    1: ("spring", "spring"), 2: ("irises", "summer-garden"), 3: ("poppies", "summer-garden"),
    4: ("daylilies", "lilies"), 5: ("lilac", "spring"), 6: ("peonies", "peonies"),
    7: ("lilies", "lilies"), 8: ("hostas", "leaves"), 9: ("july-garden", "summer-garden"),
    10: ("leaves", "leaves"), 11: ("ferns", "leaves"), 12: ("hydrangeas", "hydrangeas"),
    13: ("august", "summer-garden"), 14: ("phlox", "summer-garden"), 15: ("many-flowers", "summer-garden"),
    16: ("italian-garden", "italian-garden"), 17: ("large-panels", "interior-panels"),
    18: ("first-works", "early-works"), 19: ("tapestries", "textiles"), 20: ("textile-collages", "textiles"),
}
ROOM_BY_PAGE = {f"paintings-{v[0]}.html": (k, v[0], v[1]) for k, v in GARDEN_ROOMS.items()}

def classify(repo, page):
    """-> (collection, kind) ; kind in artwork|detail|garden|interior|illustration|skip"""
    p = page
    if repo == "garden-as-art":
        if p in ROOM_BY_PAGE: return ROOM_BY_PAGE[p][2], "artwork"
        if p == "garden.html": return "garden", "garden"
        if p == "paintings.html": return None, "artwork"          # overview: dedup decides
        if p == "creator-of-the-garden.html": return "garden", "illustration"
        if p in ("artist.html", "index.html"): return None, "illustration"
        return None, "skip"
    if repo == "Early-Works-of-Nona-Dronova":
        return ("early-works", "artwork") if p in ("watercolor-landscapes.html", "flowers-in-the-garden.html") else (None, "illustration")
    if repo == "Mood-Paintings-Spring-by-Artist-Nona-Dronova":
        return ("spring", "artwork") if p == "paintings.html" else (None, "illustration")
    if repo == "HYDRANGEA-BLOOM":
        if p in ("paintings.html", "painting-hydrangeas-red-blue.html"): return "hydrangeas", "artwork"
        if p in ("color.html", "painterly-matter.html"): return "hydrangeas", "detail"
        return None, "illustration"
    if repo == "Peony-Expansion":
        if p in ("paintings.html", "painting-peonies-ferns-thyme.html"): return "peonies", "artwork"
        if p in ("color.html", "painterly-matter.html"): return "peonies", "detail"
        return None, "illustration"
    if repo == "The-Energy-of-the-Rose":
        if p in ("pink-roses.html", "red-roses.html", "roses-in-progress.html", "energy-of-the-rose.html"): return "roses", "artwork"
        return None, "illustration"
    if repo == "Lilies-and-Daylilies":
        return ("lilies", "artwork") if p.startswith("paintings-") else (None, "illustration")
    if repo == "Leaves-in-Painting":
        if p == "paintings.html": return "leaves", "artwork"
        if p in ("color.html", "matter.html"): return "leaves", "detail"
        return None, "illustration"
    if repo == "Floral-Energy-Nona-Dronova":
        return ("floral-energy", "artwork") if p == "paintings.html" else (None, "illustration")
    if repo == "The-Theory-of-Pictorial-Contrasts":
        if p in ("paintings.html", "theory.html"): return "contrasts", "artwork"
        if p == "technique.html": return "contrasts", "detail"
        return None, "illustration"
    if repo == "Large-Interior-Panels-by-Artist-Nona-Dronova":
        if p in ("panels.html", "painting-and-space.html"): return "interior-panels", "artwork"
        if p == "panels-in-interiors.html": return "interior-panels", "interior"
        return None, "illustration"
    if repo == "textile-art-and-tapestries":
        if p in ("hand-weaving.html", "textile-collages.html", "leather-collages.html", "art-objects.html"): return "textiles", "artwork"
        return None, "illustration"
    if repo == "art-of-jewellery":
        if p in ("silver-liberi.html", "silver-hearts.html"): return "liberi", "artwork"
        if p in ("exclusive-collection.html", "gallery.html"): return "jewellery", "artwork"
        return None, "skip"
    if repo == "Nona-Dronova-Art-Studio":
        m = {"gallery-early-works.html": "early-works", "gallery-textile-art.html": "textiles",
             "gallery-jewellery-collections.html": "jewellery", "gallery-decorative-panels.html": "interior-panels",
             "gallery-diptychs-triptychs.html": "interior-panels", "gallery-interior-ensembles.html": "interior-panels"}
        if p in m: return m[p], "artwork"
        if p.startswith("gallery-") or p in ("selected-works.html", "art-gallery.html", "artist-archive.html"):
            return "studio", "artwork"
        return None, "illustration"
    return None, "skip"

COLL_PRIORITY = ["liberi", "jewellery", "textiles", "early-works", "roses", "hydrangeas", "peonies", "lilies",
                 "leaves", "spring", "summer-garden", "italian-garden", "interior-panels", "contrasts",
                 "floral-energy", "studio", "garden"]

# ---------------------------------------------------------------- parsing
TECH = [  # (regex, ru, en)
    (r"acrylic on canvas", "Холст, акрил", "Acrylic on canvas"),
    (r"oil on canvas", "Холст, масло", "Oil on canvas"),
    (r"hand-woven tapestry, wool", "Ручное ткачество, шерсть", "Hand-woven tapestry, wool"),
    (r"woven textile|hand-woven", "Ручное ткачество", "Hand-woven textile"),
    (r"mixed-media collage", "Коллаж, смешанная техника", "Mixed-media collage"),
    (r"leather", "Коллаж из кожи", "Leather collage"),
    (r"watercolou?r and pastel", "Бумага, акварель, пастель", "Watercolour and pastel on paper"),
    (r"watercolou?r and ink", "Бумага, акварель, тушь", "Watercolour and ink on paper"),
    (r"watercolou?r", "Бумага, акварель", "Watercolour on paper"),
]
SILVER_RE = re.compile(r"sterling silver[^|·]*", re.I)
STONES_RU = {"natural gemstones": "натуральные камни", "gemstones": "камни", "abalone shell": "раковина абалон",
             "garnet": "гранат", "peridot": "хризолит", "blue topaz": "голубой топаз", "enamel": "эмаль",
             "black gemstones": "чёрные камни", "mother-of-pearl": "перламутр", "smoky quartz": "дымчатый кварц",
             "turquoise": "бирюза", "coral": "коралл"}

def silver_ru(s):
    parts = [x.strip() for x in s.split(",")]
    out = ["серебро 925"]
    for x in parts[1:]:
        out.append(STONES_RU.get(x.lower(), x))
    return ", ".join(out).capitalize()

def tech_of(text):
    t = text.lower()
    m = SILVER_RE.search(text)
    if m:
        s = m.group(0).strip().rstrip(".")
        return silver_ru(s), s[0].upper() + s[1:]
    for rx, ru, en in TECH:
        if re.search(rx, t): return ru, en
    return None

YEAR_RE = re.compile(r"\b(19[6-9]\d|20[0-2]\d)\b")
GENERIC_ALT = re.compile(r"^(nona dronova|detail|sun|art of jewellery|spring garden painting)|study, nona dronova$|^(pink|red) rose study", re.I)

def parse(rec):
    cap, alt = rec["cap"], rec["alt"]
    d = {"legacy_no": None, "title_en": None, "year": None, "tech": None, "note_en": None}
    m = re.match(r"^No\.\s*([\d]+(?:-\d+)?)\s+(.*)$", cap)
    body = cap
    if m:
        d["legacy_no"], body = m.group(1), m.group(2)
    t = tech_of(cap) or tech_of(alt)
    if t: d["tech"] = t
    y = YEAR_RE.findall(cap) or YEAR_RE.findall(alt)
    if y: d["year"] = int(y[0])
    # title: text before "Nona Dronova" in caption
    mt = re.match(r"^(.*?)\s*·?\s*Nona Dronova\b(.*)$", body)
    title = None
    if mt and mt.group(1).strip(" ·—-"):
        title = mt.group(1).strip(" ·—-")
        rest = mt.group(2)
    else:
        rest = body
        if body and "Nona Dronova" not in body and not re.match(r"^(Detail|Liberi collection|Silver)", body):
            title = None
    # curatorial note after technique (Theory of Contrasts pages)
    if mt:
        tail = re.sub(r"^[\s·]*", "", rest)
        tail = re.sub(r"^(\d{4}\s*·\s*)?", "", tail)
        tail = re.sub(r"^(Oil on canvas|Acrylic on canvas)\s*(·\s*\d{4})?\s*", "", tail, flags=re.I)
        if len(tail) > 40: d["note_en"] = tail
        elif tail and not YEAR_RE.fullmatch(tail.strip()) and not tech_of(tail) and len(tail) > 3:
            if title is None: title = None
    if title is None and alt and not GENERIC_ALT.search(alt):
        a = re.split(r",\s*(oil on canvas|acrylic|watercolou?r|nona dronova)", alt, flags=re.I)[0]
        a = re.sub(r"\s+by Nona Dronova$", "", a)
        a = re.sub(r",\s*(Silver Liberi collection|Silver Hearts collection.*)$", "", a)
        a = re.sub(r"(\s+—\s+painting|,\s*(painting|jewellery))$", "", a.strip())
        if not re.match(r"^(Early Works|Selected Works|Expressionism|Post-Symbolism|Lyrical Studies|Botanical Abstraction)$", a):
            d["alt_title"] = a
    if title and re.match(r"^(Detail|Nona Dronova)$", title): title = None
    d["title_en"] = title
    return d

# ---------------------------------------------------------------- perceptual hash
def dhash(path, n=12):
    im = Image.open(path).convert("L").resize((n + 1, n), Image.LANCZOS)
    px = list(im.get_flattened_data()); bits = 0
    for r in range(n):
        for c in range(n):
            bits = (bits << 1) | (px[r * (n + 1) + c] > px[r * (n + 1) + c + 1])
    return bits

def ham(a, b): return bin(a ^ b).count("1")

rawfile = {os.path.splitext(f)[0]: f"{RAW}/{f}" for f in os.listdir(RAW)}
LOGO = re.compile(r"logo|emblem|sun mark|^Nona Dronova Art Studio$", re.I)

cands = []
for i, r in enumerate(recs):
    if max(r["w"], r["h"]) < 300 or LOGO.search(r["alt"]): continue
    coll, kind = classify(r["repo"], r["page"])
    if kind == "skip": continue
    r = dict(r); r["coll"], r["kind"] = coll, kind; r["order"] = i
    r.update(parse(r))
    if r["repo"] == "garden-as-art" and r["page"] in ROOM_BY_PAGE:
        r["room"] = ROOM_BY_PAGE[r["page"]][1]
    cands.append(r)

hashes = {}
for r in cands:
    if r["md5"] not in hashes: hashes[r["md5"]] = dhash(rawfile[r["md5"]])
    r["dh"] = hashes[r["md5"]]; r["ar"] = r["w"] / r["h"]

# union-find on near-duplicates
parent = list(range(len(cands)))
def find(x):
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
for a in range(len(cands)):
    for b in range(a + 1, len(cands)):
        A, B = cands[a], cands[b]
        if A["md5"] == B["md5"] or (abs(A["ar"] - B["ar"]) < 0.03 and ham(A["dh"], B["dh"]) <= 10):
            parent[find(a)] = find(b)
groups = collections.defaultdict(list)
for i, r in enumerate(cands): groups[find(i)].append(r)

KIND_RANK = {"artwork": 0, "garden": 1, "detail": 2, "interior": 3, "illustration": 4}
objects = []
for g in groups.values():
    g.sort(key=lambda r: r["order"])
    kind = min((r["kind"] for r in g), key=KIND_RANK.get)
    colls = [r["coll"] for r in g if r["coll"]]
    coll = min(colls, key=COLL_PRIORITY.index) if colls else None
    if kind == "illustration" and coll != "garden":
        coll = None
    best = max(g, key=lambda r: r["w"] * r["h"])
    roomcolls = [r["coll"] for r in g if r.get("room")]
    if roomcolls: coll = roomcolls[0]          # garden-as-art numbered catalogue is authoritative
    if kind == "artwork" and coll is None: coll = "studio"
    def clean(t):
        t = re.sub(r"^\d{2}\s+", "", t); t = re.sub(r"\s*·\s*\d{4}$", "", t); t = re.sub(r"\s+by$", "", t)
        return t.strip()
    REPO_PRI = lambda r: (0 if r["repo"] == "garden-as-art" and r.get("legacy_no") else
                          2 if r["repo"] == "Nona-Dronova-Art-Studio" else 1, r["order"])
    titled = sorted((r for r in g if r["title_en"]), key=REPO_PRI)
    title = clean(titled[0]["title_en"]) if titled else None
    variants = sorted({clean(r["title_en"]) for r in titled} - {title})
    alt_title = next((r.get("alt_title") for r in g if r.get("alt_title")), None)
    years = sorted({r["year"] for r in g if r["year"]})
    techs = [r["tech"] for r in g if r["tech"]]
    tech = techs[0] if techs else None
    if coll == "roses": tech = ("Холст, акрил", "Acrylic on canvas")   # confirmed by the artist 2026-10-19
    legacy = sorted({r["legacy_no"] for r in g if r["legacy_no"] and "-" in r["legacy_no"]})
    rooms = sorted({r["room"] for r in g if r.get("room")})
    note = next((r["note_en"] for r in g if r.get("note_en")), None)
    alts = [r["alt"] for r in g if r["alt"] and not GENERIC_ALT.search(r["alt"])]
    objects.append(dict(
        kind=kind, collection=coll, also=sorted(set(colls) - {coll}), rooms=rooms,
        title_en=title, alt_title_en=alt_title, desc_alt_en=(alts[0] if alts else None),
        year=(years[0] if len(years) == 1 else None), year_conflict=(years if len(years) > 1 else None),
        technique_ru=tech[0] if tech else None, technique_en=tech[1] if tech else None,
        legacy_garden_no=legacy, note_en=note,
        sources=sorted({f"https://github.com/Nona1960/{r['repo']}/blob/main/{r['page']}" for r in g}),
        img_md5=best["md5"], members=sorted({r["md5"] for r in g}), title_variants_en=variants,w=best["w"], h=best["h"], first=g[0]["order"]))

# stable ordering + IDs
CO = {c: i for i, c in enumerate(["early-works", "spring", "hydrangeas", "peonies", "roses", "lilies", "leaves",
                                  "summer-garden", "italian-garden", "floral-energy", "contrasts", "interior-panels",
                                  "studio", "textiles", "liberi", "jewellery", "garden"])}
objects.sort(key=lambda o: (o["kind"] != "artwork", CO.get(o["collection"], 99), o["first"]))
prefix = {"artwork": "NDM", "garden": "NDG", "detail": "NDD", "interior": "NDI", "illustration": "NDX"}
cnt = collections.Counter()
for o in objects:
    cnt[o["kind"]] += 1
    o["id"] = f"{prefix[o['kind']]}-{cnt[o['kind']]:04d}"

# ---------------------------------------------------------------- images
os.makedirs(f"{SITE}/img/l", exist_ok=True); os.makedirs(f"{SITE}/img/s", exist_ok=True)
for o in objects:
    src = rawfile[o["img_md5"]]; slug = o["id"].lower()
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    for d, mx, q in (("l", 1600, 82), ("s", 640, 76)):
        out = f"{SITE}/img/{d}/{slug}.webp"
        if not os.path.exists(out):
            t = im.copy(); t.thumbnail((mx, mx), Image.LANCZOS); t.save(out, "WEBP", quality=q, method=6)
    t = im.copy(); t.thumbnail((640, 640)); o["sw"], o["sh"] = t.size
    t = im.copy(); t.thumbnail((1600, 1600)); o["lw"], o["lh"] = t.size
    o.pop("first")

os.makedirs(f"{SITE}/data", exist_ok=True)
json.dump({"generated": "2026-10-19", "note": "Сгенерировано из репозиториев Nona1960. Неустановленные поля = null.",
           "objects": objects}, open(f"{SITE}/data/catalog.json", "w"), ensure_ascii=False, indent=1)
print(collections.Counter(o["kind"] for o in objects))
print(collections.Counter(o["collection"] for o in objects if o["kind"] == "artwork"))
print("titled", sum(1 for o in objects if o["kind"] == "artwork" and o["title_en"]),
      "dated", sum(1 for o in objects if o["kind"] == "artwork" and o["year"]),
      "year conflicts", sum(1 for o in objects if o["year_conflict"]))
