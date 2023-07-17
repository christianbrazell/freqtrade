import numpy as np  # noqa
import pandas as pd  # noqa
import random
from datetime import datetime, timedelta
from pandas import DataFrame
from freqtrade.strategy import (
    DecimalParameter,
    IntParameter,
    CategoricalParameter
)
from user_data.strategies import StrategyBase
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy.base import StrategyBase
import freqtrade.vendor.qtpylib.indicators as qtpylib


# This class is a sample. Feel free to customize it.
class IntoTheBlockStrategy01(StrategyBase):
    """
    This is a strategy template to get you started.
    More information in https://github.com/freqtrade/freqtrade/blob/develop/docs/bot-optimization.md

    You can:
        :return: a Dataframe with all mandatory indicators for the strategies
    - Rename the class name (Do not forget to update class_name)
    - Add any methods you want to build your strategy
    - Add any lib you need to build your strategy

    You must keep:
    - the lib in the section "Do not remove these libs"
    - the prototype for the methods: minimal_roi, stoploss, populate_indicators, populate_buy_trend,
    populate_sell_trend, hyperopt_space, buy_strategy_generator
    """

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 2

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 0.20,
        "240": 0.06,
        "360": 0.03,
        "1440": 0
    }

    stoploss = -0.05

    # Trailing stop-loss
    trailing_stop = True
    # trailing_stop_positive = 0.01
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.15
    # trailing_stop_positive_offset = 0.075
    trailing_only_offset_is_reached = True

    # Optimal ticker interval for the strategy.
    timeframe = '1m'

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # disable dataframe from being checked so we can modify it and it is not invalidated
    disable_dataframe_checks = True

    # These values can be overridden in the "ask_strategy" section in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    # startup_candle_count: int = 10

    # Optional order type mapping.
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': False
    }

    # Optional order time in force.
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc'
    }

    # bollinger bands
    bb_timeperiod = CategoricalParameter(categories=[20 * 60, 20 * 60 * 4], default=20 * 60, space="buy", optimize=True)

    # the time in minutes after a prediction that an entry is still valid
    post_prediction_entry_window = IntParameter(1, 10, default=15, space="buy", optimize=True)
    reference_price_offset_percentage = DecimalParameter(0.001, 0.04, default=0.02, space="buy", optimize=True)
    volatility_percentage = DecimalParameter(0.025, 0.10, default=0.05, space="buy", optimize=True)

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration": self.post_prediction_entry_window.value
            }
        ]

    plot_config = {
        'main_plot': {
            'bb_lowerband1': {'color': 'green'},
            'bb_middleband1': {'color': 'red'},
            'bb_upperband1': {'color': 'green'}
        },
        'subplots': {
            "Volatility Percentage": {
                'volatility_percentage': {'color': 'purple'}
            },
            "Reference Price Offset Percentage": {
                'reference_price_offset_percentage': {'color': 'orange'}
            },
            "Prediction": {
                'expected_move': {'type': 'bar'}
            },
            "Base Pair": {
                'bb_lowerband1_spot_pair': {'color': 'green'},
                'bb_middleband1_spot_pair': {'color': 'red'},
                'bb_upperband1_spot_pair': {'color': 'green'},
                'close_spot_pair': {'color': 'blue'}
            }
        }
    }

    def informative_pairs(self):
        return self.get_informative_spot_pairs()

    def add_ta(self, dataframe):
        # RSI
        # dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_timeperiod.value)
        # dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_timeperiod.value)
        # dataframe['ma'] = ta.MA(dataframe, timeperiod=100)
        #
        for std in [1, 2]:
            # Bollinger bands
            bollinger = qtpylib.bollinger_bands(dataframe['close'], window=self.bb_timeperiod.value, stds=std)
            dataframe[f'bb_lowerband{std}'] = bollinger['lower']
            dataframe[f'bb_middleband{std}'] = bollinger['mid']
            dataframe[f'bb_upperband{std}'] = bollinger['upper']

        return dataframe

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
        spot_pair = self.get_spot_pair(metadata['pair'])

        # add the informative spot pair
        informative = self.dp.get_pair_dataframe(pair=spot_pair, timeframe=self.timeframe)
        informative = self.add_ta(informative)
        informative.columns = [f"{col}_spot_pair" for col in informative.columns]

        dataframe = self.add_ta(dataframe)

        dataframe = dataframe.merge(
            informative,
            left_on='date',
            right_on=f'date_spot_pair',
            how='left'
        )

        dataframe = self.add_external_data(
            dataframe,
            metadata,
            route='order-book/predictions/v1/50',
            data_keys=['expected_move', 'reference_price'],
        )

        # notice how we forward fill the dataframe so that hourly predictions exist in every minute
        dataframe = dataframe.ffill(limit=60 - 1)
        # then we convert the predictions to
        dataframe['expected_move'] = self.convert_to_numbers(dataframe['expected_move'])

        # calculate a volatility percentage based on the bb and close price
        dataframe['volatility_percentage'] = ((
                                                      dataframe['bb_upperband2_spot_pair'] - dataframe[
                                                  'bb_lowerband2_spot_pair']
                                              ) / dataframe['close_spot_pair'])

        dataframe['reference_price_offset_percentage'] = (
                                                                 dataframe['close_spot_pair'] - dataframe[
                                                             'reference_price'].astype(float)
                                                         ) / dataframe['close_spot_pair']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame populated with indicators
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                # only buy in first 15 minutes of the hourly prediction
                #     (dataframe['date'].dt.minute < self.post_prediction_entry_window.value) &

                    # the volatility percentage needs to be greater than twice the stop loss percentage to
                    # ensure potential gains are bigger then the potential loss
                    # (dataframe['volatility_percentage'] >= self.volatility_percentage.value) &

                    # only trade when the close price is outside the bollinger bands at 2 standard deviations
                    (
                            (dataframe['close_spot_pair'] < dataframe['bb_lowerband1_spot_pair']) |
                            (dataframe['close_spot_pair'] > dataframe['bb_upperband1_spot_pair'])
                    ) &

                    # decide which direction to trade based on the prediction
                    (
                            (
                                    (self.get_direction(metadata['pair']) == 1) &
                                    (dataframe['expected_move'] == 1) #&

                                    # # spot price needs to be a certain percentage below the reference price of when the
                                    # # up prediction is made
                                    # (dataframe[
                                    #      'reference_price_offset_percentage'] <= self.reference_price_offset_percentage.value)
                            ) |
                            (
                                    (self.get_direction(metadata['pair']) == -1) &
                                    (dataframe['expected_move'] == -1) #&

                                    # # spot price needs to be a certain percentage above the reference price of when the
                                    # # down prediction is made
                                    # (dataframe[
                                    #      'reference_price_offset_percentage'] >= self.reference_price_offset_percentage.value)
                            )
                    )
            ),
            'enter_long'] = 1

        # self.print_dataframe_terminal(
        #     dataframe,
        #     metadata['pair'],
        #     tail=5,
        #     logger_name='freqtrade.strategy.interface'
        # )

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame populated with indicators
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """
        dataframe.loc[(dataframe['close'] == 0), 'exit_long'] = 1

        return dataframe
