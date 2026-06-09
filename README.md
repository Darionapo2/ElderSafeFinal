# SafeNet

SafeNet is a smart home-monitoring and safety system built on the **Arduino UNO Q**.
It combines physical entry/exit detection, voice keyword spotting, and a learned
anomaly-detection model that understands a person's daily habits and raises an
alert when something unusual happens (for example, the person leaves and does not
return within the expected time window). Alerts are delivered to a web dashboard
and to Telegram, and the whole system is configurable and controllable remotely.

---

## 1. Hardware: Arduino UNO Q

The UNO Q carries two processors on a single board that do not share memory:

- **MPU (Qualcomm, quad-core Cortex-A)** runs a full **Linux** environment. All of
  the Python application runs here: audio processing, the REST API, Firebase sync,
  the machine-learning models, and the alerting logic.
- **MCU (STM32, Cortex-M)** runs the real-time Arduino sketch (`sketch.ino`). It
  owns the GPIO pins: it reads the reed switch and PIR sensor, drives the LEDs and
  buzzer, and talks to the RFID/NFC reader over SPI.

### The Bridge

The two processors communicate through the **Bridge**, a MessagePack-RPC channel
over a Unix socket (`/var/run/arduino-router.sock`). The Python side calls
functions that physically execute on the microcontroller:

```python
from arduino.app_utils import Bridge

state = Bridge.call("get_reed_state")   # runs digitalRead() on the MCU
Bridge.call("beep_alarm")               # drives the buzzer on the MCU
```

On the firmware side, every callable is registered in `sketch.ino`:

```cpp
Bridge.provide("get_reed_state", get_reed_state);
Bridge.provide("beep_alarm",    beep_alarm);
```

The Bridge client is a thread-safe singleton with automatic reconnection and
handler re-registration, so a microcontroller reset is recovered transparently.

### Pin map (`sketch.ino`)

| Pin | Device           | Bridge method(s)                         |
|-----|------------------|------------------------------------------|
| 2   | Reed switch      | `get_reed_state`                         |
| 3   | PIR motion       | `get_pir_state`                          |
| 4   | Green LED        | `set_led_green`                          |
| 7   | Red LED          | `set_led_red`                            |
| 8   | Buzzer           | `beep_entry`, `beep_exit`, `beep_alarm`  |
| 9   | RFID RST         | (MFRC522)                                |
| 10  | RFID SS          | `get_nfc_armed`                          |

An RFID badge toggles the global armed state directly on the MCU; the Python side
reads the resulting state through the Bridge and synchronizes it to the cloud.

---

## 2. System architecture

```
            MCU (sketch.ino)                        MPU - Linux (main.py)
            ----------------                        ---------------------
   reed / PIR / RFID  --digitalRead-->|
   LEDs / buzzer      --tone/write--->|  Bridge RPC
                                      |<----- sensors.py / sensor_loop.py
                                      |       (entry/exit/NFC detection)
   USB mic --audio--> WebSocket :8080 -----> Microphone -> KeywordSpotting ("aiuto")
                                      |
                                      |  REST API :8000   (status / events / control)
                                      |  Firebase sync    (status, events, monitoring, config)
                                      |  Telegram alerts
                                      |  Anomaly models   (Isolation Forest + absence model)
                                      |
            +-------------------------+--------------------------+
            |                                                    |
     Firebase Realtime DB                                  Telegram Bot
            |                                                    |
     Web Dashboard (GitHub Pages)                          bot.py (optional)
```

The system is **push-based**: the device pushes its state and events to Firebase,
and the dashboard and bot subscribe to them. No inbound port forwarding is needed.

---

## 3. Subsystems

### 3.1 Passage detection (entry / exit / NFC)

`sensor_loop.py` polls the sensors through `sensors.py` every 50 ms and detects
the direction of a passage from the order in which the reed switch and PIR fire
(reed-then-PIR is an entry, PIR-then-reed is an exit), with debouncing to reject
noise. Each passage is logged to the local CSV (`door_log.csv`) and pushed to
Firebase. An NFC badge arms or disarms the whole system; the change is mirrored to
Firebase immediately.

### 3.2 Voice keyword spotting

`audio_bricks.py` opens a WebSocket microphone on port 8080 and runs the
`KeywordSpotting` brick (an Edge Impulse model). When the keyword "aiuto" (Italian
for "help") is detected while the system is armed, SafeNet logs an alarm, sounds
the buzzer, and sends a Telegram alert.

### 3.3 Anomaly detection

