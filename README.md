# Monitor PUN

Scarica e visualizza automaticamente il Prezzo Unico Nazionale (PUN) dell'energia elettrica.

## Come funziona

1. **GitHub Actions** esegue `fetch_pun.py` ogni giorno alle 11:00 (ora italiana)
2. Lo script scarica il PUN dal GME e salva in `data/pun.json`
3. Il commit viene fatto automaticamente nel repository
4. **GitHub Pages** serve `index.html` che legge `data/pun.json`

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
├── fetch_pun.py              # script di download
└── index.html                # dashboard web
```

## Dashboard

Dopo il setup, la dashboard è disponibile su:
`https://TUO_USERNAME.github.io/pun-tracker/`

## Fonte dati

I dati vengono scaricati dal **GME – Gestore Mercati Energetici**  
→ https://www.mercatoelettrico.org

Il PUN viene pubblicato il giorno successivo entro le 08:00 UTC.
