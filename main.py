"""
main.py
Entry point — orchestrates IB connection, strategy, and Firebase logging.

Usage:
    python main.py

Environment variables (or edit config below):
    IB_HOST      TWS/Gateway host   (default: 127.0.0.1)
    IB_PORT      TWS/Gateway port   (default: 7497 for paper, 7496 for live)
    IB_CLIENT_ID Client ID          (default: 1)
    FIREBASE_KEY Path to service account JSON (default: serviceAccountKey.json)
"""

import os
import time
import logging
import schedule
from bot.firebase_client import init_firebase, FirestoreClient
from bot.ib_client import IBClient
from bot.strategy import MovingAverageCrossover, RiskManager

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


# ── Init ──────────────────────────────────────────────────────────────────────
db      = init_firebase(os.getenv("FIREBASE_KEY", "serviceAccountKey.json"))
fs      = FirestoreClient(db)
config  = fs.get_config()

ib = IBClient(firestore_client=fs)
ib.connect_and_run(
    host      = os.getenv("IB_HOST",      config.get("ib_host",      "127.0.0.1")),
    port      = int(os.getenv("IB_PORT",  config.get("ib_port",      7497))),
    client_id = int(os.getenv("IB_CLIENT_ID", config.get("ib_client_id", 1))),
)

# One strategy instance per pair
strategies = {
    pair: MovingAverageCrossover(
        fast_period=config.get("fast_ema", 9),
        slow_period=config.get("slow_ema", 21),
    )
    for pair in config.get("pairs", ["EURUSD", "GBPUSD"])
}

risk = RiskManager(
    risk_pct=config.get("risk_per_trade_pct", 1.0),
    max_open_trades=config.get("max_daily_trades", 3),
)


# ── Main tick ─────────────────────────────────────────────────────────────────
def tick():
    """Called on each scheduled interval (e.g. every 5 minutes)."""
    # Re-read config so you can change settings live in Firestore
    global config
    config = fs.get_config()

    if not config.get("active", True):
        logger.info("Bot is paused (active=false in Firestore config).")
        return

    open_trades = fs.get_open_trades()

    for pair in config.get("pairs", ["EURUSD"]):
        price = ib.prices.get(pair)
        if price is None:
            logger.warning(f"No price data yet for {pair}, skipping.")
            continue

        signal = strategies[pair].update(price)
        logger.info(f"{pair}  price={price:.5f}  signal={signal}")

        # Log every signal to Firestore
        fs.log_signal({"pair": pair, "price": price, "signal": signal})

        if signal == "HOLD":
            continue

        # Risk checks
        open_for_pair = [t for t in open_trades if t.get("pair") == pair and t.get("status") == "open"]
        if open_for_pair:
            logger.info(f"Already have an open trade for {pair}, skipping.")
            continue

        if not risk.can_trade(len(open_trades)):
            logger.info("Max open trades reached, skipping.")
            continue

        # Calculate position size (placeholder equity — replace with IB account query)
        account_equity = config.get("account_equity_usd", 10_000)
        stop_pips      = config.get("stop_loss_pips", 20)
        qty            = risk.position_size(account_equity, stop_pips)

        # Log to Firestore first, then place order
        trade_id = fs.log_trade({
            "pair":     pair,
            "action":   signal,
            "lot_size": qty,
            "price":    price,
        })

        ib.place_market_order(pair, signal, qty, firestore_trade_id=trade_id)


# ── Scheduler ─────────────────────────────────────────────────────────────────
def start_price_streaming():
    """Subscribe to live prices for all configured pairs."""
    ib._req_map = {}
    for i, pair in enumerate(config.get("pairs", ["EURUSD"]), start=1):
        ib._req_map[pair] = i
        ib.request_price(pair, req_id=i)
    logger.info(f"Streaming prices for: {list(ib._req_map.keys())}")


if __name__ == "__main__":
    logger.info("🤖 Forex Bot starting...")
    start_price_streaming()
    time.sleep(2)   # brief pause to let first prices arrive

    interval = config.get("interval_minutes", 5)
    schedule.every(interval).minutes.do(tick)
    logger.info(f"Scheduler running every {interval} minutes. Press Ctrl+C to stop.")

    tick()   # run immediately on startup
    while True:
        schedule.run_pending()
        time.sleep(1)
