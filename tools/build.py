# -*- coding: utf-8 -*-
"""Static site generator for the Nona Dronova Virtual Art Museum.
Reads public/data/catalog.json + tools/content_*.py, writes HTML into public/.
Run: python3 -I tools/build.py   (from repo root)"""
import os, sys, json, html, re, shutil, hashlib
from datetime import date
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); PUB = os.path.join(ROOT, "public")
sys.path.insert(0, HERE)
from content_collections import COLLECTIONS, ROOMS, SEASONS, GH
from content_theory import ESSAYS, CONTEXT, GLOSSARY, THEORY_INTRO_RU, THEORY_INTRO_EN
import content_pages as P
import content_publications as PUB_
from PIL import Image

SITE_URL = os.environ.get("SITE_URL", "https://nona-dronova-museum.vercel.app").rstrip("/")
TODAY = "2026-10-19"
CAT = json.load(open(os.path.join(PUB, "data", "catalog.json"), encoding="utf-8"))["objects"]
BY_ID = {o["id"]: o for o in CAT}
EXCLUDE_RE = re.compile(r"advertising banner|theme banner|portrait of nona|^professor, art historian|installed above a sofa|circular motif, detail", re.I)
for o in CAT:
    if o["kind"] == "artwork" and EXCLUDE_RE.search((o.get("desc_alt_en") or "") + " " + (o.get("title_en") or "")):
        o["kind"] = "excluded"
EXCLUDE_IDS = {"NDM-0387", "NDM-0388", "NDM-0389", "NDM-0390", "NDM-0391", "NDM-0392"}  # portraits of the artist wearing jewellery
for o in CAT:
    o.setdefault("author", "nona")
    if o["id"] in EXCLUDE_IDS: o["kind"] = "excluded"
    if o["kind"] == "artwork" and any("exclusive-collection.html" in x for x in o["sources"]):
        o["collection"], o["author"] = "sergey-jewellery", "sergey"   # confirmed by the artist 19.10.2026
ART = [o for o in CAT if o["kind"] == "artwork"]
NONA_ART = [o for o in ART if o["author"] == "nona"]
for o in ART:   # silver is stated for the whole LIBERI collection by the artist's text
    if o["collection"] == "liberi" and not o.get("technique_en"):
        o["technique_ru"], o["technique_en"] = "Серебро", "Silver"
SRC_TITLE_RE = re.compile(r"^(.+?),\s*(textile art|jewellery|painting) by Nona Dronova$", re.I)
COLL = {c["slug"]: c for c in COLLECTIONS}
ROOM = {r[1]: r for r in ROOMS}
ESS = {e["slug"]: e for e in ESSAYS}
HERO_ID = "NDX-0038"; PORTRAIT_ID = "NDX-0030"; STUDIO_ID = "NDX-0021"; SERGEY_ID = "NDX-0001"; GARDEN_PAINT_ID = "NDX-0039"
PAGES = []  # (path, lastmod, images) for sitemap

def e(s): return html.escape(s or "", quote=True)
def L(lang, ru, en): return ru if lang == "ru" else en
def url(lang, path): return path if lang == "ru" else "/en" + path
def absu(path): return SITE_URL + path

# ------------------------------------------------------------------ object helpers
def coll_works(slug, kind="artwork"):
    slugs = slug if isinstance(slug, list) else [slug]
    return [o for o in CAT if o["kind"] == kind and o["collection"] in slugs]

def src_title(o):
    m = SRC_TITLE_RE.match(o.get("desc_alt_en") or "")
    if m and not re.search(r"collection|detail|interior", m.group(1), re.I): return m.group(1)
    return None

TYPE_RU = [(r"necklace", "Колье", "Necklace"), (r"bracelet", "Браслет", "Bracelet"), (r"brooch", "Брошь", "Brooch"),
           (r"pendant|hearts", "Подвеска", "Pendant"), (r"earring", "Серьги", "Earrings"), (r"ring", "Кольцо", "Ring"),
           (r"leather", "Коллаж из кожи", "Leather collage"), (r"crochet|cushion", "Вязаный арт-объект", "Crocheted art object"),
           (r"collage", "Текстильный коллаж", "Textile collage"), (r"tapestr|woven|weav|loom", "Гобелен", "Tapestry")]
def type_label(o, lang):
    d = ((o.get("desc_alt_en") or "") + " " + (o.get("technique_en") or "") + " " + " ".join(o["sources"])).lower()
    for rx, ru, en in TYPE_RU:
        if re.search(rx, d): return L(lang, ru, en)
    return L(lang, {"textiles": "Текстильная работа", "liberi": "Украшение LIBERI"}.get(o["collection"], "Украшение") if o["collection"] in APPLIED else "Произведение",
                   {"textiles": "Textile work", "liberi": "LIBERI piece"}.get(o["collection"], "Jewellery piece") if o["collection"] in APPLIED else "Work")

APPLIED = ("textiles", "liberi", "jewellery", "sergey-jewellery")
def title(o, lang):
    if o.get("title_en"): return o["title_en"]
    st = src_title(o)
    if st: return st
    if o["collection"] in APPLIED:
        if lang == "en" and o.get("desc_alt_en"):
            d = re.sub(r",?\s*(Silver Liberi collection|Art of Jewellery.*|by Nona Dronova)$", "", o["desc_alt_en"]).strip()
            if d and not re.search(r"collections?$", d, re.I): return d[0].upper() + d[1:]
        return type_label(o, lang)
    return L(lang, "Название не указано", "Title not recorded")

def has_title(o): return bool(o.get("title_en") or src_title(o) or o["collection"] in APPLIED)

def tech(o, lang):
    return (o.get("technique_ru") if lang == "ru" else o.get("technique_en")) or None

def coll_name(slug, lang):
    if slug == "garden": return L(lang, "Сад «Папоротники и мох»", "The Ferns and Moss Garden")
    c = COLL.get(slug); return (c["ru"] if lang == "ru" else c["en"]) if c else ""

def alt(o, lang):
    if o["kind"] == "garden" or o["id"] in P.GARDEN_CAPTIONS or o["id"] in P.INTERIOR_CAPTIONS:
        cap = P.GARDEN_CAPTIONS.get(o["id"]) or P.INTERIOR_CAPTIONS.get(o["id"])
        if cap: return cap[0] if lang == "ru" else cap[1]
    parts = []
    if o.get("title_en") or src_title(o): parts.append(f"«{title(o, lang)}»" if lang == "ru" else f"“{title(o, lang)}”")
    elif o["collection"] in APPLIED: parts.append(title(o, lang))
    elif o.get("desc_alt_en") and lang == "en": parts.append(o["desc_alt_en"])
    else: parts.append(L(lang, f"Работа из коллекции «{coll_name(o['collection'], 'ru')}»", f"Work from the {coll_name(o['collection'], 'en')} collection"))
    t = tech(o, lang)
    if t: parts.append(t.lower() if lang == "ru" else t.lower())
    if o.get("year"): parts.append(str(o["year"]))
    return f"{author_name(o, lang)}. " + ", ".join(parts)

def author_name(o, lang):
    return L(lang, "Сергей Дронов", "Sergey Dronov") if o.get("author") == "sergey" else L(lang, "Нона Дронова", "Nona Dronova")

def img(o, lang, sizes="(max-width: 640px) 50vw, 320px", large=False, eager=False, cls=""):
    s = o["id"].lower()
    w, h = (o["lw"], o["lh"]) if large else (o["sw"], o["sh"])
    src = f"/img/{'l' if large else 's'}/{s}.webp"
    srcset = f"/img/s/{s}.webp {o['sw']}w, /img/l/{s}.webp {o['lw']}w"
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<img src="{src}" srcset="{srcset}" sizes="{sizes}" width="{w}" height="{h}" '
            f'alt="{e(alt(o, lang))}" decoding="async" {load} class="{cls}">')

def meta_line(o, lang):
    bits = []
    t = tech(o, lang)
    if t: bits.append(t)
    if o.get("year"): bits.append(str(o["year"]))
    return " · ".join(bits)

def card(o, lang, link=True, show_coll=False):
    inner = img(o, lang)
    cap = f'<span class="t">{e(title(o, lang))}</span>'
    ml = meta_line(o, lang)
    if show_coll: ml = (coll_name(o["collection"], lang) + (" · " + ml if ml else ""))
    if ml: cap += f'<span class="m">{e(ml)}</span>'
    cap += f'<span class="id">{o["id"]}</span>'
    if not has_title(o): cap = cap.replace('class="t"', 'class="t muted"')
    href = url(lang, f"/archive/{o['id'].lower()}/")
    if link:
        return f'<a class="work" href="{href}"><figure>{inner}<figcaption>{cap}</figcaption></figure></a>'
    return f'<figure class="work">{inner}<figcaption>{cap}</figcaption></figure>'

def grid(objs, lang, cls="", show_coll=False):
    return f'<div class="masonry {cls}">' + "".join(card(o, lang, show_coll=show_coll) for o in objs) + "</div>"

def photo(o, lang, caption=True, large=True):
    cap = P.GARDEN_CAPTIONS.get(o["id"]) or P.INTERIOR_CAPTIONS.get(o["id"])
    c = (cap[0] if lang == "ru" else cap[1]) if cap else alt(o, lang)
    return (f'<figure class="photo">{img(o, lang, sizes="(max-width: 900px) 100vw, 900px", large=large)}'
            + (f'<figcaption>{e(c)}</figcaption>' if caption else '') + '</figure>')

