from ctypes import *
import logging, re, time, os, subprocess
from functools import lru_cache
from types import FunctionType
import time

logger = logging.getLogger(__name__)

# Create a DLL function decorator to handle error checking
class WavemeterDLLError(IOError):
    pass
class ProcHandleError(Exception):
    pass

c_sref = c_char_p
c_lref = c_long
c_dref = c_double
c_LONG_PTR = c_long
c_unsigned_short = c_ushort

def check_proc_status(target):
    out = subprocess.check_output(['tasklist']).decode('utf-8')
    for line in out.split(os.linesep):
        if target.lower() == line.split(' ')[0].lower():
            return True
    return False

class wavemeter:
    # Make sure to call using python's with syntax:
    #
    # with wavemeter() as v:
    #     print 'Connected to: %s (%i)'%(v.headType,v.laser)
    #
    # Note: Low signal error returns -1 and high signal error returns -2
    #
    # Class Properties
    #   DLLpath -> path to DLL file
    #   HeaderPath -> path to header (for error handling and function prototypes)
    #   ERRORS -> dictionary with all possible error values
    # Instance  Properties
    #   lib -> handle to loaded DLL

    DLLpath = None #path to DLL. r'C:/Path/to/wlmData.dll' 
    HeaderPath = None #path to header file. r'C:/Path/to/wlmData.h'

    def __init__(self):
        self.lib = windll.LoadLibrary(wavemeter.DLLpath)
        # Load all of header file to memory
        with open(wavemeter.HeaderPath,'rt') as f:
            self.header = f.read().split('\n')
        # Startup WLM
        try:
            self.launchWLM()
        except: # Make non fatal error
            logger.exception('Failed to launch WLM')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._Close()

    def launchWLM(self,timeout=60):
        tstart = time.time()
        out = self.SendCommand('','ControlWLMEx',1+0x0040,0,0,timeout,1) # Start (no errors displayed)
        while self.SendCommand('','Instantiate',-1,0,0,0,return_error=0) <= 0:
            time.sleep(0.1)
        self.SendCommand('','Instantiate',0,1,0,0) # Allow returning no value
        return out

    def closeWLM(self):
        self.SendCommand('','ControlWLM',3,0,0)

    def _Close(self):
        windll.kernel32.FreeLibrary.argtypes = [c_void_p]
        windll.kernel32.FreeLibrary(self.lib._handle)
        del(self.lib)
        error = 0
        return error,None

    @lru_cache(maxsize=256) # This is a global cache for all instances (fine for this implementation)
    def getError(self,fn,out):
        fn = fn.replace('Num','')
        if len(fn)>=3 and fn[0:3].lower()=='set':
            fn = 'ResultError'
        regex = r"^\s\w+\s\w+\s(\w+)[\s=]+([-+0-9]+)"
        found = False
        for i,ln in enumerate(self.header):
            if len(ln)>=2 and ln[0:2]=='//' and fn in ln:
                found = True
                break
        if found:
            i += 1 # Error values start on next line
            out = str(int(out))
            while len(self.header[i])>0 and self.header[i][0]=='\t':
                if out in self.header[i]:
                    matches = re.finditer(regex,self.header[i],re.DOTALL)
                    try:
                        match = next(matches)
                        return WavemeterDLLError(match.groups()[0])
                    except:
                        continue
                i += 1
        return WavemeterDLLError('Code: %s'%out)

    @lru_cache(maxsize=256) # This is a global cache for all instances (fine for this implementation)
    def getPrototype(self,fn):
        regex = r"^\s\w+\(([\w ]+)\)\s+(\w+)\((.*?)\)\s+\;$"
        found = False
        for ln in self.header:
            if len(ln)>0 and ln[0]=='\t' and fn in ln:
                found = True
                break
        assert found, WavemeterDLLError('%s not found in header!'%fn)
        matches = re.finditer(regex,ln,re.DOTALL)
        try:
            match = next(matches)
        except:
            raise WavemeterDLLError('regex failed: %s'%ln.strip())
        groups = match.groups()
        out = groups[0].replace(' ','_')
        inp = ['_'.join(inp.strip().split(' ')[0:-1]) for inp in groups[2].split(',')]
        return (out,inp)

    def GetVersion(self):
        ver = self.lib.GetWLMVersion(0)
        return ver

    def SendCommand(self, client_ip,fn_str,*args,**kwargs):
        # If return_error used as kwargs arg (regardless of value); error will be suppressed, returning the error integer code
        if len(kwargs.keys()) == 1 and 'return_error' not in kwargs:
            raise Exception('%s incorrect argument, perhaps looking for "return_error"?'%list(kwargs.keys())[0])
        elif len(kwargs.keys()) > 1:
            raise Exception('Wrong input arguments.')
        # Break out to some custom ones
        if 'PIDCourse' in fn_str:
            return self.PIDCourse(fn_str,*args)
        elif 'PIDSetting' in fn_str:
            return self.PIDSetting(fn_str,*args)
        elif 'GetFrequency' in fn_str or 'GetWavelength' in fn_str:
            return self.GetMeasurement(fn_str,*args)

        if fn_str in [x for x, y in wavemeter.__dict__.items() if type(y) == FunctionType]:
            # Means function overloaded in this class
            return getattr(self,fn_str)(*args)
        [out,inp] = self.getPrototype(fn_str)
        fn = getattr(self.lib,fn_str)
        fn.restype = eval('c_%s'%out)  # this could fail if custom data type...
        fn.argtypes = [eval('c_%s'%i) for i in inp]
        response = fn(*args)
        if type(response) in [float,int] and response < 0 and 'getdeviationsignal' not in fn_str.lower() and 'return_error' not in kwargs.keys():
            error = self.getError(fn_str,response)
            raise self.getError(fn_str,response)  # Will return error
        return response

    def GetMeasurement(self,fn_str,*args):
        # Will always return a numeric response
        #  0: No Value
        # -1: Low Signal
        # -2: High Signal
        # -3: Out of Range
        # Try for 1 second max if no value
        response = 0
        tstart = time.time()
        while response == 0:
            [out,inp] = self.getPrototype(fn_str)
            fn = getattr(self.lib,fn_str)
            fn.restype = eval('c_%s'%out)
            fn.argtypes = [eval('c_%s'%i) for i in inp]
            response = fn(*args)
            if time.time() - tstart > 1.0: break # timeout
        return response

    def GetSummary(self):
        # Output: 'ch,wavelength,PID;ch,wavelength,PID;...'
        if not self.SendCommand('','GetSwitcherMode',0):
            raise Exception('Not in switcher mode.')
        SwitchStates = self.GetSwitcherSignalStates('all')
        channels = [x['channel'] for x in SwitchStates if x['use']] # indexed from 1
        GlobalPID = self.SendCommand('','GetDeviationMode',0)
        out = []
        for i in channels:
            out.append({
                        'channel':i,
                        'PIDstatus': GlobalPID and self.SendCommand('','GetPIDSetting','cmiDeviationChannel',i),
                        'wavelength': self.SendCommand('','GetWavelengthNum',i,0,return_error=True)
                        })
        return out

    def GetSwitcherSignalStates(self,ch):
        if 'all' == ch:
            chs = [1,2,3,4,5,6,7,8]
        else:
            chs = [int(ch)]
        out = []
        args = [c_lref(0),c_lref(0)] # [use, show]
        for ch in chs:
            self.lib.GetSwitcherSignalStates(ch,byref(args[0]),byref(args[1]))
            out.append({
                        'channel': ch,
                        'use': args[0].value,
                        'show': args[1].value
                        })
        return out

    def PIDSetting(self,fn_str,*args):
        PS = {'cmiPID_P':[1034,1],  # [value, placement]
              'cmiPID_T':[1033,1],
              'cmiPID_I':[1035,1],
              'cmiPID_dt':[1060,1],
              'cmiPID_D':[1036,1],
              'cmiDeviation-SensitivityFactor':[1037,1],
              'cmiDeviationUnit':[1041,0],
              'cmiDeviation-SensitivityDim':[1040,0],
              'cmiPID_AutoClearHistory':[1061,0],
              'cmiPIDUseTa':[1031,0],
              'cmiPIDConstdt':[1059,0],
              'cmiDeviationPolartiy':[1038,0],
              'cmiDeviationChannel':[1063,0],
              'all':[-1,-1]}
        assert len(args) in [2,3], Exception('PIDSetting requires 2 input argument for getting and 3 for setting.')
        assert args[0] in PS, Exception('%s is not an option for PIDSetting (case sensitive). Options: %s'%(args[0],', '.join(PS.keys())))
        fn = getattr(self.lib,fn_str)
        if 'get' == fn_str[0:3].lower():
            items = [args[0]]
            if items[0] == 'all':
                items = PS.keys()
            out = []
            fn_out = [c_lref(0), c_dref(0)]
            for item in items:
                [val,pos] = PS[item]
                fn(val,int(args[1]),byref(fn_out[0]),byref(fn_out[1]))
                out.append({
                            'prop': item,
                            'val': fn_out[pos].value
                            })
            return out
        else: # Set
            item = PS[args[0]]   # [value, placement]
            setVal = int(args[2])
            inp = [0,0]
            inp[item[1]] = setVal
            response = fn(item[0],int(args[1]),c_long(inp[0]),c_double(inp[1]))
            if response < 1:
                err = self.getError(fn_str,response)  # Will return error 
                if 'ResERR_NoErr' not in str(err):
                    raise err

    def PIDCourse(self,fn_str,*args):
        args = list(args)
        if 'pidcoursenum' in fn_str.lower():
            assert len(args)==2, Exception('PIDcourseNum only takes two arguments, received %i'%(len(args)))
            args[0] = int(args[0])
        elif 'pidcourse' in fn_str.lower():
            assert len(args)==1, Exception('PIDcourse only takes one argument, received %i'%(len(args)))
        else:
            raise Exception('Unrecognized function related to PIDcourse.')
        fn = getattr(self.lib,fn_str)
        if 'get' == fn_str[0:3].lower():
            args[-1] = create_string_buffer(1024)
            fn(*args)
            return args[-1].value.decode('utf-8')
        else:  # set
            args[-1] = c_sref(args[-1].encode('utf-8'))
            return fn(*args)

