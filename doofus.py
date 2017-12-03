import json
import sys
import socket
import time
import threading
import urllib.request

from modules.network.network import Network
from modules.network.entity import Entity
import modules.dfs.dfs as dfs # DFS exceptions
from modules.dfs.dfs import DFS # DFS itself


local_test = False

LISTEN_PORT = 8889
ID = "r5"

my_host = None
my_port = None
my_id = None

network = None

dfs = None

def _get_ip():
    #Found from: https://stackoverflow.com/questions/2311510/getting-a-machines-external-ip-address-with-python/22157882#22157882
    return urllib.request.urlopen('http://ident.me').read().decode('utf8')
            
def connect_to_network():
    print("Connecting to network...")
    
    # switch to reading from a json file
    try:
        if local_test:
            network.connect_to_host(my_host)
        else:
            network.startup()
    finally:
        print("Tried all previously seen nodes")
    
    
            
####################################
## Outgoing Network Communication 
####################################
def send_heartbeats():
    while True:
        time.sleep(5)
        network.broadcast_heartbeats()


#####################################
## Incoming Network Communication
#####################################
def listen_for_messages(conn, host):    
    print("Listening to " + str(host))
    
    start_time = time.time()
    verified = False
    while True:
        msg = bytes.decode(conn.recv(1024)).split("-")
        type = msg[0]

        time_to_die = False

        # don't handle messages from unverified hosts
        verified = verified or network.verified(host)
        if not verified:
            if type == "ID":
                time_to_die = not handle_id_msg(msg, host)
            else:
                # should kill connection if not verified within 5 seconds
                time_to_die =  time.time() - start_time > 2        
        else:
            if not network.connected(host):
                time_to_die = True
            elif type == "H":
                print("Recieved heartbeat from %s" % (host))
                network.record_heartbeat(host)
            elif type == "HOST":
                time_to_die = not handle_host_msg(msg, host)

        # end thread and connection if node is no longer connected
        if time_to_die:
            print("Node %s no longer alive. Disconnecting" % (host))
            network.disconnect_from_host(host)
            conn.close()
            return
                
def handle_id_msg(msg, host):
    print("Received id from %s" % (host))
    id = msg[1] if len(msg) > 1 else None
        
    if not id:
        print("Parsing error for ID message")
        return False
        
    if network.verify_host(host, id):
        network.broadcast_host(host)
            
        # this host reached out to you, now connect to it
        if not network.connected(host):
            return network.connect_to_host(host)
            
    return True

    
def handle_host_msg(msg, host):
    new_host = msg[1] if len(msg) > 1 else None

    if not new_host:
        print("Parsing error for HOST message")
        return False
        
    if not network.connected(new_host):
        print("Notified %s online by %s" % (new_host, host))
        network.connect_to_host(new_host)
            
    return True

#########################################
## Thread for recieving new connections 
#########################################
def listen_for_nodes(listen):
    # start accepting new connections
    print("Listening...")
    while True:
        conn, addr = listen.accept()
        host = addr[0]
    #    network.print_all()
        print("Contacted by node at " + str(host))
        
        # start up a thread listening for messages from this connection
        threading.Thread(target=listen_for_messages, args=(conn, host,)).start()


        
#########################################
## Thread for user interaction
#########################################
def user_interaction():
    print("Welcome to DooFuS.")
    while True:
        text = input("-> ")
        if text == "nodes":
            print_node_list()
        elif text[:3] == "add":
            dfs.add_file(text[4:], my_id)
        elif text == "files":
            print_file_list()
        elif text[:6] == "delete":
            dfs.delete_file(text[7:])
        elif text == "help":
            print_help()
        elif text == "quit":
            disconnect()
        elif text == "start":
            connect_to_network()
        elif text == "netinfo":
            network.print_all()

def print_node_list():
    seen_nodes = network.get_seen_nodes()
    for host in seen_nodes:
        print(host + "\t\t" + ("connected" if network.connected(host) else "not connected"))

def print_file_list():
    for file in dfs.list_files():
        replicas = ""
        for replica in file.get("replicas"):
            replicas += replica
        print(file.get("filename") + "\t\t Uploaded by " + file.get("uploader") +
              ("\t\t replicated on: " + replicas))

def print_help():
    print("Commands:\n nodes - print node list\n files - print file list\n add [file_name] - add a file to the dfs\n delete [file_name] - delete a file from the dfs\n quit")

#########################################
## Startup 
#########################################
if __name__ == "__main__":
    
    dfs = DFS("test_dfs.json")

    local_test = len(sys.argv) > 2

    if local_test:
        print("You are running in testing mode")

    my_host = _get_ip() if not local_test else "127.0.0.1"    
    my_port = LISTEN_PORT if not local_test else int(sys.argv[2])        

    my_id = sys.argv[1]
    
    profile = Entity(my_host, my_port, my_id)
    network = Network(profile, local_test)
    
    # hello
    print("Starting up")

    listen = socket.socket()

    # tell os to recycle port quickly
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # start up listening socket and thread
    listen.bind((my_host, my_port))
    listen.listen()
    threading.Thread(target=listen_for_nodes, args=(listen,)).start()

    
    # attempt to connect to previously seen nodes
    # should this be on a separate thread?
    # pros: user can interact with program right away
    # cons: possible race conditions?
    threading.Thread(target=connect_to_network).start()

    # start up heatbeat thread
    threading.Thread(target=send_heartbeats).start()

    # start up UI thread
    threading.Thread(target=user_interaction).start()



   
