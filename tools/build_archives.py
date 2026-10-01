#!/usr/bin/env python3
"""
Bunker Code : génération du site + pages d'archive.

Ce script :
  1. copie ton site tel quel dans le dossier _site/
  2. lit tous les fichiers codes/AAAA/AAAA-MM.json
  3. génère une vraie page d'accueil par langue (/ en français, /en/ en anglais), avec le texte
     déjà écrit dans le HTML, puis, pour chaque mois passé, une page d'archive (FR et EN) :
        /archives/                  /en/archives/
        /archives/2026-08/          /en/archives/2026-08/
  4. génère sitemap.xml (et robots.txt s'il n'existe pas)
  5. vérifie les données (codes à 5 chiffres, plages valides, pas de chevauchement)
     et aligne l'accueil sur SITE_URL (og:url, og:image, canonical)
  6. écrit le code du jour et la liste des codes du mois directement dans le HTML de chaque accueil,
     pour les moteurs de recherche. Le JavaScript de la page les remplace ensuite par la version à jour.

Le design (CSS, polices, favicon) est repris automatiquement de ton index.html :
si tu changes le style de l'accueil, les archives suivent au prochain build.

Aucune installation nécessaire (Python 3 standard uniquement).
Lancer en local :  python tools/build_archives.py
"""

import calendar
import html
import json
import os
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

# ----------------------------------------------------------------------------
# RÉGLAGES
# ----------------------------------------------------------------------------
# Ces deux valeurs sont normalement fournies automatiquement par GitHub Actions (voir deploy.yml) :
#   SITE_URL  = adresse complète du site (ex. https://bunkercode.fr ou https://xxx.github.io/bunkercode)
#   BASE_PATH = dossier du site sur le domaine ("" si domaine perso, "/bunkercode" sur github.io/bunkercode)
SITE_URL = (os.environ.get("SITE_URL") or "https://bunkercode.fr").rstrip("/")
BASE_PATH = (os.environ.get("BASE_PATH") or "").rstrip("/")
if BASE_PATH and not BASE_PATH.startswith("/"):
    BASE_PATH = "/" + BASE_PATH
SITE_NAME = "Bunker Code"
STATS_URL = "https://bunkera.goatcounter.com/count"   # même compteur que l'accueil ("" pour le retirer)
X_DEFAULT = "en"               # langue montrée par Google aux pays sans version dédiée (hreflang x-default)
INCLURE_MOIS_COURANT = False   # True = le mois en cours apparaît aussi dans les archives

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"

