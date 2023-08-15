import os
import argparse
import logging
import pkgutil
from .core import Zelus, Mode

logger = logging.getLogger('zelus')

install_files = [
    {
        "source": "data/zelus.service",
        "dest": "etc/systemd/system/zelus.service",
        "replace": True
    },
    {
        "source": "data/zelus.yml",
        "dest": "etc/zelus/zelus.yml",
        "replace": False
    }
]


def setLoggingLevel(verbosity):
    if verbosity == 0:
        logging.basicConfig(level=logging.INFO)
    elif verbosity >= 1:
        logging.basicConfig(level=logging.DEBUG)


def parseMode(mode):
    if mode == 'monitor':
        return Mode.MONITOR
    elif mode == 'enforce':
        return Mode.ENFORCE
    elif mode == 'strict':
        return Mode.STRICT


def install(install_root='/'):
    # Ensure directories exist
    os.makedirs(
        os.path.join(
            install_root,
            'etc/zelus'
        ),
        mode=0o700,
        exist_ok=True
    )

    for f in install_files:

        if (
            not os.path.isfile(os.path.join(install_root, f['dest'])) or
            f['replace']
        ):
            with open(os.path.join(install_root, f['dest']), 'w') as out_file:
                out_file.write(
                    pkgutil.get_data(
                        "zelus",
                        f["source"]
                    ).decode()
                )


def main():
    parser = argparse.ArgumentParser(
        prog='zelus',
        description='Monitor and enforce routes using netlink')

    parser.add_argument('-c', '--config', default='config.yml')
    parser.add_argument(
        '-i', '--interface',
        nargs='+', required=True,
        default=os.environ.get('ZELUS_MONITORED_INTERFACES', 'eth0')
    )
    parser.add_argument(
        '-t', '--table',
        nargs='+',
        default=os.environ.get('ZELUS_MONITORED_TABLES', 'main').split()
    )
    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=int(os.environ.get('ZELUS_LOGLEVEL', '0'))
    )
    parser.add_argument(
        '--mode', '-m',
        choices=[
            'monitor',
            'enforce',
            'strict'
        ],
        default='enforce')

    args = parser.parse_args()

    setLoggingLevel(args.verbose)

    log = 'cli arguments: '
    for (k, v) in args._get_kwargs():
        log = log + f'{k}: {v} '

    logger.debug(log)

    z = Zelus(
        mode=parseMode(args.mode),
        monitored_interfaces=args.interface,
        monitored_tables=args.table,
        configuration_path=args.config
    )

    h = z.monitor()

    try:
        h.join()
    except KeyboardInterrupt:
        print("Exiting!")
        exit(0)
