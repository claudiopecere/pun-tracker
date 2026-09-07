#!/usr/bin/env python3
"""
Scarica il PUN giornaliero (€/MWh) e aggiorna data/pun.json.

Fonti, in ordine di priorità:
  1. GME  - API del sito ufficiale (vedi gme.py): media delle 24 ore.
            Copre qualsiasi intervallo storico ed è la fonte primaria.
  2. Papernest   - tabella degli ultimi 7 giorni (dati GME rielaborati), €/kWh
  3. QualEnergia - barra in homepage "PUN: NNN,NN €/MWh (G mes)": viene usata
                   SOLO se la data indicata coincide con quella richiesta,
                   perché espone il prezzo day-ahead (cioè di domani).
  4. AbbassaLeBollette - tabella giornaliera, €/kWh

Comportamento:
  - senza argomenti: recupera tutti i giorni mancanti degli ultimi 7,
    oggi compreso (il PUN di oggi è pubblicato dal GME il giorno prima),
    così un giorno saltato viene ritentato automaticamente nei run successivi;
  - con argomento YYYY-MM-DD: recupera solo quella data;
  - esce con codice 1 se almeno una data richiesta resta senza dato,
    così il workflow fallisce e GitHub manda la notifica. I dati
    recuperati vengono comunque salvati prima di uscire.
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
import urllib.request

from gme import ClientGME

DATA_FILE = "data/pun.json"
GIORNI_FINESTRA = 7

MESI_IT = ["gen", "feb", "mar", "apr", "mag", "giu",
           "lug", "ago", "set", "ott", "nov", "dic"]


def fetch_html(url: str) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "it-IT,it;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[WARN] fetch fallito ({url[:70]}): {e}")
        return None


def kwh_to_mwh(val: float) -> float:
    """Le tabelle in €/kWh riportano valori < 2: converte in €/MWh."""
    return round(val * 1000, 2) if val < 2 else round(val, 2)


def parse_tabella_giornaliera(html: str, target_date: date) -> float | None:
    """Cerca una riga <td>DD/MM/YYYY</td><td>valore</td>."""
    day = target_date.strftime("%d/%m/%Y")
    m = re.search(re.escape(day) + r"[^<]*</td>\s*<td[^>]*>\s*([\d]+[.,][\d]+)", html)
    if not m:
        return None
    return kwh_to_mwh(float(m.group(1).replace(",", ".")))


# ---------------------------------------------------------------- fonti

class GME:
    """Fonte primaria: una sola chiamata per tutto l'intervallo richiesto."""
    nome = "GME"

    def __init__(self, da: date, a: date):
        self._da, self._a = da, a
        self._valori = None

    def get(self, target_date: date) -> float | None:
        if self._valori is None:
            self._valori = {}
            print(f"[INFO] Scarico GME: {self._da} -> {self._a}")
            try:
                self._valori = ClientGME().pun_giornaliero(self._da, self._a)
            except Exception as e:
                print(f"[WARN] GME non raggiungibile: {e}")
        return self._valori.get(target_date.isoformat())


class Papernest:
    nome = "Papernest"
    url = "https://www.papernest.it/luce-gas/mercato-energetico/pun/"

    def __init__(self):
        self._html = None
        self._tentato = False

    def get(self, target_date: date) -> float | None:
        # la pagina è unica per tutti i giorni: la scarico una volta sola
        if not self._tentato:
            self._tentato = True
            print(f"[INFO] Scarico {self.nome}: {self.url}")
            self._html = fetch_html(self.url)
        if not self._html:
            return None
        return parse_tabella_giornaliera(self._html, target_date)


