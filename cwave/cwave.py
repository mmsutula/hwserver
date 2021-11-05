import sys, time
import ctypes
import logger 

logger = logging.getLogger(__name__)

 def init(name, cwave_addr):

    try: 
        ctypes.windll.kernel32.SetDllDirectoryW('C:/Program Files/CWave/x64')
        self.lib = ctypes.cdll.LoadLibrary('CWAVE_DLL.dll')
        logger.debug('Loaded DLL')
    except: 
        logger.error('Failed to load DLL')

    global ADDR 
    ADDR = 'cwave', cwave_addr

    self.laser = cwave.cwave_connect(ADDR.encode('ASCII'))
    if ret == 1
        pass 
    else 
        logger.error('Failed to connect to CWave')


class cwave:

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback)
        self._Close()

    def dispatch(self,client,wl):
        tstart = time.time()
        #todo: add wavelength range for vis/IR to tune OPO or SHG 
        coarsetune = self.set_intvalue(b'opo_lambda',wavelength*100)