# ----------------------------------------------------------------------------
# TEXTES DES PAGES D'ARCHIVE (une entrée par langue).
# Pour ajouter une langue : copie le bloc "en", traduis-le, et ajoute la langue
# dans lang/index.json. Une langue sans bloc ici est simplement ignorée.
# ----------------------------------------------------------------------------
TEXTS = {
    "fr": {
        "name": "Français",
        "prefix": "",
        "months": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                   "août", "septembre", "octobre", "novembre", "décembre"],
        "first": "1er",
        "sub": "Last Day on Earth · Android et iOS",
        "archives": "Archives",
        "crumbs": "Fil d’Ariane",
        "pager": "Navigation entre les mois",
        "idx_title": "Archives des codes du bunker Alfa – Last Day on Earth | Bunker Code",
        "idx_h1": "Archives des codes du bunker Alfa",
        "idx_desc": "Tous les codes du bunker Alfa (bunker A) de Last Day on Earth, mois par mois : "
                    "retrouvez les codes des mois précédents, pour Android et iOS.",
        "idx_intro": "Les codes du bunker Alfa de Last Day on Earth, mois par mois. "
                     "Pour le code d’aujourd’hui, rendez-vous sur la page d’accueil.",
        "empty": "Aucune archive pour le moment.",
        "count_one": "1 code",
        "count_many": "{n} codes",
        "m_title": "Code bunker Alfa {month} {year} – Last Day on Earth | Bunker Code",
        "m_h1": "Codes du bunker Alfa – {Month} {year}",
        "m_desc": "Tous les codes du bunker Alfa (bunker A) de Last Day on Earth pour {month} {year} : "
                  "{n} codes, jour par jour, du {a} au {b} {month}.",
        "m_range": "Codes valables du {a} au {b} {month} {year}",
        "legal": "Mentions légales",
        # --- accueil ---
        "locale": "fr_FR",
        "weekdays": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "date_fmt": "{wd} {d} {month} {y}",
        "until_single": "Ce code est valable aujourd’hui uniquement.",
        "until_range": "Ce code est valable du {a} au {b} {month}.",
        "noscript": "Activez JavaScript pour que le code se mette à jour en direct. "
                    "Codes des mois précédents : <a href=\"{link}\">archives</a>.",
        # Titre et og:* de l'accueil français : repris tels quels de index.html (pas de clé home_*)
    },
    "en": {
        "name": "English",
        "prefix": "/en",
        "months": ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"],
        "first": None,
        "sub": "Last Day on Earth · Android and iOS",
        "archives": "Archive",
        "crumbs": "Breadcrumb",
        "pager": "Month navigation",
        "idx_title": "Bunker Alfa Code Archive – Last Day on Earth | Bunker Code",
        "idx_h1": "Bunker Alfa code archive",
        "idx_desc": "Every Bunker Alfa (bunker A) code for Last Day on Earth, month by month: "
                    "find the codes from previous months, on Android and iOS.",
        "idx_intro": "The Last Day on Earth Bunker Alfa codes, month by month. "
                     "For today’s code, head to the home page.",
        "empty": "No archive yet.",
        "count_one": "1 code",
        "count_many": "{n} codes",
        "m_title": "Bunker Alfa code {month} {year} – Last Day on Earth | Bunker Code",
        "m_h1": "Bunker Alfa codes – {Month} {year}",
        "m_desc": "All the Bunker Alfa (bunker A) codes for Last Day on Earth in {month} {year}: "
                  "{n} codes, day by day, from {month} {a} to {b}.",
        "m_range": "Codes valid from {month} {a} to {b}, {year}",
        "legal": "Legal notice",
        # --- accueil ---
        "locale": "en_US",
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "date_fmt": "{wd}, {month} {d}, {y}",
        "until_single": "Valid today only.",
        "until_range": "Valid from {month} {a} to {month} {b}, inclusive.",
        "noscript": "Turn on JavaScript so the code updates live. "
                    "Codes from previous months: <a href=\"{link}\">archive</a>.",
        "home_title": "Bunker Code – Today's Bunker Alfa code (Last Day on Earth)",
        "home_og_title": "Bunker Code – Today’s Bunker Alfa code",
        "home_og_desc": "Today’s bunker A code, updated daily. Last Day on Earth, Android and iOS.",
    },
}

# CSS ajouté à celui de l'index.html (uniquement ce qui manque pour les pages d'archive)
EXTRA_CSS = """
a{color:var(--amber)}
a:focus-visible{outline:3px solid #fff;outline-offset:2px}
.brand{font-weight:500;font-size:1.6rem;margin:0}
.brand a{color:inherit;text-decoration:none}
.crumbs{color:var(--dim);font-size:.9rem;margin:12px 0 0}
.crumbs a{color:var(--dim)}
.crumbs a:hover{color:var(--amber)}
h1.page{font-size:1.5rem;font-weight:500;margin:6px 0 2px}
.intro{color:var(--dim);margin:0 0 16px}
.panel{display:grid;gap:12px;padding:14px;background:var(--frame);box-shadow:0 12px 40px rgba(0,0,0,.35)}
.panel .list{grid-area:auto}
.months{list-style:none;margin:0;padding:0;display:grid;gap:2px}
.months a{display:flex;justify-content:space-between;gap:12px;padding:12px 16px;background:var(--block);color:var(--txt);text-decoration:none}
.months a:hover{color:var(--amber)}
.months .n{color:var(--dim);font-size:.9rem}
.pager{display:flex;justify-content:space-between;gap:12px;margin-top:16px}
.pager a{color:var(--txt)}
.pager a:hover{color:var(--amber)}
.sr{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}
details.year summary{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 16px;background:var(--block2);color:var(--txt);cursor:pointer;list-style:none}
details.year summary::-webkit-details-marker{display:none}
details.year summary::after{content:"▾";color:var(--dim)}
details.year[open] summary::after{content:"▴"}
details.year summary:hover::after{color:var(--amber)}
details.year summary:focus-visible{outline:3px solid #fff;outline-offset:2px}
details.year summary h2{margin:0;font-size:1.05rem;font-weight:500;color:var(--txt)}
details.year .months{margin-top:2px}
"""


