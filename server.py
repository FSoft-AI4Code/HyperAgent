import multiprocessing
import os
import sys
from threading import Thread
import time
from typing import Any, Dict, List
from pylsp.python_lsp import PythonLSPServer, start_io_lang_server

def start(obj):
    obj.start()

class ClientServerPair:
    """
    A class to setup a client/server pair.

    args:
        start_server_in_process: if True, the server will be started in a process.
        check_parent_process: if True, the server_process will check if the parent process is alive.
    """

    def __init__(self, start_server_in_process=False, check_parent_process=False):
        # Client to Server pipe
        csr, csw = os.pipe()
        # Server to client pipe
        scr, scw = os.pipe()

        if start_server_in_process:
            ParallelKind = self._get_parallel_kind()
            self.server_process = ParallelKind(
                target=start_io_lang_server,
                args=(
                    os.fdopen(csr, "rb"),
                    os.fdopen(scw, "wb"),
                    check_parent_process,
                    PythonLSPServer,
                ),
            )
            self.server_process.start()
        else:
            self.server = PythonLSPServer(os.fdopen(csr, "rb"), os.fdopen(scw, "wb"))
            self.server_thread = Thread(target=start, args=[self.server])
            self.server_thread.start()

        self.client = PythonLSPServer(os.fdopen(scr, "rb"), os.fdopen(csw, "wb"))
        self.client_thread = Thread(target=start, args=[self.client])
        self.client_thread.start()

    def _get_parallel_kind(self):
        if os.name == "nt":
            return Thread

        if sys.version_info[:2] >= (3, 8):
            return multiprocessing.get_context("fork").Process

        return multiprocessing.Process