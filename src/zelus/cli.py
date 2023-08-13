import argparse
import logging
# import yaml
from .core import Zelus, Mode

logger = logging.getLogger('zelus')


def setLoggingLevel(verbosity):
    if verbosity == 1:
        logging.basicConfig(level=logging.WARNING)
    elif verbosity == 2:
        logging.basicConfig(level=logging.INFO)
    elif verbosity >= 3:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.ERROR)


def parseMode(mode):
    if mode == 'monitor':
        return Mode.MONITOR
    elif mode == 'enforce':
        return Mode.ENFORCE
    elif mode == 'strict':
        return Mode.STRICT


def cb(msg):
    print(msg)


def main():
    parser = argparse.ArgumentParser(
        prog='zelus',
        description='Monitor and enforce routes using netlink')

    # parser.add_argument('-c', '--config', default='config.yml')
    # parser.add_argument('-i', '--interface', action='append', required=True)
    parser.add_argument('-i', '--interface', nargs='+', required=True)
    # parser.add_argument('-t', '--table', action='append', default=['main'])
    parser.add_argument('-t', '--table', nargs='+', default=['main'])
    parser.add_argument('--verbose', '-v', action='count', default=0)
    parser.add_argument(
        '--mode', '-m',
        choices=[
            'monitor',
            'enforce',
            'strict'
        ],
        default='monitor')

    args = parser.parse_args()

    setLoggingLevel(args.verbose)

    log = 'cli arguments: '
    for (k, v) in args._get_kwargs():
        log = log + f'{k}: {v} '

    logger.debug(log)

    z = Zelus(
        mode=parseMode(args.mode),
        monitored_interfaces=args.interface,
        monitored_tables=args.table
    )

    h = z.monitor()

    try:
        h.join()
    except KeyboardInterrupt:
        print("Exiting!")
        exit(0)