# ------------------------------------------------------------------ OG images (letterboxed, never cropped)
OG_DIR = os.path.join(PUB, "og"); os.makedirs(OG_DIR, exist_ok=True)
def og_image(oid):
    out = os.path.join(OG_DIR, f"{oid.lower()}.jpg")
    if not os.path.exists(out):
        im = Image.open(os.path.join(PUB, "img", "l", f"{oid.lower()}.webp")).convert("RGB")
        im.thumbnail((1200 - 60, 630 - 60), Image.LANCZOS)
        bg = Image.new("RGB", (1200, 630), (251, 248, 241)); bg.paste(im, ((1200 - im.width) // 2, (630 - im.height) // 2))
        bg.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    return f"/og/{oid.lower()}.jpg"

# ------------------------------------------------------------------ JSON-LD
PERSON = {"@type": "Person", "@id": SITE_URL + "/#nona", "name": "Nona Dronova", "alternateName": "Нона Дронова",
          "jobTitle": "Artist", "memberOf": {"@type": "Organization", "name": "Union of Artists of Russia"},
          "url": SITE_URL + "/about/", "sameAs": ["https://nona-dronova-art-studio.vercel.app/", "https://github.com/Nona1960"]}
SERGEY = {"@type": "Person", "@id": SITE_URL + "/#sergey", "name": "Sergey Dronov", "alternateName": "Сергей Дронов",
          "spouse": {"@id": SITE_URL + "/#nona"}, "memberOf": {"@type": "Organization", "name": "Union of Artists of Russia"}}
WEBSITE = {"@type": "WebSite", "@id": SITE_URL + "/#site", "url": SITE_URL + "/", "name": P.SITE["en"],
           "alternateName": P.SITE["ru"], "inLanguage": ["ru", "en"], "publisher": {"@id": SITE_URL + "/#nona"},
           "potentialAction": {"@type": "SearchAction", "target": SITE_URL + "/archive/?q={search_term_string}",
                               "query-input": "required name=search_term_string"}}

def crumbs_ld(lang, crumbs):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": absu(url(lang, p))} for i, (n, p) in enumerate(crumbs)]}

# ------------------------------------------------------------------ layout
CSS_V = ""
def head(lang, path, ttl, desc, og=None, ld=None, extra=""):
    brand = L(lang, "Музей Ноны Дроновой", "Nona Dronova Museum")
    full = f"{ttl} | {brand}" if path != "/" else f"{P.SITE[lang]} — {P.SITE['tag_' + lang]}"
    og_url = absu(og or og_image(HERO_ID))
    ru, en = absu(url("ru", path)), absu(url("en", path))
    graph = [WEBSITE, PERSON, SERGEY] + (ld or [])
    ldj = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(full)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{absu(url(lang, path))}">
<link rel="alternate" hreflang="ru" href="{ru}">
<link rel="alternate" hreflang="en" href="{en}">
<link rel="alternate" hreflang="x-default" href="{ru}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="{L(lang, 'Нона Дронова', 'Nona Dronova')}">
<meta name="theme-color" content="#FBF8F1">
<meta property="og:type" content="{'article' if path.startswith('/theory/') else 'website'}">
<meta property="og:site_name" content="{e(P.SITE[lang])}">
<meta property="og:title" content="{e(ttl)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{absu(url(lang, path))}">
<meta property="og:image" content="{og_url}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:locale" content="{'ru_RU' if lang == 'ru' else 'en_GB'}">
<meta property="og:locale:alternate" content="{'en_GB' if lang == 'ru' else 'ru_RU'}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/assets/sun-192.png" type="image/png" sizes="192x192">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Inter:wght@400;500;600&display=swap">
<link rel="stylesheet" href="/assets/site.css?v={CSS_V}">
{extra}<script type="application/ld+json">{ldj}</script>
</head>'''

def header(lang, path, active):
    other = "en" if lang == "ru" else "ru"
    nav = "".join(f'<a href="{url(lang, p)}"{" aria-current=\"page\"" if k == active else ""}>{e(ru if lang == "ru" else en)}</a>'
                  for k, ru, en, p in P.NAV)
    sw = f'<a class="lang" href="{url(other, path)}" hreflang="{other}" lang="{other}">{"EN" if lang == "ru" else "RU"}</a>'
    return f'''<body>
<a class="skip" href="#main">{L(lang, "К содержанию", "Skip to content")}</a>
<header class="site-header">
  <div class="bar">
    <a class="brand" href="{url(lang, '/')}"><img src="/assets/sun.webp" width="40" height="40" alt=""><span><b>{L(lang, 'Нона Дронова', 'Nona Dronova')}</b><i>{L(lang, 'Виртуальный музей', 'Virtual Art Museum')}</i></span></a>
    <nav class="nav" aria-label="{L(lang, 'Основное меню', 'Main menu')}">{nav}</nav>
    {sw}
    <details class="menu"><summary aria-label="{L(lang, 'Меню', 'Menu')}"><span></span><span></span><span></span></summary>
      <nav aria-label="{L(lang, 'Мобильное меню', 'Mobile menu')}">{nav}{''.join(f'<a href="{url(lang, p)}">{e(ru if lang == "ru" else en)}</a>' for k, ru, en, p in P.FOOT)}</nav></details>
  </div>
</header>
<main id="main">'''

def footer(lang):
    links = "".join(f'<li><a href="{url(lang, p)}">{e(ru if lang == "ru" else en)}</a></li>' for k, ru, en, p in P.NAV + P.FOOT)
    return f'''</main>
<div class="stripe" aria-hidden="true"></div>
<footer class="site-footer">
  <div class="wrap foot">
    <div>
      <a class="brand light" href="{url(lang, '/')}"><img src="/assets/sun.webp" width="40" height="40" alt=""><span><b>{L(lang, 'Нона Дронова', 'Nona Dronova')}</b><i>{L(lang, 'Виртуальный музей', 'Virtual Art Museum')}</i></span></a>
      <p>{e(P.SITE['tag_' + lang])}.</p>
      <p class="small">{L(lang, 'Сад «Папоротники и мох» — Сергей Дронов.', 'The Ferns and Moss garden — Sergey Dronov.')}</p>
    </div>
    <ul class="foot-links">{links}</ul>
  </div>
  <div class="wrap foot-bottom"><span>© 2026 {L(lang, 'Нона Дронова. Все права на произведения и тексты защищены.', 'Nona Dronova. All rights to the works and texts reserved.')}</span>
  <a href="{url('en' if lang == 'ru' else 'ru', '/')}">{'English version' if lang == 'ru' else 'Русская версия'}</a></div>
</footer>
</body>
</html>'''

def breadcrumbs(lang, crumbs):
    items = "".join(f'<li><a href="{url(lang, p)}">{e(n)}</a></li>' for n, p in crumbs[:-1])
    return f'<nav class="crumbs wrap" aria-label="{L(lang, "Навигация", "Breadcrumb")}"><ol>{items}<li aria-current="page">{e(crumbs[-1][0])}</li></ol></nav>'

def write(lang, path, body, lastmod=TODAY, images=()):
    out = os.path.join(PUB, path.strip("/"), "index.html") if lang == "ru" else os.path.join(PUB, "en", path.strip("/"), "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(body)
    if lang == "ru": PAGES.append((path, lastmod, list(images)))

def page(lang, path, active, ttl, desc, content, crumbs=None, og=None, ld=None, accent=None, images=(), bodycls=""):
    ldl = list(ld or [])
    if crumbs: ldl.append(crumbs_ld(lang, crumbs))
    h = head(lang, path, ttl, desc, og=og, ld=ldl)
    hd = header(lang, path, active)
    if accent: hd = hd.replace("<body>", f'<body class="{bodycls}" style="--accent:{accent}">', 1)
    elif bodycls: hd = hd.replace("<body>", f'<body class="{bodycls}">', 1)
    bc = breadcrumbs(lang, crumbs) if crumbs else ""
    write(lang, path, h + "\n" + hd + bc + content + footer(lang), images=images)

def home_crumb(lang): return (L(lang, "Главная", "Home"), "/")
def btn(lang, path, ru, en, cls="btn"): return f'<a class="{cls}" href="{url(lang, path)}">{e(L(lang, ru, en))}</a>'
def paras(lst): return "".join(f"<p>{e(x)}</p>" for x in lst)
def badge(status, lang):
    m = {"author": ("Авторский текст", "Artist's text"), "museum": ("Текст музея", "Museum text"),
         "confirmed": ("Подтверждено автором", "Confirmed by the artist"), "stated": ("Со слов автора, ожидает проверки", "As stated by the artist, pending verification"),
         "works": ("По произведениям в архиве", "From works in the archive"), "project": ("Проект", "In preparation"),
         "hypothesis": ("Рабочая гипотеза", "Working hypothesis")}
    ru, en = m[status]; return f'<span class="badge b-{status}">{L(lang, ru, en)}</span>'

def room_works(slug): return [o for o in ART if slug in (o.get("rooms") or [])]
def cover(slug):
    ws = coll_works(slug)
    titled = [o for o in ws if has_title(o)] or ws
    return titled[0] if titled else None

COVERS = {}
def stats():
    return dict(works=len(ART), rooms=len(ROOMS), colls=len(COLLECTIONS), essays=len(ESSAYS) + 1)

# ------------------------------------------------------------------ pages
def build_home(lang):
    H = P.HOME; S = stats(); hero = BY_ID[HERO_ID]
    seasons = ""
    for sk, sru, sen, dru, den in SEASONS:
        rs = [r for r in ROOMS if r[4] == sk]
        rw = [w for r in rs for w in room_works(r[1])]
        if not rw: continue
        o = next((w for w in rw if has_title(w)), rw[0])
        seasons += (f'<a class="season" href="{url(lang, "/garden-as-art/")}#{sk}"><span class="thumb">{img(o, lang, sizes="(max-width:640px) 45vw, 240px")}</span>'
                    f'<b>{e(L(lang, sru, sen))}</b><span>{e(L(lang, dru, den))}</span></a>')
    principles = next(b for b in ESS["botanical-expressionism"]["blocks"] if b[0] == "principles")[1]
    pr = "".join(f'<li><b>{i+1:02d}</b> {e(L(lang, a, b))}</li>' for i, (a, b, c, d) in enumerate(principles))
    paint = [c for c in COLLECTIONS if c["group"] == "painting"]
    ccards = "".join(coll_card(c, lang) for c in paint[:8])
    mat = "".join(coll_card(COLL[s], lang, path=COLL[s].get("page")) for s in ("textiles", "liberi"))
    body = f'''
<section class="hero">
  <figure class="hero-art">{img(hero, lang, sizes="100vw", large=True, eager=True)}<figcaption>{L(lang, 'Нона Дронова. «The Secret Garden», 2022. Холст, масло', 'Nona Dronova. The Secret Garden, 2022. Oil on canvas')}</figcaption></figure>
  <div class="wrap hero-text">
    <p class="eyebrow">{e(P.SITE['tag_' + lang])}</p>
    <h1>{e(H['h1_' + lang])}</h1>
    <p class="lead">{e(H['lead_' + lang])}</p>
    <div class="btns">{btn(lang, '/collections/', 'Смотреть коллекции', 'View the collections')}{btn(lang, '/theory/botanical-expressionism/', 'О ботаническом экспрессионизме', 'On botanical expressionism', 'btn ghost')}{btn(lang, '/garden-as-art/', 'Сад как искусство', 'The Garden as Art', 'btn ghost')}{btn(lang, '/archive/', 'Научный каталог', 'Scholarly catalogue', 'btn ghost')}</div>
  </div>
</section>
<section class="wrap stats" aria-label="{L(lang, 'Музей в цифрах', 'The museum in numbers')}">
  <div><b>{S['works']}</b><span>{L(lang, 'произведений в каталоге', 'works in the catalogue')}</span></div>
  <div><b>{S['rooms']}</b><span>{L(lang, 'залов сада', 'garden rooms')}</span></div>
  <div><b>{S['colls']}</b><span>{L(lang, 'коллекций', 'collections')}</span></div>
  <div><b>{S['essays']}</b><span>{L(lang, 'текстов по теории', 'texts on theory')}</span></div>
</section>
<section class="wrap split">
  <div><p class="eyebrow">{L(lang, 'О музее', 'About the museum')}</p><p class="big">{e(H['about_' + lang])}</p></div>
  {photo(BY_ID[GARDEN_PAINT_ID], lang)}
</section>
<section class="band garden-band">
  <div class="wrap">
    <p class="eyebrow">{L(lang, 'Основа музея', 'The heart of the museum')}</p>
    <h2>{L(lang, 'Сад как искусство', 'The Garden as Art')}</h2>
    <p class="big narrow">{e(H['garden_' + lang])}</p>
    <div class="seasons">{seasons}</div>
    {btn(lang, '/garden-as-art/', 'Войти в сад', 'Enter the garden')}
  </div>
</section>
<section class="wrap split rev">
  <div>
    <p class="eyebrow">{L(lang, 'Теория', 'Theory')}</p>
    <h2>{L(lang, 'Ботанический экспрессионизм', 'Botanical Expressionism')}</h2>
    <p>{e(H['be_' + lang])}</p>
    <ol class="principles">{pr}</ol>
    <div class="btns">{btn(lang, '/theory/botanical-expressionism/', 'Читать о концепции', 'Read about the concept')}{btn(lang, '/theory/', 'Все тексты по теории', 'All texts on theory', 'btn ghost')}</div>
  </div>
  <div class="quote-card"><blockquote>{e(L(lang, 'Картина — не собрание цветов. Это система взаимодействующих цветовых энергий.', 'The painting is not a collection of flowers. It is a system of interacting colour energies.'))}</blockquote><cite>{L(lang, 'Нона Дронова. «Теория изобразительных контрастов»', 'Nona Dronova, The Theory of Pictorial Contrasts')}</cite></div>
</section>
<section class="wrap">
  <p class="eyebrow">{L(lang, 'Коллекции', 'Collections')}</p>
  <h2>{L(lang, 'Живопись', 'Painting')}</h2>
  <p class="narrow">{e(H['coll_' + lang])}</p>
  <div class="cards">{ccards}</div>
  {btn(lang, '/collections/', 'Все коллекции', 'All collections')}
</section>
<section class="band">
  <div class="wrap">
    <p class="eyebrow">{L(lang, 'Материал и пространство', 'Material and Space')}</p>
    <p class="big narrow">{e(H['mat_' + lang])}</p>
    <div class="cards two">{mat}</div>
  </div>
</section>
<section class="wrap split">
  <div><p class="eyebrow">{L(lang, 'Образование', 'Education')}</p><p>{e(H['edu_' + lang])}</p>{btn(lang, '/education/', 'Педагогическая лаборатория', 'Teaching laboratory', 'btn ghost')}</div>
  <div class="closing"><p class="big">{e(H['close_' + lang])}</p><div class="btns">{btn(lang, '/collections/', 'Смотреть коллекции', 'View the collections')}{btn(lang, '/archive/', 'Научный каталог', 'Scholarly catalogue', 'btn ghost')}</div></div>
</section>'''
    desc = L(lang, "Живопись, сад, текстиль и серебро Ноны Дроновой: коллекции, теория ботанического экспрессионизма, сад «Папоротники и мох» и научный каталог произведений.",
             "Paintings, garden, textiles and silver by Nona Dronova: collections, the theory of botanical expressionism, the Ferns and Moss garden and a scholarly catalogue of works.")
    page(lang, "/", "home", P.SITE[lang], desc, body, og=og_image(HERO_ID), images=[HERO_ID])

def coll_card(c, lang, path=None):
    o = cover(c["slug"]); n = len(coll_works(c["slug"]))
    if c["slug"] == "liberi": o = next((w for w in coll_works("liberi") if "ring" in (w.get("desc_alt_en") or "").lower()), o)
    th = img(o, lang, sizes="(max-width:640px) 45vw, 300px") if o else ""
    return (f'<a class="ccard" href="{url(lang, path or "/collections/" + c["slug"] + "/")}" style="--accent:{c["accent"]}">'
            f'<span class="thumb">{th}</span><span class="cbody"><b>{e(L(lang, c["ru"], c["en"]))}</b>'
            f'<span>{e(L(lang, c["lead_ru"], c["lead_en"]))}</span><i>{n} {L(lang, plural_ru(n), "works" if n != 1 else "work")}</i></span></a>')

def plural_ru(n):
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11: return "произведение"
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14: return "произведения"
    return "произведений"

def build_collections(lang):
    groups = [("painting", "Живопись", "Painting"), ("material", "Материал и пространство", "Material and Space")]
    body = f'<section class="wrap intro"><h1>{L(lang, "Художественные коллекции", "Art Collections")}</h1><p class="lead">' + e(L(lang,
        "Собрание организовано по художественным сериям, периодам и видам творчества. Каждый раздел включает произведения, сведения о материалах и датировках, авторские комментарии и исследовательские наблюдения, если они доступны. Такая структура позволяет рассматривать работы и как самостоятельные художественные высказывания, и как части развивающейся творческой практики.",
        "The collection is organised by series, periods and media. Each section includes the works, information on materials and dates, the artist's comments and research observations where available. This structure makes it possible to see the works both as independent artistic statements and as parts of a developing creative practice.")) + '</p></section>'
    for g, ru, en in groups:
        cs = [c for c in COLLECTIONS if c["group"] == g]
        body += f'<section class="wrap"><h2>{L(lang, ru, en)}</h2><div class="cards">' + "".join(coll_card(c, lang, c.get("page")) for c in cs) + '</div></section>'
    page(lang, "/collections/", "collections", L(lang, "Коллекции", "Collections"),
         L(lang, "Шестнадцать коллекций Ноны Дроновой: ранние работы, весна, гортензии, пионы, розы, лилии, листья, летний сад, интерьерные панно, текстиль и серебро LIBERI.",
           "Sixteen collections by Nona Dronova: early works, spring, hydrangeas, peonies, roses, lilies, leaves, the summer garden, interior panels, textiles and LIBERI silver."),
         body, crumbs=[home_crumb(lang), (L(lang, "Коллекции", "Collections"), "/collections/")])
    for c in COLLECTIONS:
        if c.get("page"): continue
        build_collection(c, lang)

def pub_li(pid, t, lang):
    return (f'<li class="pub"><a href="{PUB_.ZENODO}{pid}" rel="noopener" target="_blank" lang="en">{e(t)}</a>'
            f'<span class="pub-src">Zenodo · {pid} ↗</span></li>')

def pubs_for(slug):
    return [(pid, t) for pid, t, g, cs in PUB_.PUBS if slug in cs]

def zenodo_section(lang):
    out = f'<section class="wrap" id="zenodo"><p class="eyebrow">Zenodo</p><h2>{L(lang, "Публикации на Zenodo", "Publications on Zenodo")}</h2><p class="narrow">' + \
          L(lang, "Статьи, эссе и интервью о творчестве Ноны Дроновой в открытом научном репозитории Zenodo. Названия приведены в оригинале; ссылки открывают запись на Zenodo.",
              "Articles, essays and interviews on the work of Nona Dronova in the open research repository Zenodo. Links open the record on Zenodo.") + "</p>"
    for g, ru, en in PUB_.GROUPS:
        items = "".join(pub_li(pid, t, lang) for pid, t, gg, cs in PUB_.PUBS if gg == g)
        out += f'<h3>{e(L(lang, ru, en))}</h3><ul class="pubs">{items}</ul>'
    out += f'<p><a class="btn ghost" href="https://zenodo.org/search?q=%22Nona%20Dronova%22" rel="noopener" target="_blank">{L(lang, "Все записи на Zenodo", "All records on Zenodo")} ↗</a></p></section>'
    return out

def related_essays(slug):
    out = []
    for es in ESSAYS:
        for b in es["blocks"]:
            if b[0] == "works":
                cs = b[1]["collection"]; cs = cs if isinstance(cs, list) else [cs]
                if slug in cs: out.append(es); break
    return out

INTERIOR_IDS = ["NDX-0022"] + [f"NDI-{n:04d}" for n in range(1, 15)]
def interiors_section(lang, h=True):
    cells = "".join(f'<div class="dcell">{photo(BY_ID[i], lang, large=False)}</div>' for i in INTERIOR_IDS)
    head_ = (f'<h2>{L(lang, "В интерьере дома художника", "In the Artist\'s Home")}</h2><p class="narrow">'
             + L(lang, "Панно Ноны Дроновой в интерьерах её собственного дома. Фотографии подлинные (подтверждено автором).",
                 "Nona Dronova's panels in the interiors of her own home. The photographs are genuine (confirmed by the artist).") + "</p>") if h else ""
    return head_ + f'<div class="diary">{cells}</div>'

def build_collection(c, lang):
    ws = coll_works(c["slug"]); path = f"/collections/{c['slug']}/"
    name = L(lang, c["ru"], c["en"])
    q = c.get("quote_" + lang)
    rel = related_essays(c["slug"])
    relh = ""
    if rel:
        relh = f'<aside class="wrap related"><h2>{L(lang, "Теория к этой коллекции", "Theory for this collection")}</h2><ul class="essay-list">' + "".join(
            f'<li><a href="{url(lang, "/theory/" + x["slug"] + "/")}"><b>{x["n"]}</b> {e(L(lang, x["ru"], x["en"]))}</a></li>' for x in rel) + '</ul></aside>'
    cp = pubs_for(c["slug"])
    if cp:
        relh += (f'<aside class="wrap related"><h2>{L(lang, "Публикации о коллекции", "Publications on this collection")}</h2><ul class="pubs">'
                 + "".join(pub_li(pid, t, lang) for pid, t in cp) + f'</ul><p class="small"><a href="{url(lang, "/research/")}#zenodo">{L(lang, "Все публикации", "All publications")}</a></p></aside>')
    rooms = [r for r in ROOMS if any(r[1] in (o.get("rooms") or []) for o in ws)]
    roomh = ""
    if rooms:
        roomh = '<p class="small">' + L(lang, "Залы сада: ", "Garden rooms: ") + ", ".join(
            f'<a href="{url(lang, "/garden-as-art/rooms/" + r[1] + "/")}">{e(L(lang, r[2], r[3]))}</a>' for r in rooms) + "</p>"
    dated = sum(1 for o in ws if o.get("year")); titled = sum(1 for o in ws if has_title(o))
    body = f'''<section class="wrap intro coll-head">
  <p class="eyebrow">{L(lang, "Коллекция", "Collection")}</p>
  <h1>{e(name if c['slug'] in ('roses', 'lilies', 'leaves', 'summer-garden', 'italian-garden', 'floral-energy', 'contrasts', 'interior-panels', 'studio') else L(lang, c['ru'] + ' — живописная коллекция', c['en'] + ' — A Painting Collection'))}</h1>
  <p class="lead">{e(L(lang, c['lead_ru'], c['lead_en']))}</p>
  {paras(c['text_' + lang])}
  {f'<blockquote class="pull">{e(q)}<cite>{L(lang, "Нона Дронова", "Nona Dronova")}</cite></blockquote>' if q else ''}
  {roomh}
  <p class="small facts">{len(ws)} {L(lang, plural_ru(len(ws)), "works")} · {L(lang, "с названием", "titled")}: {titled} · {L(lang, "с датой", "dated")}: {dated} · {L(lang, "Источник", "Source")}: <a href="{GH}{c['src']}" rel="noopener">{c['src']}</a></p>
</section>
<section class="wrap">{grid(ws, lang, cls="stack" if c["slug"] == "interior-panels" else "")}</section>
{('<section class="band" id="home"><div class="wrap">' + interiors_section(lang) + '</div></section>') if c["slug"] == "interior-panels" else ""}
{relh}'''
    ld = [{"@type": "CollectionPage", "name": name, "url": absu(url(lang, path)), "inLanguage": lang, "isPartOf": {"@id": SITE_URL + "/#site"},
           "about": {"@id": SITE_URL + "/#nona"}, "mainEntity": {"@type": "ItemList", "numberOfItems": len(ws), "itemListElement": [
               {"@type": "ListItem", "position": i + 1, "url": absu(url(lang, f"/archive/{o['id'].lower()}/"))} for i, o in enumerate(ws[:50])]}}]
    co = cover(c["slug"])
    page(lang, path, "collections", L(lang, c["ru"] + " — коллекция Ноны Дроновой", c["en"] + " — a collection by Nona Dronova"),
         L(lang, f"{c['ru']}: {c['lead_ru']} {len(ws)} {plural_ru(len(ws))} Ноны Дроновой в виртуальном музее.", f"{c['en']}: {c['lead_en']} {len(ws)} works by Nona Dronova in the virtual museum."),
         body, crumbs=[home_crumb(lang), (L(lang, "Коллекции", "Collections"), "/collections/"), (name, path)],
         og=og_image(co["id"]) if co else None, ld=ld, accent=c["accent"], images=[o["id"] for o in ws] + (INTERIOR_IDS if c["slug"] == "interior-panels" else []))

def build_garden(lang):
    G = P.GARDEN; path = "/garden-as-art/"
    gphotos = [o for o in CAT if o["kind"] == "garden"]
    extra = [BY_ID[i] for i in ("NDX-0006", "NDX-0007", "NDX-0008", "NDX-0010", "NDX-0011", "NDX-0004", "NDX-0005", "NDX-0040", "NDX-0034", "NDX-0036", "NDX-0032", "NDX-0033")]
    path_html = ""
    for sk, sru, sen, dru, den in SEASONS:
        rs = [r for r in ROOMS if r[4] == sk]
        cards = ""
        for num, slug, rru, ren, _ in rs:
            rw = room_works(slug)
            if not rw: continue
            o = next((w for w in rw if has_title(w)), rw[0])
            cards += (f'<a class="room" href="{url(lang, "/garden-as-art/rooms/" + slug + "/")}"><span class="thumb">{img(o, lang, sizes="(max-width:640px) 45vw, 260px")}</span>'
                      f'<span class="rn">{L(lang, "Зал", "Room")} {num}</span><b>{e(L(lang, rru, ren))}</b><i>{len(rw)} {L(lang, plural_ru(len(rw)), "works")}</i></a>')
        path_html += f'<div class="season-row" id="{sk}"><h3>{e(L(lang, sru, sen))}<span>{e(L(lang, dru, den))}</span></h3><div class="rooms">{cards}</div></div>'
    diary = "".join(f'<div class="dcell">{photo(o, lang, large=False)}</div>' for o in gphotos[:8] + extra[:4])
    g2p = []
    pairs = [("NDG-0003", "hostas"), ("NDX-0005", "lilies"), ("NDX-0036", "peonies"), ("NDX-0032", "hydrangeas")]
    for pid, room in pairs:
        rw = room_works(room); o = next((w for w in rw if has_title(w)), rw[0] if rw else None)
        if o: g2p.append(f'<div class="pair">{photo(BY_ID[pid], lang, large=False)}{card(o, lang)}</div>')
    body = f'''<section class="garden-hero">
  <figure>{img(BY_ID["NDG-0001"], lang, sizes="100vw", large=True, eager=True)}</figure>
  <div class="wrap intro"><p class="eyebrow">Garden as Art</p><h1>{e(G['h1_' + lang])}</h1><p class="lead">{e(G['lead_' + lang])}</p><p>{e(G['text_' + lang])}</p></div>
</section>
<section class="wrap split">
  <div><h2>{e(G['fm_h_' + lang])}</h2>{paras(G['fm_' + lang])}<blockquote class="pull">{e(G['fm_quote_' + lang])}</blockquote></div>
  <div class="stack-photos">{photo(BY_ID["NDX-0010"], lang)}{photo(BY_ID["NDX-0006"], lang)}</div>
</section>
<section class="band"><div class="wrap split rev creator">
  <div><p class="eyebrow">{L(lang, 'Создатель сада', 'Creator of the garden')}</p><h2>{e(G['creator_h_' + lang])}</h2><p>{e(G['creator_' + lang])}</p>
  <p class="small">{badge('confirmed', lang)} {L(lang, 'Членство в Союзе художников России с 2002 года подтверждено.', 'Membership of the Union of Artists of Russia since 2002 confirmed.')} · <a href="{GH}garden-as-art" rel="noopener">{L(lang, 'Источник', 'Source')}</a></p>
  <p>{btn(lang, '/liberi/#sergey', 'Ювелирные работы Сергея Дронова', 'Jewellery by Sergey Dronov', 'btn ghost')}</p></div>
  <figure class="portrait">{img(BY_ID[SERGEY_ID], lang, sizes="(max-width:900px) 70vw, 360px", large=True)}<figcaption>{L(lang, 'Сергей Дронов', 'Sergey Dronov')}</figcaption></figure>
</div></section>
<section class="wrap" id="path"><p class="eyebrow">{L(lang, 'Двадцать залов', 'Twenty rooms')}</p><h2>{e(G['path_h_' + lang])}</h2><p class="narrow">{e(G['path_' + lang])}</p>{path_html}</section>
<section class="band"><div class="wrap"><h2>{e(G['g2p_h_' + lang])}</h2><p class="narrow">{e(G['g2p_' + lang])}</p><div class="pairs">{''.join(g2p)}</div>
<p>{btn(lang, '/theory/garden-to-painting/', 'Текст «От сада к картине»', 'Read “From Garden to Painting”', 'btn ghost')}</p></div></section>
<section class="wrap"><h2>{e(G['diary_h_' + lang])}</h2><p class="narrow">{e(G['diary_' + lang])}</p><div class="diary">{diary}</div>
<p class="small">{L(lang, 'Фотографии сада — из архива «The Garden as Art». Авторство фотографий будет уточнено.', 'Garden photographs from The Garden as Art archive. Photo credits to be confirmed.')}</p></section>'''
    ld = [SERGEY, {"@type": "CreativeWork", "name": L(lang, "Сад «Папоротники и мох»", "The Ferns and Moss Garden"), "creator": {"@id": SITE_URL + "/#sergey"},
                   "image": [absu(f"/img/l/{o['id'].lower()}.webp") for o in gphotos[:6]], "url": absu(url(lang, path))}]
    page(lang, path, "garden", L(lang, "Сад как искусство", "The Garden as Art"),
         L(lang, "Сад «Папоротники и мох» Сергея Дронова и двадцать залов живописи Ноны Дроновой: сезонная тропа от весны к тени леса, дневник сада, путь от сада к картине.",
           "Sergey Dronov's Ferns and Moss garden and the twenty painting rooms of Nona Dronova: a seasonal path from spring to woodland shade, a garden diary and the way from garden to painting."),
         body, crumbs=[home_crumb(lang), (L(lang, "Сад как искусство", "The Garden as Art"), path)], og=og_image("NDG-0001"), ld=ld,
         accent="#177245", images=[o["id"] for o in gphotos])
    for i, (num, slug, rru, ren, sk) in enumerate(ROOMS):
        rw = room_works(slug)
        if not rw: continue
        prv, nxt = ROOMS[i - 1] if i > 0 else None, ROOMS[i + 1] if i + 1 < len(ROOMS) else None
        nav = '<nav class="pager wrap">' + (f'<a href="{url(lang, "/garden-as-art/rooms/" + prv[1] + "/")}">← {e(L(lang, prv[2], prv[3]))}</a>' if prv else "<span></span>") + \
              (f'<a href="{url(lang, "/garden-as-art/rooms/" + nxt[1] + "/")}">{e(L(lang, nxt[2], nxt[3]))} →</a>' if nxt else "<span></span>") + "</nav>"
        sname = next(L(lang, s[1], s[2]) for s in SEASONS if s[0] == sk)
        coll = COLL[rw[0]["collection"]] if rw[0]["collection"] in COLL else None
        body = (f'<section class="wrap intro"><p class="eyebrow">{L(lang, "Сад как искусство", "The Garden as Art")} · {e(sname)}</p>'
                f'<h1>{L(lang, "Зал", "Room")} {num}. {e(L(lang, rru, ren))}</h1>'
                f'<p>{L(lang, "Работы этого зала пронумерованы по каталогу «Сад как искусство» Ноны Дроновой", "The works in this room are numbered according to Nona Dronova\'s Garden as Art catalogue")} (№ {num}-1 … {num}-{len(rw)}).'
                + (f' {L(lang, "Коллекция музея", "Museum collection")}: <a href="{url(lang, "/collections/" + coll["slug"] + "/")}">{e(L(lang, coll["ru"], coll["en"]))}</a>.' if coll and not coll.get("page") else "")
                + f'</p></section><section class="wrap">{grid(sorted(rw, key=lambda o: [int(x) for x in (o["legacy_garden_no"] or ["0-0"])[0].split("-")]), lang)}</section>{nav}')
        rp = f"/garden-as-art/rooms/{slug}/"
        page(lang, rp, "garden", L(lang, f"Зал {num}. {rru} — Сад как искусство", f"Room {num}. {ren} — The Garden as Art"),
             L(lang, f"Зал {num} «{rru}» каталога «Сад как искусство»: {len(rw)} {plural_ru(len(rw))} Ноны Дроновой.", f"Room {num}, {ren}, of The Garden as Art catalogue: {len(rw)} works by Nona Dronova."),
             body, crumbs=[home_crumb(lang), (L(lang, "Сад как искусство", "The Garden as Art"), path), (L(lang, rru, ren), rp)],
             og=og_image(rw[0]["id"]), accent="#177245", images=[o["id"] for o in rw])

# ------------------------------------------------------------------ theory
def works_block(spec, lang):
    cs = spec["collection"]; kind = spec.get("kind", "artwork")
    ws = coll_works(cs, kind)
    if kind == "artwork": ws = [o for o in ws if has_title(o)] + [o for o in ws if not has_title(o)]
    ws = ws[:spec.get("n", 4)]
    if kind != "artwork":
        cells = "".join(f'<figure class="work">{img(o, lang)}<figcaption><span class="m">{L(lang, "Фрагмент", "Detail")}</span>'
                        + (f'<span class="note" lang="en">{e(o["note_en"])}</span>' if spec.get("notes") and o.get("note_en") and lang == "en" else "")
                        + '</figcaption></figure>' for o in ws)
        return f'<div class="masonry inline">{cells}</div>'
    out = '<div class="masonry inline">'
    for o in ws:
        c = card(o, lang)
        if spec.get("notes") and o.get("note_en") and lang == "en":
            c = c.replace("</figcaption>", f'<span class="note">{e(o["note_en"])}</span></figcaption>')
        out += c
    return out + "</div>"

def render_blocks(blocks, lang):
    out = ""
    for b in blocks:
        t = b[0]
        if t == "p": out += f"<p>{e(L(lang, b[1], b[2]))}</p>"
        elif t == "lead": out += f'<p class="lead">{e(L(lang, b[1], b[2]))}</p>'
        elif t == "h2": out += f"<h2>{e(L(lang, b[1], b[2]))}</h2>"
        elif t == "quote": out += f'<blockquote class="pull">{e(L(lang, b[1], b[2]))}</blockquote>'
        elif t == "def": out += f'<p class="definition">{e(L(lang, b[1], b[2]))}</p>'
        elif t == "note": out += f'<aside class="note-box">{e(L(lang, b[1], b[2]))}</aside>'
        elif t == "principles":
            out += '<ol class="principle-cards">' + "".join(
                f'<li><b>{L(lang, "Принцип", "Principle")} {i+1}</b><h3>{e(L(lang, a, bb))}</h3><p>{e(L(lang, c, d))}</p></li>' for i, (a, bb, c, d) in enumerate(b[1])) + "</ol>"
        elif t == "questions":
            qs = b[1] if lang == "ru" else b[2]
            out += f'<aside class="questions"><h3>{L(lang, "Вопросы для наблюдения", "Questions for looking")}</h3><ol>' + "".join(f"<li>{e(q)}</li>" for q in qs) + "</ol></aside>"
        elif t == "works": out += works_block(b[1], lang)
        elif t == "interiors": out += interiors_section(lang, h=False)
    return out

def build_theory(lang):
    path = "/theory/"
    items = "".join(f'''<li><a class="essay-card" href="{url(lang, "/theory/" + x["slug"] + "/")}"><span class="n">{x["n"]}</span>
      <span><b>{e(L(lang, x["ru"], x["en"]))}</b><i>{e(L(lang, x["sub_ru"], x["sub_en"]))}</i></span>{badge(x["status"], lang)}</a></li>''' for x in ESSAYS)
    items += f'''<li><a class="essay-card" href="{url(lang, "/theory/context/")}"><span class="n">10</span><span><b>{e(L(lang, CONTEXT["ru"], CONTEXT["en"]))}</b><i>{e(L(lang, CONTEXT["sub_ru"], CONTEXT["sub_en"]))}</i></span>{badge("museum", lang)}</a></li>'''
    body = f'''<section class="wrap intro"><p class="eyebrow">Theory of Contemporary Painting</p><h1>{L(lang, "Теория современной живописи", "The Theory of Contemporary Painting")}</h1>
<p class="lead">{e(L(lang, THEORY_INTRO_RU, THEORY_INTRO_EN))}</p></section>
<section class="wrap"><ol class="essays">{items}</ol>
<div class="btns">{btn(lang, "/theory/glossary/", "Глоссарий терминов", "Glossary of terms", "btn ghost")}{btn(lang, "/research/#zenodo", "Публикации на Zenodo", "Publications on Zenodo", "btn ghost")}</div></section>'''
    page(lang, path, "theory", L(lang, "Теория современной живописи", "The Theory of Contemporary Painting"),
         L(lang, "Тексты Ноны Дроновой о цвете, контрасте, мазке и пастозной живописи — курс теории современной ботанической живописи с произведениями и вопросами для наблюдения.",
           "Nona Dronova's texts on colour, contrast, brushwork and impasto — a course in the theory of contemporary botanical painting with works and questions for looking."),
         body, crumbs=[home_crumb(lang), (L(lang, "Теория", "Theory"), path)], og=og_image(cover("contrasts")["id"]))
    seq = ESSAYS + [CONTEXT]
    for i, x in enumerate(seq):
        p = f"/theory/{x['slug']}/"
        prv, nxt = (seq[i - 1] if i else None), (seq[i + 1] if i + 1 < len(seq) else None)
        src = "".join(f'<a href="{GH}{s}" rel="noopener">{s}</a> ' for s in x.get("src", []))
        trans = (L(lang, "Перевод музея с английского; оригинал — в английской версии страницы.", "Original English text by the artist.") if x["status"] == "author" else "")
        sub = x.get("sub_ru") if lang == "ru" else x.get("sub_en")
        pager = '<nav class="pager">' + (f'<a href="{url(lang, "/theory/" + prv["slug"] + "/")}">← {e(L(lang, prv["ru"], prv["en"]))}</a>' if prv else "<span></span>") + \
                (f'<a href="{url(lang, "/theory/" + nxt["slug"] + "/")}">{e(L(lang, nxt["ru"], nxt["en"]))} →</a>' if nxt else f'<a href="{url(lang, "/theory/glossary/")}">{L(lang, "Глоссарий", "Glossary")} →</a>') + "</nav>"
        body = f'''<article class="wrap essay"><header><p class="eyebrow">{L(lang, "Теория", "Theory")} · {x.get("n", "10")}</p><h1>{e(L(lang, x["ru"], x["en"]))}</h1>
<p class="sub">{e(sub)}</p><p class="meta">{badge(x["status"], lang)} {L(lang, "Автор текста: Нона Дронова", "Text by Nona Dronova") if x["status"] == "author" else L(lang, "Текст подготовлен музеем", "Text prepared by the museum")}{(" · " + trans) if trans else ""}{(" · " + L(lang, "Источник", "Source") + ": " + src) if src else ""}</p></header>
{render_blocks(x["blocks"], lang)}
<footer class="cite"><h3>{L(lang, "Как цитировать", "How to cite")}</h3><p>{cite(lang, x, p)}</p></footer>
{pager}</article>'''
        first_desc = next((L(lang, b[1], b[2]) for b in x["blocks"] if b[0] in ("lead", "p")), "")
        ld = [{"@type": "Article", "headline": L(lang, x["ru"], x["en"]), "inLanguage": lang, "url": absu(url(lang, p)),
               "author": {"@id": SITE_URL + "/#nona"} if x["status"] == "author" else {"@type": "Organization", "name": P.SITE[lang]},
               "about": "Botanical painting, colour theory", "isPartOf": {"@id": SITE_URL + "/#site"}, "dateModified": TODAY}]
        page(lang, p, "theory", L(lang, x["ru"], x["en"]) + L(lang, " — теория живописи", " — painting theory"), first_desc[:158].rsplit(" ", 1)[0] + "…",
             body, crumbs=[home_crumb(lang), (L(lang, "Теория", "Theory"), "/theory/"), (L(lang, x["ru"], x["en"]), p)], ld=ld)
    # glossary
    p = "/theory/glossary/"
    dl = "".join(f'<div id="g{i}"><dt>{e(L(lang, a, b))}</dt><dd>{e(L(lang, c, d))}</dd></div>' for i, (a, b, c, d) in enumerate(GLOSSARY))
    body = f'<section class="wrap essay"><h1>{L(lang, "Глоссарий", "Glossary")}</h1><p class="lead">{L(lang, "Авторские понятия Ноны Дроновой и общие термины живописи, встречающиеся в текстах музея.", "Nona Dronova\'s own concepts and general painting terms used in the museum\'s texts.")}</p><dl class="glossary">{dl}</dl></section>'
    ld = [{"@type": "DefinedTermSet", "name": L(lang, "Глоссарий", "Glossary"), "hasDefinedTerm": [{"@type": "DefinedTerm", "name": L(lang, a, b), "description": L(lang, c, d)} for a, b, c, d in GLOSSARY]}]
    page(lang, p, "theory", L(lang, "Глоссарий терминов теории живописи", "Glossary of Painting Theory Terms"),
         L(lang, "Доминирующий контраст, хроматическая непрерывность, импасто, Impasto Bloom, постсимволизм, ботанический экспрессионизм — словарь терминов.", "Dominant contrast, chromatic continuity, impasto, Impasto Bloom, Post-Symbolism, botanical expressionism — a glossary of terms."),
         body, crumbs=[home_crumb(lang), (L(lang, "Теория", "Theory"), "/theory/"), (L(lang, "Глоссарий", "Glossary"), p)], ld=ld)

def cite(lang, x, p):
    if lang == "ru":
        a = "Дронова Н." if x["status"] == "author" else "Виртуальный музей Ноны Дроновой."
        return e(f"{a} {x['ru']} // Виртуальный музей Ноны Дроновой [Электронный ресурс]. 2026. URL: {absu(p)} (дата обращения: ДД.ММ.ГГГГ).")
    a = "Dronova, N." if x["status"] == "author" else "Nona Dronova Virtual Art Museum."
    return e(f"{a} (2026) ‘{x['en']}’, Nona Dronova Virtual Art Museum. Available at: {absu('/en' + p)} (Accessed: DD Month YYYY).")

# ------------------------------------------------------------------ feature pages
def build_textiles(lang):
    T = P.TEXTILES; path = "/artistic-interior-textiles/"; ws = coll_works("textiles")
    body = f'''<section class="wrap intro"><p class="eyebrow">{e(T["sub_" + lang])}</p><h1>{e(T["h1_" + lang])}</h1><p class="lead">{e(T["text_" + lang])}</p></section>
<section class="band"><div class="wrap split"><div><h2>{e(T["loom_h_" + lang])}</h2>{paras(T["loom_" + lang])}<blockquote class="pull">{e(T["loom_quote_" + lang])}</blockquote>
<p class="small">{badge("author", lang)} {L(lang, "По тексту Ноны Дроновой", "Based on Nona Dronova's text")} · <a href="{GH}textile-art-and-tapestries" rel="noopener">textile-art-and-tapestries</a></p></div>
<div>{photo(ws[0], lang) if ws else ""}</div></div></section>
<section class="wrap"><h2>{L(lang, "Произведения", "Works")}</h2>{grid(ws, lang)}</section>
<section class="wrap narrow"><h2>{e(T["gi_h_" + lang])}</h2><p>{e(T["gi_" + lang])}</p>{btn(lang, "/theory/painting-and-space/", "Живопись и пространство", "Painting and Space", "btn ghost")}</section>'''
    page(lang, path, "textiles", T["h1_" + lang], L(lang, "Гобелены ручного ткачества, текстильные и кожаные коллажи, арт-объекты Ноны Дроновой: ткань, цвет и фактура как язык искусства.",
         "Hand-woven tapestries, textile and leather collages and art objects by Nona Dronova: fabric, colour and texture as a language of art."),
         body, crumbs=[home_crumb(lang), (L(lang, "Текстиль", "Textiles"), path)], og=og_image(ws[0]["id"]), accent=COLL["textiles"]["accent"],
         images=[o["id"] for o in ws], bodycls="textile")

def build_liberi(lang):
    T = P.LIBERI; path = "/liberi/"; ws = coll_works("liberi")
    hearts = [o for o in ws if "heart" in (" ".join(o["sources"]) + (o.get("desc_alt_en") or "")).lower()]
    rings = [o for o in ws if o not in hearts]
    other = coll_works("jewellery"); serg = coll_works("sergey-jewellery")
    body = f'''<section class="wrap intro"><p class="eyebrow">{e(T["sub_" + lang])}</p><h1>{e(T["h1_" + lang])}</h1><p class="lead">{e(T["text_" + lang])}</p></section>
<section class="wrap" id="rings"><h2>{e(T["rings_h_" + lang])}</h2><p class="narrow">{e(T["rings_" + lang])}</p>{grid(rings, lang, cls="dense")}</section>
<section class="band" id="hearts"><div class="wrap"><h2>{e(T["hearts_h_" + lang])}</h2><p class="narrow">{e(T["hearts_" + lang])}</p>{grid(hearts, lang)}</div></section>
<section class="wrap" id="jewellery"><h2>{e(T["other_h_" + lang])}</h2><p class="narrow">{e(T["other_" + lang])}</p>{grid(other, lang, cls="dense")}
</section>
<section class="band" id="sergey"><div class="wrap"><p class="eyebrow">{L(lang, "Создатель сада", "Creator of the garden")}</p><h2>{e(T["sergey_h_" + lang])}</h2><p class="narrow">{e(T["sergey_" + lang])}</p>
{grid(serg, lang, cls="dense")}<div class="pairs">{photo(BY_ID["NDX-0002"], lang, large=False)}{photo(BY_ID["NDX-0003"], lang, large=False)}</div>
<p class="small">{badge("confirmed", lang)} {L(lang, "Авторство Сергея Дронова подтверждено.", "Sergey Dronov's authorship confirmed.")} · {L(lang, "Источник", "Source")}: <a href="{GH}art-of-jewellery" rel="noopener">art-of-jewellery</a> · <a href="{url(lang, "/garden-as-art/")}">{L(lang, "Сергей Дронов в разделе «Сад как искусство»", "Sergey Dronov in The Garden as Art")}</a></p></div></section>'''
    page(lang, path, "liberi", L(lang, "LIBERI — авторские серебряные украшения", "LIBERI — Author's Silver Jewellery"),
         L(lang, "LIBERI — авторская коллекция серебряных колец и подвесок «Сердца» Ноны Дроновой: каждое украшение ручной работы в единственном экземпляре.",
           "LIBERI — Nona Dronova's collection of silver rings and Hearts pendants: each piece handcrafted as a single edition."),
         body, crumbs=[home_crumb(lang), ("LIBERI", path)], og=og_image(rings[0]["id"]), accent=COLL["liberi"]["accent"],
         images=[o["id"] for o in ws + serg], bodycls="liberi")

import content_about as AB
def md(t):
    t = e(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)

def about_strip(spec, lang):
    if spec == "garden":
        ids = ["NDG-0001", "NDX-0010", "NDX-0039", "NDG-0003"]
        return '<div class="bio-strip">' + "".join(f'<a href="{url(lang, "/garden-as-art/")}" class="thumb">{img(BY_ID[i], lang, sizes="200px")}</a>' for i in ids) + "</div>"
    if spec == "interiors":
        ids = ["NDX-0022", "NDI-0005", "NDI-0008", "NDI-0012"]
        return '<div class="bio-strip">' + "".join(f'<a href="{url(lang, "/collections/interior-panels/")}#home" class="thumb">{img(BY_ID[i], lang, sizes="200px")}</a>' for i in ids) + "</div>"
    cells = ""
    n_each = 4 // len(spec) if len(spec) < 4 else 1
    for c in spec:
        ws = [o for o in coll_works(c) if o.get("title_en")] or coll_works(c)
        for o in ws[:max(1, n_each)]:
            href = url(lang, COLL[c].get("page") or "/collections/" + c + "/")
            cells += f'<a href="{href}" class="thumb" title="{e(L(lang, COLL[c]["ru"], COLL[c]["en"]))}">{img(o, lang, sizes="200px")}</a>'
    return f'<div class="bio-strip">{cells}</div>'

def build_about(lang):
    A = P.ABOUT; path = "/about/"
    toc = "".join(f'<li><a href="#{sid}">{e(L(lang, hru, hen))}</a></li>' for sid, hru, hen, *_ in AB.SECTIONS)
    secs = ""
    for sid, hru, hen, pru, pen, ill in AB.SECTIONS:
        body_ = "".join(f"<p>{md(x)}</p>" for x in (pru if lang == "ru" else pen))
        if sid == "botanical-expressionism":
            body_ += '<ol class="principle-cards">' + "".join(
                f'<li><b>{L(lang, "Принцип", "Principle")} {i+1}</b><h3>{e(L(lang, a, b))}</h3><p>{e(L(lang, c, d))}</p></li>' for i, (a, b, c, d) in enumerate(AB.PRINCIPLES)) + "</ol>"
            body_ += f'<aside class="note-box">{e(L(lang, AB.BE_NOTE_RU, AB.BE_NOTE_EN))}</aside>'
            body_ += f'<p>{btn(lang, "/theory/botanical-expressionism/", "Подробнее о концепции", "More on the concept", "btn ghost")}</p>'
        if sid == "research":
            body_ += '<ul class="facts-list">' + "".join(f"<li><em>{e(L(lang, a, b))}</em></li>" for a, b in AB.THEMES) + "</ul>"
            body_ += f'<aside class="note-box">{e(L(lang, AB.THEMES_NOTE_RU, AB.THEMES_NOTE_EN))}</aside>'
            body_ += f'<div class="btns">{btn(lang, "/theory/", "Теория современной живописи", "The Theory of Contemporary Painting", "btn ghost")}{btn(lang, "/research/#zenodo", "Публикации на Zenodo", "Publications on Zenodo", "btn ghost")}</div>'
        if sid == "education":
            body_ += f'<p>{btn(lang, "/education/", "Педагогическая лаборатория", "Teaching laboratory", "btn ghost")}</p>'
        if ill: body_ += about_strip(ill, lang)
        secs += f'<section class="bio-sec" id="{sid}"><h2>{e(L(lang, hru, hen))}</h2>{body_}</section>'
    facts = "".join(f'<li>{e(L(lang, ru, en))} {badge(st, lang)}</li>' for ru, en, st in A["facts"])
    arch = "".join(f'<li><a href="{u}" rel="noopener">{e(n)}</a></li>' for n, u in P.ARCHIVES)
    foot = AB.FOOT_RU if lang == "ru" else AB.FOOT_EN
    body = f'''<section class="wrap split about">
  <div><p class="eyebrow">{e(L(lang, AB.KICKER_RU, AB.KICKER_EN))}</p><h1>{e(L(lang, AB.TITLE_RU, AB.TITLE_EN))}</h1>
  <p class="lead">{e(L(lang, AB.SUB_RU, AB.SUB_EN))}</p>
  <p class="small">{badge("museum", lang)} {L(lang, "Кураторский и исследовательский профиль. Перевод на русский — музея; оригинал — английская версия.", "Curatorial and research profile.")}</p></div>
  <figure class="portrait">{img(BY_ID[PORTRAIT_ID], lang, sizes="(max-width:900px) 80vw, 420px", large=True, eager=True)}<figcaption>{L(lang, "Нона Дронова", "Nona Dronova")}</figcaption></figure>
</section>
<div class="wrap bio">
  <nav class="bio-toc" aria-label="{L(lang, "Содержание", "Contents")}"><p class="eyebrow">{L(lang, "Содержание", "Contents")}</p><ol>{toc}</ol></nav>
  <article class="bio-text">{secs}
    <blockquote class="pull closing-quote">{e(L(lang, AB.CLOSING_RU, AB.CLOSING_EN))}</blockquote>
    <footer class="cite"><p><em>{e(foot[0])}</em></p><p><em>{e(foot[1])}</em></p></footer>
  </article>
</div>
<section class="band"><div class="wrap grid2">
  <div><h2>{L(lang, "Подтверждённые сведения", "Verified information")}</h2><ul class="facts-list">{facts}</ul></div>
  <div><h2>{L(lang, "Мастерская", "The studio")}</h2>{photo(BY_ID[STUDIO_ID], lang)}</div>
</div></section>
<section class="wrap"><h2>{L(lang, "Цифровые архивы автора", "The artist\'s digital archives")}</h2><p>{L(lang, "Первоисточники, из которых собран музей:", "The primary sources from which the museum is assembled:")}</p><ul class="cols">{arch}</ul></section>'''
    ld = [dict(PERSON, image=absu(f"/img/l/{PORTRAIT_ID.lower()}.webp"), description=L(lang, AB.SUB_RU, AB.SUB_EN),
               knowsAbout=["Botanical painting", "Botanical Expressionism", "Textile art", "Silver jewellery", "Art education"]),
          {"@type": "ProfilePage", "url": absu(url(lang, path)), "mainEntity": {"@id": SITE_URL + "/#nona"}, "inLanguage": lang, "dateModified": TODAY}]
    page(lang, path, "about", L(lang, "Нона Дронова — художник, исследователь ботанического экспрессионизма", "Nona Dronova — Artist and Researcher of Botanical Expressionism"),
         L(lang, "Искусствоведческая биография Ноны Дроновой: ботанический экспрессионизм, цветовой язык, сад как искусство, интерьерный текстиль, LIBERI и художественное образование.",
           "An art-historical biography of Nona Dronova: botanical expressionism, colour language, the garden as art, interior textiles, LIBERI and art education."),
         body, crumbs=[home_crumb(lang), (L(lang, "Об авторе", "About"), path)], og=og_image(PORTRAIT_ID), ld=ld)

def build_simple(lang):
    E = P.EDUCATION; path = "/education/"
    mods = "".join(f'<li><span class="badge b-project">{L(lang, "Проектируется", "In development")}</span><h3>{e(L(lang, ru, en))}</h3><a href="{url(lang, "/theory/" + s + "/")}">{L(lang, "Опорный текст", "Core text")}: {e(L(lang, ESS[s]["ru"], ESS[s]["en"]))}</a></li>' for ru, en, s in E["modules"])
    body = f'''<section class="wrap intro"><h1>{e(E["h1_" + lang])}</h1><p class="lead">{e(E["text_" + lang])}</p></section>
<section class="wrap"><h2>{L(lang, "Предлагаемые модули", "Proposed modules")}</h2><p class="small">{L(lang, "Модули проектируются; сведения о преподававшихся курсах будут добавлены после подтверждения.", "The modules are in development; information on courses actually taught will be added once confirmed.")}</p><ol class="modules">{mods}</ol></section>
<section class="band"><div class="wrap narrow"><h2>{L(lang, "Музей на занятии", "The museum in class")}</h2><p>{e(E["howto_" + lang])}</p><div class="btns">{btn(lang, "/theory/", "Теория", "Theory")}{btn(lang, "/theory/glossary/", "Глоссарий", "Glossary", "btn ghost")}</div></div></section>'''
    page(lang, path, "education", L(lang, "Педагогика и творческая лаборатория", "Education and Creative Laboratory"),
         L(lang, "Педагогическая лаборатория музея: наблюдение и рисунок, цвет как язык, сад как композиция, от живописи к текстилю — модули на основе текстов Ноны Дроновой.",
           "The museum's teaching laboratory: observation and drawing, colour as language, the garden as composition, from painting to textile — modules based on Nona Dronova's texts."),
         body, crumbs=[home_crumb(lang), (L(lang, "Педагогика", "Education"), path)])
    R = P.RESEARCH; path = "/research/"
    lv = "".join(f'<li><b>{e(L(lang, a, b))}</b> — {e(L(lang, c, d))}</li>' for a, b, c, d in R["levels"])
    tp = "".join(f'<li>{e(L(lang, a, b))} <span class="badge b-project">{L(lang, "Планируется", "Planned")}</span></li>' for a, b in R["topics"])
    es = "".join(f'<li><a href="{url(lang, "/theory/" + x["slug"] + "/")}">{e(L(lang, x["ru"], x["en"]))}</a> {badge(x["status"], lang)}</li>' for x in ESSAYS + [CONTEXT])
    body = f'''<section class="wrap intro"><h1>{e(R["h1_" + lang])}</h1><p class="lead">{e(R["text_" + lang])}</p></section>
{zenodo_section(lang)}
<section class="wrap"><h2>{L(lang, "Тексты в музее", "Texts in the museum")}</h2><ul class="facts-list narrow">{es}</ul></section>
<section class="band"><div class="wrap narrow"><h2>{L(lang, "Открытые данные", "Open data")}</h2><p>{L(lang, "Каталог музея доступен в машиночитаемом виде:", "The museum's catalogue is available in machine-readable form:")} <a href="/data/catalog.json">catalog.json</a>. {L(lang, "Поля записей опираются на элементы Dublin Core (title, creator, date, format, source, rights); полная совместимость с CIDOC CRM не заявляется.", "Record fields draw on Dublin Core elements (title, creator, date, format, source, rights); full CIDOC CRM compliance is not claimed.")}</p></div></section>'''
    rld = [{"@type": "ItemList", "name": "Zenodo", "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": {"@type": "ScholarlyArticle", "name": t,
            "url": PUB_.ZENODO + pid, "publisher": {"@type": "Organization", "name": "Zenodo"}, "about": {"@id": SITE_URL + "/#nona"}}} for i, (pid, t, g, cs) in enumerate(PUB_.PUBS)]}]
    page(lang, path, "research", L(lang, "Исследования и публикации", "Research and Publications"),
         L(lang, "Публикации Ноны Дроновой на Zenodo: ботанический экспрессионизм, постсимволизм, цвет, композиция, серии «Пионы», «Розы», «Лилейники», интервью.",
           "Nona Dronova's publications on Zenodo: botanical expressionism, Post-Symbolism, colour, composition, the Peonies, Roses and Daylilies series, interviews."),
         body, crumbs=[home_crumb(lang), (L(lang, "Исследования", "Research"), path)], ld=rld)
    X = P.EXHIBITIONS; path = "/exhibitions/"
    its = ""
    for ru, en, cs in X["items"]:
        ws = [w for c in cs for w in coll_works(c) if has_title(w)][:4] or [w for c in cs for w in coll_works(c)][:4]
        its += f'<article class="exh"><span class="badge b-project">{L(lang, "Проект", "In preparation")}</span><h2>{e(L(lang, ru, en))}</h2><p class="small">{L(lang, "Коллекции", "Collections")}: ' + ", ".join(
            f'<a href="{url(lang, COLL[c].get("page") or "/collections/" + c + "/")}">{e(L(lang, COLL[c]["ru"], COLL[c]["en"]))}</a>' for c in cs) + \
            f'. {L(lang, "Отбор произведений будет согласован с автором.", "The selection of works will be agreed with the artist.")}</p><div class="strip">' + "".join(f'<span class="thumb">{img(w, lang, sizes="160px")}</span>' for w in ws) + '</div></article>'
    body = f'<section class="wrap intro"><h1>{e(X["h1_" + lang])}</h1><p class="lead">{e(X["text_" + lang])}</p></section><section class="wrap exhs">{its}</section>'
    page(lang, path, "exhibitions", L(lang, "Виртуальные выставки", "Virtual Exhibitions"),
         L(lang, "Проекты виртуальных выставок: цветение как художественное событие, сад и художник, от живописи к текстилю, LIBERI.",
           "Planned virtual exhibitions: flowering as an artistic event, the garden and the artist, from painting to textile, LIBERI."),
         body, crumbs=[home_crumb(lang), (L(lang, "Выставки", "Exhibitions"), path)])
    C = P.CONTACT; path = "/contact/"
    body = f'''<section class="wrap intro"><h1>{e(C["h1_" + lang])}</h1><p class="lead">{e(C["text_" + lang])}</p>
<aside class="note-box">{L(lang, "Подтверждённые контактные данные будут опубликованы после согласования с автором.", "Verified contact details will be published once agreed with the artist.")}</aside>
<h2>{L(lang, "Сайты автора", "The artist's websites")}</h2><ul class="facts-list"><li><a href="https://nona-dronova-art-studio.vercel.app/" rel="noopener">Nona Dronova Art Studio</a></li><li><a href="https://github.com/Nona1960" rel="noopener">GitHub — Nona1960</a></li></ul></section>'''
    page(lang, path, "contact", L(lang, "Контакты и сотрудничество", "Contact and Collaboration"),
         L(lang, "Сотрудничество с виртуальным музеем Ноны Дроновой: выставки, публикации, образовательные инициативы и цифровое наследие.",
           "Collaboration with the Nona Dronova Virtual Museum: exhibitions, publications, educational initiatives and digital heritage."),
         body, crumbs=[home_crumb(lang), (L(lang, "Контакты", "Contact"), path)])

# ------------------------------------------------------------------ archive + object pages
def build_archive(lang):
    A = P.ARCHIVE; path = "/archive/"
    opts = "".join(f'<option value="{c["slug"]}">{e(L(lang, c["ru"], c["en"]))}</option>' for c in COLLECTIONS)
    cells = ""
    for o in ART:
        key = " ".join(filter(None, [o["id"], o.get("title_en"), " ".join(o.get("title_variants_en") or []), " ".join(o.get("legacy_garden_no") or []),
                                     o.get("desc_alt_en"), coll_name(o["collection"], "ru"), coll_name(o["collection"], "en"), str(o.get("year") or "")])).lower()
        c = card(o, lang, show_coll=True)
        cells += c.replace('<a class="work"', f'<a class="work" data-c="{o["collection"]}" data-y="{o.get("year") or ""}" data-t="{1 if has_title(o) else 0}" data-k="{e(key)}"', 1)
    body = f'''<section class="wrap intro"><h1>{e(A["h1_" + lang])}</h1><p class="lead">{e(A["text_" + lang])}</p></section>
<section class="wrap"><form class="filters" role="search" onsubmit="return false">
  <label><span>{L(lang, "Поиск", "Search")}</span><input type="search" id="q" placeholder="{L(lang, "Название, номер, ID…", "Title, number, ID…")}" autocomplete="off"></label>
  <label><span>{L(lang, "Коллекция", "Collection")}</span><select id="c"><option value="">{L(lang, "Все", "All")}</option>{opts}</select></label>
  <label class="chk"><input type="checkbox" id="d"> {L(lang, "Только с датой", "Dated only")}</label>
  <label class="chk"><input type="checkbox" id="t"> {L(lang, "Только с названием", "Titled only")}</label>
  <output id="n" aria-live="polite">{len(ART)}</output>
</form>
<div class="masonry" id="grid">{cells}</div>
<p class="small">{L(lang, "Данные каталога", "Catalogue data")}: <a href="/data/catalog.json">catalog.json</a></p></section>
<script>
(()=>{{const q=document.getElementById('q'),c=document.getElementById('c'),d=document.getElementById('d'),t=document.getElementById('t'),n=document.getElementById('n');
const items=[...document.querySelectorAll('#grid .work')];
const p=new URLSearchParams(location.search);if(p.get('q'))q.value=p.get('q');if(p.get('c'))c.value=p.get('c');
function f(){{const s=q.value.trim().toLowerCase();let k=0;for(const a of items){{const ok=(!s||a.dataset.k.includes(s))&&(!c.value||a.dataset.c===c.value)&&(!d.checked||a.dataset.y)&&(!t.checked||a.dataset.t==='1');a.hidden=!ok;if(ok)k++}}n.textContent=k;}}
[q,c,d,t].forEach(x=>x.addEventListener('input',f));f();}})();
</script>'''
    page(lang, path, "archive", L(lang, "Научный каталог произведений", "Scholarly Catalogue of Works"),
         L(lang, f"Цифровой каталог: {len(NONA_ART)} произведений Ноны Дроновой и ювелирные работы Сергея Дронова с постоянными номерами, источниками и статусом проверки. Поиск по названию и коллекции.",
           f"Digital catalogue: {len(NONA_ART)} works by Nona Dronova and jewellery by Sergey Dronov, with permanent IDs, sources and verification status. Search by title and collection."),
         body, crumbs=[home_crumb(lang), (L(lang, "Каталог", "Catalogue"), path)])
    objs = ART + [o for o in CAT if o["kind"] == "garden"]
    for o in objs: build_object(o, lang)

def build_object(o, lang):
    oid = o["id"]; path = f"/archive/{oid.lower()}/"
    cslug = o["collection"]; c = COLL.get(cslug)
    same = [x for x in CAT if x["kind"] == o["kind"] and x["collection"] == cslug]
    i = same.index(o); prv = same[i - 1] if i > 0 else None; nxt = same[i + 1] if i + 1 < len(same) else None
    na = L(lang, "не установлено", "not established")
    t = tech(o, lang)
    rows = [
        (L(lang, "Автор", "Artist"), author_name(o, lang) if o["kind"] == "artwork" else L(lang, "Сад: Сергей Дронов", "Garden: Sergey Dronov")),
        (L(lang, "Коллекция", "Collection"), f'<a href="{url(lang, (c.get("page") if c and c.get("page") else "/collections/" + cslug + "/") if c else "/garden-as-art/")}">{e(coll_name(cslug, lang))}</a>'),
        (L(lang, "Инвентарный номер", "Inventory number"), oid),
    ]
    if o.get("legacy_garden_no"):
        rooms = o.get("rooms") or []
        rl = ", ".join(f'<a href="{url(lang, "/garden-as-art/rooms/" + r + "/")}">{e(L(lang, ROOM[r][2], ROOM[r][3]))}</a>' for r in rooms if r in ROOM)
        rows.append((L(lang, "№ в каталоге «Сад как искусство»", "No. in The Garden as Art catalogue"), ", ".join(o["legacy_garden_no"]) + (f" · {rl}" if rl else "")))
    if o["kind"] == "artwork":
        rows += [(L(lang, "Дата", "Date"), str(o["year"]) if o.get("year") else f'<span class="muted">{na}</span>'),
                 (L(lang, "Материалы и техника", "Materials and technique"), e(t) if t else f'<span class="muted">{L(lang, "не установлены", "not established")}</span>'),
                 (L(lang, "Размеры", "Dimensions"), f'<span class="muted">{L(lang, "не установлены", "not established")}</span>'),
                 (L(lang, "Авторский комментарий", "Artist's comment"), f'<span class="muted">—</span>'),
                 (L(lang, "История экспонирования", "Exhibition history"), f'<span class="muted">{L(lang, "нет документированных сведений", "no documented records")}</span>')]
    if o.get("title_variants_en"):
        rows.append((L(lang, "Варианты названия в источниках", "Title variants in sources"), e("; ".join(o["title_variants_en"]))))
    rows += [(L(lang, "Источник изображения", "Image source"), "<br>".join(f'<a href="{s}" rel="noopener">{e(s.split("/")[4] + " / " + s.split("/")[-1])}</a>' for s in o["sources"])),
             (L(lang, "Права", "Rights"), (f"© {author_name(o, lang)}. " + L(lang, "Все права защищены", "All rights reserved")) if o["kind"] == "artwork" else L(lang, "уточняются", "to be confirmed")),
             (L(lang, "Статус проверки", "Verification status"), L(lang, "Данные перенесены из цифровых источников автора; ожидают проверки", "Data transferred from the artist's digital sources; pending verification")),
             (L(lang, "Обновлено", "Updated"), TODAY)]
    dl = "".join(f"<div><dt>{a}</dt><dd>{b}</dd></div>" for a, b in rows)
    desc_en = o.get("desc_alt_en") if lang == "en" and o["kind"] == "artwork" else None
    note = o.get("note_en") if lang == "en" else None
    ttl = title(o, lang) if o["kind"] == "artwork" else (P.GARDEN_CAPTIONS.get(oid, (None, None))[0 if lang == "ru" else 1] or title(o, lang))
    pager = '<nav class="pager">' + (f'<a href="{url(lang, "/archive/" + prv["id"].lower() + "/")}">← {prv["id"]}</a>' if prv else "<span></span>") + \
            (f'<a href="{url(lang, "/archive/" + nxt["id"].lower() + "/")}">{nxt["id"]} →</a>' if nxt else "<span></span>") + "</nav>"
    neigh = [x for x in same if x is not o][:6]
    body = f'''<article class="object wrap">
  <figure class="object-art">{img(o, lang, sizes="(max-width: 900px) 100vw, 60vw", large=True, eager=True)}
  <figcaption><a href="/img/l/{oid.lower()}.webp">{L(lang, "Открыть изображение крупно", "Open large image")}</a></figcaption></figure>
  <div class="object-info">
    <p class="eyebrow">{e(coll_name(cslug, lang))}</p>
    <h1 class="{'' if has_title(o) or o['kind'] != 'artwork' else 'muted'}">{e(ttl)}</h1>
    <p class="meta">{e(meta_line(o, lang))}</p>
    {f'<p class="desc"><span class="badge b-works">From source</span> {e(desc_en)}</p>' if desc_en else ''}
    {f'<p class="desc"><span class="badge b-author">Artist\'s text</span> {e(note)}</p>' if note else ''}
    <dl class="record">{dl}</dl>
    {pager}
  </div>
</article>
{f'<section class="wrap"><h2>{L(lang, "Из той же коллекции", "From the same collection")}</h2>{grid(neigh, lang)}</section>' if neigh else ''}'''
    ld_obj = {"@type": "VisualArtwork" if o["kind"] == "artwork" else "Photograph", "name": ttl, "identifier": oid, "url": absu(url(lang, path)),
              "image": absu(f"/img/l/{oid.lower()}.webp"), "isPartOf": {"@type": "Collection", "name": coll_name(cslug, lang)}, "inLanguage": lang}
    if o["kind"] == "artwork":
        who = SITE_URL + ("/#sergey" if o["author"] == "sergey" else "/#nona")
        ld_obj.update({"creator": {"@id": who}, "copyrightHolder": {"@id": who}})
        if o.get("year"): ld_obj["dateCreated"] = str(o["year"])
        if o.get("technique_en"):
            ld_obj["artMedium"] = o["technique_en"]
            ld_obj["artform"] = "Painting" if "canvas" in o["technique_en"].lower() or "watercolour" in o["technique_en"].lower() else ("Jewellery" if "silver" in o["technique_en"].lower() else "Textile art")
        if o.get("title_variants_en"): ld_obj["alternateName"] = o["title_variants_en"]
    d = (f"{ttl}. " if has_title(o) else "") + f"{author_name(o, lang)}, {coll_name(cslug, lang)}"
    if t: d += f". {t}"
    if o.get("year"): d += f", {o['year']}"
    d += L(lang, f". Запись {oid} научного каталога виртуального музея.", f". Record {oid} in the virtual museum's scholarly catalogue.")
    tshort = ttl if len(ttl) <= 48 else ttl[:46].rsplit(" ", 1)[0] + "…"
    page(lang, path, "archive", f"{tshort} ({oid}) — " + author_name(o, lang),
         d, body, crumbs=[home_crumb(lang), (L(lang, "Каталог", "Catalogue"), "/archive/"), (oid, path)], og=og_image(oid), ld=[ld_obj],
         accent=(c["accent"] if c else "#177245"), images=[oid])

def build_404():
    for lang in ("ru", "en"):
        body = f'<section class="wrap intro"><h1>{L(lang, "Страница не найдена", "Page not found")}</h1><p>{L(lang, "Возможно, адрес изменился.", "The address may have changed.")}</p><div class="btns">{btn(lang, "/", "На главную", "Home")}{btn(lang, "/archive/", "Каталог", "Catalogue", "btn ghost")}</div></section>'
        h = head(lang, "/404/", L(lang, "Страница не найдена", "Page not found"), "404").replace('content="index, follow, max-image-preview:large"', 'content="noindex"')
        html_ = h + header(lang, "/", "") + body + footer(lang)
        if lang == "ru": open(os.path.join(PUB, "404.html"), "w", encoding="utf-8").write(html_)

# ------------------------------------------------------------------ sitemap, robots, manifest
def build_meta():
    xs = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for path, lm, ims in PAGES:
        for lang in ("ru", "en"):
            u = absu(url(lang, path))
            alts = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{absu(url(l, path))}"/>' for l in ("ru", "en")) + \
                   f'<xhtml:link rel="alternate" hreflang="x-default" href="{absu(url("ru", path))}"/>'
            imgs = "".join(f'<image:image><image:loc>{absu("/img/l/" + i.lower() + ".webp")}</image:loc></image:image>' for i in ims[:50])
            pr = "1.0" if path == "/" else ("0.9" if path.count("/") <= 2 else ("0.5" if path.startswith("/archive/") else "0.7"))
            xs.append(f"<url><loc>{u}</loc><lastmod>{lm}</lastmod><priority>{pr}</priority>{alts}{imgs}</url>")
    xs.append("</urlset>")
    open(os.path.join(PUB, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(xs))
    open(os.path.join(PUB, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n\nUser-agent: Yandex\nAllow: /\nClean-param: q&c\n\nSitemap: {SITE_URL}/sitemap.xml\n")
    json.dump({"name": P.SITE["ru"], "short_name": "Музей Дроновой", "lang": "ru", "start_url": "/", "display": "standalone",
               "background_color": "#FBF8F1", "theme_color": "#177245",
               "icons": [{"src": "/assets/sun-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/assets/sun-512.png", "sizes": "512x512", "type": "image/png"}]},
              open(os.path.join(PUB, "site.webmanifest"), "w", encoding="utf-8"), ensure_ascii=False)

def main():
    global CSS_V
    css = open(os.path.join(HERE, "site.css"), encoding="utf-8").read()
    os.makedirs(os.path.join(PUB, "assets"), exist_ok=True)
    open(os.path.join(PUB, "assets", "site.css"), "w", encoding="utf-8").write(css)
    CSS_V = hashlib.md5(css.encode()).hexdigest()[:8]
    for d in ("en", "collections", "garden-as-art", "theory", "archive", "about", "education", "research", "exhibitions", "contact", "liberi", "artistic-interior-textiles"):
        shutil.rmtree(os.path.join(PUB, d), ignore_errors=True)
    for lang in ("ru", "en"):
        build_home(lang); build_collections(lang); build_garden(lang); build_theory(lang)
        build_textiles(lang); build_liberi(lang); build_about(lang); build_simple(lang); build_archive(lang)
    build_404(); build_meta()
    data = json.load(open(os.path.join(PUB, "data", "catalog.json"), encoding="utf-8"))
    data["objects"] = CAT; data["updated"] = TODAY
    data["note"] = "Сгенерировано из репозиториев Nona1960. Неустановленные поля = null. kind=excluded — запись скрыта (портреты, баннеры, фото не-произведений)."
    json.dump(data, open(os.path.join(PUB, "data", "catalog.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(len(f) for _, _, f in os.walk(PUB))
    print("pages:", len(PAGES) * 2, "files:", n)

if __name__ == "__main__":
    main()
