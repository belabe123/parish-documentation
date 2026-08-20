#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Costruisce il sito del catechismo a partire dai file markdown del repository.

Come funziona, in due righe: legge tutti i .md, li converte in HTML, e li
impagina dentro un modello unico con barra laterale, ricerca e pulsante di
segnalazione. Il risultato finisce nella cartella _site/, che GitHub Pages
pubblica.

I file markdown NON vengono toccati: niente intestazioni da aggiungere,
niente sintassi speciale. Si scrive markdown normale e basta.

Per provarlo sul proprio computer:
    python3 tools/costruisci_sito.py
    python3 -m http.server -d _site 8000
e poi si apre http://localhost:8000
"""

import html
import json
import os
import re
import shutil
import sys
import unicodedata
import urllib.parse

# --------------------------------------------------------------------------
# CONFIGURAZIONE — le uniche righe che di solito serve cambiare
# --------------------------------------------------------------------------

TITOLO_SITO = "Catechismo a Promano"
SOTTOTITOLO = "Parrocchia di Promano"

# Indirizzo del modulo Google per le segnalazioni.
# Finché resta vuoto, il pulsante «Segnala» spiega che il modulo non c'è
# ancora invece di aprire una pagina rotta.
#
# Per collegarlo: crea un modulo Google con cinque domande a risposta breve
# (pagina, sezione, frase, nome, segnalazione), scegli «Ottieni link
# precompilato», compila con dei valori finti e copia l'indirizzo. Poi
# incolla qui la parte prima di «&entry.» e sostituisci i cinque numeri.
MODULO_URL = ""
MODULO_CAMPI = {
    "pagina": "entry.000000001",
    "sezione": "entry.000000002",
    "frase": "entry.000000003",
    "chi": "entry.000000004",
    "nota": "entry.000000005",
}

# Alcuni titoli funzionano dentro il documento ma non come voce di menu:
# «Il catechismo a Promano» ripeterebbe il nome del sito. Qui si correggono.
TITOLI_MENU = {
    "01 - Come lo facciamo oggi.md": "Come lo facciamo oggi",
    "README.md": "Come è organizzato questo archivio",
    "Schede/_Modello scheda.md": "Modello di scheda, da copiare",
}

# File e cartelle che non diventano pagine del sito.
ESCLUSI = {
    "00 - Indice.md",        # la barra laterale fa già da indice
    "_Inventario Drive.md",  # documento di lavoro interno
}
CARTELLE_ESCLUSE = {".git", ".github", "_site", "tools", "node_modules"}

# I gruppi della barra laterale, nell'ordine in cui appaiono.
# Ogni voce: (etichetta, funzione che dice se un percorso ci appartiene)
GRUPPI = [
    ("Il manuale",                      lambda p: p.startswith("01 - ")),
    ("I percorsi",                      lambda p: re.match(r"0[2-6] - ", p) is not None),
    ("I ritiri",                        lambda p: p.startswith("Ritiri/")),
    ("Schede · I e II elementare",      lambda p: p.startswith("Schede/I-II/")),
    ("Schede · III e IV elementare",    lambda p: p.startswith("Schede/III-IV/")),
    ("Schede · V elementare e I media", lambda p: p.startswith("Schede/V-I media/")),
    ("Schede · Tempi forti",            lambda p: p.startswith("Schede/Tempi forti/")),
    ("Schede · Prima Comunione",        lambda p: p.startswith("Schede/Sacramenti/")),
    ("Schede · Cresima",                lambda p: p.startswith("Schede/Cresima/")),
    ("Materiali comuni",                lambda p: p.startswith("Comuni/")),
    ("Strumenti",                       lambda p: p == "Schede/_Modello scheda.md"),
    ("Il progetto",                     lambda p: p == "README.md"),
]

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USCITA = os.path.join(RADICE, "_site")


# --------------------------------------------------------------------------
# UTILITÀ
# --------------------------------------------------------------------------

def slug(testo):
    """«03 - Percorso III-IV elementare» -> «03-percorso-iii-iv-elementare»"""
    t = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode()
    t = re.sub(r"[^\w\s-]", "", t).strip().lower()
    t = re.sub(r"[-\s]+", "-", t)
    return t or "pagina"


def url_di(percorso_rel):
    """Percorso del file markdown -> indirizzo della pagina sul sito.

    Quando il file ripete il nome della sua cartella — la convenzione delle
    schede — il nome non viene ripetuto anche nell'indirizzo:
    «Schede/III-IV/09 - Il buon samaritano/09 - Il buon samaritano.md»
    diventa «/schede/iii-iv/09-il-buon-samaritano/».
    """
    parti = percorso_rel[:-3].split("/")          # via il .md
    if len(parti) > 1 and parti[-1] == parti[-2]:
        parti = parti[:-1]
    return "/".join(slug(p) for p in parti) + "/"


def titolo_di(testo_md, ripiego):
    m = re.search(r"^#\s+(.+?)\s*$", testo_md, re.M)
    return m.group(1).strip() if m else ripiego


def gruppo_di(percorso_rel):
    for etichetta, test in GRUPPI:
        if test(percorso_rel):
            return etichetta
    return "Altro"


# --------------------------------------------------------------------------
# RACCOLTA DEI FILE
# --------------------------------------------------------------------------

def raccogli():
    pagine = []
    for radice, cartelle, file in os.walk(RADICE):
        cartelle[:] = [c for c in cartelle if c not in CARTELLE_ESCLUSE]
        for nome in file:
            if not nome.endswith(".md"):
                continue
            assoluto = os.path.join(radice, nome)
            rel = os.path.relpath(assoluto, RADICE).replace(os.sep, "/")
            if rel in ESCLUSI:
                continue
            testo = open(assoluto, encoding="utf-8").read()
            pagine.append({
                "file": rel,
                "titolo": TITOLI_MENU.get(rel) or titolo_di(testo, nome[:-3]),
                "gruppo": gruppo_di(rel),
                "url": url_di(rel),
                "md": testo,
                # gli allegati stanno nella stessa cartella della scheda e non
                # ripetono il nome della cartella: servono a rientrare nel menu
                "allegato": rel.startswith("Schede/")
                            and "/" in rel[len("Schede/"):]
                            and os.path.basename(rel)[:-3] != os.path.basename(os.path.dirname(rel)),
            })

    ordine = {etichetta: i for i, (etichetta, _) in enumerate(GRUPPI)}
    pagine.sort(key=lambda p: (ordine.get(p["gruppo"], 99), p["file"]))
    return pagine


# --------------------------------------------------------------------------
# CONVERSIONE MARKDOWN
# --------------------------------------------------------------------------

def converti(pagina, per_url):
    """Markdown -> HTML, con i collegamenti interni riscritti e le sezioni
    dotate di ancora e pulsante «Segnala»."""
    import markdown

    md = markdown.Markdown(extensions=["tables", "fenced_code", "attr_list", "sane_lists"])
    corpo = md.convert(pagina["md"])

    # il titolo lo mette il modello, non il corpo
    corpo = re.sub(r"^\s*<h1[^>]*>.*?</h1>", "", corpo, count=1, flags=re.S)

    cartella = os.path.dirname(pagina["file"])

    def rifai_link(m):
        grezzo = m.group(1)
        if grezzo.startswith(("http://", "https://", "#", "mailto:")):
            return m.group(0)
        bersaglio = urllib.parse.unquote(grezzo)
        risolto = os.path.normpath(os.path.join(cartella, bersaglio)).replace(os.sep, "/")
        if risolto in per_url:
            return 'href="/%s"' % per_url[risolto]
        return m.group(0)

    corpo = re.sub(r'href="([^"]+)"', rifai_link, corpo)

    # ancore e pulsante di segnalazione su ogni titolo di sezione
    sezioni = []

    def h2(m):
        grezzo = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        s = slug(grezzo)
        sezioni.append({"id": s, "t": grezzo})
        return (
            '<h2 id="%s" data-raw="%s">%s'
            '<a class="anch" href="#%s" title="Collegamento a questa sezione">#</a>'
            '<button class="seg" data-s="%s">Segnala</button></h2>'
            % (s, html.escape(grezzo, True), m.group(1), s, html.escape(grezzo, True))
        )

    corpo = re.sub(r"<h2>(.*?)</h2>", h2, corpo, flags=re.S)

    # markdown crea sempre un'intestazione di tabella, anche quando nel testo
    # non c'è: se è vuota la si segna, e il foglio di stile la nasconde
    corpo = re.sub(r"<tr>\s*(<th[^>]*>\s*</th>\s*)+</tr>",
                   lambda m: m.group(0).replace("<tr>", '<tr class="vuota">', 1),
                   corpo)

    testo = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", corpo)))
    return corpo, sezioni, testo.strip()


# --------------------------------------------------------------------------
# MODELLO DELLA PAGINA
# --------------------------------------------------------------------------

def barra_laterale(pagine, corrente):
    out, gruppo_aperto = [], None
    for p in pagine:
        if p["gruppo"] != gruppo_aperto:
            gruppo_aperto = p["gruppo"]
            out.append('<div class="grp">%s</div>' % html.escape(gruppo_aperto))
        classe = "sub" if p["allegato"] else ""
        if p is corrente:
            classe += " on"
        out.append('<a class="%s" href="/%s">%s</a>' % (classe.strip(), p["url"], html.escape(p["titolo"])))
        if p is corrente and p["sezioni"]:
            out.append('<div class="subs">')
            for s in p["sezioni"]:
                out.append('<a class="sez" href="#%s">%s</a>' % (s["id"], html.escape(s["t"])))
            out.append("</div>")
    return "\n".join(out)


def scrivi_pagina(pagina, pagine, css, js):
    modello = """<!doctype html>
