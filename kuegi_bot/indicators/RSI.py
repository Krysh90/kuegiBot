from typing import List

from kuegi_bot.indicators.indicator import Indicator
from kuegi_bot.utils.trading_classes import Bar


class Data:
    def __init__(self, rsi, up_src, down_src, up, down):
        self.rsi = rsi
        self.up_src = up_src
        self.down_src = down_src
        self.up = up
        self.down = down

class RSI(Indicator):
    ''' Relative Strength Index
        up = RMA(MAX(CHANGE(input), 0), period))
        down = RMA(-MIN(CHANGE(input), 0), period)
        RSI[i] = 100 - (100 / (1 + up / down))
    '''

    def __init__(self, period: int = 14):
        super().__init__(f'RSI({str(period)})')
        self.period = period
        self.alpha = 1 / period

    def on_tick(self, bars: List[Bar]):
        first_changed = 0
        for idx in range(len(bars)):
            if bars[idx].did_change:
                first_changed = idx
            else:
                break

        for idx in range(first_changed, -1, -1):
            self.process_bar(bars[idx:])

    def process_bar(self, bars: List[Bar]):
        if len(bars) < 2:
            self.write_data(bars[0], None)
            return

        change = bars[0].close - bars[1].close
        up_src = max(change, 0)
        down_src = -min(change, 0)
        if len(bars) < self.period + 1:
            self.write_data(bars[0], Data(None, up_src, down_src, None, None))
            return

        previous_data = self.get_data(bars[1])
        if previous_data.up is None and previous_data.down is None:
            source_up, source_down = self.sources_of_past_length(bars, up_src, down_src)

            sma_up = self.sma(source_up, self.period)
            sma_down = self.sma(source_down, self.period)

            up = sma_up
            down = sma_down
        else:
            up = self.alpha * up_src + (1 - self.alpha) * previous_data.up
            down = self.alpha * down_src + (1 - self.alpha) * previous_data.down

        if down == 0:
            rsi = 100
        elif up == 0:
            rsi = 0
        else:
            rsi = 100 - (100 / (1 + up / down))

        self.write_data(bars[0], Data(rsi, up_src, down_src, up, down))

    def sources_of_past_length(self, bars: List[Bar], up_src, down_src):
        # build up sources from previous data objects
        source_up: [float] = [up_src]
        source_down: [float] = [down_src]
        for idx in range(1, self.period):
            data = self.get_data(bars[idx])
            source_up.append(data.up_src)
            source_down.append(data.down_src)

        return source_up, source_down

    def sma(self, sources: [float], length: int):
        sum: float = 0
        for src in sources:
            sum += src

        return sum / length

    def get_line_names(self):
        return [f'rsi{str(self.period)}']

    def get_data_for_plot(self, bar: Bar):
        return [self.get_data(bar)]
