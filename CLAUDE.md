# Site Paradise Patrimoine

Site public : https://paradisepatrimoine.github.io/ (GitHub Pages, branche `main`, aucune étape de build).
Le propriétaire n'est pas technique : c'est Claude qui publie. Écrire en français.

## Publier une mise à jour (« publie mon site »)

Le propriétaire modifie ses annonces dans l'espace privé du site (adresse + `#admin`). Le bouton « Publier »
télécharge `site-paradise-patrimoine-AAAA-MM-JJ-HHhMM.zip` : un `index.html` d'environ 8 Mo (toutes les photos
intégrées) et le dossier `videos/`.

**Ne jamais déposer cet `index.html` tel quel** : Google ne lit que les 2 premiers Mo d'une page, le site
disparaîtrait des résultats. Toujours passer par le script, puis pousser sur `main` :

    python3 outils/publier.py chemin/vers/le.zip
    git add -A && git commit -m "…" && git push

Le script sort les photos dans `photos/`, reconstruit `index.html` (moins de 1 Mo) à partir du modèle intégré,
régénère `annonces/<id>/index.html`, `sitemap.xml` et `robots.txt`. Il est relançable sans risque ; sans
argument il repart de l'`index.html` du dépôt. Il s'arrête avec une erreur si une photo manque ou si la page
dépasse la limite.

## Modifier le code du site

`index.html` contient trois blocs : `PP_DATA` (annonces), `PP_IMG` (photos intégrées, vide une fois publié)
et `PP_TPL` (le modèle de la page, réutilisé par « Publier »). Le code se modifie **dans le modèle**, jamais
directement dans la page, sinon la modification disparaît à la publication suivante :

    python3 outils/modele.py extraire modele.html
    # … modifier modele.html …
    python3 outils/modele.py appliquer modele.html && python3 outils/publier.py

## Statistiques de visite

Le propriétaire les consulte dans l'espace privé, bouton « 📊 Statistiques » (visites par jour/mois, provenance,
annonces les plus consultées, liens `?src=` à mettre dans ses réseaux). Aucun compte ni cookie :

- `mesure.js` (chargé par `index.html` via le modèle, et par chaque `annonces/<id>/` via `publier.py`) compte une
  visite par session et sa provenance, et chaque annonce consultée, dans le compteur public
  abacus.jasoncameron.dev (espace `paradisepatrimoine-gh`, clés `AAAAMMJJ-v`, `-s-<source>`, `-a-<id>`).
  Les visites du propriétaire ne sont pas comptées (`localStorage.pp_nostats`, posé à l'ouverture de l'espace privé).
- `outils/statistiques.py`, lancé chaque nuit par `.github/workflows/statistiques.yml`, recopie les compteurs
  (qui expirent au bout de 6 mois) dans `stats/historique.json`. Ne pas modifier ce fichier à la main.
- La page « Confidentialité » du site décrit cette mesure : la garder à jour si elle change.

## À ne pas faire

- Ne pas modifier à la main `annonces/`, `photos/`, `files/`, `stats/`, `sitemap.xml`, `robots.txt` ni les balises
  ajoutées dans l'en-tête de `index.html` : tout est régénéré par le script.
- Ne pas afficher de téléphone ni d'e-mail dans les pages générées (le lien de la bio TikTok doit rester sans coordonnées).
- Garder le fichier `.nojekyll`.
- Si le site passe sur un nom de domaine : changer `SITE` en tête de `outils/publier.py` et relancer le script.
