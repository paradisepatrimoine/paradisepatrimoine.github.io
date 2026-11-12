#!/usr/bin/env python3
"""Relevé des statistiques de visite (onglet « Statistiques » de l'espace privé).

Le site compte les visites sans cookie (mesure.js) dans un compteur public par jour :
  AAAAMMJJ-v           nombre de visites
  AAAAMMJJ-s-<source>  visites par provenance (google, facebook, instagram, tiktok…)
  AAAAMMJJ-a-<id>      consultations de chaque annonce
Ces compteurs expirent au bout de 6 mois : ce script les recopie dans stats/historique.json,
que l'espace privé lit. Il tourne chaque nuit (.github/workflows/statistiques.yml) et peut être
relancé à la main sans risque :

    python3 outils/statistiques.py [nombre de jours à relire, 10 par défaut]
"""
import datetime, json, pathlib, re, sys, time, urllib.error, urllib.request
from zoneinfo import ZoneInfo

API = "https://abacus.jasoncameron.dev/get/paradisepatrimoine-gh/"
SOURCES = ["google", "facebook", "instagram", "tiktok", "youtube", "linkedin", "leboncoin", "moteurs", "direct", "autres"]
REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "stats" / "historique.json"
PAUSE = 0.4   # le compteur accepte 30 requêtes par tranche de 10 secondes


def get(key):
    for attempt in range(8):
        try:
            req = urllib.request.Request(API + key, headers={"User-Agent": "paradisepatrimoine-statistiques"})
            with urllib.request.urlopen(req, timeout=20) as r:
                value = int(json.load(r).get("value") or 0)
            time.sleep(PAUSE)
            return value
        except urllib.error.HTTPError as e:
            if e.code == 404:          # compteur jamais touché ce jour-là
                time.sleep(PAUSE)
                return 0
            wait = 12 if e.code == 429 else 5 * (attempt + 1)
        except (urllib.error.URLError, TimeoutError, ValueError):
            wait = 5 * (attempt + 1)
        time.sleep(wait)
    sys.exit("ERREUR : compteur injoignable pour " + key)


def listing_ids():
    h = (REPO / "index.html").read_text(encoding="utf-8")
    op = '<script id="pp-data">'
    i = h.index(op) + len(op)
    body = h[i:h.index("</script>", i)].strip()
    data = json.loads(body[len("window.PP_DATA = "):].rstrip(";"))
    ids = [re.sub(r"[^A-Za-z0-9_.-]", "", str(l.get("id") or ""))[:50] for l in data.get("listings") or [] if isinstance(l, dict)]
    return [x for x in dict.fromkeys(ids) if x]


def main():
    back = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    today = datetime.datetime.now(ZoneInfo("Europe/Paris")).date()
    hist = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    jours = hist.get("jours") or {}
    ids = listing_ids()
    for n in range(back, 0, -1):
        d = today - datetime.timedelta(days=n)
        iso, k = d.isoformat(), d.strftime("%Y%m%d")
        if iso in jours and n > 2:      # jour déjà relevé (les 2 derniers sont toujours relus)
            continue
        entry = {"v": get(k + "-v")}
        if entry["v"]:
            entry["s"] = {s: v for s in SOURCES if (v := get(k + "-s-" + s))}
            entry["a"] = {a: v for a in ids if (v := get(k + "-a-" + a))}
        jours[iso] = entry
        print(iso, entry["v"], "visite(s)")
    out = {"maj": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "jours": dict(sorted(jours.items()))}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
