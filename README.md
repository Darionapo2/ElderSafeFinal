# ElderSafeFinal

Integrated monitoring system for elderly care combining audio classification, keyword spotting, anomaly detection for entry/exit patterns, and Telegram alerting.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Arduino UNO Q (main.py)                                    │
├─────────────────────────────────────────────────────────────┤
│ - WebSocket :8080 (audio streaming client)                 │
│ - REST API :8000 (GET status, POST events)                 │
│ - KeywordSpotting brick (keyword="aiuto")                  │
│ - AudioClassification brick (crying_baby, scream)          │
│ - Isolation Forest for entry/exit anomaly detection        │
│ - CSV logging for entry/exit events                        │
│ - Telegram Bot API alerts                                  │
│ - Firebase Realtime Database sync                          │
└─────────────────────────────────────────────────────────────┘
              ^                                  ^
              | real-time updates              | reads/writes
              | (Firebase)                     | events
              |                                |
    ┌─────────┴──────────────────┐   ┌────────┴──────────┐
    │ Dashboard Web              │   │ Firebase Realtime  │
    │ (GitHub Pages)             │   │ Database           │
    │ - Email/Password login     │   │ - Events log       │
    │ - Real-time timeline       │   │ - System status    │
    │ - Stats + arm/disarm       │   │ - Configuration    │
    │   (Telegram commands)      │   │                    │
    └────────────────────────────┘   └────────────────────┘
```

## Modular Components

### Entry Point
- **`main.py`** — Main orchestration, coordinates all components

### Core Modules

- **`config.py`** — Constants and configuration (ports, paths, credentials)
- **`models.py`** — `SystemState` class (thread-safe), model loading
- **`csv_handler.py`** — CSV read/write operations
- **`telegram.py`** — Telegram Bot API for alerts
- **`firebase.py`** — Firebase Realtime Database sync
- **`events.py`** — Event logging logic and handlers (keyword, sound, anomaly)
- **`audio_bricks.py`** — KeywordSpotting and AudioClassification setup
- **`anomaly_detection.py`** — Isolation Forest logic and monitoring loop
- **`sensor_loop.py`** — Hardware sensor monitoring (Reed, PIR, NFC)
- **`firebase_commands.py`** — Firebase command polling
- **`api.py`** — Flask REST API endpoints (:8000)

**Server Features**:
- WebSocket Microphone (:8080) for audio streaming
- REST API (:8000) with `/api/status`, `/api/events`, `/api/control`, `/api/health`
- Audio bricks: KeywordSpotting ("aiuto") + AudioClassification (crying_baby, scream)
- Isolation Forest for anomaly detection on entry/exit patterns
- Local CSV logging for entry/exit events
- Telegram alerts for: keywords, dangerous sounds, anomalies
- Firebase events for real-time dashboard

### 2. `dataset_generator.py`
- Generates synthetic dataset with regular daily habits
- Patterns: Mon-Fri exits 8-9am, returns 12-1pm, exits 3-4pm, returns 7-8pm
- Trains Isolation Forest model offline
- Saves model to `isolation_forest_model.pkl`

### 3. `docs/` (Dashboard - GitHub Pages)
- `index.html`: interface with Firebase Email/Password login
- `app.js`: real-time logic from Firebase
- `style.css`: responsive styling
- Displays:
  - Timeline of entries/exits/alarms
  - Statistics (total events, anomalies)
  - System status (armed/disarmed)
  - Arm/disarm commands via Telegram bot

### 4. `bot.py` (optional - Telegram Bot)
- Polls Telegram for user commands
- Arduino executes: arm/disarm, enable/disable features
- Optional if using only unidirectional alerts

## Setup & Running

### Arduino UNO Q

1. **Clone repo and configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your values:
   # - TELEGRAM_BOT_TOKEN (from BotFather)
   # - TELEGRAM_CHAT_ID (your chat ID)
   # - FIREBASE_* fields (from Firebase Console → Project Settings)
   #   Copy fields from service account JSON to .env
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Generate and train Isolation Forest model** (offline):
   ```bash
   python dataset_generator.py
   # Creates: isolation_forest_model.pkl, synthetic_habits.csv
   ```

4. **Start server**:
   ```bash
   python main.py
   ```
   
   Expected output:
   ```
   ElderSafeFinal system starting
   CSV initialized: door_log.csv
   Isolation Forest loaded
   Starting WebSocket microphone on port 8080
   KeywordSpotting brick configured
   Starting REST API on port 8000
   System ready. Press Ctrl+C to stop.
   ```

### Dashboard (GitHub Pages)

1. Enable GitHub Pages in repo settings → deploy from `/docs`
2. Configure Firebase in `docs/app.js`:
   ```javascript
   const firebaseConfig = {
     apiKey: "YOUR_API_KEY",
     authDomain: "your-project.firebaseapp.com",
     databaseURL: "https://your-project.firebaseio.com",
     ...
   };
   ```
3. Create Firebase Email/Password user
4. Push to main → dashboard live at `https://username.github.io/ElderSafeFinal/`

## Features

- Real-time keyword spotting ("aiuto")
- Sound classification (crying_baby, scream, fall, glass_breaking)
- Anomaly detection on entry/exit patterns (Isolation Forest)
- Instant Telegram alerts
- Web dashboard with login
- Local CSV logging on Arduino
- Firebase sync for remote viewing

## Logged Events

```csv
id, datetime, date, time, direction, first_sensor, delta_ms, anomaly_score
1, 2026-06-03 08:15:30.123, 2026-06-03, 08:15:30, entry, REED, 0, 0.15
2, 2026-06-03 12:45:10.456, 2026-06-03, 12:45:10, exit, PIR, 1050000, 0.08
3, 2026-06-03 15:30:45.789, 2026-06-03, 15:30:45, alarm, VOICE, 0, 1.0
```

## Isolation Forest Model

**Features:**
- `hour_of_day`: hour of day (0-23)
- `day_of_week`: day of week (0=Monday, 6=Sunday)
- `time_since_last_event`: seconds since last event
- `event_type`: entry (0) or exit (1)
- `time_of_day_bucket`: time bucket (0=6-12, 1=12-18, 2=18-00, 3=00-06)

**Anomaly threshold:** anomaly_score > 0.5

## Firebase Security Rules

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

## Module Structure

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
├── sensor_loop.py             # Sensor monitoring
├── anomaly_detection.py       # Isolation Forest logic
├── api.py                     # Flask REST API
├── sensors.py                 # Sensor interface
├── dataset_generator.py       # Training script
├── bot.py                     # Optional Telegram bot
├── requirements.txt           # Dependencies
├── sketch.ino                 # Arduino MCU firmware
└── docs/                      # Dashboard (GitHub Pages)
```

## Testing

1. Test modules locally in order: config → models → csv_handler → audio_bricks → main
2. Setup Firebase and update credentials
3. Test dashboard on localhost
4. Push to GitHub and enable GitHub Pages
5. Deploy to Arduino UNO Q
6. Optional: integrate bot.py for Telegram commands
7. End-to-end testing with real sensors

## Requirements

See `requirements.txt`:
- numpy
- websockets
- flask
- requests
- scikit-learn
- firebase-admin
- python-dotenv
