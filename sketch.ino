#include <SPI.h>
#include <MFRC522.h>
#include "Arduino_RouterBridge.h"

const int reedPin   = 2;
const int pirPin    = 3;
const int ledGreen  = 4;
const int ledRed    = 7;
const int buzzerPin = 8;
const int RST_PIN   = 9;
const int SS_PIN    = 10;

MFRC522 rfid(SS_PIN, RST_PIN);

bool systemArmed = false;

// ── Functions exposed to the bridge ───────────────────────────────────────────
int get_reed_state()  { return digitalRead(reedPin); }
int get_pir_state()   { return digitalRead(pirPin);  }
int get_system_armed(){ return systemArmed ? 1 : 0;  }
int get_nfc_armed()   { return systemArmed ? 1 : 0;  }  // Same as armed for now

void set_system_armed(int armed) {
  systemArmed = armed ? true : false;
  updateLeds();
  if (systemArmed) beep_arm();
  else             beep_disarm();
}

void set_led_green(int state) {
  digitalWrite(ledGreen, state ? HIGH : LOW);
}

void set_led_red(int state) {
  digitalWrite(ledRed, state ? HIGH : LOW);
}

void beep_entry() {
  tone(buzzerPin, 1800); delay(80); noTone(buzzerPin);
  delay(60);
  tone(buzzerPin, 2200); delay(80); noTone(buzzerPin);
}

void beep_exit() {
  tone(buzzerPin, 2200); delay(80); noTone(buzzerPin);
  delay(60);
  tone(buzzerPin, 1800); delay(80); noTone(buzzerPin);
}

void beep_arm() {
  tone(buzzerPin, 1000); delay(100); noTone(buzzerPin);
  delay(80);
  tone(buzzerPin, 1500); delay(100); noTone(buzzerPin);
  delay(80);
  tone(buzzerPin, 2000); delay(150); noTone(buzzerPin);
}

void beep_disarm() {
  tone(buzzerPin, 2000); delay(100); noTone(buzzerPin);
  delay(80);
  tone(buzzerPin, 1500); delay(100); noTone(buzzerPin);
  delay(80);
  tone(buzzerPin, 1000); delay(150); noTone(buzzerPin);
}

void beep_alarm() {
  for (int i = 0; i < 6; i++) {
    tone(buzzerPin, 2600); delay(80); noTone(buzzerPin);
    delay(50);
  }
}

void updateLeds() {
  digitalWrite(ledGreen, systemArmed ? HIGH : LOW);
  digitalWrite(ledRed,   systemArmed ? LOW  : HIGH);
}

void setup() {
  pinMode(reedPin,  INPUT_PULLUP);
  pinMode(pirPin,   INPUT);
  pinMode(ledGreen, OUTPUT);
  pinMode(ledRed,   OUTPUT);
  pinMode(buzzerPin,OUTPUT);

  SPI.begin();
  rfid.PCD_Init();

  Bridge.begin();
  // Sensors (read-only)
  Bridge.provide("get_reed_state",     get_reed_state);
  Bridge.provide("get_pir_state",      get_pir_state);
  Bridge.provide("get_system_armed",   get_system_armed);
  Bridge.provide("get_nfc_armed",      get_nfc_armed);

  // Control (write)
  Bridge.provide("set_system_armed",   set_system_armed);
  Bridge.provide("set_led_green",      set_led_green);
  Bridge.provide("set_led_red",        set_led_red);

  // Feedback (audio)
  Bridge.provide("beep_entry",         beep_entry);
  Bridge.provide("beep_exit",          beep_exit);
  Bridge.provide("beep_alarm",         beep_alarm);

  updateLeds();
}

void loop() {
  // Check RFID badge
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    String uid = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
      if (rfid.uid.uidByte[i] < 0x10) uid += "0";
      uid += String(rfid.uid.uidByte[i], HEX);
      if (i < rfid.uid.size - 1) uid += ":";
    }

    if (uid == "e3:12:3f:16") {
      systemArmed = !systemArmed;
      updateLeds();
      if (systemArmed) beep_arm();
      else             beep_disarm();
    }

    rfid.PICC_HaltA();
    delay(1000);
  }

  updateLeds();
  delay(20);
}
