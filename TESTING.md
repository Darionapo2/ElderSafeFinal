# ElderSafeFinal Testing Guide

## Test Files

### main_test1.py - Audio Bricks Only
Testa **KeywordSpotting + AudioClassification** senza API.

**Cosa fa:**
- Avvia WebSocket Microphone su porta 8080
- Configura KeywordSpotting ("aiuto")
- Configura AudioClassification (crying_baby, fall, glass_breaking, scream)
- Aspetta audio in streaming
- Logga le rilevazioni

**Come usare:**
```bash
# Terminal 1: avvia server test
python main_test1.py

# Terminal 2: invia audio via WebSocket
python ../client_mic.py --ip localhost --port 8080
```

**Output atteso:**
```
ElderSafeFinal - Test 1: KeywordSpotting + AudioClassification
Starting WebSocket Microphone on ws://0.0.0.0:8080
✓ KeywordSpotting configured
✓ AudioClassification configured
🟢 Ready to receive audio via WebSocket
```

Quando sentirai "aiuto" o suoni pericolosi nel microfono:
```
🔴 KEYWORD 'aiuto' DETECTED!
🔴 SOUND DETECTED: 'scream'
```

---

### main_test2.py - Audio Bricks + REST API
Testa **KeywordSpotting + AudioClassification + Flask API** insieme.

**Cosa fa:**
- Tutto come main_test1.py
- Aggiunge Flask REST API su porta 8000
- Testa che i due sistemi convivono (bricks in App.run(), API in thread daemon)

**Come usare:**
```bash
# Terminal 1: avvia server test
python main_test2.py

# Terminal 2: testa API
curl http://localhost:8000/api/health
curl http://localhost:8000/api/test

# Terminal 3: invia audio
python ../client_mic.py --ip localhost --port 8080
```

**Output atteso:**
```
ElderSafeFinal - Test 2: Bricks + REST API
Starting WebSocket Microphone on ws://0.0.0.0:8080
✓ KeywordSpotting configured
✓ AudioClassification configured
✓ REST API started
🟢 Ready to receive audio via WebSocket
```

API responses:
```bash
$ curl http://localhost:8000/api/health
{"status":"ok","timestamp":"2026-06-07T12:34:56.789012"}

$ curl http://localhost:8000/api/test
{"message":"ElderSafeFinal Test 2 - Audio Bricks + API","timestamp":"2026-06-07T12:34:56.789012"}
```

---

## Testing Checklist

### Before Arduino Deployment

- [ ] **Test 1**: main_test1.py riceve audio e rileva keyword/sounds
- [ ] **Test 2**: main_test2.py ha API responsive while receiving audio
- [ ] **dataset_generator.py**: crea isolation_forest_model.pkl senza errori
- [ ] **main.py**: avvia e non crasha (se Firebase/Telegram non configurati)

### Local Testing Without Brick Models

Se i brick models non sono caricati (errore "model not found"):

1. Verifica che sei sull'Arduino UNO Q con Arduino App Lab installato
2. O, localmente, puoi mockare con print statements (vedi sotto)

### Mocking Audio Bricks (for desktop testing)

Se vuoi testare la logica senza i brick fisici:

```python
# In main_test1.py, sostituisci:
class MockBrick:
    def on_detect(self, keyword, callback):
        self.callback = callback
    
    def trigger(self):
        self.callback()

# Usa MockBrick al posto di KeywordSpotting/AudioClassification
```

---

## Troubleshooting

### "Model not found" error
- ✓ Stai usando Arduino UNO Q con Arduino App Lab?
- ✓ I brick models sono caricati dal container di Edge Impulse
- ✓ Localmente, puoi mockare come sopra

### "Address already in use"
- ✓ Port 8080 o 8000 già in uso
- ✓ `lsof -i :8080` per trovare il processo
- ✓ Modifica WS_PORT o API_PORT nel file test

### "WebSocket connection refused"
- ✓ client_mic.py non è connesso
- ✓ Verifica che server test è in esecuzione
- ✓ Controlla firewall/network

---

## Next Steps

Una volta che i test passano:

1. ✓ Configura `isolation_forest_model.pkl` con `dataset_generator.py`
2. ✓ Aggiungi `.env` con credenziali Telegram/Firebase
3. ✓ Testa `main.py` (full system)
4. ✓ Deploy su Arduino UNO Q
