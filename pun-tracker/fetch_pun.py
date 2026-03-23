#!/usr/bin/env python3
"""
Scarica il PUN giornaliero dal GME (Gestore Mercati Energetici)
e aggiorna data/pun.json nel repository.
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
import urllib.request
import urllib.error

DATA_FILE = "data/pun.json"


def fetch_pun_from_gme(target_date: date) -> float | None:
    """
    Scarica il PUN dal file XML/CSV pubblicato dal GME.
    GME pubblica i prezzi orari del giorno precedente.
    URL: https://www.mercatoelettrico.org/It/Tools/Accessodati.aspx
    oppure endpoint diretto dei prezzi zonali MGP.
    """
    year = target_date.strftime("%Y")
    month = target_date.strftime("%m")
    day = target_date.strftime("%d")

    # Endpoint XML dei prezzi MGP del GME
    url = (
        f"https://www.mercatoelettrico.org/DesktopModules/GmeDownload/API/ExcelDownload"
        f"/downloadzipfile?DataInizio={day}{month}{year}&DataFine={day}{month}{year}"
        f"&Mercato=MGP&Grandezza=PUN&Zona=PUN&Pagina=1"
    )

    # Fallback: endpoint dati storici GME (CSV prezzi MGP)
    url_csv = (
        f"https://storico.mercatoelettrico.org/DesktopModules/GmeDownload/API/ExcelDownload"
        f"/downloadzipfile?DataInizio={day}{month}{year}&DataFine={day}{month}{year}"
        f"&Mercato=MGP&Grandezza=PUN&Zona=PUN&Pagina=1"
    )

    for attempt_url in [url, url_csv]:
        try:
            req = urllib.request.Request(
                attempt_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; PUN-Tracker/1.0)",
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                # Il file contiene righe tipo: "01/01/2024;98.50;..."
                # Cerca pattern numerici che rappresentano prezzi
                numbers = re.findall(r"[\d]+[.,][\d]+", content)
                if numbers:
                    # Il PUN medio giornaliero è la media delle 24 ore
                    values = []
                    for n in numbers:
                        try:
                            v = float(n.replace(",", "."))
                            if 0 < v < 1000:  # range ragionevole €/MWh
                                values.append(v)
                        except ValueError:
                            pass
                    if values:
                        return round(sum(values) / len(values), 2)
        except Exception as e:
            print(f"[WARN] Tentativo fallito ({attempt_url[:60]}...): {e}")
            continue

    return None


def fetch_pun_entsoe(target_date: date) -> float | None:
    """
    Fallback: ENTSO-E Transparency Platform (dati pubblici, no API key).
    Restituisce il prezzo day-ahead per l'Italia Nord (approssimazione PUN).
    """
    # ENTSO-E richiede registrazione per API completa.
    # Usiamo l'endpoint pubblico non autenticato per i prezzi IT.
    day_str = target_date.strftime("%Y%m%d")
    url = (
        f"https://transparency.entsoe.eu/transmission-domain/r2/dayAheadPrices/show"
        f"?name=&defaultValue=false&viewType=TABLE&areaCode=10Y0-RTE------F"  # placeholder
        f"&atch=false&dateTime.dateTime={day_str}+00:00|UTC|DAY&dateTime.endDateTime={day_str}+23:00|UTC|DAY"
    )
    # ENTSO-E senza token ritorna HTML — skip, usiamo solo come placeholder
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

    # Determina la data da scaricare (default: ieri, GME pubblica il giorno dopo)
    if len(sys.argv) > 1:
        try:
            target = date.fromisoformat(sys.argv[1])
        except ValueError:
            print(f"[ERR] Data non valida: {sys.argv[1]}. Usa formato YYYY-MM-DD.")
            sys.exit(1)
    else:
        target = date.today() - timedelta(days=1)

    date_str = target.isoformat()
    print(f"[INFO] Download PUN per {date_str}...")

    if record_exists(records, date_str):
        print(f"[SKIP] Dato già presente per {date_str}")
        sys.exit(0)

    pun = fetch_pun_from_gme(target)

    if pun is None:
        pun = fetch_pun_entsoe(target)

    if pun is None:
        print(f"[ERR] Impossibile scaricare il PUN per {date_str}")
        print("[INFO] Controlla manualmente su https://www.mercatoelettrico.org")
        # Non uscire con errore — permette al workflow di continuare
        sys.exit(0)

    record = {
        "data": date_str,
        "pun": pun,
        "picco": "",
        "note": "import automatico GME",
        "fonte": "GME",
        "ts": datetime.utcnow().isoformat() + "Z",
    }

    records.append(record)
    save_data(records)
    print(f"[OK] PUN {date_str}: {pun} €/MWh")


if __name__ == "__main__":
    main()
