from enum import Enum
from pyroute2 import IPRoute
import logging
import re
import threading
import select


logger = logging.getLogger('zelus')
class Route():
    def __init__(self, table, dst, gateway, interface):
        self.table = table

        with open('/etc/iproute2/rt_tables', 'r') as route_tables:
            self._table_map = {}
            for line in route_tables.readlines():
                m = re.match(r'^(\d+)\s+(\w+)$', line)
                if m is not None:
                    self._table_map[m.group(2)] = int(m.group(1))
                    logger.debug(
                        f'Found table {m.group(1)}={m.group(2)} in rt_tables'
                    )

        try:
            self.table_id = self._table_map[table]
        except KeyError:
            try:
                # Maybe we passed a table id?
                table_id = int(table)
                self.table_id = table_id
            except ValueError:
                logger.error(
                    f'Could not find table id for {table}. '

        self.dst = dst
        self.gateway = gateway

        self.interface = interface

        self.oif = None
        interfaces = self._ipr.get_links()
        for i in interfaces:
            if i.get_attr('IFLA_IFNAME') == interface:
                self.oif = i['index']

        if self.oif == None:
            try:
                # Maybe we passed a interface id?
                interface_id = int(interface)
                self.oif = interface_id
            except ValueError:
                logger.error(
                    f'Could not find interface id for {interface}. '


class Mode(Enum):
    MONITOR = 1
    ENFORCE = 2
    STRICT = 3


class Zelus():
    def __init__(
            self, mode,
            monitored_interfaces, monitored_tables=['main'],
            protected_routes=[]):

        self.mode = mode
        logger.debug(f"Zelus in {mode} mode!")

        self._protected_routes = protected_routes

        self._ipr = IPRoute()

        self.stop = threading.Event()

        self._monitored_tables = []
        with open('/etc/iproute2/rt_tables', 'r') as route_tables:
            self._table_map = {}
            for line in route_tables.readlines():
                m = re.match(r'^(\d+)\s+(\w+)$', line)
                if m is not None:
                    self._table_map[m.group(2)] = int(m.group(1))
                    logger.debug(
                        f'Found table {m.group(1)}={m.group(2)} in rt_tables'
                    )

            for t in monitored_tables:
                try:
                    self._monitored_tables.append(self._table_map[t])
                    logger.debug(f'Monitoring table {t}({self._table_map[t]})')
                except KeyError:
                    try:
                        # Maybe we passed a table id?
                        table_id = int(t)
                        self._monitored_tables.append(table_id)
                        logger.debug(f'Monitoring table UNKNOWN({table_id})')
                    except ValueError:
                        logger.error(
                            f'Could not find table id for {t}. '
                            f'Not monitoring this table')

        self._monitored_interfaces = []

        interfaces = self._ipr.get_links()
        for m_i in monitored_interfaces:
            for i in interfaces:
                if i.get_attr('IFLA_IFNAME') == m_i:
                    if_id = i['index']
                    self._monitored_interfaces.append(if_id)
                    logger.debug(f"Monitoring interface {m_i}({if_id})")

    def __del__(self):
        self._ipr.close()

    def loadConfiguration(self, config_path):
        '''
        Load configuation from config_path and construct routes to be enforced
        and interfaces to be monitored
        '''
        pass

    def formatRoute(self, message):
        if message['event'] == 'RTM_NEWROUTE':
            action = 'add'
        elif message['event'] == 'RTM_DELROUTE':
            action = 'del'

        table_id = message.get_attr('RTA_TABLE')

        # Try to extract the nice table name
        # If we can't just use the table_id
        table_name = table_id

        for (table, id) in self._table_map.items():
            if table_id == id:
                table_name = table
                break

        dest = message.get_attr('RTA_DST')
        gw = message.get_attr('RTA_GATEWAY')

        oif = message.get_attr('RTA_OIF')
        oif_name = self._ipr.get_links(oif)[0].get_attr('IFLA_IFNAME')

        return (
            f'ip route {action} table {table_name} '
            f'{dest} via {gw} dev {oif_name}'
        )

    def monitor(self):
        thread = threading.Thread(target=self._monitor)
        thread.start()
        return thread

    def _processMessage(self, message):
        if message['event'] in ['RTM_NEWROUTE', 'RTM_DELROUTE']:
            logger.debug(
                f'Netlink message event:{message["event"]} '
                f'table: {message.get_attr("RTA_TABLE")} '
                f'OIF: {message.get_attr("RTA_OIF")}'
            )
            if (
                message.get_attr('RTA_TABLE') in self._monitored_tables and
                message.get_attr('RTA_OIF') in self._monitored_interfaces
            ):
                logger.info(f'Detected change: {self.formatRoute(message)}')

            if (
                message['event'] == 'RTM_DELROUTE' and
                self.mode in [Mode.ENFORCE, Mode.STRICT]
            ):
                self._enforceDeletedRoute(message)

            if (
                message['event'] == 'RTM_ADDROUTE' and
                self.mode == Mode.STRICT
            ):
                self._enforceAddedRoute(message)

    def routeProtected(self, msg):
        '''Check if the route is in the protected routes list'''

        for route in self._protected_routes:
            # Check if the route is a protected route
            if (
                message.get_attr('RTA_TABLE') == route.table_id and
                message.get_attr('RTA_OIF') == route.oif and
                message.get_attr('RTA_DST') == route.dst and
                message.get_attr('RTA_GATEWAY') = route.gateway
            ):
                return True

            return False

    def _enforceDeletedRoute(self, message):
        '''
        Check if the deleted route is in the protected route list and re-added it if it is.
        '''
        if message['event'] != 'RTM_DELROUTE':
            return

        if self.routeProtected(message) is False:
            # Route is protected. re-add it
            self._ipr.route(
                'add',
                dst = message.get_attr('RTA_DST')
                gateway = message.get_attr('RTA_GATEWAY')
                oif = message.get_attr('RTA_OIF')
                table = message.get_attr('RTA_TABLE')
            )
            logger.info(f'Enforcing. Reverting {self.formatRoute(message)}')

    def _enforceAddedRoute(self, message):
        '''
        Check if the added route is in the protected route list and delete it if it is not
        '''
        if message['event'] != 'RTM_ADDROUTE':
            return

        if self.routeProtected(message) is False:
            # Route is not protected. Remove it
            self._ipr.route(
                'del',
                dst = message.get_attr('RTA_DST')
                gateway = message.get_attr('RTA_GATEWAY')
                oif = message.get_attr('RTA_OIF')
                table = message.get_attr('RTA_TABLE')
            )
            logger.info(f'Enforcing. Reverting {self.formatRoute(message)}')

    def _monitor(self):
        '''
        Monitor interfaces for changes in routing
        '''

        poll = select.poll()
        poll.register(self._ipr)
        self._ipr.bind()  # receive broadcasts on IPRoute

        while True:
            if self.stop.is_set():
                break

            events = poll.poll()
            for fd, flags in events:
                if fd == self._ipr.fileno():
                    for message in self._ipr.get():
                        self._processMessage(message)
