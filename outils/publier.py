#!/usr/bin/env python3
"""Publication du site Paradise Patrimoine (GitHub Pages).

    python3 outils/publier.py [source] [dossier du dépôt]

source : le .zip téléchargé depuis l'espace privé du site (bouton « Publier »), ou un index.html.
         Sans argument : l'index.html du dépôt (régénère tout à partir de l'état en ligne).

Pourquoi ce script : Google ne lit que les 2 premiers Mo d'une page. Le fichier produit par
« Publier » contient toutes les photos (environ 8 Mo) : publié tel quel, il est illisible pour Google.
Le script :
  1. sort les photos du fichier (photos/…) : index.html redescend sous 1 Mo, le site reste identique ;
  2. crée une page légère par annonce publique (annonces/<id>/index.html) ;
  3. écrit sitemap.xml et robots.txt, et ajoute à l'accueil les balises pour Google
     (canonical, données structurées, liste des annonces lisible sans JavaScript).

index.html est toujours reconstruit à partir du modèle intégré (PP_TPL) : le script peut être relancé
autant de fois que nécessaire, sur un .zip neuf comme sur le site déjà publié.
"""
import base64, datetime, html, io, json, pathlib, re, shutil, sys, zipfile

SITE = "https://paradisepatrimoine.github.io"   # à changer si le site passe sur un nom de domaine
BRAND = "Paradise Patrimoine"
HOME_TITLE = "Paradise Patrimoine · Immobilier Côte d’Azur & Corse : neuf, ancien, défiscalisation"
MAX_HTML = 1_500_000      # Googlebot s'arrête à 2 Mo : on garde de la marge
SAFE = re.compile(r"^(photos|files)/[A-Za-z0-9][A-Za-z0-9._-]*$")
ID_OK = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CATS = {"defiscalisation": "Défiscalisation & immobilier neuf", "ancien": "Immobilier ancien"}
REGIONS = {"cote-azur": "Côte d’Azur", "corse": "Corse", "montagne": "Montagne"}
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def fail(msg):
    sys.exit("ERREUR : " + msg)


def block(text, bid):
    op = '<script id="%s">' % bid
    if op not in text:
        fail("bloc %s introuvable" % bid)
    i = text.index(op) + len(op)   # première occurrence, comme le bouton « Publier » du site
    return i, text.index("</script>", i)


def get_block(text, bid):
    a, b = block(text, bid)
    return text[a:b]


def set_block(text, bid, body):
    a, b = block(text, bid)
    return text[:a] + body + text[b:]


