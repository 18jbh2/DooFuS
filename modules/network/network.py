import json
import socket
import logging
import sys
from threading import Lock
from .entity import Entity
from .node import Node
from .networkconfig import NetworkConfig
from modules.logger.log import Log

logger = None
log = None

# _nodes:       mapping of host -> node, all nodes created since startup
# _names:       mapping of host -> id (currently not updated when hosts disconnect)
# _users:       mapping of id -> host (currently not updated when hosts disconnect)
# _seen:        all hosts encountered (theoretically ever)
# _new:         hosts first connected to during this run
# _connected:   hosts currently connected to
# _verified:    hosts verifed during this run


class Network:
    LISTEN_PORT = 8889
    TESTING_MODE = False

    def __init__(self, me, test):
        self._me = me
        self.TESTING_MODE = test

        self._nodes = {}
        self._seen = set()
        self._new = set()
        self._connected = set()
        self._verified = set()
        self._config = NetworkConfig()

        self._names = {}
        self._users = {}

        self._lock = Lock()

        self._load_from_config()

        log = Log()
        self._logger = log.get_logger()
        


######################################
## Network Outgoing Interface
#####################################
    def connect_to_host(self, host):
        if host in self._connected:
            return False

        self._logger.info("Network: Attempting to connect to %s" % (host))

        try:
            # Connect to host
            # for testing locally: 8825 -> 8826 and 8826 -> 8825
            test_port = 8825 + (self._me.port % 2)
            port = test_port if self.TESTING_MODE else self.LISTEN_PORT

            conn = socket.create_connection((host, port), 1)
            node = Node(host, port, conn)

            # send host your credentials
            node.send_verification(self._me.id)

            # add node to all relevant sets
            self._nodes[host] = node
            self._connected.add(host)
            if host not in self._seen:
                self._new.add(host)
                self._seen.add(host)

            if host in self._verified:
                print("Connected to %s at %s" % (self._names[host], host))
            else:
                self._logger.info("Network: Connection to %s succeeded. Awaiting verification..." % (host))
            return True
        except:
            self._logger.info("Network: Connection to %s failed" % (host))
            return False

    def disconnect_from_host(self, host):
        if host in self._connected: self._connected.remove(host)
        if host in self._verified: self._verified.remove(host)
        if host in self._nodes: self._nodes[host].close_connection()
        if host in self._names:
            id = self._names[host]
            self._users[id] = None
            self._names.remove(host)

    def broadcast_heartbeats(self):
        try:
            for host in self._connected:
                if host in self._verified:
                    if self._nodes[host].send_heartbeat():
                        self._logger.debug("Network: Heartbeat sent to %s" % (host))
                    else:
                        self._logger.info("Network: Heartbeat to %s failed" % (host))
                        self.disconnect_from_host(host)
        except RuntimeError:
            # This is from _connected changing size
            pass


    def broadcast_host(self, new_host):
        if new_host not in self._verified:
            self._logger.warning("Network: Shouldn't broadcast an unverified host")
            return

        try:
            self._logger.info("Network: Broadcasting %s" % (new_host))
            for host in self._connected:
                if host in self._verified and not host == new_host:
                    self._nodes[host].send_host(new_host)
        except RuntimeError:
            # This is from _connected changing size
            pass

    def send_poke(self, id):
        if id not in self._users or self._users[id] not in self._nodes:
            return False

        self._nodes[self._users[id]].send_poke()

    def send_file(self, host, file_name):
        if not self.connected(host):
            print("Tried to send file to disconnected host")
            return
        
        self._nodes[host].send_file(file_name)
    
    def send_network_info(self, host):
        if not host in self._nodes:
            return

        node = self._nodes[host]
        node.send_verified_ids(self._users.keys())


    def send_dfs(self, files, host):
        if not host in self._nodes:
            return

        node = self._nodes[host]        


######################################
## Network Internal Interface
#####################################
    def print_all(self):
        print(self._nodes)
        print(self._new)
        print(self._seen)
        print(self._connected)
        print(self._verified)
        print(self._users)

    def startup(self):
        try:
            for host in self._seen:
                self.connect_to_host(host)
        except RuntimeError:
            # This is from hosts being added to _seen
            pass

    def verify_host(self, host, id):
        verified = id in self._users and self._users[id] == None

        if self._users[id]:
            self._logger.info("someone is already signed in as %s" % (id))

        if verified:
            if host in self._connected:                
                print("Connected to %s at %s" % (id, host))
            else:
                self._logger.info("Network: %s identity verified as %s. Awaiting connection..." % (host, id))
                
            self._verified.add(host)

            # for now
            self._users[id] = host
            self._names[host] = id

            # if this is a new host save it
            if (host not in self._seen or host in self._new) and not self.TESTING_MODE:
                self._config.store_host(host)
                self._new.add(host)
                self._logger.info("Added host %s to network config file" % (host))
        else:
            self._logger.info("Network: %s identity %s not recognized" % (host, id))

            # if there is a connection get rid of it
            if host in self._nodes:
                self.disconnect_from_host(host)

        return verified

    def add_users(self, ids):
        for id in ids:
            if not id in self._users:
                self._users[id] = None
                self._config.store_id(id)

    def record_heartbeat(self, host):
        if not host in self._nodes:
            self._logger.error("can't recieve heartbeat from nonexistent node")
            return
        self._nodes[host].record_heartbeat()

    def connected(self, host):
        if not host in self._connected: return False

        node = self._nodes[host]
        alive = node.is_alive()

        if not alive:
            self.disconnect_from_host(host)

        return alive

    def verified(self, host):
        return host in self._verified

    def users(self):
        return self._users.keys()

    def id(self, host):
        if host not in self._users:
            return "HUGONO"
        return self._users[host]

    def get_seen_nodes(self):
        return list(self._seen)

    def get_connected_nodes(self):
        return list(self._connected)


######################################
## Helper Functions
#####################################

    def _load_from_config(self):
        for host in self._config.hosts():
            # don't add self (for running local test)
            if not self.TESTING_MODE and not host == self._me.host:
                self._seen.add(host)

        ids = self._config.identities()

        for id in ids:
            self._users[id] = None
