#!/usr/bin/env python3
"""
Synthetic dataset generator for entry/exit pattern anomaly detection.
Generates regular habits and trains Isolation Forest model.
"""

import csv
import pickle
from datetime import datetime, timedelta
import numpy as np
from sklearn.ensemble import IsolationForest
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# Configuration
DAYS_TO_GENERATE = 30
OUTPUT_CSV = "synthetic_habits.csv"
MODEL_OUTPUT = "isolation_forest_model.pkl"

# Typical habits: weekday patterns (Mon-Fri)
WEEKDAY_PATTERNS = [
    {"time": 8, "direction": "exit"},     # Exit 8am
    {"time": 12, "direction": "entry"},   # Entry 12pm
    {"time": 15, "direction": "exit"},    # Exit 3pm
    {"time": 19, "direction": "entry"},   # Entry 7pm
]

# Weekend patterns are less regular
WEEKEND_PATTERNS = [
    {"time": 9, "direction": "exit"},     # Exit 9am (late)
    {"time": 13, "direction": "entry"},   # Entry 1pm
    {"time": 16, "direction": "exit"},    # Exit 4pm
    {"time": 20, "direction": "entry"},   # Entry 8pm
]


def generate_synthetic_events(days=DAYS_TO_GENERATE):
    """Generate synthetic entry/exit events with regular habits.

    The synthetic dataset stands in for the user's real habits up to deploy time
    (we do not have time to collect real ones). It is anchored to END at the
    current date, preserving real weekday/weekend alignment, so that it sits at
    the recent edge of the training sliding window and ages out naturally as real
    events accumulate.
    """
    events = []
    event_id = 1
    prev_event_time = None

    # Anchor the synthetic history so its last day is yesterday relative to "now".
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = today - timedelta(days=days)

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday

        # Select pattern based on weekday/weekend
        if day_of_week < 5:  # Monday-Friday
            patterns = WEEKDAY_PATTERNS
        else:  # Saturday-Sunday
            patterns = WEEKEND_PATTERNS

        for pattern in patterns:
            minute_base = 30
            minute_variation = int(np.random.randint(-15, 16))
            second_variation = int(np.random.randint(0, 60))

            minute_final = max(0, min(59, minute_base + minute_variation))

            event_time = current_date.replace(
                hour=pattern["time"],
                minute=minute_final,
                second=second_variation,
                microsecond=0
            )

            # Calculate delta from last event
            if prev_event_time is not None:
                delta_ms = int((event_time - prev_event_time).total_seconds() * 1000)
            else:
                delta_ms = 0

            event = {
                "id": event_id,
                "datetime": event_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "date": event_time.strftime("%Y-%m-%d"),
                "time": event_time.strftime("%H:%M:%S"),
                "direction": pattern["direction"],
                "first_sensor": "REED" if pattern["direction"] == "entry" else "PIR",
                "delta_ms": delta_ms,
            }

            events.append(event)
            prev_event_time = event_time
            event_id += 1

    return events


def save_csv(events, filepath=OUTPUT_CSV):
    """Save events to CSV."""
    headers = ["id", "datetime", "date", "time", "direction", "first_sensor", "delta_ms"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(events)

    log.info(f"Generated {len(events)} events: {filepath}")


def extract_features(events):
    """Extract Isolation Forest features using the shared feature layout."""
    from ml_features import extract_if_feature_matrix
    return extract_if_feature_matrix(events)


def train_isolation_forest(features, contamination=0.05):
    """Train Isolation Forest model."""
    log.info(f"Training Isolation Forest with {len(features)} samples...")

    model = IsolationForest(
        contamination=contamination,  # Expected proportion of anomalies
        max_samples=100,               # Keep it light for Arduino
        n_estimators=50,               # Number of trees
        random_state=42,
        n_jobs=-1,
    )

    model.fit(features)
    log.info("Model trained")

    predictions = model.predict(features)
    anomalies = np.sum(predictions == -1)
    log.info(f"Anomalies in training set: {anomalies}/{len(features)}")

    return model


def save_model(model, filepath=MODEL_OUTPUT):
    """Save trained model to pickle."""
    with open(filepath, "wb") as f:
        pickle.dump(model, f)
    log.info(f"Model saved: {filepath}")


def main():
    log.info("=" * 60)
    log.info("Synthetic Dataset Generator for Anomaly Detection")
    log.info("=" * 60)

    log.info(f"Generating {DAYS_TO_GENERATE} days of synthetic events...")
    events = generate_synthetic_events(DAYS_TO_GENERATE)
    save_csv(events)

    log.info("Extracting features...")
    features = extract_features(events)
    log.info(f"Shape: {features.shape}")

    log.info("Training Isolation Forest model...")
    model = train_isolation_forest(features)

    log.info("Saving model...")
    save_model(model)

    log.info("=" * 60)
    log.info("Done")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