# Mention de bas de page par langue, lue dans lang/<code>.json (clé "footer"), comme sur l'accueil
FOOTER = {}
LANGJSON = {}


def lire_lang(code):
    """Contenu de lang/<code>.json ({} si absent ou illisible)."""
    if code not in LANGJSON:
        try:
            LANGJSON[code] = json.loads((ROOT / "lang" / f"{code}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            LANGJSON[code] = {}
    return LANGJSON[code]


def lire_footers(langs):
    for l in langs:
        FOOTER[l] = lire_lang(l).get("footer", "") or lire_lang("en").get("footer", "")


# ----------------------------------------------------------------------------
# OUTILS
# ----------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s), quote=True)


def aujourdhui():
    """Date du jour en UTC (comme FUSEAU = "UTC" dans index.html).
    BUNKER_TODAY=AAAA-MM-JJ permet de simuler une autre date pour tester."""
    v = os.environ.get("BUNKER_TODAY")
    return date.fromisoformat(v) if v else datetime.now(timezone.utc).date()


def cap(s):
    return s[:1].upper() + s[1:]


def jour(lang, d):
    return TEXTS[lang]["first"] if d == 1 and TEXTS[lang]["first"] else str(d)


def href(chemin):
    """Lien interne : ajoute le dossier de base du site (ex. /bunkercode) si besoin."""
    return BASE_PATH + chemin


def p_home(lang):
    return f'{TEXTS[lang]["prefix"]}/'


def p_index(lang):
    return f'{TEXTS[lang]["prefix"]}/archives/'


def p_month(lang, y, m):
    return f'{TEXTS[lang]["prefix"]}/archives/{y}-{m:02d}/'


def label(lang, y, m):
    return f'{TEXTS[lang]["months"][m - 1]} {y}'


def ecrire(chemin_url, contenu):
    dossier = OUT / chemin_url.strip("/")
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "index.html").write_text(contenu, encoding="utf-8")


# ----------------------------------------------------------------------------
# LECTURE DES DONNÉES ET DU MODÈLE
# ----------------------------------------------------------------------------
def verifier(f, y, mo, lignes):
    """Contrôle le contenu d'un fichier mensuel : stoppe le build si une erreur de saisie est détectée."""
    nb = calendar.monthrange(y, mo)[1]
    vus = set()
    for a, b, code in lignes:
        if not re.fullmatch(r"\d{5}", code):
            raise SystemExit(f"Erreur dans {f} : code invalide {code!r} (5 chiffres attendus)")
        if not 1 <= a <= b or a > nb:
            raise SystemExit(f"Erreur dans {f} : plage invalide {a}-{b} (ce mois a {nb} jours)")
        if b > nb:   # ex. « 30-31 » dans un mois de 30 jours : toléré, simple avertissement
            print(f"Attention {f} : la plage {a}-{b} dépasse la fin du mois ({nb} jours)")
        jours = set(range(a, min(b, nb) + 1))
        if vus & jours:
            raise SystemExit(f"Erreur dans {f} : chevauchement sur les jours {sorted(vus & jours)}")
        vus |= jours
    manquants = sorted(set(range(1, nb + 1)) - vus)
    if manquants:
        print(f"Attention {f} : jours sans code : {manquants}")


def lire_mois():
    """Retourne {(année, mois): [(jour_début, jour_fin, code), ...]}"""
    resultat = {}
    dossier = ROOT / "codes"
    if not dossier.is_dir():
        raise SystemExit("Erreur : dossier « codes/ » introuvable à la racine du dépôt.")
    for f in sorted(dossier.glob("*/*.json")):
        m = re.fullmatch(r"(\d{4})-(\d{2})\.json", f.name)
        if not m:
            continue
        y, mo = int(m[1]), int(m[2])
        if not 1 <= mo <= 12:
            raise SystemExit(f"Erreur : nom de fichier invalide : {f}")
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            raise SystemExit(f"Erreur : JSON invalide dans {f} ({e})")
        lignes = []
        for i, r in enumerate(data, 1):
            if not (isinstance(r, list) and len(r) == 3 and isinstance(r[0], int) and isinstance(r[1], int)):
                raise SystemExit(f"Erreur dans {f}, ligne {i} : attendu [jour début, jour fin, \"code\"], reçu {r!r}")
            code = str(r[2]).strip()
            if code:                      # un code vide compte comme absent (comme sur l'accueil)
                lignes.append((r[0], r[1], code))
        if lignes:
            verifier(f, y, mo, lignes)
            resultat[(y, mo)] = lignes
    return resultat


def lire_modele():
    """Récupère CSS, polices, favicon… dans index.html pour garder le même design."""
    src = (ROOT / "index.html").read_text(encoding="utf-8")

    def trouve(motif):
        m = re.search(motif, src, re.S)
        return m.group(0) if m else ""

    css = re.search(r"<style>(.*?)</style>", src, re.S)
    if not css:
        print("Attention : aucun <style> trouvé dans index.html, les pages n'auront pas de design.")
    return {
        "css": css.group(1) if css else "",
        "favicon": trouve(r'<link rel="icon"[^>]*>'),
        "theme": trouve(r'<meta name="theme-color"[^>]*>'),
        "fonts": trouve(r'<link rel="preconnect"[^>]*>') + "\n" + trouve(r'<link href="https://fonts\.googleapis\.com[^>]*>'),
    }


def langues_actives():
    """Langues de lang/index.json pour lesquelles on a des textes d'archive."""
    try:
        declarees = json.loads((ROOT / "lang" / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("Attention : lang/index.json illisible, langues par défaut : fr, en")
        declarees = {k: k for k in TEXTS}
    actives = [k for k in declarees if k in TEXTS]
    for k in declarees:
        if k not in TEXTS:
            print(f"Info : langue « {k} » ignorée pour les archives (pas de texte dans TEXTS).")
    return actives or list(TEXTS)


# ----------------------------------------------------------------------------
# CONSTRUCTION D'UNE PAGE HTML
# ----------------------------------------------------------------------------
def defaut_lang(langs):
    return X_DEFAULT if X_DEFAULT in langs else langs[0]


def balises_alternate(langs, chemins):
    """Balises hreflang (une par langue + x-default). Chaque page doit lister toutes les versions, elle-même comprise."""
    out = "\n".join(f'<link rel="alternate" hreflang="{l}" href="{SITE_URL}{chemins[l]}">' for l in langs)
    return out + f'\n<link rel="alternate" hreflang="x-default" href="{SITE_URL}{chemins[defaut_lang(langs)]}">'


def page(modele, langs, lang, chemins, titre, desc, corps, jsonld):
    """chemins = {langue: chemin} de cette même page dans chaque langue (pour hreflang)."""
    T = TEXTS[lang]
    canon = SITE_URL + chemins[lang]
    alternates = balises_alternate(langs, chemins)

    options = "".join(
        f'<option value="{href(chemins[l])}" data-lang="{l}"{" selected" if l == lang else ""}>{esc(TEXTS[l]["name"])}</option>'
        for l in langs
    )
    liens_secours = " ".join(
        f'<a href="{href(chemins[l])}" hreflang="{l}" lang="{l}">{esc(TEXTS[l]["name"])}</a>'
        for l in langs if l != lang
    )
    an = aujourdhui().year
    copyright_ = "© " + (f"2026–{an}" if an > 2026 else "2026") + " Obi"
    pied = f'<footer>{esc(FOOTER[lang])}</footer>' if FOOTER.get(lang) else ""
    stats = (f'<script data-goatcounter="{STATS_URL}" async src="https://gc.zgo.at/count.js"></script>'
             if STATS_URL else "")

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titre)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canon}">
{alternates}
{modele["theme"]}
{modele["favicon"]}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(titre)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{SITE_URL}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="{canon}">
<meta name="twitter:card" content="summary_large_image">
{modele["fonts"]}
<style>{modele["css"]}{EXTRA_CSS}</style>
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
<body>
<main>
 <header>
  <p class="brand"><a href="{href(p_home(lang))}">{SITE_NAME}</a></p>
  <select id="lang" aria-label="Language">{options}</select>
  <noscript>{liens_secours}</noscript>
 </header>
{corps}
 {pied}
 <p class="copy">{copyright_}</p>
 <p class="copy"><a class="linklike" href="{href("/mentions.html")}">{esc(T["legal"])}</a></p>
</main>
<script>
document.getElementById("lang").onchange = function () {{
  try {{ localStorage.setItem("lang", this.options[this.selectedIndex].dataset.lang); }} catch (e) {{}}
  location.href = this.value;
}};
</script>
{stats}
</body>
</html>
"""


def fil_ariane(lang, dernier=None, y=None, m=None):
    """Retourne (html visible, données structurées) du fil d'Ariane."""
    T = TEXTS[lang]
    etapes = [(SITE_NAME, p_home(lang)), (T["archives"], p_index(lang))]
    if dernier:
        etapes.append((dernier, p_month(lang, y, m)))
    visible = []
    for i, (nom, chemin) in enumerate(etapes):
        visible.append(esc(nom) if i == len(etapes) - 1 else f'<a href="{href(chemin)}">{esc(nom)}</a>')
    html_ = f'<nav class="crumbs" aria-label="{esc(T["crumbs"])}">' + " › ".join(visible) + "</nav>"
    ld = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": nom, "item": SITE_URL + chemin}
            for i, (nom, chemin) in enumerate(etapes)
        ],
    }
    return html_, ld


