# ElderSafeFinal

Sistema integrato di monitoraggio per anziani che combina sound classification, keyword spotting, anomaly detection per pattern entrata/uscita, e alerting via Telegram.

## Architettura

```
┌─────────────────────────────────────────────────────────────┐
│ Arduino UNO Q (server.py)                                  │
├─────────────────────────────────────────────────────────────┤
│ ▪ WS :8080  ← Audio streaming client                       │
│ ▪ REST :8000 (GET status, POST events)                     │
│ ▪ KeywordSpotting brick (keyword="aiuto")                  │
│ ▪ AudioClassification brick (crying_baby, scream)          │
│ ▪ Isolation Forest for entry/exit anomaly detection        │
│ ▪ CSV logging entrate/uscite locali                        │
│ ▪ POST alerts a Telegram Bot API                           │
│ ▪ POST events a Firebase Realtime Database                 │
└─────────────────────────────────────────────────────────────┘
              ▲                                  ▲
              │ real-time updates              │ reads/writes
              │ (Firebase)                     │ events
              │                                │
    ┌─────────┴──────────────────┐   ┌────────┴──────────┐
    │ Dashboard Web              │   │ Firebase Realtime  │
    │ (GitHub Pages)             │   │ Database           │
    │ ▪ Email/Password login     │   │ ▪ Events log       │
    │ ▪ Real-time timeline       │   │ ▪ System status    │
    │ ▪ Stats + arm/disarm via   │   │ ▪ Config           │
    │   Telegram (polling)       │   │                    │
    └────────────────────────────┘   └────────────────────┘
```

## Componenti Modulari

### Entry Point
- **`main.py`** — Orchestrazione principale, coordina tutti i componenti

### Core Modules

- **`config.py`** — Costanti e configurazioni (porte, path, credenziali)
- **`models.py`** — `SystemState` class (thread-safe), caricamento modello
- **`csv_handler.py`** — Lettura/scrittura log CSV
- **`telegram.py`** — Telegram Bot API per alerts
- **`firebase.py`** — Firebase Realtime Database sync
- **`events.py`** — Logica event logging + handlers (keyword, sound, anomaly)
- **`audio_bricks.py`** — Setup KeywordSpotting + AudioClassification
- **`anomaly_detection.py`** — Isolation Forest logic + loop di controllo
- **`api.py`** — Flask REST API endpoints (:8000)

**Caratteristiche del Server**:
- WebSocket Microphone (:8080) per audio streaming
- REST API (:8000) con `/api/status`, `/api/events`, `/api/control`, `/api/health`
- Integrazione bricks: KeywordSpotting ("aiuto") + AudioClassification (crying_baby, scream, etc)
- Isolation Forest per anomaly detection su pattern entry/exit
- CSV logging locale entrate/uscite
- POST alerts Telegram per: keyword, suoni pericolosi, anomalie
- POST events Firebase per dashboard real-time

### 2. `dataset_generator.py`
- Genera dataset sintetico con abitudini regolari di una persona
- Patterns: lunedì-venerdì esce 8-9, torna 12-13, esce 15-16, torna 19-20
- Allena Isolation Forest offline
- Salva modello in `isolation_forest_model.pkl`

### 3. `docs/` (Dashboard - GitHub Pages)
- `index.html`: interfaccia con login Firebase Email/Password
- `app.js`: logica real-time da Firebase
- `style.css`: styling responsive
- Mostra:
  - Timeline entrate/uscite/allarmi
  - Stats (total events, anomalies)
  - Status sistema (armed/disarmed)
  - Comandi arm/disarm via Telegram bot polling

### 4. `bot.py` (opzionale - Telegram)
- Polling Telegram per comandi da dashboard
- Arduino esegue: arm/disarm, enable/disable features
- Non necessario se usi solo alert unidirezionali

## Setup & Avvio

### Arduino UNO Q