if __name__=='__main__':
    with wavemeter() as w:
        # print('Waiting for WLM to startup')
        # while True:
        #     if w.SendCommand('','Instantiate',-1,0,0,0) > 0:
        #         break
        #     time.sleep(0.5)
        # if w.SendCommand('','GetDisplayMode',0) == 1:       # Turn off "Show signal"
        #     w.SendCommand('','SetDisplayMode',0)
        # if  w.SendCommand('','GetOperationState',0) <= 0:   # Begin measurement
        #     w.SendCommand('','Operation',2)
        #w.SendCommand('','ControlWLM',2,0,0)                # Hide window (shows in lower right)
        print('Version:',w.GetVersion())
        print(w.GetSummary())
        # print(w.SendCommand('','GetSwitcherMode',0))
        # #print(w.GetSwitcherSignalStates('all'))
        # print(w.SendCommand('','GetSwitcherSignalStates','all'))
        # print(w.GetSummary())
        # print(w.SendCommand('','GetWavelengthNum',1,0))



        import json
        # Simulate a client connecting to wavemeter
        chan = 3
        print('SwitcherMode:',w.SendCommand([],'GetSwitcherMode',0))
        print(json.dumps(w.GetSummary(),indent=2,sort_keys=True))
        inuse = w.SendCommand([],'GetSwitcherSignalStates',chan)
        print('Chan %i state:'%chan,inuse)
        if not inuse:
            w.SendCommand([],'SetSwitcherSignalStates',chan,1,0)

        # Client now attempts to lock
        pidON = w.SendCommand([],'GetDeviationMode',0)
        print('PID Status:',pidON)
        if not pidON:
            print('Turning PID regulation on')
            w.SendCommand([],'SetDeviationMode',1)
        else:
            print('PID regulation already on')
        print('Setting PID signal chan')
        freq = 470.52
        w.SendCommand([],'SetPIDSetting','cmiDeviationChannel',chan,chan)
        print('Setting PID value: %0.7f THz'%freq)
        ###############################################################
        ############### THIS IS THE PROBLEMATIC COMMAND ###############
        ###############################################################
        print(w.SendCommand([],'GetPIDCourseNum',chan,0))
        w.SendCommand([],'SetPIDCourseNum',chan,'%0.7f'%freq)
     #   input('Hit Enter')
     #   print(w.SendCommand([],'GetPIDCourseNum',chan,0))
     #   w.SendCommand([],'SetPIDCourseNum',chan,'%0.7f'%freq)
        # It will execute and not block, but WLM DLL does not actually
        # do anything, thus in our software, we wait until tuning has 
        # finished, which won't occur until we go to the server:
        #   1) open the Laser Control window
        #   2) click on port 3 (in this example) in the upper right
        ###############################################################
        print('Done')