# ----------------------------------------------------------------------------
# PAGES
# ----------------------------------------------------------------------------
def page_index(modele, langs, lang, archives):
    T = TEXTS[lang]
    crumbs, ld = fil_ariane(lang)
    if archives:
        blocs = []
        for i, y in enumerate(sorted({k[0] for k in archives}, reverse=True)):
            items = []
            for (yy, mm) in sorted((k for k in archives if k[0] == y), reverse=True):
                n = len(archives[(yy, mm)])
                compte = T["count_one"] if n == 1 else T["count_many"].format(n=n)
                items.append(
                    f'<li><a href="{href(p_month(lang, yy, mm))}"><span>{esc(cap(label(lang, yy, mm)))}</span>'
                    f'<span class="n">{esc(compte)}</span></a></li>'
                )
            # <details> : repliable sans JavaScript, et les liens restent dans le HTML (lisibles par Google).
            # L'année la plus récente est dépliée, les autres repliées.
            ouvert = " open" if i == 0 else ""
            blocs.append(f'<details class="year list"{ouvert}><summary><h2>{y}</h2></summary>'
                         f'<ul class="months">{"".join(items)}</ul></details>')
        contenu = "\n".join(blocs)
    else:
        contenu = f'<section class="list"><p class="intro">{esc(T["empty"])}</p></section>'

    corps = f"""{crumbs}
 <h1 class="page">{esc(T["idx_h1"])}</h1>
 <p class="intro">{esc(T["idx_intro"])}</p>
 <div class="panel">
{contenu}
 </div>"""
    chemins = {l: p_index(l) for l in langs}
    return page(modele, langs, lang, chemins, T["idx_title"], T["idx_desc"], corps, ld_wrap(ld))


