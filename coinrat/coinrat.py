import datetime
import logging

import dateutil.parser
import click
import sys
from typing import Tuple, Dict, NoReturn
from os.path import join, dirname

from click import Context
from dotenv import load_dotenv

from coinrat.domain import Market
from coinrat.domain.candle import CandleExporter
from coinrat.di_container import DiContainer
from coinrat.domain import CurrentUtcDateTimeFactory
from coinrat.domain import Pair, ForEndUserException, DateTimeInterval
from coinrat.domain.order import OrderExporter
from coinrat.market_plugins import MarketNotProvidedByAnyPluginException
from coinrat.strategy_plugins import StrategyNotProvidedByAnyPluginException

dotenv_path = join(dirname(__file__), '../.env')
load_dotenv(dotenv_path)

root = logging.getLogger()
root.setLevel(logging.DEBUG)

# Todo: solve proper logging configuration
# logs_file = join(dirname(__file__), '../logs/log.log')
# logger = logging.getLogger()
# logger.addHandler(RotatingFileHandler(logs_file, maxBytes=200000, backupCount=5))
# logger.setLevel(logging.INFO)

di_container = DiContainer()


@click.group('coinrat')
@click.version_option(version='0.1')
@click.help_option()
@click.pass_context
def cli(ctx: Context) -> None:
    pass


@cli.command(help='Shows available markets.')
def markets() -> None:
    click.echo('Available markers:')
    for market_name in di_container.market_plugins.get_available_markets():
        click.echo('  - {}'.format(market_name))


@cli.command(help='Shows market detail.')
@click.argument('market_name', nargs=1)
def market(market_name) -> None:
    try:
        market_obj: Market = di_container.market_plugins.get_market_class(market_name)
    except MarketNotProvidedByAnyPluginException as e:
        print_error_and_terminate(str(e))

    click.echo('Markets configuration structure:')
    print_structure_configuration(market_obj.get_configuration_structure())


@cli.command(help='Shows available synchronizers.')
def synchronizers() -> None:
    click.echo('Available synchronizers:')
    for synchronizer_name in di_container.synchronizer_plugins.get_available_synchronizers():
        click.echo('  - {}'.format(synchronizer_name))


@cli.command(help='Shows available candle storages.')
def candle_storages() -> None:
    click.echo('Available candle storages:')
    for synchronizer_name in di_container.candle_storage_plugins.get_available_candle_storages():
        click.echo('  - {}'.format(synchronizer_name))


@cli.command(help='Shows available order storages.')
def order_storages() -> None:
    click.echo('Available order storages:')
    for synchronizer_name in di_container.order_storage_plugins.get_available_order_storages():
        click.echo('  - {}'.format(synchronizer_name))


@cli.command(help='Shows available strategies.')
def strategies() -> None:
    click.echo('Available strategies:')
    for synchronizer_name in di_container.strategy_plugins.get_available_strategies():
        click.echo('  - {}'.format(synchronizer_name))


@cli.command(help='Shows strategy detail.')
@click.argument('strategy_name', nargs=1)
def strategy(strategy_name) -> None:
    try:
        strategy_obj: Market = di_container.strategy_plugins.get_strategy_class(strategy_name)
    except StrategyNotProvidedByAnyPluginException as e:
        print_error_and_terminate(str(e))

    click.echo('Strategy configuration structure:')
    print_structure_configuration(strategy_obj.get_configuration_structure())
    click.echo()
    click.echo(click.style(
        'You can provide this configuration via JSON file into `run_strategy` command using -c argument.\n',
        fg="green"
    ))


@cli.command(help="""
Exports candles into JSON file. Interval must be in UTC. \n\nExample: \n\n
    "python -m coinrat export_candles bittrex USD BTC \'2017-12-02T00:00:00\' \'2017-12-03T00:00:00\' output.json"
""")
@click.argument('market_name', nargs=1)
@click.argument('pair', nargs=2)
@click.argument('interval', nargs=2)
@click.argument('output_file', nargs=1)
@click.pass_context
def export_candles(
    ctx: Context,
    market_name,
    pair: Tuple[str, str],
    interval: Tuple[str, str],
    output_file: str
) -> None:
    storage = di_container.candle_storage_plugins.get_candle_storage('influx_db')
    pair = Pair(pair[0], pair[1])
    interval = DateTimeInterval(
        dateutil.parser.parse(interval[0]).replace(tzinfo=datetime.timezone.utc),
        dateutil.parser.parse(interval[1]).replace(tzinfo=datetime.timezone.utc)
    )
    exporter = CandleExporter(storage)
    exporter.export_to_file(output_file, market_name, pair, interval)


