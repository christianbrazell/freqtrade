# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from freqtrade.strategy import (
    CategoricalParameter,
    DecimalParameter,
    IntParameter
)

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy.base import StrategyBase


class OrderBookStrategy02(StrategyBase):
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
    can_short: bool = False

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 0.20,
        "240": 0.10,
        "480": 0.05,
        "960": 0.025
    }

    stoploss = -0.10

    # Trailing stop-loss
    trailing_stop = True
    trailing_stop_positive = 0.025
    trailing_stop_positive_offset = 0.15
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
    startup_candle_count: int = 20 * 60

    # Strategy parameters
    # ------------------------------------
    # bollinger bands
    bb_timeperiod = CategoricalParameter(
        categories=[20 * 60, 20 * 60 * 4],
        default=20 * 60,
        space="buy",
        optimize=True
    )

    # the time in minutes after a prediction that an entry is still valid
    post_prediction_entry_window = IntParameter(
        1,
        10,
        default=5,
        space="buy",
        optimize=True
    )
    volatility_percentage = DecimalParameter(
        0.025,
        0.15,
        default=0.02,
        space="buy",
        optimize=True
    )

    # Optional order type mapping.
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': True
    }

    # Optional order time in force.
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc'
    }

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration": self.post_prediction_entry_window.value
            }
        ]

    @property
    def plot_config(self):
        return {
            'main_plot': {
                'bb_lowerband1': {'color': 'green'},
                'bb_middleband1': {'color': 'red'},
                'bb_upperband1': {'color': 'green'}
            },
            'subplots': {
                "Volatility Percentage": {
                    'volatility_percentage': {'color': 'purple'}
                },
                "Reference Price": {
                    'reference_price': {'color': 'orange'}
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
        return self.get_informative_spot_pairs()

    def add_ta(self, dataframe, post_fix=''):
        for std in [1, 2]:
            # Bollinger bands
            bollinger = qtpylib.bollinger_bands(
                dataframe[f'close_{post_fix}'],
                window=self.bb_timeperiod.value,
                stds=std
            )
            dataframe[f'bb_lowerband{std}_{post_fix}'] = bollinger['lower']
            dataframe[f'bb_middleband{std}_{post_fix}'] = bollinger['mid']
            dataframe[f'bb_upperband{std}_{post_fix}'] = bollinger['upper']

        # calculate a volatility percentage based on the bb and close price
        dataframe['volatility_percentage'] = (
                 dataframe[f'bb_upperband2_{post_fix}'] - dataframe[f'bb_lowerband2_{post_fix}']
        ) / dataframe[f'close_{post_fix}']

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
        informative.columns = [f"{col}_spot_pair" for col in informative.columns]
        dataframe = dataframe.merge(
            informative,
            left_on='date',
            right_on=f'date_spot_pair',
            how='left'
        )

        dataframe = self.add_ta(dataframe, post_fix='spot_pair')

        dataframe = self.add_external_data(
            dataframe,
            metadata,
            route='order-book/predictions/v1/50',
            data_keys=['expected_move', 'reference_price'],
        )

        # notice how we forward fill the dataframe so that hourly predictions exist in every minute
        dataframe = dataframe.ffill(limit=60 - 1)
        # then we convert the predictions to numbers
        dataframe['expected_move'] = self.convert_to_numbers(dataframe['expected_move'])

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
                # only buy in first 5 minutes of the hourly prediction
                (dataframe['date'].dt.minute < self.post_prediction_entry_window.value) &
                (dataframe['close_spot_pair'] < dataframe['reference_price']) &

                # the volatility percentage needs to be greater than twice the stop loss percentage to
                # ensure potential gains are bigger then the potential loss
                (dataframe['volatility_percentage'] >= self.volatility_percentage.value) &

                # only trade when the close price is outside the bollinger bands at 2 standard deviations
                (
                    (dataframe['close_spot_pair'] < dataframe['bb_lowerband1_spot_pair']) |
                    (dataframe['close_spot_pair'] > dataframe['bb_upperband1_spot_pair'])
                ) &
                (
                    (
                        (self.get_direction(metadata['pair']) == 1) &
                        (dataframe['expected_move'] == 1)
                    ) |
                    (
                        (self.get_direction(metadata['pair']) == -1) &
                        (dataframe['expected_move'] == -1)
                    )
                )
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        dataframe.loc[(dataframe['close'] == 0), 'exit_long'] = 1
        return dataframe