def ld_wrap(*items):
    return {"@context": "https://schema.org", "@graph": list(items)}


def page_mois(modele, langs, lang, y, m, lignes, prec, suiv):
    T = TEXTS[lang]
    mois = T["months"][m - 1]
    debut = min(a for a, _, _ in lignes)
    fin = max(b for _, b, _ in lignes)
    vals = dict(month=mois, Month=cap(mois), year=y, n=len(lignes),
                a=jour(lang, debut), b=jour(lang, fin))
    crumbs, ld = fil_ariane(lang, cap(label(lang, y, m)), y, m)

    rows = "\n".join(
        f'   <tr><td>{a if a == b else f"{a} – {b}"}</td><td>{esc(c)}</td></tr>' for a, b, c in lignes
    )
    pager = []
    if prec:
        pager.append(f'<a rel="prev" href="{href(p_month(lang, *prec))}">← {esc(cap(label(lang, *prec)))}</a>')
    else:
        pager.append("<span></span>")
    if suiv:
        pager.append(f'<a rel="next" href="{href(p_month(lang, *suiv))}">{esc(cap(label(lang, *suiv)))} →</a>')
    corps = f"""{crumbs}
 <h1 class="page">{esc(T["m_h1"].format(**vals))}</h1>
 <p class="intro">{esc(T["sub"])}</p>
 <div class="panel">
  <section class="list">
   <h2>{esc(T["m_range"].format(**vals))}</h2>
   <table>
    <caption class="sr">{esc(T["m_h1"].format(**vals))}</caption>
    <tbody>
{rows}
    </tbody>
   </table>
  </section>
 </div>
 <nav class="pager" aria-label="{esc(T["pager"])}">{"".join(pager)}</nav>"""
    chemins = {l: p_month(l, y, m) for l in langs}
    return page(modele, langs, lang, chemins, T["m_title"].format(**vals), T["m_desc"].format(**vals),
                corps, ld_wrap(ld))