<html lang="it"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titolo} · {sito}</title>
<meta name="description" content="{sito} — {gruppo}">
<style>{css}</style>
</head><body>
<button id="burger" aria-label="Menu">&#9776;</button>
<div id="wrap">
  <aside id="side">
    <div id="brand"><a href="/"><b>{sito}</b><span>{sotto}</span></a></div>
    <input id="q" type="search" placeholder="Cerca nel testo..." autocomplete="off">
    <nav id="nav" class="nav">{nav}</nav>
  </aside>
  <main id="main"><div class="colonna">
    <article id="doc">
      <div id="crumb">{gruppo}</div>
      <h1 id="h1">{titolo}</h1>
      <div id="body">{corpo}</div>
      <div id="foot">
        <p>Hai notato qualcosa che non torna in questa pagina?</p>
        <button onclick="openSeg('')">Segnala qualcosa</button>
      </div>
    </article>
    <div id="res"></div>
  </div></main>
</div>
<button id="fab"><span class="ic">&#9998;</span><span class="tx"><span class="t1">Segnala</span><span class="t2" id="fab_s"></span></span></button>
<div id="bub">Segnala questa frase</div>
<div id="ov"><div id="mod">{modale}</div></div>
<script>var PAGINA={pagina_js};var MODULO={modulo_js};</script>
<script>{js}</script>
</body></html>"""

    return modello.format(
        titolo=html.escape(pagina["titolo"]),
        sito=html.escape(TITOLO_SITO),
        sotto=html.escape(SOTTOTITOLO),
        gruppo=html.escape(pagina["gruppo"]),
        css=css,
        js=js,
        nav=barra_laterale(pagine, pagina),
        corpo=pagina["html"],
        modale=MODALE,
        pagina_js=json.dumps(pagina["titolo"], ensure_ascii=False),
        modulo_js=json.dumps({"url": MODULO_URL, "campi": MODULO_CAMPI}, ensure_ascii=False),
    )


def pagina_home(pagine):
    gruppi = {}
    for p in pagine:
        gruppi.setdefault(p["gruppo"], []).append(p)

    schede = sum(1 for p in pagine if p["file"].startswith("Schede/") and not p["allegato"]
                 and p["file"] != "Schede/_Modello scheda.md")

    md = """# %s

