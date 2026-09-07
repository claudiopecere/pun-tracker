# Monitor PUN

Scarica e visualizza automaticamente il Prezzo Unico Nazionale (PUN) dell'energia elettrica.

## Come funziona

1. **GitHub Actions** esegue `fetch_pun.py` ogni giorno alle 11:00 (ora italiana)
2. Lo script recupera i giorni mancanti degli ultimi 7 (oggi compreso) e li salva in `data/pun.json`
3. Il commit viene fatto automaticamente nel repository
4. **GitHub Pages** serve `index.html` che legge `data/pun.json`

Se anche una sola data resta senza dato il workflow **fallisce** e GitHub
invia la notifica via email: i giorni mancanti vengono ritentati nei run
successivi finché rientrano nella finestra dei 7 giorni. Per date più
vecchie: Actions → "Download PUN giornaliero" → Run workflow, indicando la data.

## Setup (5 minuti)

### 1. Crea il repository su GitHub
- Vai su github.com → New repository
- Nome: `pun-tracker`
- Visibilità: **Public** (necessario per GitHub Pages gratuito)
- Non inizializzare con README

### 2. Carica i file
```bash
git init
git add .
git commit -m "primo commit"
git branch -M main
git remote add origin https://github.com/TUO_USERNAME/pun-tracker.git
git push -u origin main
```

### 3. Abilita GitHub Pages
- Repository → Settings → Pages
- Source: **Deploy from a branch**
- Branch: `main` / `/ (root)`
- Salva

### 4. Aggiorna index.html
Modifica le prime righe di `index.html`:
```js
const GITHUB_USER = 'TUO_USERNAME';  // ← il tuo username GitHub
const GITHUB_REPO = 'pun-tracker';
```

### 5. Abilita i permessi per GitHub Actions
- Repository → Settings → Actions → General
- Workflow permissions: **Read and write permissions** ✓
- Salva

Il workflow partirà automaticamente ogni giorno. Puoi anche avviarlo manualmente:
- Repository → Actions → "Download PUN giornaliero" → Run workflow

## Struttura

```
pun-tracker/
├── .github/
│   └── workflows/
│       └── fetch_pun.yml     # automazione giornaliera
├── data/
│   └── pun.json              # dati storici (aggiornato automaticamente)
├── fetch_pun.py              # script di download (fonti in cascata)
├── gme.py                    # client dell'API del sito GME
└── index.html                # dashboard web
```

## Uso manuale

```bash
python fetch_pun.py               # giorni mancanti degli ultimi 7
python fetch_pun.py 2026-04-14    # una data specifica
python gme.py 2026-01-01 2026-01-31   # stampa il PUN GME di un intervallo, senza salvare
```

## Dashboard

Dopo il setup, la dashboard è disponibile su:
`https://TUO_USERNAME.github.io/pun-tracker/`

## Fonte dati

Fonte primaria: **GME – Gestore dei Mercati Energetici**, tramite l'API
(non documentata) che alimenta la pagina pubblica *Esiti → MGP → PUN Index GME*
su https://gme.mercatoelettrico.org. Il PUN giornaliero è la media aritmetica
dei 24 prezzi orari. Dettagli in `gme.py`.

Fonti di riserva, usate solo se il GME non risponde: Papernest (ultimi 7 giorni),
QualEnergia (solo se la data esposta coincide con quella richiesta: la homepage
mostra il prezzo day-ahead, cioè di domani) e AbbassaLeBollette.

Il GME pubblica il PUN del giorno D il giorno D-1, dopo l'esito del mercato
del giorno prima (MGP), verso le 13:00. Il campo `fonte` di ogni record indica
da dove è arrivato il valore.

## Storico

Il 07/09/2026 l'intera serie da novembre 2025 è stata ricostruita dal GME
(nota `ricostruzione storica`): i valori raccolti in precedenza dalle fonti di
riserva contenevano 27 giorni sfasati di una data e 4 medie mensili al posto
dei valori giornalieri.
