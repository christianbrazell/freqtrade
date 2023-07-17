# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from typing import Optional
from pandas import DataFrame
from datetime import datetime
from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta

from freqtrade.persistence import Trade
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy.base import StrategyBase


class MACDCrossStrategy01(StrategyBase):
    """
    This is a strategy template to get you started.
    More information in https://www.freqtrade.io/en/latest/strategy-customization/

    You can:
        :return: a Dataframe with all mandatory indicators for the strategies
    - Rename the class name (Do not forget to update class_name)
    - Add any methods you want to build your strategy
    - Add any lib you need to build your strategy

    You must keep:
    - the lib in the section "Do not remove these libs"
    - the methods: populate_indicators, populate_entry_trend, populate_exit_trend
    You should keep:
    - timeframe, minimal_roi, stoploss, trailing_*
    """
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = True

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    # minimal_roi = {
    #     "0": 0.20,
    #     "240": 0.06,
    #     "360": 0.03,
    #     "1440": 0
    # }

    # SharpeHyperOptLoss
    minimal_roi = {
        "0": 0.253,
        "1514": 0.217,
        "2174": 0.039,
        "6556": 0
    }

    stoploss = -0.14127

    # Trailing stop-loss
    trailing_stop = True
    trailing_stop_positive = 0.067
    trailing_stop_positive_offset = 0.23557
    trailing_only_offset_is_reached = True

    # Optimal ticker interval for the strategy.
    timeframe = '1m'

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # disable dataframe from being checked so we can modify it and it is not invalidated
    disable_dataframe_checks = False

    # These values can be overridden in the "ask_strategy" section in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    # startup_candle_count: int = 20 * 60

    # Strategy parameters
    # ------------------------------------
    # bollinger bands
    bb_timeperiod = CategoricalParameter(categories=[20 * 60, 20 * 60 * 4], default=20 * 60 * 4, space="buy", optimize=True)

    # bollinger bands
    macd_fast = CategoricalParameter(categories=[9 * 60, 9 * 60 * 4], default=9 * 60 * 4, space="buy", optimize=True)
    macd_slow = CategoricalParameter(categories=[50 * 60, 50 * 60 * 4], default=50 * 60 * 4, space="buy", optimize=True)

    # the percentage of volatility in the market
    volatility_percentage = DecimalParameter(0.025, 0.10, default=abs(stoploss), space="buy", optimize=True)

    # Optional order type mapping.
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # Optional order time in force.
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc'
    }

    # @property
    # def protections(self):
    #     return [
    #         {
    #             "method": "CooldownPeriod",
    #             "stop_duration": self.post_prediction_entry_window.value
    #         }
    #     ]

    @property
    def plot_config(self):
        return {
        'main_plot': {
            'bb_lowerband2': {'color': 'green'},
            'bb_middleband1': {'color': 'red'},
            'bb_upperband2': {'color': 'green'}
        },
        'subplots': {
            "MACD": {
                'macd': {'color': 'blue'},
                'macdsignal': {'color': 'orange'},
                'macdhist': {'color': 'green'},
            }
        }
    }

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        """
        Customize leverage for each new trade. This method is only called in futures mode.

        :param pair: Pair that's currently analyzed
        :param current_time: datetime object, containing the current datetime
        :param current_rate: Rate, calculated based on pricing settings in exit_pricing.
        :param proposed_leverage: A leverage proposed by the bot.
        :param max_leverage: Max leverage allowed on this pair
        :param entry_tag: Optional entry_tag (buy_tag) if provided with the buy signal.
        :param side: 'long' or 'short' - indicating the direction of the proposed trade
        :return: A leverage amount, which is between 1.0 and max_leverage.
        """
        return 3.0

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """
        # RSI
        # dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_timeperiod.value)
        # dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_timeperiod.value)
        # dataframe['ma'] = ta.MA(dataframe, timeperiod=100)

        # MACD
        macd = ta.MACD(dataframe, fast=self.macd_fast.value, slow=self.macd_slow.value)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        for std in [1, 2, 3]:
            # Bollinger bands
            bollinger = qtpylib.bollinger_bands(dataframe['close'], window=self.bb_timeperiod.value, stds=std)
            dataframe[f'bb_lowerband{std}'] = bollinger['lower']
            dataframe[f'bb_middleband{std}'] = bollinger['mid']
            dataframe[f'bb_upperband{std}'] = bollinger['upper']

        # calculate a volatility percentage based on the bb and close price
        dataframe['volatility_percentage'] = (
                 dataframe['bb_upperband2'] - dataframe['bb_lowerband2']
        ) / dataframe['close']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        dataframe.loc[
            (
                # the volatility percentage needs to be greater than the stop loss percentage to
                # ensure potential gains are bigger then the potential loss
                (dataframe['volatility_percentage'] >= self.volatility_percentage.value) &

                (dataframe[f'macd'] > dataframe[f'macdsignal']) &
                (dataframe[f'close'] < dataframe[f'bb_middleband1']) &
                (dataframe[f'close'] > dataframe[f'bb_middleband1'] * (1 + self.stoploss)) &
                (dataframe[f'volume'] > 0)
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                # the volatility percentage needs to be greater than the stop loss percentage to
                # ensure potential gains are bigger then the potential loss
                (dataframe['volatility_percentage'] >= self.volatility_percentage.value) &

                (dataframe[f'macd'] < dataframe[f'macdsignal']) &
                (dataframe[f'close'] > dataframe[f'bb_middleband1']) &
                (dataframe[f'close'] < dataframe[f'bb_middleband1'] * (1 - self.stoploss)) &
                (dataframe[f'volume'] > 0)
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        dataframe.loc[
            (
                (dataframe[f'close'] > dataframe[f'bb_upperband3'])
            ), 'exit_long'] = 1

        dataframe.loc[
            (
                (dataframe[f'close'] < dataframe[f'bb_lowerband3'])
            ), 'exit_short'] = 1

        return dataframe
