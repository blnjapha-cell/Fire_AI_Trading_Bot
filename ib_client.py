"""
ib_client.py
Interactive Brokers connection, market data, and order management.
"""

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.common import BarData
import threading
import time
import logging

logger = logging.getLogger(__name__)


def make_forex_contract(pair: str) -> Contract:
    """Build an IB Forex contract from a pair string like 'EURUSD'."""
    contract = Contract()
    contract.symbol   = pair[:3]
    contract.currency = pair[3:]
    contract.secType  = "CASH"
    contract.exchange = "IDEALPRO"
    return contract


class IBClient(EWrapper, EClient):
    def __init__(self, firestore_client=None):
        EClient.__init__(self, self)
        self.firestore    = firestore_client
        self.next_order_id = None
        self.prices        = {}          # { "EURUSD": 1.0852 }
        self.pending_trades = {}         # { ib_order_id: firestore_trade_id }
        self._connected    = threading.Event()

    # ── Connection ────────────────────────────────────────────
    def connect_and_run(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.connect(host, port, client_id)
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        self._connected.wait(timeout=10)
        if not self._connected.is_set():
            raise ConnectionError("Could not connect to IB TWS/Gateway.")
        logger.info("Connected to Interactive Brokers.")

    def nextValidId(self, orderId: int):
        self.next_order_id = orderId
        self._connected.set()
        logger.info(f"IB ready. Next order ID: {orderId}")

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode not in (2104, 2106, 2158):   # ignore benign info messages
            logger.error(f"IB Error {errorCode} (req {reqId}): {errorString}")

    # ── Market Data ───────────────────────────────────────────
    def request_price(self, pair: str, req_id: int):
        contract = make_forex_contract(pair)
        self.reqMktData(req_id, contract, "", False, False, [])

    def tickPrice(self, reqId, tickType, price, attrib):
        # tickType 4 = last price
        if tickType == 4 and price > 0:
            for pair, rid in getattr(self, "_req_map", {}).items():
                if rid == reqId:
                    self.prices[pair] = price

    # ── Orders ────────────────────────────────────────────────
    def place_market_order(self, pair: str, action: str, quantity: float, firestore_trade_id: str = None):
        """
        Place a market order on IDEALPRO.
        action: "BUY" or "SELL"
        quantity: notional amount in base currency (e.g. 20000 for 0.2 lots)
        """
        if self.next_order_id is None:
            raise RuntimeError("Not connected to IB.")

        contract = make_forex_contract(pair)
        order          = Order()
        order.action   = action
        order.orderType = "MKT"
        order.totalQuantity = quantity

        oid = self.next_order_id
        self.next_order_id += 1

        if firestore_trade_id:
            self.pending_trades[oid] = firestore_trade_id

        self.placeOrder(oid, contract, order)
        logger.info(f"Order placed: {action} {quantity} {pair} (IB order {oid})")
        return oid

    def cancel_order(self, ib_order_id: int):
        self.cancelOrder(ib_order_id)

    # ── Order callbacks ───────────────────────────────────────
    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                    permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        logger.info(f"Order {orderId} status: {status} filled@{avgFillPrice}")

        if self.firestore and orderId in self.pending_trades:
            fs_id = self.pending_trades[orderId]
            if status == "Filled":
                self.firestore.update_trade(fs_id, {
                    "status": "open",
                    "entry_price": avgFillPrice,
                    "ib_order_id": orderId,
                })
            elif status in ("Cancelled", "Inactive"):
                self.firestore.update_trade(fs_id, {"status": status.lower()})