# ----------------------------------------------------------------------------
# SITEMAP / ROBOTS
# ----------------------------------------------------------------------------
def sitemap(langs, cles):
    defaut = defaut_lang(langs)
    homes = {p_home(l) for l in langs}
    groupes = [{l: p_home(l) for l in langs}, {l: p_index(l) for l in langs}]
    groupes += [{l: p_month(l, y, m) for l in langs} for (y, m) in cles]
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for g in groupes:
        for l, chemin in g.items():
            out.append(f"<url><loc>{SITE_URL}{chemin}</loc>")
            if chemin in homes:
                out.append(f"<lastmod>{aujourdhui().isoformat()}</lastmod>")
            for l2, c2 in g.items():
                out.append(f'<xhtml:link rel="alternate" hreflang="{l2}" href="{SITE_URL}{c2}"/>')
            out.append(f'<xhtml:link rel="alternate" hreflang="x-default" href="{SITE_URL}{g[defaut]}"/>')
            out.append("</url>")
    out.append("</urlset>")
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# PROGRAMME PRINCIPAL
# ----------------------------------------------------------------------------
def code_du_jour(mois):
    """Ligne (début, fin, code) valable aujourd'hui (UTC), ou None."""
    t = aujourdhui()
    for a, b, c in mois.get((t.year, t.month), []):
        if a <= t.day <= b:
            return a, b, c
    return None


def remplir(h, motif, contenu, nom):
    """Remplace le contenu d'une balise de index.html. motif = 3 groupes : ouverture, ancien contenu, fermeture."""
    h, n = re.subn(motif, lambda m: m.group(1) + contenu + m.group(3), h, count=1, flags=re.S)
    if not n:
        print(f"Attention : emplacement introuvable dans index.html ({nom}), cette partie n'est pas pré-remplie.")
    return h