@cli.command(help="""
Exports orders into JSON file. Interval must be in UTC.

Example:
    "python -m coinrat export_orders bittrex USD BTC \'2017-12-02T00:00:00\' \'2017-12-03T00:00:00\' output.json"
""")
@click.argument('market_name', nargs=1)
@click.argument('pair', nargs=2)
@click.argument('interval', nargs=2)
@click.argument('output_file', nargs=1)
@click.pass_context
def export_orders(
    ctx: Context,
    market_name,
    pair: Tuple[str, str],
    interval: Tuple[str, str],
    output_file: str
) -> None:
    storage = di_container.order_storage_plugins.get_order_storage('influx_db')
    pair = Pair(pair[0], pair[1])
    interval = DateTimeInterval(
        dateutil.parser.parse(interval[0]).replace(tzinfo=datetime.timezone.utc),
        dateutil.parser.parse(interval[1]).replace(tzinfo=datetime.timezone.utc)
    )
    exporter = OrderExporter(storage)
    exporter.export_to_file(output_file, market_name, pair, interval)


@cli.command(help="""
Runs synchronization process. Synchronizes data from market into local database for analysis and strategies.

Example:
    python -m coinrat synchronize cryptocompare USD BTC
""")
@click.argument('synchronizer_name', nargs=1)
@click.argument('pair', nargs=2)
@click.pass_context
def synchronize(ctx: Context, synchronizer_name: str, pair: Tuple[str, str]) -> None:
    pair = Pair(pair[0], pair[1])

    synchronizer = di_container.synchronizer_plugins.get_synchronizer(
        synchronizer_name,
        di_container.candle_storage_plugins.get_candle_storage('influx_db'),
        di_container.event_emitter
    )
    synchronizer.synchronize(pair)


@cli.command(help="""
Starts trading with given strategy.

Example:
    python -m coinrat run_strategy double_crossover bittrex
""")
@click.argument('strategy_name', nargs=1)
@click.argument('pair', nargs=2)
@click.argument('market_names', nargs=-1)
@click.pass_context
def run_strategy(ctx: Context, strategy_name: str, pair: Tuple[str, str], market_names: Tuple[str]) -> None:
    pair = Pair(pair[0], pair[1])

    strategy = di_container.strategy_plugins.get_strategy(
        strategy_name,
        di_container.candle_storage_plugins.get_candle_storage('influx_db'),
        di_container.order_storage_plugins.get_order_storage('influx_db'),
        di_container.event_emitter,
        di_container.datetime_factory,
        # todo: make it configurable by definition from cmd line
        {
            'long_average_interval': 60 * 60,
            'short_average_interval': 15 * 60,
        }
    )

    try:
        markers = [
            di_container.market_plugins.get_market(marker_name, CurrentUtcDateTimeFactory(), {})
            for marker_name in market_names
        ]
        strategy.run(markers, pair)
    except ForEndUserException as e:
        print_error_and_terminate(str(e))


@cli.command()
@click.pass_context
def testing(ctx: Context) -> None:  # Todo: Used only for testing during development, remove it after
    print(di_container.candle_storage_plugins.get_available_candle_storages())


@cli.command(help="Starts an socket server for communication with frontend.")
@click.pass_context
def start_server(ctx: Context):
    di_container.socket_server.start()
    di_container.rabbit_event_consumer.start()


@cli.command(help="Runs consumer of planned tasks.")
@click.pass_context
def start_task_consumer(ctx: Context):
    di_container.task_consumer.run()


def print_structure_configuration(structure: Dict) -> None:
    for key, value in structure.items():
        if 'hidden' in value and value['hidden'] is True:
            continue

        title = value['title'] if 'title' in value else ''
        description = ' - ' + value['description'] if 'description' in value else ''
        click.echo('    {:<40} {}{}'.format(key + ':' + value['type'], title, description))


def print_error_and_terminate(error_message: str) -> NoReturn:
    click.echo(click.style('ERROR: {}\n'.format(error_message), fg='red'), err=True)
    sys.exit(1)


def main():
    cli(obj={})
