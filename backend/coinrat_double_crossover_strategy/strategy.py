import datetime, time
from typing import Union, Tuple
from decimal import Decimal

from coinrat.domain import Strategy, MarketsCandleStorage, Signal, MarketPair, \
    CANDLE_STORAGE_FIELD_CLOSE, SIGNAL_SELL, SIGNAL_BUY, Market

DOUBLE_CROSSOVER_STRATEGY = 'double_crossover'


class DoubleCrossoverStrategy(Strategy):
    """
    @link http://www.financial-spread-betting.com/course/using-two-moving-averages.html
    """

    def __init__(
        self,
        market: Market,
        pair: MarketPair,
        storage: MarketsCandleStorage,
        long_average_interval: datetime.timedelta,
        short_average_interval: datetime.timedelta,
        delay: int = 30,
        number_of_runs: Union[int, None] = None
    ) -> None:
        assert short_average_interval < long_average_interval

        self._long_average_interval = long_average_interval
        self._short_average_interval = short_average_interval
        self._pair = pair
        self._delay = delay
        self._number_of_runs = number_of_runs
        self._market = market
        self._storage = storage
        self._last_short_average = None

    def run(self):
        while self._number_of_runs is None or self._number_of_runs > 0:

            signal = self._check_for_signal()
            if signal is not None:
                self._react_on_signal(signal)

            if self._number_of_runs is not None:
                self._number_of_runs -= 1

            time.sleep(self._delay)

    def _check_for_signal(self) -> Union[Signal, None]:
        long_average, short_average = self.get_averages()

        if self._last_short_average is not None:
            if self._last_short_average < long_average < short_average:
                return Signal(SIGNAL_BUY)
            elif self._last_short_average > long_average > short_average:
                return Signal(SIGNAL_SELL)

        self._last_short_average = short_average
        return None

    def get_averages(self) -> Tuple[Decimal, Decimal]:
        now = datetime.datetime.now().astimezone(datetime.timezone.utc)  # Todo: DateTimeFactory
        long_interval = (now - self._long_average_interval, now)
        long_average = self._storage.mean(
            self._market.get_name(),
            self._pair,
            CANDLE_STORAGE_FIELD_CLOSE,
            long_interval
        )
        short_interval = (now - self._short_average_interval, now)
        short_average = self._storage.mean(
            self._market.get_name(),
            self._pair,
            CANDLE_STORAGE_FIELD_CLOSE,
            short_interval
        )

        return long_average, short_average

    def _react_on_signal(self, signal: Signal):
        if signal.is_buy():
            self._market.buy_max_available(self._pair)
        elif signal.is_sell():
            self._market.buy_max_available(self._pair)
        else:
            raise ValueError('Unknown signal: "{}"'.format(signal))