SafeNet uses **two complementary detectors** that share a single retraining
pipeline. Both notify only the dashboard and Telegram (no buzzer).

**Detector A - Unusual-time events (Isolation Forest).**
`anomaly_detection.py` scores each entry/exit event with an Isolation Forest over
six features (hour of day, day of week, time since last event, event type, time
bucket, weekend flag). An event that is unusual for its time of day (for example,
an exit at 3 a.m.) raises an alert. Its reactivity is controlled by the
**Unusual-time sensitivity** slider.

**Detector B - Overdue return (statistical absence model).**
The Isolation Forest cannot predict *when* a person should be back, so the
expected-return logic is handled by a simple, explainable statistical model
(`absence_model.py`). From the learned history it computes, per time bucket
(hour-bucket x weekend), the distribution of how long the person usually stays out
between an exit and the following entry. For each new exit it derives:

- an **expected return time** (mean absence duration),
- an **expected return window** (mean +/- one standard deviation),
- a **late deadline** = `expected + k * std`, where `k` comes from the
  **Return-late sensitivity** slider (higher sensitivity = smaller `k` = earlier
  alert).

`absence_tracker.py` runs the state machine: it opens an absence on an exit,
closes it on the matching entry, and a background loop fires the overdue alert
when the deadline passes. When a bucket has too little history the model falls
back to the global distribution (and flags the estimate as low-confidence).

**Toggle semantics.** Absence tracking and the dashboard clock always run,
regardless of the anomaly-detection toggle. The toggle only gates **alert
emission**, evaluated continuously: if detection is off when the deadline passes
and is turned back on while the person is still out (and no alert has fired yet),
the alert fires at that moment.

**Manual dismiss.** From the dashboard the caregiver can dismiss an active overdue
alert in advance if they know the prediction is wrong (for example, the person is
legitimately away longer). This cancels the alert for the current absence only and
does not change the model.

### 3.4 Retraining (sliding obsolescence window)

`retraining.py` rebuilds both models from the same windowed history:

- The training set is the **synthetic seed plus all real CSV events**, keeping only
  events within the last `HABIT_WINDOW_DAYS` (default 120 days, about four months).
- The synthetic dataset stands in for the person's real habits up to deploy time
  (we do not have time to collect them first). It is anchored to end at the deploy
  date and **ages out of the window naturally** as real events accumulate, so the
  model gradually adapts to the real person without any explicit phase switch.
- If the person's routine changes, old habits leave the window within a few months
  and the model realigns.

Retraining runs **automatically once a day** at `RETRAIN_HOUR` (default 03:00) and
**on demand** from the dashboard "Retrain model now" button. Each run reads the
full CSV, so newly accumulated events are always included.

### 3.5 REST API (`api.py`, port 8000)

| Method | Endpoint        | Purpose                                   |
|--------|-----------------|-------------------------------------------|
| GET    | `/api/health`   | Liveness check                            |
| GET    | `/api/status`   | Armed state, feature flags, event counts  |
| GET    | `/api/events`   | Recent events with optional filtering     |
| POST   | `/api/control`  | Arm/disarm and toggle features locally    |

### 3.6 Telegram (`telegram.py`, `bot.py`)

`telegram.py` sends alert messages from the device. The optional `bot.py` can run
anywhere and lets a user control the system from Telegram (`/arm`, `/disarm`,
`/enable_anomaly`, `/disable_anomaly`, `/status`, ...). Commands are delivered to
the device through Firebase, exactly like the dashboard.

### 3.7 Web dashboard (`docs/`, GitHub Pages)

A static site with Firebase Email/Password login that shows, in real time:

- System controls (arm/disarm, keyword spotting, anomaly detection).
- An **Anomaly Detection** panel with the two sensitivity sliders, the
  "Retrain model now" button, and a live model-status line.
- An **Active Absence** card with a live clock counting up from the exit, the
  expected return window, the overdue deadline, a progress bar, and a Dismiss
  button. It appears only while the person is out.
- Statistics and a **horizontal event timeline** (entries, exits, alarms,
  anomalies).

The dashboard treats Firebase as the single source of truth: every status push
re-applies the authoritative state to the toggles and labels.

---

## 4. Firebase data model