Come lo facciamo, i percorsi per ciascun gruppo, le schede dei singoli incontri.

## Da dove cominciare

Se sei un catechista nuovo, leggi **[Come lo facciamo oggi](/01-come-lo-facciamo-oggi/)**: è il manuale del metodo, e spiega perché facciamo le cose come le facciamo. In fondo c'è il **Decalogo del catechista**.

Se devi preparare un incontro, vai direttamente alla sua **scheda**: le trovi nel menu a sinistra, divise per gruppo.

Se cerchi qualcosa e non sai dov'è, usa la **casella di ricerca** in alto a sinistra: cerca dentro il testo di tutte le pagine.

## Che cosa c'è dentro

| | |
|---|---|
| **Il manuale** | Il metodo, l'anatomia di un incontro, il Decalogo del catechista |
| **I percorsi** | Uno per ciascuno dei tre gruppi, più Prima Comunione e Cresima |
| **Le schede** | %d incontri: obiettivo, messaggio chiave, scaletta, materiale, allegati |
| **I ritiri** | I tre giorni di Prima Comunione: la guida per chi conduce e il quadernino |
| **Materiali comuni** | Canti, preghiere, esame di coscienza |

## Come segnalare qualcosa

Questo testo è **ricostruito dall'archivio**, e in molti punti è stato scritto da zero perché una traccia non c'era. Alcune cose saranno sbagliate. Servono le vostre correzioni.

