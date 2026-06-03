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

## Componenti

### 1. `server.py` (Arduino)
- Server WebSocket per audio streaming (:8080)
- REST API per status e control (:8000)
- Integra KeywordSpotting + AudioClassification bricks
- Isolation Forest model per anomaly detection
- CSV logging entrate/uscite
- POST alerts a Telegram quando rileva:
  - Keyword "aiuto"
  - Suoni pericolosi (scream, crying_baby)
  - Anomalia entry/exit pattern
- POST events a Firebase per dashboard

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

## Setup

### Arduino UNO Q

1. Clona questo repo sull'Arduino
2. Configura Firebase:
   ```bash
   export FIREBASE_DATABASE_URL="https://your-project.firebaseio.com"
   export FIREBASE_SERVICE_ACCOUNT_JSON="/path/to/serviceAccountKey.json"
   ```
3. Configura Telegram:
   ```bash
   export TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
   export TELEGRAM_CHAT_ID="9876543210"
   ```
4. Installa dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
5. Genera/allena Isolation Forest model:
   ```bash
   python dataset_generator.py
   ```
6. Avvia server:
   ```bash
   python server.py
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

## TODO

- [ ] Implementare server.py con bricks
- [ ] Implementare dataset_generator.py
- [ ] Implementare dashboard (index.html, app.js)
- [ ] Testing su Arduino UNO Q
- [ ] Integrazione bot.py (opzionale)