```
/status/                      device state, pushed on every change + every 10s
    armed, keyword_spotting, anomaly_detection, last_update

/events/{push_id}             entry / exit / alarm / anomaly events
    id, datetime, direction, anomaly_type, anomaly_score, ...

/monitoring/absence/          current absence (drives the live clock)
    active, exit_time, expected_return_at, window_start, window_end,
    late_deadline_at, status, alerted, dismissed, confidence

/model/status/                training status
    last_trained_at, training_window_days, real_events_in_window,
    synthetic_in_window, training_samples, trained

/config/anomaly/              sensitivities (dashboard writes, device reads)
    unusual_time_sensitivity, return_late_sensitivity

/commands/{id}                control channel with acknowledgement
    type, value, source, timestamp, status, response
    types: set_armed, set_keyword_spotting, set_anomaly_detection,
           set_sound_classification, retrain_model, dismiss_absence
```

---

## 5. Setup and running

### Device (Arduino UNO Q)

1. **Configure the environment**:
   ```bash
   cp .env.example .env
   # Set TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, and the FIREBASE_* fields
   # (copied from your Firebase service-account JSON).
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Generate the synthetic baseline and initial model** (anchored to today):
   ```bash
   python dataset_generator.py
   # Produces synthetic_habits.csv and isolation_forest_model.pkl
   ```

4. **Run the system**:
   ```bash
   python main.py
   ```
   On startup SafeNet rebuilds both models from the windowed history (also
   creating `absence_stats.pkl`), then starts the audio, sensor, anomaly,
   retraining, and API threads.

### Dashboard (GitHub Pages)

1. Enable GitHub Pages and serve from the `/docs` folder.
2. The Firebase web config is already set in `docs/app.js`.
3. Create a Firebase Email/Password user to log in.

### Telegram bot (optional)

```bash
python bot.py
```

---

## 6. Configuration reference (`config.py`)

| Constant                          | Default | Meaning                                              |
|-----------------------------------|---------|------------------------------------------------------|
| `WS_AUDIO_PORT`                   | 8080    | WebSocket microphone port                            |
| `API_PORT`                        | 8000    | REST API port                                        |
| `CONFIDENCE`                      | 0.80    | Keyword-spotting confidence threshold                |
| `HABIT_WINDOW_DAYS`               | 120     | Sliding training window (obsolescence horizon)       |
| `RETRAIN_HOUR`                    | 3       | Hour of the daily automatic retrain                  |
| `ANOMALY_CHECK_INTERVAL`          | 60      | Seconds between unusual-time checks                  |
| `ABSENCE_DEADLINE_CHECK_INTERVAL` | 5       | Seconds between overdue-deadline checks              |
| `MIN_BUCKET_SAMPLES`              | 3       | Min samples before a bucket's window is trusted      |
| `DEFAULT_UNUSUAL_TIME_SENSITIVITY`| 50      | Initial Detector A sensitivity (0..100)              |
| `DEFAULT_RETURN_LATE_SENSITIVITY` | 50      | Initial Detector B sensitivity (0..100)              |

The two sensitivities are mapped to internal parameters by
`unusual_time_threshold()` and `return_late_k()`, and can be changed live from the
dashboard sliders.

---

## 7. Project structure

```
.
├── main.py                 # Entry point, thread orchestration
├── config.py               # Constants and sensitivity mappings
├── models.py               # SystemState (thread-safe) + model loading
├── ml_features.py          # Shared Isolation Forest feature engineering
├── anomaly_detection.py    # Detector A: unusual-time events
├── absence_model.py        # Detector B: absence-duration statistics
├── absence_tracker.py      # Detector B runtime: state machine + deadline loop
├── retraining.py           # Sliding-window daily/on-demand retraining
├── dataset_generator.py    # Synthetic habit generator (anchored to deploy date)
├── sensors.py              # Bridge sensor/actuator interface
├── sensor_loop.py          # Passage and NFC monitoring loop
├── events.py               # Event logging and alert handlers
├── csv_handler.py          # Local CSV I/O
├── firebase.py             # Firebase Realtime Database helpers
├── firebase_commands.py    # Command polling + live config sync
├── telegram.py             # Telegram alert sender
├── bot.py                  # Optional Telegram control bot
├── api.py                  # Flask REST API
├── logging_setup.py        # File + console logging
├── sketch.ino              # MCU firmware (sensors, LEDs, buzzer, RFID)
└── docs/                   # Web dashboard (GitHub Pages)
    ├── index.html
    ├── app.js
    └── style.css
```

---

## 8. Requirements

See `requirements.txt`: numpy, websockets, cryptography, flask, requests,
scikit-learn, firebase-admin, pandas, python-dotenv. The `arduino-app-bricks`
package (Microphone, KeywordSpotting, Bridge, App) is pre-installed on the device.