def prerendre_accueil(h, mois, lang):
    """Écrit dans le HTML de l'accueil (dans la langue de la page) le code du jour et la liste des codes du mois.
    Le JS de la page reconstruit ces éléments au chargement : les visiteurs voient donc toujours la version
    à jour. Les robots, eux, lisent ce texte tel quel."""
    T, J = TEXTS[lang], lire_lang(lang)
    t = aujourdhui()
    mois_nom = T["months"][t.month - 1]
    lignes = mois.get((t.year, t.month), [])
    ligne = code_du_jour(mois)

    if ligne:
        a, b, code = ligne
        date_txt = cap(T["date_fmt"].format(wd=T["weekdays"][t.weekday()], d=jour(lang, t.day), month=mois_nom, y=t.year))
        if a == b:
            until = T["until_single"]
        else:
            until = T["until_range"].format(a=jour(lang, a), b=jour(lang, b), month=mois_nom)
        chiffres = "".join(f'<span aria-hidden="true">{esc(c)}</span>' for c in code)
        chiffres += f'<span class="sr">{esc(code)}</span>'
        h = remplir(h, r'(<p class="date" id="date">)(.*?)(</p>)', esc(date_txt), "date")
        h = remplir(h, r'(<div class="digits" id="digits">)(.*?)(</div>)', chiffres, "chiffres")
        h = remplir(h, r'(<p class="until" id="until">)(.*?)(</p>)', esc(until), "validité")
        print(f"OK [{lang}] : accueil pré-rempli avec le code du {date_txt} ({code}).")
    else:
        print(f"Info [{lang}] : pas de code pour aujourd'hui, le code n'est pas pré-rempli.")

    if lignes:
        if J.get("all"):
            titre = J["all"].replace("{month}", label(lang, t.year, t.month))
            h = remplir(h, r'(<h2 id="tt">)(.*?)(</h2>)', esc(titre), "titre de la liste")
        rows = []
        for a, b, c in lignes:
            cls = ' class="now"' if ligne and ligne[0] == a else ""
            plage = str(a) if a == b else f"{a} – {b}"
            rows.append(f"<tr{cls}><td>{plage}</td><td>{esc(c)}</td></tr>")
        rows = "".join(rows)
        h = remplir(h, r'(<tbody id="rows">)(.*?)(</tbody>)', rows, "liste des codes")
    return h


