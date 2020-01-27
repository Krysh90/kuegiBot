from functools import reduce

import plotly.graph_objects as go
from kuegi_bot.bots.trading_bot import  TradingBot
from kuegi_bot.utils.trading_classes import Position,  Account, Bar, Symbol
from typing import List


class Strategy:
    def __init__(self):
        self.logger = None
        self.order_interface = None
        self.symbol = None

    def myId(self):
        return "GenericStrategy"

    def prepare(self, logger, order_interface):
        self.logger = logger
        self.order_interface = order_interface

    def init(self, bars: List[Bar], account: Account, symbol: Symbol):
        self.symbol = symbol

    def min_bars_needed(self) -> int:
        return 5

    def owns_signal_id(self, signalId: str):
        return False

    def got_data_for_position_sync(self, bars: List[Bar]) -> bool:
        raise NotImplementedError

    def get_stop_for_unmatched_amount(self, amount:float,bars:List[Bar]):
        return None

    def prep_bars(self, is_new_bar: bool, bars: list):
        pass

    def position_got_opened(self, position: Position, bars: List[Bar], account: Account, open_positions):
        pass

    def manage_open_order(self, order, position, bars, to_update, to_cancel, open_positions):
        pass

    def manage_open_position(self, p, bars, account, pos_ids_to_cancel):
        pass

    def open_orders(self, is_new_bar, directionFilter, bars, account, open_positions):
        pass

    def add_to_plot(self, fig: go.Figure, bars: List[Bar], time):
        pass


class MultiStrategyBot(TradingBot):

    def __init__(self, logger=None, directionFilter=0):
        super().__init__(logger, directionFilter)
        self.myId = "MultiStrategy"
        self.strategies: List[Strategy] = []

    def add_strategy(self, strategy: Strategy):
        self.strategies.append(strategy)

    def prepare(self, logger, order_interface):
        super().prepare(logger, order_interface)
        for strat in self.strategies:
            strat.prepare(logger, order_interface)

    def init(self, bars: List[Bar], account: Account, symbol: Symbol, unique_id: str = ""):
        self.logger.info(
            "init with strategies: %s" % reduce((lambda result, strategy: result + ", " + strategy.myId()),
                                                self.strategies,
                                                ""))
        for strat in self.strategies:
            strat.init(bars, account, symbol)
        super().init(bars=bars, account=account, symbol=symbol, unique_id=unique_id)

    def min_bars_needed(self):
        return reduce(lambda x, y: max(x, y.min_bars_needed()), self.strategies, 5)

    def prep_bars(self, bars: list):
        for strategy in self.strategies:
            strategy.prep_bars(self.is_new_bar, bars)

    def got_data_for_position_sync(self, bars: List[Bar]):
        return reduce((lambda x, y: x and y.got_data_for_position_sync(bars)), self.strategies, True)

    def position_got_opened(self, position: Position, bars: List[Bar], account: Account):
        [signalId, direction] = self.split_pos_Id(position.id)
        for strat in self.strategies:
            if strat.owns_signal_id(signalId):
                strat.position_got_opened(position, bars, account, self.open_positions)
                break

    def get_stop_for_unmatched_amount(self, amount:float,bars:List[Bar]):
        if len(self.strategies) == 1:
            return self.strategies[0].get_stop_for_unmatched_amount(amount,bars)
        return None

    def manage_open_orders(self, bars: List[Bar], account: Account):
        self.sync_executions(bars, account)

        to_cancel = []
        to_update = []
        for order in account.open_orders:
            posId = self.position_id_from_order_id(order.id)
            if posId is None or posId not in self.open_positions.keys():
                continue
            [signalId, direction] = self.split_pos_Id(posId)
            for strat in self.strategies:
                if strat.owns_signal_id(signalId):
                    strat.manage_open_order(order, self.open_positions[posId], bars, to_update, to_cancel,
                                            self.open_positions)
                    break

        for order in to_cancel:
            self.order_interface.cancel_order(order)

        for order in to_update:
            self.order_interface.update_order(order)

        pos_ids_to_cancel = []
        for p in self.open_positions.values():
            [signalId, direction] = self.split_pos_Id(p.id)
            for strat in self.strategies:
                if strat.owns_signal_id(signalId):
                    strat.manage_open_position(p, bars, account, pos_ids_to_cancel)
                    break

        for posId in pos_ids_to_cancel:
            self.cancel_all_orders_for_position(posId, account)
            del self.open_positions[posId]

    def open_orders(self, bars: List[Bar], account: Account):
        for strat in self.strategies:
            strat.open_orders(self.is_new_bar, self.directionFilter, bars, account, self.open_positions)


    def add_to_plot(self, fig: go.Figure, bars: List[Bar], time):
        super().add_to_plot(fig, bars, time)
        for strat in self.strategies:
            strat.add_to_plot(fig, bars, time)