def safe_json(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def js_value(body, name):
    body = body.strip()
    prefix = "window.%s = " % name
    if not body:
        return None
    if not (body.startswith(prefix) and body.endswith(";")):
        fail("bloc %s inattendu" % name)
    return json.loads(body[len(prefix):-1])


def read_source(path):
    """Renvoie (texte d'index.html, {chemin: octets} des autres fichiers du .zip)."""
    p = pathlib.Path(path)
    if zipfile.is_zipfile(p):
        extra = {}
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            idx = [n for n in names if n == "index.html" or n.endswith("/index.html")]
            if not idx:
                fail("pas d'index.html dans " + p.name)
            idx.sort(key=len)
            root = idx[0][:-len("index.html")]
            text = z.read(idx[0]).decode("utf-8")
            for n in names:
                rel = n[len(root):] if n.startswith(root) else n
                if n != idx[0] and re.fullmatch(r"videos/[A-Za-z0-9][A-Za-z0-9._-]*", rel):
                    extra[rel] = z.read(n)
        return text, extra
    return p.read_text(encoding="utf-8"), {}


# ---------- mise en forme ----------
def fr_int(n):
    if isinstance(n, float) and not n.is_integer():
        return ("%s" % n).replace(".", ",")
    return "{:,}".format(int(n)).replace(",", " ")


def price_text(l):
    if l.get("priceLabel"):
        return str(l["priceLabel"])
    p = l.get("price")
    return fr_int(p) + " € HAI" if isinstance(p, (int, float)) and not isinstance(p, bool) else "Prix sur demande"


def facts(l):
    out = []
    if l.get("surfaceLabel"):
        out.append(str(l["surfaceLabel"]))
    elif l.get("surface"):
        out.append(fr_int(l["surface"]) + " m²")
    if l.get("roomsLabel"):
        out.append(str(l["roomsLabel"]))
    elif l.get("bedrooms"):
        n = l["bedrooms"]
        out.append("%s chambre%s" % (fr_int(n), "" if n == 1 else "s"))
    if l.get("bathrooms"):
        n = l["bathrooms"]
        out.append("%s salle%s de bain / d’eau" % (fr_int(n), "" if n == 1 else "s"))
    return out


def shorten(text, n):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= n:
        return text
    cut = text[:n - 1]
    return cut[:cut.rfind(" ")].rstrip(" ,;:–-") + "…"


def groups_of(l):
    out = []
    for g in l.get("groups") or []:
        if isinstance(g, list) and len(g) == 2 and isinstance(g[1], list):
            out.append((str(g[0] or ""), [str(x) for x in g[1] if x]))
    return out


def photos_of(l):
    ps = l.get("photos") if isinstance(l.get("photos"), list) else ([l["image"]] if l.get("image") else [])
    return [re.sub(r"^\.?/", "", p) for p in ps if isinstance(p, str) and p]


def img_size(repo, p):
    """Attributs width/height réels (évite que la page saute au chargement) ; vide si inconnus."""
    try:
        from PIL import Image
        with Image.open(repo / p) as im:
            return ' width="%d" height="%d"' % im.size
    except Exception:
        return ""


def photo_url(p):
    return p if re.match(r"^https?:", p, re.I) else SITE + "/" + p


def ld(obj):
    return '<script type="application/ld+json">' + safe_json(obj) + "</script>"


# ---------- page d'une annonce ----------
CSS = """
:root{--bg:#07111E;--panel:#0D2040;--gold:#C5A059;--txt:#e2e8f0;--mut:#94a3b8}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--txt);font:16px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--gold)}img,video{display:block;width:100%;height:auto;border-radius:16px;border:1px solid rgba(197,160,89,.3);background:#0A192F}
.wrap{max-width:860px;margin:0 auto;padding:0 20px}
header{background:#0A192F;border-bottom:1px solid rgba(197,160,89,.2)}
header .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:76px;padding-top:12px;padding-bottom:12px}
.brand{text-decoration:none;display:flex;flex-direction:column;gap:4px}
.brand b{font:700 22px/1 ui-serif,Georgia,Cambria,"Times New Roman",Times,serif;color:#fff;letter-spacing:.03em}.brand b i{font-style:normal;color:var(--gold)}
.brand small{font-size:10px;line-height:1.3;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);font-weight:600}
.btn{display:inline-block;padding:13px 22px;border-radius:10px;background:linear-gradient(90deg,#C5A059,#9E7D3B);color:#07111E;font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase;text-decoration:none;text-align:center}
.btn.ghost{background:none;border:1px solid var(--gold);color:var(--gold)}
header .btn{padding:10px 16px;white-space:nowrap}
main{padding:28px 0 56px}
.crumb{font-size:12px;color:var(--mut);margin:0 0 18px}.crumb a{color:var(--mut)}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.tag{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;padding:5px 11px;border-radius:999px;background:#fbbf24;color:#07111E}
.tag.cat{background:none;border:1px solid rgba(197,160,89,.5);color:var(--gold)}.tag.st{background:#fff}
h1{font:700 30px/1.25 ui-serif,Georgia,Cambria,"Times New Roman",Times,serif;color:#fff;margin:0 0 10px}
.loc{color:#cbd5e1;font-size:14px;margin:0 0 22px}
.facts{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0;padding:0;list-style:none}
.facts li{padding:9px 14px;border-radius:10px;background:var(--panel);border:1px solid rgba(197,160,89,.25);font-size:14px}
.price{font:700 28px/1.2 ui-serif,Georgia,Cambria,"Times New Roman",Times,serif;color:var(--gold);margin:22px 0 4px}
.note{font-size:12px;color:var(--mut);margin:0 0 22px}
h2{font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin:30px 0 10px}
ul.pts{margin:0;padding-left:20px}ul.pts li{margin:6px 0}ul.pts li::marker{color:var(--gold)}
.cta{display:flex;flex-wrap:wrap;gap:12px;margin:34px 0}.cta .btn{flex:1 1 240px}
.more{margin-top:44px;padding-top:26px;border-top:1px solid #1e293b}.more ul{list-style:none;padding:0;margin:0}
.more li{padding:10px 0;border-bottom:1px solid #152033;font-size:14px}.more a{color:#fff;text-decoration:none}.more a:hover{color:var(--gold)}.more span{color:var(--mut)}
.gal{display:grid;gap:14px;margin-top:14px}
footer{border-top:1px solid #0f172a;padding:26px 0 40px;font-size:12px;color:var(--mut);text-align:center}footer a{color:var(--mut);margin:0 8px}
@media(min-width:640px){h1{font-size:38px}.gal{grid-template-columns:1fr 1fr}}
""".strip()


def listing_page(l, others, updated, repo):
    lid = l["id"]
    url = "%s/annonces/%s/" % (SITE, lid)
    title = str(l.get("title") or "Annonce")
    loc = str(l.get("location") or l.get("city") or "")
    city = str(l.get("city") or "")
    region = REGIONS.get(l.get("region"), "")
    cat = CATS.get(l.get("category"), "")
    price = price_text(l)
    fx = facts(l)
    intro = str(l.get("intro") or "")
    photos = photos_of(l)
    status = l.get("status") if l.get("status") in ("vendu", "sous-offre") else ""
    desc = shorten(" · ".join(x for x in [intro or title, price] if x), 158)
    page_title = shorten(title, 70) + " | " + BRAND

    tags = []
    if status:
        tags.append('<span class="tag st">%s</span>' % ("Vendu" if status == "vendu" else "Sous offre"))
    if l.get("badge"):
        tags.append('<span class="tag">%s</span>' % E(l["badge"]))
    if cat:
        tags.append('<span class="tag cat">%s</span>' % E(cat))

    body = []
    crumb = ['<a href="/">Accueil</a>'] + [E(x) for x in (region, city) if x]
    body.append('<p class="crumb">%s</p>' % " › ".join(crumb))
    if tags:
        body.append('<p class="tags">%s</p>' % "".join(tags))
    body.append("<h1>%s</h1>" % E(title))
    if loc:
        body.append('<p class="loc">%s%s</p>' % (E(loc), " · " + E(region) if region and region not in loc else ""))
    if photos:
        body.append('<img src="%s" alt="%s"%s fetchpriority="high">' % (E("/" + photos[0] if not photos[0].startswith("http") else photos[0]), E(title), img_size(repo, photos[0])))
    if fx:
        body.append('<ul class="facts">%s</ul>' % "".join("<li>%s</li>" % E(x) for x in fx))
    body.append('<p class="price">%s</p>' % E(price))
    body.append('<p class="note">Honoraires d’agence inclus%s · <a href="/#honoraires">Barème d’honoraires</a></p>' % (" · " + E(l["dpe"]) if l.get("dpe") else ""))
    if intro:
        body.append("<p>%s</p>" % E(intro))
    for g_title, items in groups_of(l):
        if g_title:
            body.append("<h2>%s</h2>" % E(g_title))
        if items:
            body.append('<ul class="pts">%s</ul>' % "".join("<li>%s</li>" % E(x) for x in items))
    vf = l.get("videoFile")
    if isinstance(vf, str) and re.fullmatch(r"videos/[A-Za-z0-9][A-Za-z0-9._-]*", vf):
        body.append("<h2>Vidéo du bien</h2>")
        body.append('<video controls preload="none" playsinline%s><source src="/%s" type="video/mp4"></video>' % (' poster="/%s"' % E(photos[0]) if photos and not photos[0].startswith("http") else "", E(vf)))
    if len(photos) > 1:
        body.append('<div class="gal">%s</div>' % "".join('<img src="%s" alt="%s" loading="lazy"%s>' % (E("/" + p if not p.startswith("http") else p), E(title + " – photo " + str(i + 2)), img_size(repo, p)) for i, p in enumerate(photos[1:])))
    body.append('<p class="cta"><a class="btn" href="/#annonce-%s">Ce bien m’intéresse</a><a class="btn ghost" href="/">Voir toutes nos annonces</a></p>' % E(lid))
    if others:
        body.append('<section class="more"><h2>Autres biens à découvrir</h2><ul>%s</ul></section>' % "".join(
            '<li><a href="/annonces/%s/">%s</a><br><span>%s · %s</span></li>' % (E(o["id"]), E(o.get("title") or ""), E(o.get("location") or o.get("city") or ""), E(price_text(o))) for o in others))

    offer = {"@type": "Offer", "url": url, "priceCurrency": "EUR",
             "availability": "https://schema.org/" + ("SoldOut" if status == "vendu" else "InStock")}
    if isinstance(l.get("price"), (int, float)) and not isinstance(l.get("price"), bool):
        offer["price"] = l["price"]
    address = {"@type": "PostalAddress", "addressCountry": "FR"}
    if city:
        address["addressLocality"] = city
    if region:
        address["addressRegion"] = region
    place = {"@type": "Residence", "name": title, "address": address}
    if isinstance(l.get("surface"), (int, float)):
        place["floorSize"] = {"@type": "QuantitativeValue", "value": l["surface"], "unitCode": "MTK"}
    if isinstance(l.get("bedrooms"), (int, float)):
        place["numberOfBedrooms"] = l["bedrooms"]
    graph = [
        {"@type": "RealEstateListing", "@id": url, "url": url, "name": title, "description": intro or title, "inLanguage": "fr",
         "dateModified": updated, "image": [photo_url(p) for p in photos], "offers": offer, "about": place,
         "provider": {"@type": "RealEstateAgent", "@id": SITE + "/#agence", "name": BRAND, "url": SITE + "/"}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": title, "item": url}]},
    ]
    head = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        "<title>%s</title>" % E(page_title),
        '<meta name="description" content="%s">' % E(desc),
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        '<link rel="canonical" href="%s">' % E(url),
        '<meta name="theme-color" content="#07111E">',
        '<meta property="og:type" content="article">',
        '<meta property="og:site_name" content="%s">' % E(BRAND),
        '<meta property="og:locale" content="fr_FR">',
        '<meta property="og:title" content="%s">' % E(shorten(title, 90)),
        '<meta property="og:description" content="%s">' % E(desc),
        '<meta property="og:url" content="%s">' % E(url),
    ]
    if photos:
        head += ['<meta property="og:image" content="%s">' % E(photo_url(photos[0])), '<meta name="twitter:card" content="summary_large_image">']
    head += [ld({"@context": "https://schema.org", "@graph": graph}), "<style>%s</style>" % CSS]
    return ("<!DOCTYPE html>\n<html lang=\"fr\"><head>\n" + "\n".join(head) + "\n</head><body>\n"
            '<header><div class="wrap"><a class="brand" href="/"><b>Paradise<i>Patrimoine</i></b><small>Immobilier ancien et neuf · Côte d’Azur et Corse</small></a>'
            '<a class="btn" href="/#annonce-%s">Prendre RDV</a></div></header>\n' % E(lid) +
            '<main><div class="wrap">\n' + "\n".join(body) + "\n</div></main>\n"
            '<footer><div class="wrap">© %d %s · <a href="/#mentions-legales">Mentions légales</a><a href="/#confidentialite">Politique de confidentialité</a><a href="/#honoraires">Honoraires</a></div></footer>\n'
            "</body></html>\n" % (datetime.date.today().year, E(BRAND)))


def pick_others(l, pool, n=6):
    rest = [o for o in pool if o["id"] != l["id"]]
    rank = lambda o: (0 if o.get("city") and o.get("city") == l.get("city") else 1 if o.get("region") == l.get("region") else 2)
    return sorted(rest, key=rank)[:n]


# ---------- accueil ----------
def home_static(listings, description):
    items = "".join('<li style="margin:12px 0"><a style="color:#fff" href="/annonces/%s/">%s</a><br><span style="color:#94a3b8">%s · %s</span></li>' % (
        E(l["id"]), E(l.get("title") or ""), E(l.get("location") or l.get("city") or ""), E(price_text(l))) for l in listings)
    serif = "ui-serif,Georgia,Cambria,'Times New Roman',Times,serif"
    return ('<div style="color:#e2e8f0;font-family:ui-sans-serif,system-ui,-apple-system,\'Segoe UI\',Roboto,Arial,sans-serif;line-height:1.6">'
            '<div style="min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:24px">'
            '<p style="margin:0 0 14px;font-size:11px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:#C5A059">Immobilier &amp; conseil en gestion de patrimoine</p>'
            '<h1 style="margin:0;font:700 34px/1.2 %s;color:#fff">Paradise Patrimoine<br><span style="color:#C5A059">Immobilier Côte d’Azur &amp; Corse</span></h1>'
            '<p style="max-width:560px;margin:18px auto 0;font-size:14px;color:#94a3b8">%s</p></div>'
            '<div style="max-width:860px;margin:0 auto;padding:24px 20px 60px"><h2 style="font:700 24px/1.3 %s;color:#fff">Nos annonces immobilières</h2>'
            '<ul style="list-style:none;padding:0;margin:0;font-size:14px">%s</ul></div></div>') % (serif, E(description), serif, items)


def build_home(tpl, data, listings, inline_img, raw):
    m = re.search(r'<meta name="description" content="([^"]*)">', tpl)
    description = html.unescape(m.group(1)) if m else BRAND
    first_photo = next((photo_url(p) for l in listings for p in photos_of(l)), None)
    graph = [
        {"@type": "RealEstateAgent", "@id": SITE + "/#agence", "name": BRAND, "url": SITE + "/", "description": description,
         "areaServed": ["Côte d’Azur", "Corse"], **({"image": first_photo} if first_photo else {})},
        {"@type": "WebSite", "@id": SITE + "/#site", "name": BRAND, "url": SITE + "/", "inLanguage": "fr", "publisher": {"@id": SITE + "/#agence"}},
        {"@type": "ItemList", "name": "Annonces immobilières", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": "%s/annonces/%s/" % (SITE, l["id"]), "name": l.get("title") or ""} for i, l in enumerate(listings)]},
    ]
    head = ['<meta name="robots" content="index,follow,max-image-preview:large">',
            '<link rel="canonical" href="%s/">' % SITE,
            '<meta property="og:site_name" content="%s">' % E(BRAND),
            '<meta property="og:locale" content="fr_FR">']
    if first_photo:
        head += ['<meta property="og:image" content="%s">' % E(first_photo), '<meta name="twitter:card" content="summary_large_image">']
    head.append(ld({"@context": "https://schema.org", "@graph": graph}))
    out = tpl
    for old, new in (("<title>%s</title>" % BRAND, "<title>%s</title>" % E(HOME_TITLE)),
                     ("</head>", "\n".join(head) + "\n</head>"),
                     ('<div id="root"></div>', '<div id="root">%s</div>' % home_static(listings, description))):
        if out.count(old) != 1:
            fail("repère introuvable dans le modèle : " + old)
        out = out.replace(old, new)
    out = set_block(out, "pp-img", "window.PP_IMG = " + safe_json(inline_img) + ";")
    out = set_block(out, "pp-data", raw["pp-data"])
    out = set_block(out, "pp-tpl", raw["pp-tpl"])
    return out


# ---------- programme ----------
def main():
    repo = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parent.parent).resolve()
    source = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else repo / "index.html"
    if not source.exists():
        fail("source introuvable : %s" % source)
    text, extra = read_source(source)
    raw = {b: get_block(text, b) for b in ("pp-img", "pp-data", "pp-tpl")}
    tpl = js_value(raw["pp-tpl"], "PP_TPL")
    data = js_value(raw["pp-data"], "PP_DATA")
    img = js_value(raw["pp-img"], "PP_IMG") or {}
    if not isinstance(tpl, str) or not isinstance(data, dict):
        fail("ce fichier ne contient pas le modèle du site (PP_TPL) : utilise le .zip produit par le bouton « Publier »")
    for b in ("pp-img", "pp-data", "pp-tpl"):
        if get_block(tpl, b) != "":
            fail("modèle inattendu (bloc %s non vide)" % b)

    # 1. photos et fichiers intégrés -> vrais fichiers
    inline, written = {}, 0
    for key, val in img.items():
        if SAFE.match(key) and isinstance(val, str) and val.startswith("data:") and ";base64," in val:
            dest = repo / key
            content = base64.b64decode(val.split(";base64,", 1)[1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists() or dest.read_bytes() != content:
                dest.write_bytes(content)
                written += 1
        else:
            inline[key] = val
    for rel, content in extra.items():
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_bytes() != content:
            dest.write_bytes(content)

    all_listings = [l for l in data.get("listings") or [] if isinstance(l, dict)]
    used = set()
    for l in all_listings:
        used.update(photos_of(l))
        if isinstance(l.get("videoFile"), str):
            used.add(re.sub(r"^\.?/", "", l["videoFile"]))
    fees = (data.get("legal") or {}).get("feesPdf")
    if isinstance(fees, str):
        used.add(fees)
    missing = [p for p in sorted(used) if not re.match(r"^(https?:|data:|idb:)", p) and p not in inline and not (repo / p).is_file()]
    if missing:
        fail("fichiers référencés par les annonces mais absents : " + ", ".join(missing))
    removed = 0
    for folder in ("photos", "files"):
        d = repo / folder
        for f in (sorted(d.iterdir()) if d.is_dir() else []):
            if f.is_file() and (folder + "/" + f.name) not in used:
                f.unlink()
                removed += 1

    # 2. une page par annonce publique
    updated = str(data.get("updated") or "")[:10] or datetime.date.today().isoformat()
    public = [l for l in all_listings if not l.get("hidden") and l.get("category") != "offmarket" and ID_OK.match(str(l.get("id") or ""))]
    skipped = [str(l.get("id")) for l in all_listings if not l.get("hidden") and l.get("category") != "offmarket" and l not in public]
    adir = repo / "annonces"
    if adir.exists():
        shutil.rmtree(adir)
    for l in public:
        d = adir / l["id"]
        d.mkdir(parents=True)
        (d / "index.html").write_text(listing_page(l, pick_others(l, public), updated, repo), encoding="utf-8")

    # 3. accueil, plan du site, robots
    home = build_home(tpl, data, public, inline, raw)
    size = len(home.encode("utf-8"))
    (repo / "index.html").write_text(home, encoding="utf-8")
    urls = [(SITE + "/", "1.0")] + [("%s/annonces/%s/" % (SITE, l["id"]), "0.8") for l in public]
    (repo / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join("  <url><loc>%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>\n" % (E(u), updated, pr) for u, pr in urls) +
        "</urlset>\n", encoding="utf-8")
    (repo / "robots.txt").write_text("User-agent: *\nAllow: /\nDisallow: /outils/\nDisallow: /CLAUDE.md\n\nSitemap: %s/sitemap.xml\n" % SITE, encoding="utf-8")

    print("index.html : %d Ko%s" % (size // 1024, "" if size <= MAX_HTML else "  <-- TROP LOURD pour Google (limite 2 Mo)"))
    print("photos : %d écrites, %d supprimées, %d restées dans la page" % (written, removed, len(inline)))
    print("annonces : %d pages%s" % (len(public), (" (ignorées, identifiant inattendu : " + ", ".join(skipped) + ")") if skipped else ""))
    print("sitemap.xml : %d adresses" % len(urls))
    if size > MAX_HTML:
        sys.exit(1)


if __name__ == "__main__":
    main()
