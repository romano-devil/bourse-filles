#!/usr/bin/env python3
"""Récupère les cours (Yahoo Finance) et génère une page HTML par portefeuille.

Usage : python3 build.py
- Après la clôture du jour d'achat ("debut"), fige le prix d'achat de chaque action
  dans portefeuilles.json.
- Chaque lancement met les cours à jour dans site/juliette.html et site/ines.html.
  Sur GitHub, le workflow .github/workflows/mise-a-jour.yml le lance chaque soir de semaine.
"""
import html as h
import json
import pathlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ICI = pathlib.Path(__file__).parent
FICHIER_PORTEFEUILLES = ICI / "portefeuilles.json"
GABARIT = ICI / "gabarit.html"
SITE = ICI / "site"

INFOS = {
    "GOOGL": {"nom": "Alphabet (Google)", "place": "Nasdaq · New York",
              "metier": "Recherche Google, YouTube, Android, l'IA Gemini et le cloud."},
    "AAPL": {"nom": "Apple", "place": "Nasdaq · New York",
             "metier": "iPhone, Mac, AirPods, et les services comme l'App Store ou Apple Music."},
    "PEP": {"nom": "PepsiCo", "place": "Nasdaq · New York",
            "metier": "Boissons et snacks : Pepsi, Lay's, Doritos, Tropicana, 7UP."},
    "SPOT": {"nom": "Spotify", "place": "NYSE · New York",
             "metier": "Streaming de musique et de podcasts. Entreprise suédoise, cotée aux États-Unis."},
    "ADS.DE": {"nom": "Adidas", "place": "Xetra · Francfort",
               "metier": "Chaussures et vêtements de sport. Entreprise allemande, cotée en euros."},
}


def yahoo(symbole, periode="1y"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbole}?range={periode}&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for essai in range(4):  # Yahoo refuse parfois une requête : on réessaie
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.load(r)["chart"]["result"][0]
            break
        except urllib.error.URLError:
            if essai == 3:
                raise
            time.sleep(10 * (essai + 1))
    tz = ZoneInfo(res["meta"]["exchangeTimezoneName"])
    serie = {}
    for ts, close in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
        if close is not None:
            serie[datetime.fromtimestamp(ts, tz).date().isoformat()] = round(close, 4)
    # le dernier point = cours le plus récent (même en séance)
    dernier_jour = datetime.fromtimestamp(res["meta"]["regularMarketTime"], tz).date().isoformat()
    serie[dernier_jour] = round(res["meta"]["regularMarketPrice"], 4)
    return res["meta"]["currency"], dict(sorted(serie.items()))


def valeur_au(serie, jour):
    """Dernier cours connu à la date `jour` (ou avant)."""
    v = None
    for d, c in serie.items():
        if d > jour:
            break
        v = c
    return v if v is not None else next(iter(serie.values()))


# --- Mise en forme (tout est calculé ici : la page n'a besoin d'aucun JavaScript) ---

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def nombre(v, dec=2):
    return f"{v:,.{dec}f}".replace(",", "\u202f").replace(".", ",")


def eur(v, dec=2):
    return nombre(v, dec) + "\u00a0€"


def prix(v, devise):
    return nombre(v) + ("\u00a0$" if devise == "USD" else "\u00a0€")


def pct(v):
    if abs(v) < 0.05:
        return "0,0\u00a0%"
    return ("+" if v > 0 else "−") + nombre(abs(v), 1) + "\u00a0%"


def sens(v):
    return "flat" if abs(v) < 0.005 else "up" if v > 0 else "down"


def date_fr(iso, jour_semaine=False, annee=True):
    d = datetime.fromisoformat(iso).date()
    txt = f"{d.day} {MOIS[d.month - 1]}" + (f" {d.year}" if annee else "")
    return (JOURS[d.weekday()] + " " + txt) if jour_semaine else txt


def prix_eur_au(ligne, jour):
    v = None
    for d, _, pe in ligne["historique"]:
        if d > jour:
            break
        v = pe
    return v