1. **Clona repo e configura variabili**:
   ```bash
   cp .env.example .env
   # Modifica .env con i tuoi valori:
   # - TELEGRAM_BOT_TOKEN (da BotFather)
   # - TELEGRAM_CHAT_ID (il tuo chat ID)
   # - FIREBASE_* fields (da Firebase Console → Project Settings → Service Accounts)
   #   Copia i campi dal JSON service account nel .env (no file path needed!)
   ```

2. **Installa dipendenze**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Genera/allena Isolation Forest model** (offline):
   ```bash
   python dataset_generator.py
   # Crea: isolation_forest_model.pkl, synthetic_habits.csv
   ```

4. **Avvia server**:
   ```bash
   python main.py
   ```
   
   Output atteso:
   ```
   ElderSafeFinal Server - Arduino UNO Q
   ✓ CSV initialized
   ✓ Loaded Isolation Forest
   Starting WebSocket Microphone on port 8080...
   ✓ KeywordSpotting configured
   ✓ AudioClassification configured
   Starting REST API on port 8000...
   🟢 All systems ready. Press Ctrl+C to stop.
   ```

### Dashboard (GitHub Pages)

1. Abilita GitHub Pages in repo settings → deploy from `/docs`
2. Configura Firebase nel `docs/app.js`:
   ```javascript
   const firebaseConfig = {
     apiKey: "YOUR_API_KEY",
     authDomain: "your-project.firebaseapp.com",
     databaseURL: "https://your-project.firebaseio.com",
     ...
   };
   ```
3. Crea utente Firebase Email/Password
4. Push to main → dashboard live su `https://username.github.io/ElderSafeFinal/`

## Features

- ✅ Real-time keyword spotting ("aiuto")
- ✅ Sound classification (crying_baby, scream, fall, glass_breaking)
- ✅ Anomaly detection entry/exit patterns (Isolation Forest)
- ✅ Alert Telegram istantanei
- ✅ Dashboard web con login
- ✅ CSV logging locale Arduino
- ✅ Firebase sync per remote viewing

## Events Logged

```csv
id, datetime, date, time, direction, first_sensor, delta_ms, anomaly_score
1, 2026-06-03 08:15:30.123, 2026-06-03, 08:15:30, entry, REED, 0, 0.15
2, 2026-06-03 12:45:10.456, 2026-06-03, 12:45:10, exit, PIR, 1050000, 0.08
3, 2026-06-03 15:30:45.789, 2026-06-03, 15:30:45, alarm, VOICE, 0, 1.0
```

## Modello Isolation Forest

**Features:**
- `hour_of_day`: ora del giorno (0-23)
- `day_of_week`: giorno della settimana (0=lunedì, 6=domenica)
- `time_since_last_event`: secondi dall'ultimo evento
- `event_type`: entry (0) o exit (1)
- `time_of_day_bucket`: fascia oraria (0=6-12, 1=12-18, 2=18-00, 3=00-06)

**Threshold anomalia:** anomaly_score > 0.5

## Configurazione Firestore Security Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /elderly/{uid} {
      allow read: if request.auth.uid == uid;
      allow write: if request.auth.uid == uid || request.auth.token.admin == true;
    }
  }
}
```

## Struttura dei Moduli

```
ElderSafeFinal/
├── main.py                    # Entry point
├── config.py                  # Constants
├── models.py                  # SystemState + model loading
├── csv_handler.py             # CSV I/O
├── telegram.py                # Telegram alerts
├── firebase.py                # Firebase sync
├── events.py                  # Event handlers
├── audio_bricks.py            # Brick setup
├── anomaly_detection.py       # Isolation Forest logic
├── api.py                     # Flask REST API
├── dataset_generator.py       # Training script
├── bot.py                     # Optional Telegram bot
├── requirements.txt           # Dependencies
└── docs/                      # Dashboard (GitHub Pages)
```

## TODO

- [ ] Test moduli localmente (in ordine: config → models → csv_handler → audio_bricks → main)
- [ ] Setup Firebase e aggiorna credenziali
- [ ] Test dashboard su localhost
- [ ] Push a GitHub e abilita GitHub Pages
- [ ] Deploy su Arduino UNO Q
- [ ] Integrazione bot.py (opzionale)
- [ ] Testing end-to-end con sensori reali