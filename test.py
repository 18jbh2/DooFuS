## Testing program for DooFuS
##
## TEST MODULE WRITERS, PLEASE READ:
##      - A test returns 1 if successful, and 0 otherwise.
##      - Use traceback.print_tb to print the full trace of the exception.
##      - Catch all errors in your module so other tests will be performed!
##      - Add your module to the main method or it won't be called.
##
## To use: python3 test.py <test1> <test2> ... <testn>

import sys
import traceback

def _test_dfs():
    import modules.dfs.dfs as dfs

    prefix = "DFS test: "

    try:
        # Test DFS instantiation
        file_system = dfs.DFS("test_dfs.json")

        # Remove and add file
        file_system.delete_file("newfile")
        ls = file_system.list_files()
        file_system.add_file("newfile", "userA")
        if len(ls) == len(file_system.list_files()):
           print(prefix + "ERROR: list_files() did not reflect change in file list")
           return 0

        # Try to remove non-existent file
        try:
            file_system.delete_file("ff")
            print(prefix + "ERROR: was able to \"remove\" nonexistent file.")
            return 0
        except dfs.DFSRemoveFileError:
            pass 

        # Try to add pre-existing file
        try:
            file_system.add_file("newfile", "userA")
            print(prefix + "ERROR: was able to add the same file twice.")
            return 0
        except dfs.DFSAddFileError:
            pass

    # All unintentional errors caught here
    except Exception as e:
        print(prefix + str(e))
        traceback.print_tb(e.__traceback__)
        return 0

    print(prefix + "SUCCESS")
    return 1

def _test_Msg_abstraction():
    prefix = "Msg abstraction test: "
    try:
        from modules.network.msg import Msg
        if not Msg.VERIFY == "V":
            return 0

        return 1

    except Exception as e:
        print(prefix + str(e))
        traceback.print_tb(e.__traceback__)
        return 0

if __name__ == "__main__":
    outcome = 0

    for test in sys.argv[1:]:

        if test == "dfs":
            outcome += _test_dfs()

        if test == "Msg":
            outcome += _test_Msg_abstraction()

        ## ADDITIONAL MODULES:
        #elif test == "othertestmodule":
        #	outcome += _other_test_module() 

    result = "Success" if outcome == len(sys.argv[1:]) else "Failure"
    print(result + ": passed " + str(outcome) + " of " + str(len(sys.argv[1:])) + " testing modules.")
