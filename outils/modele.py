#!/usr/bin/env python3
"""Modifier le code du site (et pas seulement ses annonces).

Le code de la page vit dans le modèle intégré à index.html (PP_TPL) : c'est lui que le bouton
« Publier » de l'espace privé réutilise, et c'est à partir de lui que publier.py reconstruit la page.

    python3 outils/modele.py extraire modele.html    # écrit le modèle dans un fichier à modifier
    python3 outils/modele.py appliquer modele.html   # le remet dans index.html
    python3 outils/publier.py                        # reconstruit la page à partir du nouveau modèle
"""
import json, pathlib, sys

INDEX = pathlib.Path(__file__).resolve().parent.parent / "index.html"
OPEN, PREFIX = '<script id="pp-tpl">', "window.PP_TPL = "


def span(text):
    i = text.index(OPEN) + len(OPEN)
    return i, text.index("</script>", i)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("extraire", "appliquer"):
        sys.exit(__doc__)
    text = INDEX.read_text(encoding="utf-8")
    a, b = span(text)
    target = pathlib.Path(sys.argv[2])
    if sys.argv[1] == "extraire":
        target.write_text(json.loads(text[a:b][len(PREFIX):-1]), encoding="utf-8")
        print("modèle écrit dans", target)
        return
    tpl = target.read_text(encoding="utf-8")
    for bid in ("pp-img", "pp-data", "pp-tpl"):
        if '<script id="%s"></script>' % bid not in tpl:
            sys.exit("ERREUR : le modèle doit garder le bloc vide %s" % bid)
    body = PREFIX + json.dumps(tpl, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c") + ";"
    INDEX.write_text(text[:a] + body + text[b:], encoding="utf-8")
    print("modèle remplacé dans index.html : lance maintenant outils/publier.py")


if __name__ == "__main__":
    main()
