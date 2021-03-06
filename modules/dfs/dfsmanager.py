## DFS Manager
## Soft state:
##  _fs: FS objet
##  _network: Network object
##  _file_list: initial file list from FS object

from threading import Lock
import modules.dfs.dfs as dfs
from modules.dfs.filewriter import Filewriter

class DFSManager:

    def __init__(self, network, my_id, filewriter, log_name = None):
        self._network   = network
        self._id        = my_id
        self._fs        = dfs.DFS(log_name)
        self._file_list = self._fs.list_files()
        self._filewriter = filewriter

    # Based on our failure model, calculates number of replicas needed
    # given the priority and number of nodes
    def _compute_replica_count(self, priority, node_count):
        return node_count

    def get_DFS_ref(self):
        return self._fs

    def get_log(self):
        return self._fs.return_log()

    def update_with_dfs_json(self, dfs):
        files = dfs["files"]
        for file in files:
            name = file["filename"]
            uploader = file["uploader"]
            replicas = file["replicas"]
            if not self._fs.check_file(name, uploader):
                self._fs.add_file(name, uploader, replicas)
            else:
                self._fs.add_replicas(name, replicas)

###### For updating local file system ########

    def add_to_fs(self, filename, uploader):
        self._fs.add_file(filename, uploader)
            
    def add_replica(self, filename, replicator):
        self._fs.add_replicas(filename, [replicator])

    def clear_files(self):
        self._fs.clear_files()

##############################################

    def acknowledge_replica(self, filename, uploader, replica_host):
        if self._fs.check_file(filename, uploader):
            self._fs.add_replicas(filename, replica_host)
        else:
            self._fs.add_file(filename, uploader, [replica_host])

    def upload_file(self, filepath, priority = 0.5):
        filename = filepath[filepath.rfind("/") + 1:]

        if self._fs.check_file(filename, self._id):
            print("This file is already on the dfs")
            return False
            #raise dfs.DFSAddFileError(filename, self._id)

        ## choose replicas (all)
        total_nodes = len(self._network._connected)

        if not total_nodes:
            print("No nodes on network")
            return False
        #raise DFSManagerAddFileError(filename)

        num_replicas = self._compute_replica_count(priority, total_nodes)

        ## call network send file function
        i = 0
        ## currently just adds to host in order
        for host in self._network._connected:
            if i == num_replicas:
                break
            data = self._filewriter.read_from_file(filepath)
            if not data:
                print("No such file: %s" % (filepath))
                return False
            self._network.send_replica(host, filename, self._id, "1", "1", data)

            i += 1

        #self._fs.add_file(filename, self._id)
        
        # ####### Don't need this because the replicas will tell them
        # send dfs with updated file list to everyone
        #for host in self._network.get_connected_nodes():
         #   print("about to tell host %s the new dfs" % (host))
          #  self._network.add_file(host, filename, self._id) # Send metadata telling hosts about new file   


    def store_replica(self, filename, uploader, part, total, data):
        ## add replica to dfs
        self.acknowledge_replica(filename, uploader, self._id)
        ## write data to filename
        self._filewriter.write_to_replica(filename, part, total, data)

    def dump_replica(self, filename):
        file = self._fs.get_file(filename)
        if not file:
            print("Invalid name")
            return

        # Check that you are a replica before removing file from disk
        file_replicas = file["replicas"]
        if self._id in file_replicas:
            self._filewriter.remove(filename)

        ## remove from _fs
        self._fs.delete_file(filename)

    ## Throws DFSManagerDownloadError exception. Please catch it.
    def download_file(self, filename, dst = "files/"):

        # set file destination
        self._filewriter.set_path(filename, dst)

        ## Check if you are a replica
        file = self._fs.get_file(filename)
        if not file:
            print("Invalid name")
            return

        file_replicas = file["replicas"]

        if self._id in file_replicas:
            self._filewriter.write_to_file(filename)

        ## Find active replicas
        ##active_hosts  = self._network._connected
        ##active_replicas = list(filter(lambda host: host in file_replicas, active_hosts))
        active_replicas = []
        for user in file_replicas:
            if self._network.user_connected(user):
                active_replicas += [self._network.host(user)]


        if len(active_replicas) == 0:
            print("No active replicas of file")
            return
            #raise DFSManagerDownloadError(filename, "No active replicas of file")

        self._network.request_file(active_replicas[0], filename, "1", "1")

    def delete_file(self, filename):
        ## remove from disk (if present)
        ## remove from _fs
        ## tell network to tell replicas
        file = self._fs.get_file(filename)
        if not file:
            print("Invalid name")
            return

        # Check that you are a replica before removing file from disk
        file_replicas = file["replicas"]
        if self._id in file_replicas:
            self._filewriter.remove(filename)

        ## remove from _fs
        self._fs.delete_file(filename)

        ## tell network to tell replicas
        self._network.delete_file(filename)

        print("Deleted %s" % (filename))

    def set_priority(self, filename, priority):
        ## punt
        pass

    def node_offline(self, node):
        ## punt
        pass

    def node_online(self, node):
        ## punt
        pass
    
    def display_files(self):
        online = []
        offline = []
        for file in self._fs.list_files():
            if self._file_online(file):
                online.append(file)
            else:
                offline.append(file)
                
        print("*Online*")
        for file in online:
            self._display_file(file)
            
        print("")
        print("*Offline*")
        for file in offline:
            self._display_file(file)

    def _display_file(self, file):                
        filename = truncate(file.get("filename"), 22).ljust(25)
        uploader = truncate(file.get("uploader"), 22).ljust(25)
        replicas = (', '.join(str(replica) for replica in file.get("replicas")))

        print("%s Uploaded by %s Replicated on %s" % (filename, uploader, replicas))


    def _file_online(self, file):
        replicas = file.get("replicas")

        for r in replicas:
            if self._network.user_connected(r):
                return True
            
        return False



##########################
## Utilities
#########################

# cuts off the end of the text for better formatting
def truncate(text, length):
    if len(text) > length:
        return text[:(length-3)] + "..."
    return text

        

###########################
## DFSManager Exceptions
###########################
class DFSManagerError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)


class DFSManagerIOError(DFSManagerError):
    def __init__(self, msg):
        DFSManagerError.__init__(self, "DFSManager i/o error: \n" + msg)

class DFSManagerDownloadError(DFSManagerError):
    def __init__(self, filename, additional = ""):
        DFSManagerError.__init__(self, "DFSManager download file error: " + additional + "\nfilename: " + filename)

class DFSManagerAddFileError(DFSManagerError):
    def __init__(self, filename):
        DFSManagerError.__init__(self, "DFSManager add file error: Could not upload file to replicas\n"
            + "filename: " + filename)

class DFSManagerRemoveFileError(DFSManagerError):
    def __init__(self, filename):
        DFSManagerError.__init__(self, "DFS remove file error: Could not add file\n"
            + "filename: " + filename) 

