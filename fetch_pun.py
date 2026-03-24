#!/usr/bin/env python3
"""
Scarica il PUN giornaliero da Papernest (fonte: dati GME rielaborati).
Fallback: QualEnergia.
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
import urllib.request

DATA_FILE = "data/pun.json"


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


def parse_pun_from_papernest(html: str, target_date: date) -> float | None:
    """
    Papernest pubblica una tabella con righe tipo:
    <td>23/03/2026</td><td>0.1652</td>
    """
    day = target_date.strftime("%d/%m/%Y")
    # Cerca la data nel formato DD/MM/YYYY seguita dal valore
    pattern = re.compile(
        re.escape(day) + r"[^<]*</td>\s*<td[^>]*>\s*([\d]+[.,][\d]+)"
    )
    m = pattern.search(html)
    if m:
        val = float(m.group(1).replace(",", "."))
        # Papernest riporta in €/kWh → converti in €/MWh
        if val < 2:
            val = round(val * 1000, 2)
        return val

    # Alternativa: cerca tutte le celle con date e valori
    rows = re.findall(
        r"(\d{2}/\d{2}/\d{4})[^<]*</td>\s*<td[^>]*>\s*([\d]+[.,][\d]+)",
        html
    )
    for d_str, v_str in rows:
        if d_str == day:
            val = float(v_str.replace(",", "."))
            if val < 2:
                val = round(val * 1000, 2)
            return val

    return None


def fetch_from_papernest(target_date: date) -> float | None:
    url = "https://www.papernest.it/luce-gas/mercato-energetico/pun/"
    print(f"[INFO] Provo Papernest: {url}")
    html = fetch_html(url)
    if not html:
        return None
    val = parse_pun_from_papernest(html, target_date)
    if val:
        print(f"[OK] Papernest → {val} €/MWh")
    return val


def fetch_from_qualenergia(target_date: date) -> float | None:
    """
    QualEnergia pubblica il PUN nella barra in cima.
    Estratta con regex sul testo 'PUN: NNN.NN €/MWh'.
    Solo se la data corrisponde a oggi/ieri.
    """
    url = "https://www.qualenergia.it/"
    print(f"[INFO] Provo QualEnergia: {url}")
    html = fetch_html(url)
    if not html:
        return None
    # Cerca pattern: PUN: 165.64 €/MWh (giorno)
    m = re.search(r"PUN:\s*([\d]+[.,][\d]+)\s*€/MWh\s*\((\d+)\s*mar\b", html, re.I)
    if not m:
        m = re.search(r"PUN:\s*([\d]+[.,][\d]+)\s*€/MWh", html)
    if m:
        val = float(m.group(1).replace(",", "."))
        if val > 0:
            print(f"[OK] QualEnergia → {val} €/MWh")
            return round(val, 2)
    return None


def fetch_from_abbassalebollette(target_date: date) -> float | None:
    """
    Abbassalebollette pubblica tabella mensile con PUN giornaliero.
    """
    year = target_date.strftime("%Y")
    month_it = [
        "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
    ][target_date.month]
    url = f"https://www.abbassalebollette.it/glossario/pun-prezzo-unico-nazionale/"
    print(f"[INFO] Provo AbbassaLeBollette: {url}")
    html = fetch_html(url)
    if not html:
        return None
    day = target_date.strftime("%d/%m/%Y")
    pattern = re.compile(
        re.escape(day) + r"[^<]*</td>\s*<td[^>]*>\s*([\d]+[.,][\d]+)"
    )
    m = pattern.search(html)
    if m:
        val = float(m.group(1).replace(",", "."))
        if val < 2:
            val = round(val * 1000, 2)
        print(f"[OK] AbbassaLeBollette → {val} €/MWh")
        return val
    return None


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


def record_exists(records: list, date_str: str) -> bool:
    return any(r["data"] == date_str for r in records)


def main():
    records = load_data()

    # Data target: default ieri (GME pubblica il giorno dopo)
    if len(sys.argv) > 1:
        try:
            target = date.fromisoformat(sys.argv[1])
        except ValueError:
            print(f"[ERR] Data non valida: {sys.argv[1]}")
            sys.exit(1)
    else:
        target = date.today() - timedelta(days=1)

    date_str = target.isoformat()
    print(f"[INFO] Download PUN per {date_str} ...")

    if record_exists(records, date_str):
        print(f"[SKIP] Dato già presente per {date_str}")
        sys.exit(0)

    # Prova le fonti in ordine
    pun = fetch_from_papernest(target)

    if pun is None:
        pun = fetch_from_qualenergia(target)

    if pun is None:
        pun = fetch_from_abbassalebollette(target)

    if pun is None:
        print(f"[ERR] Nessuna fonte ha restituito il PUN per {date_str}")
        print("[INFO] Inserisci il dato manualmente su github.com/claudiopecere/pun-tracker")
        sys.exit(0)

    record = {
        "data": date_str,
        "pun": pun,
        "picco": "",
        "note": "import automatico",
        "ts": datetime.utcnow().isoformat() + "Z",
    }

    records.append(record)
    save_data(records)
    print(f"[OK] PUN {date_str}: {pun} €/MWh")


if __name__ == "__main__":
    main()
