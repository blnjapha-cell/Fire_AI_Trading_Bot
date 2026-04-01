"""
strategy.py
Pluggable strategy layer. Swap out or extend with your own logic.
Currently implements a simple Moving Average Crossover strategy.
"""

from collections import deque
import logging

logger = logging.getLogger(__name__)


class MovingAverageCrossover:
    """
    Generates BUY/SELL/HOLD signals based on fast/slow EMA crossover.
    
    Parameters
    ----------
    fast_period : int   Short EMA window (default 9)
    slow_period : int   Long EMA window  (default 21)
    """

    def __init__(self, fast_period: int = 9, slow_period: int = 21):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self._prices: deque = deque(maxlen=slow_period + 1)
        self._prev_fast_ema = None
        self._prev_slow_ema = None

    @staticmethod
    def _ema(prices: list, period: int) -> float:
        k = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = price * k + ema * (1 - k)
        return ema

    def update(self, price: float) -> str:
        """
        Feed a new price and get a signal.
        Returns: "BUY" | "SELL" | "HOLD"
        """
        self._prices.append(price)

        if len(self._prices) < self.slow_period:
            return "HOLD"

        prices_list = list(self._prices)
        fast_ema = self._ema(prices_list[-self.fast_period:], self.fast_period)
        slow_ema = self._ema(prices_list, self.slow_period)

        signal = "HOLD"

        if self._prev_fast_ema is not None and self._prev_slow_ema is not None:
            crossed_up   = self._prev_fast_ema <= self._prev_slow_ema and fast_ema > slow_ema
            crossed_down = self._prev_fast_ema >= self._prev_slow_ema and fast_ema < slow_ema

            if crossed_up:
                signal = "BUY"
            elif crossed_down:
                signal = "SELL"

        self._prev_fast_ema = fast_ema
        self._prev_slow_ema = slow_ema

        logger.debug(f"Price={price:.5f}  FastEMA={fast_ema:.5f}  SlowEMA={slow_ema:.5f}  → {signal}")
        return signal


class RiskManager:
    """
    Simple fixed-fractional risk manager.
    Calculates position size based on account equity and risk %.
    """

    def __init__(self, risk_pct: float = 1.0, max_open_trades: int = 3):
        self.risk_pct        = risk_pct
        self.max_open_trades = max_open_trades

    def position_size(self, account_equity: float, stop_distance_pips: float,
                      pip_value: float = 10.0) -> float:
        """
        Returns notional quantity to trade.
        
        account_equity     : USD value of account
        stop_distance_pips : distance to stop loss in pips
        pip_value          : USD value of 1 pip per standard lot (default $10)
        """
        risk_amount = account_equity * (self.risk_pct / 100)
        lots = risk_amount / (stop_distance_pips * pip_value)
        notional = round(lots * 100_000, -3)   # round to nearest 1000 units
        return max(notional, 1000)

    def can_trade(self, open_trade_count: int) -> bool:
        return open_trade_count < self.max_open_trades
