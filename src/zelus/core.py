import os
from enum import Enum, IntEnum
import logging
import re
import threading
import select
import yaml
from jinja2 import Environment, FileSystemLoader
import jinja2

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pyroute2 import IPRoute

logger = logging.getLogger('zelus')


class RouteType(IntEnum):
    # https://github.com/svinota/pyroute2/blob/6bf02c1f461b471a012658f043c7c47d66fd20f5/pyroute2/netlink/rtnl/__init__.py#L179

    unspec = 0
    unicast = 1
    local = 2
    broadcast = 3
    anycast = 4
    multicast = 5
    blackhole = 6
    unreachable = 7
    prohibit = 8
    throw = 9
    nat = 10
    xresolve = 11

    def __str__(self):
        return f'{self.name}'


class RouteProto(IntEnum):
    # https://github.com/svinota/pyroute2/blob/6bf02c1f461b471a012658f043c7c47d66fd20f5/pyroute2/netlink/rtnl/__init__.py#L201
    unspec = 0
    redirect = 1
    kernel = 2
    boot = 3
    static = 4
    gated = 8
    ra = 9
    mrt = 10
    zebra = 11
    bird = 12
    dnrouted = 13
    xorp = 14
    ntk = 15
    dhcp = 16

    def __str__(self):
        return f'{self.name}'


class RouteScope(IntEnum):
    universe = 0
    site = 200
    link = 253
    host = 254
    nowhere = 255

    def __str__(self):
        return f'{self.name}'


class InterfaceMap():
    def __init__(self):
        # This maps interface names to interface ids
        self.interface_map = {}

        # This maps interface ids to interface names
        self._interface_id_map = {}

        with IPRoute() as ipr:
            interfaces = ipr.get_links()
            for i in interfaces:
                interface_name = i.get_attr('IFLA_IFNAME')
                interface_id = i['index']
                interface_addrs = ipr.get_addr(label=interface_name)

                self._interface_id_map[interface_id] = interface_name

                self.interface_map[interface_name] = {
                    'id': interface_id,
                    'addresses': [i.get_attr('IFA_ADDRESS') for i in interface_addrs]
                }

    def getInterfaceId(self, interface_name):
        try:
            return self.interface_map[interface_name]['id']
        except KeyError:
            try:
                # Maybe we passed a interface id?
                interface_id = int(interface_name)
                return interface_id
            except ValueError:
                logger.error(
                    f'Could not find interface id for {interface_name}'
                )
                return None

    def getInterfaceName(self, interface_id):
        '''Translate an interface id into an interface name'''
        try:
            return self._interface_id_map[interface_id]
        except KeyError:
            logger.error(
                f"Unable to get interface name for interface {interface_id}"
            )
            return interface_id


class TableMap():
    def __init__(self):
        with open('/etc/iproute2/rt_tables', 'r') as route_tables:
            self.table_map = {}  # This maps table names to table ids
            self._table_id_map = {}  # This maps table ids to table names
            for line in route_tables.readlines():
                m = re.match(r'^(\d+)\s+(\w+)$', line)
                if m is not None:
                    self.table_map[m.group(2)] = int(m.group(1))
                    self._table_id_map[int(m.group(1))] = m.group(2)
                    logger.debug(
                        f'Found table {m.group(1)}={m.group(2)} in rt_tables'
                    )

    def getTableId(self, table_name):
        try:
            return self.table_map[table_name]
        except KeyError:
            try:
                # Maybe we passed a table id?
                return int(table_name)
            except ValueError:
                logger.error(
                    f'Could not find table id for {table_name}. '
                )
            return None

    def getTableName(self, table_id):
        '''Translate a table_id into a table name'''
        try:
            return self._table_id_map[table_id]
        except KeyError:
            logger.error(f"Unable to get table name for table {table_id}")
            return table_id


