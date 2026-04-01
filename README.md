# 🤖 Forex Bot — IB + Firebase Scaffold

A production-ready Python trading bot scaffold connecting
**Interactive Brokers** for execution and **Firebase Firestore** for
state, logging, and live config.

---

## Project Structure

```
forex-bot/
├── main.py                  # Entry point & scheduler
├── requirements.txt
├── firestore.rules          # Deploy to Firebase
├── config/
│   └── bot_config.json      # Seed this into Firestore once
└── bot/
    ├── firebase_client.py   # All Firestore read/write helpers
    ├── ib_client.py         # IB connection, market data, orders
    └── strategy.py          # MA crossover strategy + risk manager
```

---

## Prerequisites

| Tool | Notes |
|------|-------|
| Python 3.10+ | |
| IB TWS or IB Gateway | Enable API: `Edit → Global Configuration → API → Settings` |
| Firebase project | Create at [console.firebase.google.com](https://console.firebase.google.com) |

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Firebase service account
1. Go to **Firebase Console → Project Settings → Service Accounts**
2. Click **Generate new private key** → download JSON
3. Place it in the project root as `serviceAccountKey.json`

### 3. Seed Firestore config
Run this once to create the bot config document:
```bash
python - <<'EOF'
import firebase_admin
from firebase_admin import credentials, firestore
import json

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

with open("config/bot_config.json") as f:
    config = json.load(f)

db.collection("config").document("bot").set(config)
print("Config seeded ✓")
EOF
```

### 4. Deploy Firestore security rules
```bash
firebase deploy --only firestore:rules
```

### 5. Start IB TWS or IB Gateway
- Paper trading port: **7497**
- Live trading port:  **7496**
- Enable socket connections in IB settings

### 6. Run the bot
```bash
python main.py
```

---

## Live Config (no restart needed)

Update any value in Firestore `config/bot` and the bot will pick it up
on the next tick:

| Key | Effect |
|-----|--------|
| `active: false` | Pauses trading immediately |
| `pairs` | Change which pairs are traded |
| `risk_per_trade_pct` | Adjust position sizing |
| `interval_minutes` | Change polling frequency |

---

## Firestore Collections

| Collection | Purpose |
|------------|---------|
| `config`   | Live bot settings |
| `trades`   | Every order placed + fill info |
| `signals`  | Every signal generated (BUY/SELL/HOLD) |
| `performance` | Periodic PnL snapshots |

---

## Swapping the Strategy

Edit `bot/strategy.py` and replace or extend `MovingAverageCrossover`.
The only contract `main.py` expects is:

```python
signal = strategy.update(price)  # returns "BUY" | "SELL" | "HOLD"
```

---

## ⚠️ Disclaimer

This scaffold is for **educational purposes only**. Always test on a
paper trading account before risking real capital. Past performance of
any strategy does not guarantee future results.
