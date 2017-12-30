import datetime
import json
import logging
from typing import Dict

import pika
import dateutil.parser

from coinrat.strategy_replayer import StrategyReplayer
from coinrat.domain import Pair
from coinrat.candle_storage_plugins import CandleStoragePlugins
from coinrat.market_plugins import MarketPlugins
from coinrat.order_storage_plugins import OrderStoragePlugins
from coinrat.strategy_plugins import StrategyPlugins
from .task_types import TASK_REPLY_STRATEGY


class TaskConsumer:
    def __init__(
        self,
        rabbit_connection: pika.BlockingConnection,
        candle_storage_plugins: CandleStoragePlugins,
        orders_storage_plugins: OrderStoragePlugins,
        strategy_plugins: StrategyPlugins,
        market_plugins: MarketPlugins

    ) -> None:
        super().__init__()
        self.candle_storage_plugins = candle_storage_plugins
        self.orders_storage_plugins = orders_storage_plugins
        self.strategy_plugins = strategy_plugins
        self.market_plugins = market_plugins

        self._channel = rabbit_connection.channel()
        self._channel.queue_declare(queue='tasks')

        def rabbit_message_callback(ch, method, properties, body) -> None:
            decoded_body = json.loads(body.decode("utf-8"))
            print(decoded_body)

            task = decoded_body['task']
            if task == TASK_REPLY_STRATEGY:
                self.process_reply_strategy(decoded_body['data'])

            else:
                logging.info("[Rabbit] Task received -> not supported | %r", decoded_body)

        self._channel.basic_consume(rabbit_message_callback, queue='events', no_ack=True)

    def process_reply_strategy(self, data: Dict) -> None:
        logging.info("[Rabbit] Task %s -> not supported | %r", TASK_REPLY_STRATEGY, data)

        start = dateutil.parser.parse(data['start']).replace(tzinfo=datetime.timezone.utc)
        end = dateutil.parser.parse(data['stop']).replace(tzinfo=datetime.timezone.utc)

        # todo: make it configurable from frontend
        configuration = {
            'long_average_interval': datetime.timedelta(hours=1),
            'short_average_interval': datetime.timedelta(minutes=15),
        }

        orders_storage = self.orders_storage_plugins.get_order_storage(data['orders_storage'])
        candle_storage = self.candle_storage_plugins.get_candle_storage(data['candles_storage'])
        replayer = StrategyReplayer(self.strategy_plugins, self.market_plugins)

        print('----')

        replayer.replay(
            data['strategy_name'],
            data['market'],
            Pair.from_string(data['pair']),
            candle_storage,
            orders_storage,
            start,
            end,
            configuration
        )

        print('--222')

    def run(self):
        self._channel.start_consuming()