class RouteBuilder():
    '''
    This class builds route objects
    '''
    def __init__(self):
        # Generate table mapping information
        self.table_map = TableMap()
        self.interface_map = InterfaceMap()

    def build(
        self,
        dst_len=32,
        src_len=0,
        tos=0,
        table='main',
        proto='static',
        scope='universe',
        dst=None,
        type='unicast',
        gateway=None,
        prefsrc=None,
        iinterface=None,
        ointerface=None
    ):
        '''Build a route from kwargs'''

        try:
            # Parse proto
            proto = RouteProto[proto.lower()]
        except Exception as ex:
            logger.critical(
                f'Unable to parse proto={proto}. Options are {[str(p) for p in RouteProto]}. Exception: {ex}'
            )
            proto = RouteProto.static

        try:
            # Parse type
            type = RouteType[type.lower()]
        except Exception as ex:
            logger.critical(
                f'Unable to parse type={type}. Options are {[str(t) for t in RouteType]}. Exception: {ex}'
            )
            type = RouteType.unicast

        try:
            # Parse scope
            scope = RouteScope[scope.lower()]
        except Exception as ex:
            logger.critical(
                f'Unable to parse scope={scope}. Options are {[str(s) for s in RouteScope]}. Exception: {ex}'
            )
            scope = RouteScope.universe

        logger.debug(
            f'Building route: '
            f'dst_len={dst_len} '
            f'src_len={src_len} '
            f'tos={tos} '
            f'table_id={table} '
            f'proto={proto} '
            f'scope={scope} '
            f'type={type} '
            f'gateway={gateway} '
            f'prefsrc={prefsrc} '
            f'dst={dst} '
            f'iif={iinterface} '
            f'oif={ointerface} '
        )

        # Try to parse the iinterface as an interface name
        if iinterface is not None:
            iif = self.interface_map.getInterfaceId(iinterface)
        else:
            iif = None

        # Try to parse the ointerface as an interface name
        if ointerface is not None:
            oif = self.interface_map.getInterfaceId(ointerface)
        else:
            oif = None

        # Try to parse table an a table name
        try:
            table_id = self.table_map.getTableId(table)
        except KeyError:
            try:
                # Maybe we passed a table id?
                table_id = int(table)
            except ValueError:
                logger.error(
                    f'Could not find table id for {table}. '
                )

        # TODO check that dst_len is valid

        # TODO check that src_len is valid

        # TODO check that tos is valid

        # TODO check that proto is valid

        # TODO check that scope is valid

        # TODO check that dst is valid ip address

        # TODO check that type is valid

        # TODO check that gateway is valid ip address

        # TODO check that prefsrc is valid ip address

        return Route(
            dst_len=dst_len,
            src_len=src_len,
            tos=tos,
            table_id=table_id,
            proto=proto,
            scope=scope,
            type=type,
            gateway=gateway,
            prefsrc=prefsrc,
            dst=dst,
            iif=iif,
            oif=oif,
            route_builder=self
        )

    def fromNetlinkMessage(self, message):
        '''Build a route from a netlink message'''
        try:
            dst_len = message['dst_len']
        except KeyError:
            dst_len = None

        try:
            src_len = message['src_len']
        except KeyError:
            src_len = None

        try:
            tos = message['tos']
        except KeyError:
            tos = None

        try:
            table_id = message['table']
        except KeyError:
            table_id = None

        try:
            proto = message['proto']
        except KeyError:
            proto = None

        try:
            scope = message['scope']
        except KeyError:
            scope = None

        try:
            type = message['type']
        except KeyError:
            type = None

        try:
            gateway = message.get_attr('RTA_GATEWAY')
        except AttributeError:
            gateway = None

        try:
            prefsrc = message.get_attr('RTA_PREFSRC')
        except AttributeError:
            prefsrc = None

        try:
            dst = message.get_attr('RTA_DST')
        except AttributeError:
            dst = None

        try:
            iif = message.get_attr('RTA_IIF')
        except AttributeError:
            iif = None

        try:
            oif = message.get_attr('RTA_OIF')
        except AttributeError:
            oif = None

        logger.debug(
            f'Building route: '
            f'dst_len={dst_len} '
            f'src_len={src_len} '
            f'tos={tos} '
            f'table_id={table_id} '
            f'proto={proto} '
            f'scope={scope} '
            f'type={type} '
            f'gateway={gateway} '
            f'prefsrc={prefsrc} '
            f'dst={dst} '
            f'iif={iif} '
            f'oif={oif} '
        )

        return Route(
            dst_len=dst_len,
            src_len=src_len,
            tos=tos,
            table_id=table_id,
            proto=proto,
            scope=scope,
            type=type,
            gateway=gateway,
            prefsrc=prefsrc,
            dst=dst,
            iif=iif,
            oif=oif,
            route_builder=self
        )


