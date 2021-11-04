import socket, select
import logging, re, time, os, subprocess
import ctypes

logger = logging.getLogger(__name__)


class cwave:
    # DLLpath -> path to DLL file
    # HeaderPath -> path to header file 

    DLLpath = r'C:/path.dll'
    HeaderPath = r'C:/path.h'
    ADDR = {
        'cwave':
    }

    def __init__(self, cwave_addr):
        self.lib = windll.LoadLibrary(cwave.DLLpath)
        with open(cwave.HeaderPath,'rt') as f:
            self.header = f.read().split('\n')
        try:
            self.dispatch()
        except: 
            logger.exception('Failed to launch cwave')
        global ADDR 
        ADDR = 'cwave', cwave_addr
        self.laser = cwave()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback)
        self._Close()

    def dispatch(self,client,fn,timeout=60):
        tstart = time.time()
        out = cwave.cwave_connect(ipAddr.encode('ASCII'))