def construire_accueil(src, lang, langs, mois):
    """Version complète de l'accueil pour une langue, à partir du gabarit index.html (qui est en français)."""
    T, J = TEXTS[lang], lire_lang(lang)
    chemins = {l: p_home(l) for l in langs}
    canon = SITE_URL + chemins[lang]
    h = src

    # --- langue, balises <head>
    h = h.replace('<html lang="fr">', f'<html lang="{lang}" data-pages="{" ".join(langs)}">', 1)
    if "data-pages" not in h:
        print("Attention : <html lang=\"fr\"> introuvable dans index.html.")
    depth = len([x for x in T["prefix"].split("/") if x])
    if depth:   # les chemins relatifs de la page (lang/, codes/, archives/…) restent valables depuis /en/
        h = h.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<base href="' + "../" * depth + '">', 1)
    h = remplir(h, r'(<meta property="og:url" content=")(.*?)(">)', canon, "og:url")
    if "home_title" in T:   # langues autres que le français : le gabarit est en français
        h = remplir(h, r"(<title>)(.*?)(</title>)", esc(T["home_title"]), "title")
        h = remplir(h, r'(<meta name="description" content=")(.*?)(">)', esc(J.get("metaDesc", "")), "description")
        h = remplir(h, r'(<meta property="og:title" content=")(.*?)(">)', esc(T["home_og_title"]), "og:title")
        h = remplir(h, r'(<meta property="og:description" content=")(.*?)(">)', esc(T["home_og_desc"]), "og:description")
    autres_locales = "".join(
        f'\n<meta property="og:locale:alternate" content="{TEXTS[l]["locale"]}">' for l in langs if l != lang)
    tete = (f'<link rel="canonical" href="{canon}">\n{balises_alternate(langs, chemins)}\n'
            f'<meta property="og:locale" content="{T["locale"]}">{autres_locales}\n')
    h = h.replace("<title>", tete + "<title>", 1)

    # --- corps de page : textes de la langue
    if "home_title" in T:
        h = remplir(h, r'(<p class="sub" id="sub">)(.*?)(</p>)', esc(J.get("sub", "")), "sous-titre")
    lien_archives = href(p_index(lang))
    if T["prefix"]:   # liens absolus vers les pages sans version dans cette langue ou à un autre niveau
        h = h.replace('href="archives/"', f'href="{lien_archives}"')
        h = h.replace('href="mentions.html"', f'href="{href("/mentions.html")}"')
    h = re.sub(r'<noscript><p class="err">.*?</noscript>',
               lambda m: f'<noscript><p class="err">{T["noscript"].format(link=lien_archives)}</p></noscript>',
               h, count=1, flags=re.S)
    options = "".join(
        f'<option value="{l}"{" selected" if l == lang else ""}>{esc(TEXTS[l]["name"])}</option>' for l in langs)
    h = remplir(h, r'(<select id="lang"[^>]*>)(.*?)(</select>)', options, "sélecteur de langue")
    if FOOTER.get(lang):
        h = remplir(h, r'(<footer id="footer">)(.*?)(</footer>)', esc(FOOTER[lang]), "pied de page")
    an = aujourdhui().year
    h = remplir(h, r'(<p class="copy" id="copyright">)(.*?)(</p>)',
                "© " + (f"2026–{an}" if an > 2026 else "2026") + " Obi", "copyright")
    h = remplir(h, r'(<a id="legalLink"[^>]*>)(.*?)(</a>)', esc(T["legal"]), "mentions légales")
    h = remplir(h, r'(<a id="archiveLink"[^>]*>)(.*?)(</a>)', esc(J.get("archive") or T["archives"]), "archives")
    # vrais liens vers les autres langues (un <select> n'est pas suivi par les moteurs de recherche)
    liens = " · ".join(
        f'<a class="linklike" href="{href(chemins[l])}" hreflang="{l}" lang="{l}">{esc(TEXTS[l]["name"])}</a>'
        for l in langs if l != lang)
    h = remplir(h, r'(<p class="copy" id="langLinks">)(.*?)(</p>)', liens, "liens de langue")

    return prerendre_accueil(h, mois, lang)


def main():
    # 1. copie du site tel quel
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT, OUT, ignore=shutil.ignore_patterns(
        ".git", ".github", "tools", "_site", "node_modules", "*.md", ".gitignore"))

    # 2. données
    modele = lire_modele()
    langs = langues_actives()
    lire_footers(langs)
    mois = lire_mois()

    t = aujourdhui()
    limite = (t.year, t.month)
    archives = {k: v for k, v in mois.items() if k < limite or (INCLURE_MOIS_COURANT and k == limite)}
    cles = sorted(archives)

    # 3. accueil (une vraie page par langue) puis archives
    src = (ROOT / "index.html").read_text(encoding="utf-8").replace("https://bunkercode.fr", SITE_URL)
    for lang in langs:
        ecrire(p_home(lang), construire_accueil(src, lang, langs, mois))
        ecrire(p_index(lang), page_index(modele, langs, lang, archives))
        for i, (y, m) in enumerate(cles):
            prec = cles[i - 1] if i > 0 else None
            suiv = cles[i + 1] if i < len(cles) - 1 else None
            ecrire(p_month(lang, y, m), page_mois(modele, langs, lang, y, m, archives[(y, m)], prec, suiv))

    # 4. sitemap + robots
    (OUT / "sitemap.xml").write_text(sitemap(langs, cles), encoding="utf-8")
    robots = OUT / "robots.txt"
    if not robots.exists():
        robots.write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")

    print(f"OK : {len(cles)} mois archivés x {len(langs)} langue(s) ({', '.join(langs)}).")
    for (y, m) in cles:
        print(f"  - {y}-{m:02d} : {len(archives[(y, m)])} codes")


if __name__ == "__main__":
    main()