class QualEnergia:
    nome = "QualEnergia"
    url = "https://www.qualenergia.it/"

    def __init__(self):
        self._html = None
        self._tentato = False

    def get(self, target_date: date) -> float | None:
        if not self._tentato:
            self._tentato = True
            print(f"[INFO] Scarico {self.nome}: {self.url}")
            self._html = fetch_html(self.url)
        if not self._html:
            return None
        # es. "PUN: 218,93 €/MWh (7 sett)"  - il testo può avere l'euro
        # codificato male, quindi accetto qualsiasi carattere prima di /MWh
        m = re.search(
            r"PUN:\s*([\d]+[.,][\d]+)\s*\S{0,3}/MWh\s*\((\d{1,2})\s*([a-zà]+)\)",
            self._html, re.I,
        )
        if not m:
            print(f"[WARN] {self.nome}: pattern PUN con data non trovato")
            return None
        val = float(m.group(1).replace(",", "."))
        giorno = int(m.group(2))
        mese_txt = m.group(3).lower()[:3]
        if mese_txt not in MESI_IT:
            print(f"[WARN] {self.nome}: mese non riconosciuto '{m.group(3)}'")
            return None
        mese = MESI_IT.index(mese_txt) + 1
        # il sito non indica l'anno: lo deduco dalla data richiesta
        if (giorno, mese) != (target_date.day, target_date.month):
            print(f"[INFO] {self.nome}: espone il {giorno:02d}/{mese:02d}, "
                  f"non il {target_date:%d/%m} richiesto -> ignorato")
            return None
        return round(val, 2)


class AbbassaLeBollette:
    nome = "AbbassaLeBollette"
    url = "https://www.abbassalebollette.it/glossario/pun-prezzo-unico-nazionale/"

    def __init__(self):
        self._html = None
        self._tentato = False

    def get(self, target_date: date) -> float | None:
        if not self._tentato:
            self._tentato = True
            print(f"[INFO] Scarico {self.nome}: {self.url}")
            self._html = fetch_html(self.url)
        if not self._html:
            return None
        return parse_tabella_giornaliera(self._html, target_date)


# ---------------------------------------------------------------- dati

def load_data() -> list:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_data(records: list):
    os.makedirs("data", exist_ok=True)
    records.sort(key=lambda r: r["data"])
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"[OK] Salvati {len(records)} record in {DATA_FILE}")


def date_presenti(records: list) -> set:
    return {r["data"] for r in records}


# ---------------------------------------------------------------- main

def main():
    records = load_data()
    presenti = date_presenti(records)

    if len(sys.argv) > 1:
        try:
            targets = [date.fromisoformat(sys.argv[1])]
        except ValueError:
            print(f"[ERR] Data non valida: {sys.argv[1]}")
            sys.exit(1)
    else:
        oggi = date.today()
        targets = [oggi - timedelta(days=n) for n in range(GIORNI_FINESTRA - 1, -1, -1)]

    da_fare = [t for t in targets if t.isoformat() not in presenti]
    if not da_fare:
        print(f"[SKIP] Nessuna data mancante tra {targets[0]} e {targets[-1]}")
        sys.exit(0)
    print(f"[INFO] Date da recuperare: {', '.join(t.isoformat() for t in da_fare)}")

    fonti = [GME(da_fare[0], da_fare[-1]), Papernest(), QualEnergia(), AbbassaLeBollette()]
    mancanti = []
    nuovi = 0

    for target in da_fare:
        date_str = target.isoformat()
        pun, fonte = None, None
        for f in fonti:
            pun = f.get(target)
            if pun is not None and pun > 0:
                fonte = f.nome
                break
            pun = None
        if pun is None:
            print(f"[ERR] Nessuna fonte ha restituito il PUN per {date_str}")
            mancanti.append(date_str)
            continue
        records.append({
            "data": date_str,
            "pun": pun,
            "picco": "",
            "note": "import automatico",
            "fonte": fonte,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        })
        nuovi += 1
        print(f"[OK] PUN {date_str}: {pun} €/MWh ({fonte})")

    if nuovi:
        save_data(records)

    if mancanti:
        print("[ERR] Date rimaste senza dato: " + ", ".join(mancanti))
        sys.exit(1)


if __name__ == "__main__":
    main()