class Route():
    def __init__(
        self,
        dst_len=32,
        src_len=0,
        tos=0,
        table_id=254,  # main
        proto=RouteProto.static,
        scope=RouteScope.universe,
        dst=None,
        type=RouteType.unicast,
        gateway=None,
        prefsrc=None,
        iif=None,
        oif=None,
        route_builder=None
    ):

        self.dst_len = dst_len
        self.src_len = src_len
        self.tos = tos
        self.table_id = table_id
        self.proto = proto
        self.scope = scope
        self.dst = dst
        self.type = type
        self.gateway = gateway
        self.prefsrc = prefsrc
        self.iif = iif
        self.oif = oif
        self._route_builder = route_builder

    def getTableName(self):
        if self._route_builder is not None:
            return self._route_builder.table_map.getTableName(self.table_id)
        else:
            return self.table_id

    def getInterfaceName(self, interface_id):
        if self._route_builder is not None:
            return (
                self._route_builder.interface_map.getInterfaceName(interface_id)
            )
        else:
            return interface_id

    def __repr__(self):
        return f'Route({self.__format__(None)})'

    def __format__(self, format_spec):
        f = ''

        route_type = RouteType(self.type)

        if route_type is not RouteType.unicast:
            f = f + f'{route_type} '

        if self.dst is not None:
            f = f + f'{self.dst} '
        else:
            f = f + 'default '

        if self.gateway is not None:
            f = f + f'via {self.gateway} '

        f = f + f'dev {self.getInterfaceName(self.oif)} '

        if self.getTableName() != 'main':
            f = f + f'table {self.getTableName()} '

        route_proto = RouteProto(self.proto)
        if route_proto != RouteProto.static:
            f = f + f'proto {route_proto} '

        route_scope = RouteScope(self.scope)
        if route_scope != RouteScope.universe:
            f = f + f'scope {route_scope} '

        if self.prefsrc is not None:
            f = f + f'src {self.prefsrc} '

        return f.strip()

    def __eq__(self, other):
        return (
            self.dst_len == other.dst_len and
            self.src_len == other.src_len and
            self.tos == other.tos and
            self.table_id == other.table_id and
            self.proto == other.proto and
            self.scope == other.scope and
            self.dst == other.dst and
            self.type == other.type and
            self.gateway == other.gateway and
            self.prefsrc == other.prefsrc and
            self.iif == other.iif and
            self.oif == other.oif
        )

    def __ne__(self, other):
        return (
            self.dst_len != other.dst_len or
            self.src_len != other.src_len or
            self.tos != other.tos or
            self.table_id != other.table_id or
            self.proto != other.proto or
            self.scope != other.scope or
            self.dst != other.dst or
            self.type != other.type or
            self.gateway != other.gateway or
            self.prefsrc != other.prefsrc or
            self.iif != other.iif or
            self.oif != other.oif
        )

    def add(self, ipr):
        '''Add the route to the routing table'''
        ipr.route(
            'add',
            dst_len=self.dst_len,
            src_len=self.src_len,
            tos=self.tos,
            table_id=self.table_id,
            proto=self.proto,
            scope=self.scope,
            type=self.type,
            gateway=self.gateway,
            prefsrc=self.prefsrc,
            dst=self.dst,
            iif=self.iif,
            oif=self.oif
        )

    def delete(self, ipr):
        '''Delete the route to the routing table'''
        ipr.route(
            'del',
            dst_len=self.dst_len,
            src_len=self.src_len,
            tos=self.tos,
            table_id=self.table_id,
            proto=self.proto,
            scope=self.scope,
            type=self.type,
            gateway=self.gateway,
            prefsrc=self.prefsrc,
            dst=self.dst,
            iif=self.iif,
            oif=self.oif
        )


class Mode(Enum):
    MONITOR = 1
    ENFORCE = 2
    STRICT = 3


class ConfigurationHandler(FileSystemEventHandler):
    def __init__(self, zelus):
        self._zelus = zelus

    def on_modified(self, event):
        if not event.is_directory:
            logger.info(f"Configuration changed detected. Reloading. {event}")
            self._zelus._loadConfiguration()


