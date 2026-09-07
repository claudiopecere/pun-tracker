#!/usr/bin/env python3
"""
Client per l'API pubblica non documentata del sito GME (Gestore dei
Mercati Energetici) che alimenta la pagina "Esiti > MGP > PUN Index GME".

La pagina è un'app Angular che chiama
    /DesktopModules/GmeEsitiPrezziME/API/item/GetMEPrezzi
con quattro intestazioni prese dal framework DNN della pagina stessa:
ModuleId, TabId, RequestVerificationToken (anti-forgery) e userid.
Senza queste intestazioni, e senza i cookie della pagina, l'API risponde 401.

Procedura:
  1. GET della pagina esiti -> cookie di sessione, token anti-forgery,
     TabId e ModuleId dal sorgente HTML;
  2. GET dell'API con intestazioni e cookie -> lista di prezzi orari
     {df: yyyymmdd, h: ora, p: prezzo €/MWh};
  3. il PUN giornaliero è la media aritmetica delle 24 ore.

Verificato il 07/09/2026: la media oraria coincide con il PUN giornaliero
pubblicato da Papernest e QualEnergia al centesimo.
"""

import http.cookiejar
import json
import re
import urllib.request
from collections import defaultdict
from datetime import date

BASE = "https://gme.mercatoelettrico.org"
PAGE = BASE + "/en-us/Home/Results/Electricity/MGP/Results/PUN/ResultsMGP"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class ClientGME:
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cj)
        )
        self._hdr = None

    def _inizializza(self):
        """Scarica la pagina esiti e ricava token, TabId e ModuleId."""
        req = urllib.request.Request(
            PAGE, headers={"User-Agent": UA, "Accept": "text/html"}
        )
        with self._opener.open(req, timeout=self.timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        tok = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
        tab = re.search(r"sf_tabId`:`(\d+)`", html)
        mod = re.search(r'"ModuleId":(\d+)[^<]*"routingWebAPI":"([^"]+)"', html)
        if not (tok and tab and mod):
            raise RuntimeError(
                "GME: impossibile ricavare token/TabId/ModuleId dalla pagina "
                f"(token={bool(tok)}, tab={bool(tab)}, modulo={bool(mod)})"
            )
        self._api = BASE + mod.group(2)
        self._hdr = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": PAGE,
            "ModuleId": mod.group(1),
            "TabId": tab.group(1),
            "RequestVerificationToken": tok.group(1),
            "userid": "-1",
        }

    def prezzi_orari(self, da: date, a: date) -> list[dict]:
        """Prezzi orari PUN nell'intervallo [da, a], estremi inclusi."""
        if self._hdr is None:
            self._inizializza()
        url = (
            f"{self._api}item/GetMEPrezzi"
            f"?DataInizio={da:%Y%m%d}&DataFine={a:%Y%m%d}"
            f"&Granularita=h&Mercato=MGP&Zona=PUN&Tipologia=PUN"
        )
        req = urllib.request.Request(url, headers=self._hdr)
        with self._opener.open(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def pun_giornaliero(self, da: date, a: date) -> dict[str, float]:
        """
        PUN medio giornaliero (€/MWh, 2 decimali) per data ISO.
        Restituisce solo i giorni con almeno 23 ore (cambio ora legale
        compreso): un giorno parziale non viene considerato valido.
        """
        per_giorno = defaultdict(list)
        for r in self.prezzi_orari(da, a):
            per_giorno[str(r["df"])].append(float(r["p"]))
        out = {}
        for k, v in per_giorno.items():
            if len(v) >= 23:
                iso = f"{k[:4]}-{k[4:6]}-{k[6:8]}"
                out[iso] = round(sum(v) / len(v), 2)
        return out


if __name__ == "__main__":
    import sys
    from datetime import timedelta

    if len(sys.argv) == 3:
        da, a = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
    else:
        a = date.today()
        da = a - timedelta(days=7)
    for giorno, pun in sorted(ClientGME().pun_giornaliero(da, a).items()):
        print(giorno, pun)
