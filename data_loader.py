"""Mock Data Loader - Simulate 1-minute candles for testing"""

import random
from datetime import datetime, timedelta
from typing import List
from omen_bot import Candle


class MockDataLoader:
    """Generate realistic mock 1-minute OHLCV data for backtesting"""

    def __init__(self, start_price: float = 100.0, seed: int = 42):
        self.start_price = start_price
        self.current_price = start_price
        self.current_time = datetime.strptime("09:30:00", "%H:%M:%S")
        random.seed(seed)

    def generate_candles(
        self,
        num_candles: int,
        volatility: float = 0.5,
        trend: float = 0.0,
        scenario: str = "random"
    ) -> List[Candle]:
        """
        Generate mock candles.
        volatility: price swing per candle (%)
        trend: directional bias (+1 = up, -1 = down, 0 = neutral)
        scenario: 'random', 'breakout', 'retest', 'hammer'
        """
        candles = []

        for i in range(num_candles):
            # Trend bias
            trend_move = trend * self.current_price * 0.001

            # Random walk
            random_move = random.uniform(-volatility, volatility) * self.current_price / 100

            # Open
            open_price = self.current_price
            close_price = open_price + trend_move + random_move

            # High/Low
            if close_price > open_price:
                # Bullish candle
                high = max(close_price, open_price) + random.uniform(0, volatility * self.current_price / 100)
                low = min(open_price, close_price) - random.uniform(0, volatility * self.current_price / 100)
            else:
                # Bearish candle
                high = max(open_price, close_price) + random.uniform(0, volatility * self.current_price / 100)
                low = min(open_price, close_price) - random.uniform(0, volatility * self.current_price / 100)

            # Scenario adjustments
            if scenario == "hammer" and i == num_candles - 1:
                # Last candle is a hammer (large lower wick)
                low = open_price * 0.98
                close_price = open_price * 1.001
                high = open_price * 1.005

            elif scenario == "retest" and i >= num_candles // 2:
                # Second half: consolidation/retest
                close_price = self.current_price * 0.99
                low = self.current_price * 0.985
                high = self.current_price * 1.002

            elif scenario == "breakout":
                # Consistent upward breakout
                close_price = open_price + (volatility * self.current_price / 100) * 0.8
                high = close_price + (volatility * self.current_price / 100) * 0.2
                low = open_price

            # Volume (higher on breakouts/reversals)
            base_volume = 1000
            if abs(high - low) > volatility * self.current_price / 100:
                volume = int(base_volume * random.uniform(1.2, 1.8))
            else:
                volume = int(base_volume * random.uniform(0.8, 1.2))

            # Ensure OHLC is valid
            high = max(high, open_price, close_price)
            low = min(low, open_price, close_price)

            timestamp = self.current_time.strftime("%H:%M:%S")
            candle = Candle(
                timestamp=timestamp,
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close_price, 2),
                volume=volume
            )

            candles.append(candle)
            self.current_price = close_price
            self.current_time += timedelta(minutes=1)

        return candles

    def generate_break_and_retest_scenario(self) -> List[Candle]:
        """
        Generate a realistic break-and-retest scenario:
        - First 5 candles: establish opening range
        - Next 5: breakout above OR
        - Next 3: consolidation
        - Last candle: retest with hammer
        - Plus 10 more for uptrend continuation (to hit target)
        """
        # Opening range (neutral)
        opening = self.generate_candles(5, volatility=0.3, trend=0.0, scenario="random")

        # Breakout
        breakout = self.generate_candles(5, volatility=0.6, trend=0.8, scenario="breakout")

        # Consolidation
        consolidation = self.generate_candles(3, volatility=0.2, trend=0.0, scenario="random")

        # Retest with hammer
        retest = self.generate_candles(1, volatility=0.5, trend=0.0, scenario="hammer")

        # Follow-through move (hits target)
        followthrough = self.generate_candles(10, volatility=0.6, trend=0.7, scenario="breakout")

        return opening + breakout + consolidation + retest + followthrough

    def generate_one_candle_rule_scenario(self) -> List[Candle]:
        """
        Generate one-candle rule scenario:
        - Establish red support candle
        - Break away
        - Retest support with hammer
        - Follow-through move
        """
        setup = self.generate_candles(2, volatility=0.3, trend=0.0)  # Context
        red_candle = self.generate_candles(1, volatility=0.4, trend=-0.5)  # Red support
        breakaway = self.generate_candles(3, volatility=0.6, trend=-0.8)  # Break down
        retest = self.generate_candles(1, volatility=0.5, trend=0.0, scenario="hammer")  # Hammer retest
        followthrough = self.generate_candles(10, volatility=0.6, trend=-0.7, scenario="breakout")  # Continue down

        return setup + red_candle + breakaway + retest + followthrough

    def generate_84_rule_scenario(self) -> List[Candle]:
        """
        Generate 84% rule scenario:
        - Entry candle
        - Breakout move
        - Stop loss hit candle
        - Retest entry level
        """
        entry_setup = self.generate_candles(2, volatility=0.3, trend=0.0)
        entry_candle = self.generate_candles(1, volatility=0.3, trend=0.0)  # A+ entry
        profit_move = self.generate_candles(2, volatility=0.6, trend=0.5)  # Profitable move
        stop_loss = self.generate_candles(1, volatility=0.5, trend=-1.0)  # Stop hit
        reentry = self.generate_candles(2, volatility=0.4, trend=0.0)  # Consolidation
        reclaim = self.generate_candles(1, volatility=0.5, trend=0.8)  # Reclaim entry

        return entry_setup + entry_candle + profit_move + stop_loss + reentry + reclaim


# Test
if __name__ == "__main__":
    loader = MockDataLoader(start_price=100.0)

    print("=== Break and Retest Scenario ===")
    br_candles = loader.generate_break_and_retest_scenario()
    for i, c in enumerate(br_candles):
        print(f"{i}: {c.timestamp} | O={c.open} H={c.high} L={c.low} C={c.close} | Body={c.body_size:.2f} Lower_wick={c.lower_wick:.2f}")

    print("\n=== One Candle Rule Scenario ===")
    loader = MockDataLoader(start_price=100.0)
    ocr_candles = loader.generate_one_candle_rule_scenario()
    for i, c in enumerate(ocr_candles):
        print(f"{i}: {c.timestamp} | O={c.open} H={c.high} L={c.low} C={c.close}")

    print("\n=== 84% Rule Scenario ===")
    loader = MockDataLoader(start_price=100.0)
    rule84_candles = loader.generate_84_rule_scenario()
    for i, c in enumerate(rule84_candles):
        print(f"{i}: {c.timestamp} | O={c.open} H={c.high} L={c.low} C={c.close}")