Ci sono due modi, e nessuno dei due chiede di registrarsi:

- il pulsante **Segnala** accanto a ogni titolo di sezione, o quello che compare in basso a destra mentre leggi
- **seleziona una frase** con il dito o col mouse: compare una bollina *Segnala questa frase*, e la frase arriva citata

**Scrivi anche le cose piccole.** Un materiale sbagliato, un orario che non è mai stato quello, un gioco che si è sempre fatto in un altro modo: sono esattamente le cose che nessuno segnala e che poi fanno perdere mezz'ora a chi prepara.
""" % (TITOLO_SITO, schede)

    return {"file": "__home__", "titolo": TITOLO_SITO, "gruppo": "", "url": "",
            "md": md, "allegato": False}


MODALE = """<h3>Segnala qualcosa</h3>
<p class="lead">Non serve registrarsi. Scrivi anche solo mezza riga.</p>
<div class="fld"><label>Pagina</label><div class="ro" id="m_pag"></div></div>
<div class="fld"><label>Sezione</label><div class="ro" id="m_sez"></div></div>
<div class="fld" id="fr_wrap"><label>La frase, se ce n'è una precisa</label><input type="text" id="m_frase" placeholder="Oppure seleziona il testo nella pagina"></div>
<div class="fld"><label>Che cosa non torna</label><textarea id="m_txt" rows="4" placeholder="Es. «Il gioco non si è mai fatto così: le squadre erano tre, non due.»"></textarea></div>
<div class="fld"><label>Chi sei</label><input type="text" id="m_chi" placeholder="Nome"></div>
<div class="acts"><button onclick="closeSeg()">Annulla</button><button class="pri" onclick="sendSeg()">Invia</button></div>"""


# --------------------------------------------------------------------------
# COSTRUZIONE
# --------------------------------------------------------------------------

def main():
    css = open(os.path.join(RADICE, "tools", "sito.css"), encoding="utf-8").read()
    js = open(os.path.join(RADICE, "tools", "sito.js"), encoding="utf-8").read()

    pagine = raccogli()
    home = pagina_home(pagine)
    tutte = [home] + pagine

    per_url = {p["file"]: p["url"] for p in pagine}

    indice = []
    for p in tutte:
        p["html"], p["sezioni"], testo = converti(p, per_url)
        indice.append({"t": p["titolo"], "u": "/" + p["url"], "g": p["gruppo"], "x": testo[:24000]})

    if os.path.isdir(USCITA):
        shutil.rmtree(USCITA)
    os.makedirs(USCITA)

    for p in tutte:
        cartella = os.path.join(USCITA, p["url"])
        os.makedirs(cartella, exist_ok=True)
        with open(os.path.join(cartella, "index.html"), "w", encoding="utf-8") as f:
            f.write(scrivi_pagina(p, pagine, css, js))

    with open(os.path.join(USCITA, "ricerca.json"), "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False)

    # pagina 404 (GitHub Pages la usa da sola)
    manca = dict(home)
    manca["titolo"] = "Pagina non trovata"
    manca["md"] = "# Pagina non trovata\n\nQuesta pagina non esiste, o è stata spostata.\n\nTorna alla [pagina iniziale](/), oppure cerca quello che ti serve nella casella in alto a sinistra."
    manca["html"], manca["sezioni"], _ = converti(manca, per_url)
    with open(os.path.join(USCITA, "404.html"), "w", encoding="utf-8") as f:
        f.write(scrivi_pagina(manca, pagine, css, js))

    open(os.path.join(USCITA, ".nojekyll"), "w").close()

    peso = sum(os.path.getsize(os.path.join(r, n))
               for r, _, fs in os.walk(USCITA) for n in fs)
    print("pagine costruite: %d" % len(tutte))
    print("indice di ricerca: %d KB" % (os.path.getsize(os.path.join(USCITA, "ricerca.json")) // 1024))
    print("sito completo:     %d KB" % (peso // 1024))
    if not MODULO_URL:
        print("\nNota: MODULO_URL non è ancora configurato in tools/costruisci_sito.py.")
        print("Il pulsante «Segnala» spiegherà che il modulo non è ancora collegato.")


if __name__ == "__main__":
    main()