def graphique(p, lignes, investi, gain_total):
    jours = sorted({hh[0] for l in lignes for hh in l["historique"] if hh[0] >= p["debut"]})
    points = [(d, sum(l["achat"]["nb_actions"] * (prix_eur_au(l, d) or 0) for l in lignes)) for d in jours]
    if len(points) < 2:
        return ('<p class="vide">Ton portefeuille vient de démarrer. La courbe se dessinera jour après jour, '
                'à chaque clôture de la bourse.</p>')
    W, H, g, b, t, r = 700, 220, 44, 24, 10, 10
    vals = [v for _, v in points] + [investi]
    mn, mx = min(vals), max(vals)
    marge = max((mx - mn) * 0.15, 1)
    mn, mx = mn - marge, mx + marge
    x = lambda i: g + (W - g - r) * i / (len(points) - 1)
    y = lambda v: t + (H - t - b) * (1 - (v - mn) / (mx - mn))
    c = "var(--up)" if gain_total >= 0 else "var(--down)"
    trace = "".join(f"{'L' if i else 'M'}{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(points))
    ref = y(investi)
    n = len(points) - 1
    return f"""<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Valeur du portefeuille jour après jour">
      <line x1="{g}" x2="{W - r}" y1="{ref:.1f}" y2="{ref:.1f}" style="stroke:var(--muted)" stroke-dasharray="4 4"/>
      <text x="{g - 6}" y="{ref + 4:.1f}" text-anchor="end">{round(investi)} €</text>
      <path d="{trace}L{x(n):.1f},{H - b}L{g},{H - b}Z" style="fill:{c}" fill-opacity=".12"/>
      <path d="{trace}" style="fill:none;stroke:{c}" stroke-width="2.5" stroke-linejoin="round"/>
      <circle cx="{x(n):.1f}" cy="{y(points[-1][1]):.1f}" r="4.5" style="fill:{c}"/>
      <text x="{g}" y="{H - 6}">{date_fr(points[0][0], annee=False)}</text>
      <text x="{W - r}" y="{H - 6}" text-anchor="end">{date_fr(points[-1][0], annee=False)}</text>
    </svg>"""


def sparkline(l, debut):
    hist = l["historique"][-66:]
    W, H, p = 700, 70, 4
    vals = [v[1] for v in hist]
    mn, mx = min(vals), max(vals)
    ecart = (mx - mn) or 1
    x = lambda i: p + (W - 2 * p) * i / max(len(hist) - 1, 1)
    y = lambda v: p + (H - 2 * p - 14) * (1 - (v - mn) / ecart)
    trace = "".join(f"{'L' if i else 'M'}{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
    marque = ""
    i_achat = next((i for i, v in enumerate(hist) if v[0] >= debut), None) if l["achat"] else None
    if i_achat is not None:
        ancre = "end" if i_achat > len(hist) * 0.8 else "middle"
        marque = (f'<line x1="{x(i_achat):.1f}" x2="{x(i_achat):.1f}" y1="{p}" y2="{H - 14}" '
                  f'style="stroke:var(--accent)" stroke-dasharray="3 3"/>'
                  f'<text x="{x(i_achat):.1f}" y="{H - 2}" text-anchor="{ancre}" style="fill:var(--accent)">ton achat</text>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Cours de {h.escape(l["nom"])} sur 3 mois">'
            f'<path d="{trace}" style="fill:none;stroke:var(--muted)" stroke-width="1.6"/>{marque}'
            f'<text x="{p}" y="{H - 2}">il y a 3 mois</text></svg>')


def rendre(p, lignes, maj, eurusd_actuel):
    en_attente = any(not l["achat"] for l in lignes)
    jour_achat = date_fr(p["debut"], jour_semaine=True, annee=False)
    for l in lignes:
        dernier = l["historique"][-1]
        l["cours_natif"], l["prix_eur"] = dernier[1], dernier[2]
        l["valeur"] = l["achat"]["nb_actions"] * dernier[2] if l["achat"] else l["montant_eur"]
        l["gain"] = l["valeur"] - l["montant_eur"]
    investi = sum(l["montant_eur"] for l in lignes)
    total = sum(l["valeur"] for l in lignes)
    gain_total = total - investi

    if en_attente:
        sous_titre = f"{eur(investi, 0)} à investir le {jour_achat}, répartis sur {len(lignes)} entreprises."
        libelle = "Ton argent, prêt à être investi"
        ecart = (f'<span class="pill flat">Achat le {jour_achat}</span>'
                 '<span>Les compteurs démarreront le jour de l\'achat.</span>')
        graph = (f'<p class="vide">La courbe démarrera après ton achat du {jour_achat}. En attendant, '
                 'regarde plus bas comment tes actions ont bougé ces 3 derniers mois.</p>')
    else:
        sous_titre = f"{eur(investi, 0)} investis le {date_fr(p['debut'])}, répartis sur {len(lignes)} entreprises."
        libelle = "Ce que valent tes 100 € aujourd'hui"
        if abs(gain_total) < 0.005:
            texte = "Ni gain ni perte pour l'instant"
        else:
            texte = ("+" if gain_total > 0 else "−") + eur(abs(gain_total)) + (" de gain" if gain_total > 0 else " de perte")
        ecart = (f'<span class="pill {sens(gain_total)}">{pct(gain_total / investi * 100)}</span>'
                 f'<span class="num">{texte}</span>')
        graph = graphique(p, lignes, investi, gain_total)

    fiches = []
    for l in lignes:
        a = l["achat"]
        badge = (f'<span class="pill {sens(l["gain"])}">{pct(l["gain"] / l["montant_eur"] * 100)}</span>' if a
                 else '<span class="pill flat">à acheter</span>')
        chiffres = [
            ("Investi" if a else "À investir", eur(l["montant_eur"])),
            ("Nombre d'actions" if a else "Actions (estimation)",
             nombre(a["nb_actions"], 4) if a else "≈\u00a0" + nombre(l["montant_eur"] / l["prix_eur"], 4)),
            ("Prix d'achat", prix(a["prix"], l["devise"]) if a else "à venir"),
            ("Cours actuel", prix(l["cours_natif"], l["devise"])),
        ]
        dl = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in chiffres)
        cotation = "dollars" if l["devise"] == "USD" else "euros"
        fiches.append(f"""    <article class="panneau action">
      <div class="titre"><h3>{h.escape(l["nom"])}</h3><span class="meta">{l["symbole"]} · {l["place"]} · cotée en {cotation}</span></div>
      <div class="droite"><span class="v">{eur(l["valeur"])}</span>{badge}</div>
      <p class="metier">{h.escape(l["metier"])}</p>
      <dl class="chiffres">{dl}</dl>
      <div class="spark">{sparkline(l, p["debut"])}</div>
    </article>""")

    m = datetime.fromisoformat(maj).astimezone(ZoneInfo("Europe/Paris"))
    pied = (f"Cours mis à jour le {date_fr(m.date().isoformat(), annee=False)} à {m:%H:%M} (heure de Paris) · "
            f"1 € = {nombre(eurusd_actuel, 4)} $ · Source : Yahoo Finance. "
            "Les montants en dollars sont convertis en euros au cours du jour.")

    remplacements = {"PRENOM": h.escape(p["prenom"]), "SOUS_TITRE": sous_titre, "LIBELLE_TOTAL": libelle,
                     "VALEUR": eur(total), "ECART": ecart, "GRAPHIQUE": graph,
                     "ACTIONS": "\n".join(fiches), "PIED": pied}
    page = GABARIT.read_text()
    for k, v in remplacements.items():
        page = page.replace("{{" + k + "}}", v)
    return page


def main():
    portefeuilles = json.loads(FICHIER_PORTEFEUILLES.read_text())
    symboles = {l["symbole"] for p in portefeuilles.values() for l in p["lignes"]}
    cours = {s: yahoo(s) for s in symboles}
    _, eurusd = yahoo("EURUSD=X")
    maj = datetime.now(timezone.utc).isoformat(timespec="minutes")
    # l'achat est figé au cours de clôture du jour d'achat : on attend la fermeture de Wall Street
    paris = datetime.now(ZoneInfo("Europe/Paris"))
    cloture_passee = lambda jour: jour < paris.date().isoformat() or (
        jour == paris.date().isoformat() and (paris.hour, paris.minute) >= (22, 30))

    modifie = False
    for cle, p in portefeuilles.items():
        lignes = []
        for l in p["lignes"]:
            devise, serie = cours[l["symbole"]]
            # on fige l'achat une seule fois, quand le cours du jour d'achat existe
            if "achat" not in l and p["debut"] in serie and cloture_passee(p["debut"]):
                prix = valeur_au(serie, p["debut"])
                fx = valeur_au(eurusd, p["debut"]) if devise == "USD" else 1.0
                l["achat"] = {"prix": prix, "eurusd": fx,
                              "nb_actions": round(l["montant_eur"] * fx / prix, 6)}
                modifie = True
            fx_serie = eurusd if devise == "USD" else None
            historique = [
                [d, c, round(c / valeur_au(fx_serie, d), 4) if fx_serie else c]
                for d, c in serie.items()
            ]
            lignes.append({**INFOS[l["symbole"]], "symbole": l["symbole"], "devise": devise,
                           "montant_eur": l["montant_eur"], "achat": l.get("achat"),
                           "historique": historique})
        html = rendre(p, lignes, maj, list(eurusd.values())[-1])
        # page autonome, publiée sur GitHub Pages (s'ouvre dans n'importe quel navigateur)
        SITE.mkdir(exist_ok=True)
        (SITE / f"{cle}.html").write_text(
            '<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '<meta name="robots" content="noindex">\n'
            '<style>[hidden]{display:none!important}img{max-width:100%}</style>\n</head>\n<body>\n'
            + html + "\n</body>\n</html>\n")
        print(f"site/{cle}.html généré")

    if modifie:
        FICHIER_PORTEFEUILLES.write_text(json.dumps(portefeuilles, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