class Zelus():
    def __init__(
            self, mode,
            monitored_interfaces, monitored_tables=['main'],
            configuration_path="zelus.yml"):

        self.mode = mode
        logger.info(f"Zelus in {mode} mode!")

        self._route_builder = RouteBuilder()

        self._ipr = IPRoute()

        self.stop = threading.Event()

        # This is used to ensure that if config is reloaded while a new netlink message
        # arrives we do not end up with an empty list of protected routes while building
        # the new protected route list
        self._protected_routes_lock = threading.Lock()

        self.table_map = TableMap()
        self.interface_map = InterfaceMap()

        self._monitored_tables = []  # This is a list of table ids to monitor
        for t in monitored_tables:
            try:
                table_id = self.table_map.getTableId(t)
                self._monitored_tables.append(table_id)
                table_name = self.table_map.getTableName(table_id)
                logger.debug(f'Monitoring table {table_name}({table_id})')
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

        # This is a list of interface ids to monitor
        self._monitored_interfaces = []

        for interface_name in monitored_interfaces:
            interface_id = self.interface_map.getInterfaceId(interface_name)
            self._monitored_interfaces.append(interface_id)
            i_name = self.interface_map.getInterfaceName(interface_id)
            logger.debug(
                f"Monitoring interface {i_name}({interface_id})"
            )

        self._configuration_path = configuration_path
        self._protected_routes = []

        self.loadConfiguration()

    def __del__(self):
        self._ipr.close()

    def loadConfiguration(self):
        # 1. Load initial configuation

        self._loadConfiguration()

        # 2. Watch for configuration file changes and reload

        config_observer = Observer()
        config_handler = ConfigurationHandler(self)

        config_observer.schedule(
            config_handler,
            os.path.expanduser(self._configuration_path)
        )

        config_observer.start()

    def _loadConfiguration(self):
        '''
        Load configuation from config_path and construct routes to be enforced
        and interfaces to be monitored
        '''
        protected_routes = []

        try:
            # 1. Use config file as jinja2 template
            template_loader = FileSystemLoader(
                searchpath=os.path.dirname(
                    os.path.expanduser(self._configuration_path)
                )
            )

            environment = Environment(loader=template_loader)
            template = environment.get_template(
                os.path.basename(
                    os.path.expanduser(self._configuration_path)
                )
            )

            configuration_content = template.render(
                interfaces=self.interface_map.interface_map
            )

            logger.debug(f"Configuation file content: {configuration_content}")

            # 2. Load templated content as yaml
            contents = yaml.safe_load(configuration_content)
            logger.debug(f"Configuation file content: {contents}")

            protected_routes = contents['protected_routes']

        except OSError as ex:
            logger.critical(f'Unable to load configuration file @ {self._configuration_path}. Exception: {ex}')
        except KeyError:
            logger.critical(f'Configuration file @ {self._configuration_path} must contain protected_routes key.')
        except yaml.YAMLError as ex:
            logger.critical(f'Error in configuration file @ {self._configuration_path}: {ex}')
        except jinja2.exceptions.UndefinedError as ex:
            logger.critical(f'Error in configuration file @ {self._configuration_path}: {ex}')
        except Exception as ex:
            logger.critical(f"Could not load configuration @ {self._configuration_path}. Exception: {ex}")

        # Clear old protected routes
        new_protected_routes = []

        for route in protected_routes:
            try:
                ointerface = route['ointerface']
                oif = self._route_builder.interface_map.getInterfaceId(ointerface)
            except KeyError:
                logger.critical(f'Each route must have a ointerface. Not protecting. {route}')
                continue

            if oif is None:
                logger.critical(f'Unable to find interface id for ointerface {ointerface}. Not protecting. {route}')
                continue

            if oif not in self._monitored_interfaces:
                logger.critical(
                    f'Protected route ointerface {ointerface} '
                    f'must be in the monitored interface list '
                    f'{[ self._route_builder.interface_map.getInterfaceName(i) for i in self._monitored_interfaces]}. '
                    f'Not protecting. route: {route}'
                )
                continue

            try:
                table_name = route['table']
                table_id = self._route_builder.table_map.getTableId(table_name)
            except KeyError:
                table_id = 254  # main

            if table_id not in self._monitored_tables:
                logger.critical(
                    f'Protected route table {self.table_map.getTableName(table_id)} '
                    f'must be in the monitored table list '
                    f'{[ self._route_builder.table_map.getTableName(t) for t in self._monitored_tables]}. '
                    f'Not protecting. route: {route}'
                )
                continue

            try:
                new_protected_route = self._route_builder.build(**route)  # Pass in dictionary as kwargs
                logger.info(f"Protecting route {new_protected_route}")
                new_protected_routes.append(new_protected_route)
            except Exception as ex:
                logger.critical(f"Could not build route for {route}. {ex}")

        # LOCK PROTECTED ROUTES while we update
        self._protected_routes_lock.acquire()
        self._protected_routes = new_protected_routes
        self._protected_routes_lock.release()

        self.initialSync()

    def formatRoute(self, action, route):
        return (
            f'ip route {action} {route}'
        )

    def initialSync(self):
        # Process initial routes
        logger.info("Performing initial sync.")

        initial_routes = []

        for message in self._ipr.get_routes():
            # Process all the intial routes construct the inital route list
            initial_route = self._processMessage(message)
            if initial_route is not None:
                initial_routes.append(initial_route)

        logger.debug(
            f'initial routes: {initial_routes}')

        logger.info("Adding missing protected routes")
        self._protected_routes_lock.acquire()
        for route in self._protected_routes:
            if route not in initial_routes:
                if self.mode in [Mode.ENFORCE, Mode.STRICT]:
                    logger.info(f'Missing initial route. Enforcing. {self.formatRoute("add", route)}')
                    try:
                        route.add(self._ipr)
                    except Exception as ex:
                        logger.critical(f'Unable to add route. {self.formatRoute("add", route)} Exception: {ex}')
                else:
                    logger.info(f'Missing initial route: {route}')
        self._protected_routes_lock.release()

        if self.mode == Mode.STRICT:
            logger.info("Removing unprotected routes")
            for route in initial_routes:
                if route not in self._protected_routes:
                    logger.info(f'Extra initial route. Enforcing. {self.formatRoute("del", route)}')
                    try:
                        route.delete(self._ipr)
                    except Exception as ex:
                        logger.critical(f'Unable to delete route. {self.formatRoute("del", route)} Exception: {ex}')

        logger.info("Initial sync completed.")

    def monitor(self):
        thread = threading.Thread(target=self._monitor)
        thread.start()
        return thread

    def _processMessage(self, message):
        if message['event'] in ['RTM_NEWROUTE', 'RTM_DELROUTE']:
            if (
                message.get_attr('RTA_TABLE') in self._monitored_tables and
                message.get_attr('RTA_OIF') in self._monitored_interfaces
            ):
                logger.debug(
                    f'NETLINK MESSAGE: {message}'
                )

                route = self._route_builder.fromNetlinkMessage(message)

                logger.debug(f'{route}')

                if message['event'] == 'RTM_DELROUTE':
                    logger.info(
                        f'Detected change: {self.formatRoute("del", route)}'
                    )
                    if self.mode in [Mode.ENFORCE, Mode.STRICT]:
                        self._enforceDeletedRoute(route)

                if message['event'] == 'RTM_NEWROUTE':
                    logger.info(
                        f'Detected change: {self.formatRoute("add", route)}'
                    )
                    if self.mode == Mode.STRICT:
                        self._enforceAddedRoute(route)

                return route
            return None

    def routeProtected(self, route):
        '''Check if the route is in the protected routes list'''

        self._protected_routes_lock.acquire()
        protected = route in self._protected_routes
        self._protected_routes_lock.release()

        return protected

    def _enforceDeletedRoute(self, route):
        '''
        Check if the deleted route is in the protected route list and re-added
        it if it is.
        '''

        if self.routeProtected(route) is False:
            # Route is protected. re-add it
            route.add(self._ipr)
            logger.info(f'Enforcing. Reverting {self.formatRoute("add", route)}')

    def _enforceAddedRoute(self, route):
        '''
        Check if the added route is in the protected route list and delete it
        if it is not
        '''

        if self.routeProtected(route) is False:
            # Route is not protected. Remove it
            route.delete(self._ipr)
            logger.info(f'Enforcing. Reverting {self.formatRoute("del", route)}')

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
