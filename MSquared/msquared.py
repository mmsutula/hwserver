import socket, select
import sys, time, os, inspect
import json
import subprocess, datetime
import logging # Should grab default logger

logger = None # Should initialize with init_logger

MSQUARED_UTILS = r'C:\Users\Experiment\msquared_server'
MY_IP = None #add the IP of the computer this server is running on here. 'xxx.xxx.xxx.xxx'
ADDR = {
    'solstis': None,
    'EMM': None
} #defined for a given module in init file

help_text = '''This wrapper is for the hwserver. It will take care of entering and exiting \
EMM or solstis as needed (keeping the last one called alive until it needs to \
switch)

This also keeps track of the last client until client requests to "close" connection. \
It is possible to force client out by calling force_client() method (e.g. function="force_client", args=[]).

When calling a laser, the first argument must be name of laser (e.g. function="function_name", args=["laser_name",...]). \
Note, that anything with an equals sign in the prototype is optional. Anything that has a positive (non-zero) timeout will return a tuple \
of the original command response along with a report.
Valid "laser_name" options (along with their valid "function_name" options):

EMM:
  %s

solstis:
  %s
'''

def init(name, solstis_addr, emm_addr):
	# Addresses: (IP, PORT)
    global logger, ADDR
    logger = logging.getLogger(name)
    ADDR = {
        'solstis': solstis_addr,
        'EMM': emm_addr
    }

def _help():
    EMM_help = []
    for f in (a for a in dir(EMM) if a[0]!='_'):
        try:
            EMM_help.append(inspect.getsource(getattr(EMM,f)) \
                                        .strip().split('\n')[0][4:-1] \
                                        .replace('self,','').replace('self',''))
        except: pass # property
    solstis_help = []
    for f in (a for a in dir(solstis) if a[0]!='_'):
        try:
            solstis_help.append(inspect.getsource(getattr(solstis,f)) \
                                        .strip().split('\n')[0][4:-1] \
                                        .replace('self,','').replace('self',''))
        except: pass # property
    return help_text%('\n  '.join(EMM_help),'\n  '.join(solstis_help))

class LaserWrapper:
    # This wrapper is for the hwserver. It will take care of entering and exiting
    # EMM or solstis as needed (keeping the last one called alive until it needs to
    # switch)
    #
    # This also keeps track of the last client until client requests to "close" connection.
    # It is possible to force client out by calling force_client() method

    def __init__(self):
        # We will try to instantiate EMM if exists, if not try solstis, else error
        if ADDR['EMM']:
            self.laser = EMM() # Handle to either EMM or solstis (load EMM first because takes a while to init)
        elif ADDR['solstis']:
            self.laser = solstis()
        else:
            raise Exception('EMM and solstis are not configured with an address. Can\'t initialize.')
        self.client = (None,None)  # Keep track of last client (IP,last_use datetime)

    def __enter__(self):
        return self
    def __exit__(self,*args,**kwargs):
        if self.laser:
            self.laser.__exit__(self, *args,**kwargs)

    def dispatch(self,client,fn,*args):
        if fn == 'force_client':
            self.force_client(client)
            return
        elif fn == 'close':
            self.close()
            return
        # Check input, and fix vars
        assert len(args)>0, 'The first argument must be the laser!'
        laser = args[0]
        args = args[1:]
        assert laser in ['EMM','solstis'], 'The laser must be one of (case matters): "EMM", "solstis"'
        # Check client status and update
        if client != self.client[0] and self.client[0] is not None:
            raise Exception('Another client was using the laser (last call: %s)'%self.client[1])
        self.client = (client,datetime.datetime.now())
        # Check laser and update if necessary
        if laser != self.laser.__class__.__name__: # This will work with None too
            if not ADDR[laser]: raise Exception('"%s" is not configured with an address. Can\'t initialize.')
            try: self.laser.__exit__(None,None,None)
            except: pass
            self.laser = globals()[laser]()
        # Dispatch
        assert fn in dir(self.laser), \
            'Function "%s" not found in laser "%s". Available: %s'%(fn,laser,', '.join([f for f in dir(self.laser) if f[0]!='_']))
        return getattr(self.laser,fn)(*args)

    def force_client(self,client):
        self.client = (client,datetime.datetime.now())

    def close(self):
        self.client = (None,None)

############################################################
######################## Laser code ########################
############################################################

class ClientDisconnected(IOError):
    pass
class ParseError(IOError):
    ErrorCodes = {
                    1:'JSON parsing error, invalid start command, wrong IP address.',
                    2:'"message" string missing.',
                    3:'"transmission_id" string missing.',
                    4:'No transmission id value.',
                    5:'"op" string missing.',
                    6:'No operation name.',
                    7:'Operation not recognised.',
                    8:'"parameters" string missing.',
                    9:'Invalid parameter tag or value.'
                }
    def __init__(self,original,response,*args,**kwargs):
        ID = response['parameters']['protocol_error'][0]
        if ID == 1:
            buf = response['parameters']['JSON_parse_error']
            msg = '%s\n  Original: %s\n  Error At: %s'%(self.ErrorCodes[ID],original,buf)
        else:
            msg = '%s\n  Original: %s'%(self.ErrorCodes[ID],original)
        super(ParseError,self).__init__(msg,*args,**kwargs)
class WrongTransmissionID(IOError):
    pass

def recvjson(connection,recv_buffer=1):
    # Having recv_buffer larger than 1 byte could result in multiple json strings loaded at once
    buffer = b''
    while True:
        data = connection.recv(recv_buffer)
        if not data: ClientDisconnected('Client disconnected.')
        buffer += data
        try:
            return json.loads(buffer)
        except ValueError:
            pass

class msquared:
    default_timeout = 2 # Default timeout
    def __init__(self):
        # Begin socket creation
        logger.debug('Creating Socket')
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(msquared.default_timeout)
        self.sock = sock
        self.transmission_id = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logger.debug('Closing TCP socket')
        self.sock.close()
        logger.debug('Closed')

    def _clean_input_buffer(self):
        # Make sure input buffer is clear (mainly in case report is sent, but timeout occurs before receiving)
        [r,w,x] = select.select([self.sock],[],[],0)
        if r:
            self.sock.setblocking(0)
            try:
                old = self.sock.recv(4096).decode('utf-8') # Empty buffer by reading
                logger.error('Found old bytes in input:\n%s'%old)
            finally:
                self.sock.setblocking(1)
 
    def _waitfor_report(self,op,report_timeout):
        logger.debug('Waiting for report')
        self.sock.settimeout(report_timeout)
        try:
            report = recvjson(self.sock)
            if report['message']['op'] != op+'_f_r':
                raise Exception('Failed to receive report, instead received:\n%s'%json.dumps(report))
        finally:
            self.sock.settimeout(self.default_timeout)
        logger.debug(report['message'])
        return report['message']

    def _recv(self,msg,n=5):
        # Attemt to receive correct transmission_id
        attempt = 0
        while True:
            try:
                response = recvjson(self.sock)
                response = response['message']
                logger.debug(response)
                if response['op'] == 'parse_fail':
                    raise ParseError(msg,response)
                if response['transmission_id'][0] != self.transmission_id:
                    raise WrongTransmissionID('Received response from wrong transmission_id:\n%s'%json.dumps(response))
                break
            except WrongTransmissionID:
                attempt += 1
                if attempt >= n:
                    raise
        return response

    def _transmit(self,op,parameters={},report='',report_timeout=60):
        # op should be the desired operation
        # parameters should be dictionary of parameters (if None, will omit)
        # report should be a string if desired. will add to parameters
        # report_timeout should be seconds to wait for recvjson on report (ignored if no report)
        #
        # Returns parameters of returned message
        self._clean_input_buffer()
        self.transmission_id += 1  # Increment unique transmission ID
        msg =   {'message':{'transmission_id':[self.transmission_id],'op':op}}
        if report:
            parameters['report'] = report
        if parameters:
            msg['message']['parameters'] = parameters
        self.sock.sendall(json.dumps(msg).encode('utf-8'))
        response = self._recv(msg)
        if report:
            #assert response['parameters']['status'][0]==0, '%s failed with status %i'%(op,response['parameters']['status'][0])
            report_out = self._waitfor_report(op,report_timeout)
            return response['parameters'],report_out['parameters']
        return response['parameters']

    def _hello(self):
        # Try twice here
        try:
            response = self._transmit('start_link',{'ip_address':MY_IP})
        except:
            response = self._transmit('start_link',{'ip_address':MY_IP})
        assert response['status']=='ok', 'Could not connect to msquared device, returned:\n%s'%str(response)

class EMM(msquared):
    
    def __init__(self):
        super(EMM,self).__init__()
        # Connect the socket to the port where the server is listening
        self.sock.connect(ADDR['EMM'])
        self._hello()  # Introduce to msquared server
        # Launch man_in_the_middle.py
        self._MITM_proc = None

    def __exit__(self, *args):
        try:
            if self._MITM_proc:
                logger.info('Killing MITM proc')
                self._MITM_proc.kill()
        finally:
            super(EMM,self).__exit__(*args)

    def _launch_MITM(self):
        # Blocks until EMM sees connection
        logger.info('Launching man-in-the-middle')
        # startup info flags for starting MITM minimized
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 6 # SW_MINIMIZE
        self._MITM_proc = subprocess.Popen(['python',os.path.join(MSQUARED_UTILS,'man_in_the_middle.py')],
                                            creationflags=subprocess.CREATE_NEW_CONSOLE,
                                            startupinfo=startupinfo,
                                            stderr=subprocess.PIPE,stdout=subprocess.PIPE)
        ip = self._MITM_proc.stderr.readline().decode('utf-8').strip() # This line could hang forever
        if ip != ADDR['EMM'][0]: # Must be an actual error
            ip += '\n'+self._MITM_proc.stderr.read().decode('utf-8') # Get rest of message
            raise Exception('MITM Error:\n%s'%ip.replace('\r\n','\n'))
        time.sleep(1)
        logger.info('EMM connected from %s'%ip)
        

    def _check_MITM_proc(self):
        if not self._MITM_proc or self._MITM_proc.poll():
            self._launch_MITM()
            logger.error('Had to re-launch _MITM_proc')

    def laser_control(self,action):
        assert action in ['on','off'], 'action must be either "on" or "off"'
        return self._transmit('laser_control',{'action':action})

    def status(self):
        return self._transmit('status')

    def start_ppln(self,oven,timeout=60):
        assert oven in [1,2,3], 'oven must be an integer of either 1, 2 or 3'
        if timeout:
            return self._transmit('start_ppln',{'fitted_oven':oven},report='finished',report_timeout=timeout)
        else:
            return self._transmit('start_ppln',{'fitted_oven':oven})

    def optimise_ppln(self,timeout=60):
        raise Exception('Not working right now, sorry!!')
        if timeout:
            return self._transmit('optimise_ppln',report='finished',report_timeout=timeout)
        else:
            return self._transmit('optimise_ppln')

    def change_ppln(self,timeout=60):
        if timeout:
            return self._transmit('change_ppln',report='finished',report_timeout=timeout)
        else:
            return self._transmit('change_ppln')

    def pba_control(self,action):
        self._check_MITM_proc()
        assert action in ['start','stop'], 'action must be either "start" or "stop"'
        self._transmit('pba_control',{'action':action})

    def pba_reference(self,action,timeout=60):
        self._check_MITM_proc()
        assert action in ['start','stop'], 'action must be either "start" or "stop"'
        if timeout:
            return self._transmit('pba_reference',{'action':action,'solstis':[1]},report='finished',report_timeout=timeout)
        else:
            return self._transmit('pba_reference',{'action':action,'solstis':[1]})

    def set_wavelength(self,target,timeout=120,wavelength_range='visible'):
        assert wavelength_range in ['visible','infrared'], 'Wavelength_range must be either "visible" or "infrared"'
        self._check_MITM_proc()
        if timeout:
            return self._transmit('wavelength',{'target':[target],'beam':wavelength_range},report='finished',report_timeout=timeout)
        else:
            return self._transmit('wavelength',{'target':[target],'beam':wavelength_range})

    def abort_tune(self):
        # For some reason requires a parameters timeout with nothing
        self._check_MITM_proc()
        return self._transmit('wavelength_stop',{None:None})

    def ready(self):
        # Nice call that does nothing other than wait for connection
        self._check_MITM_proc()
        return True



class solstis(msquared):
    def __init__(self):
        super(solstis,self).__init__()
        # Connect the socket to the port where the server is listening
        self.sock.connect(ADDR['solstis'])
        self._hello()  # Introduce to msquared server

    def _set_wavelengthMeter_channel(self,channel,recovery=1):
        # Shouldn't really be called, because requires knowledge that clients might not have
        #
        # channel: 1-8 (or 0 is single channel operation)
        # recovery: If wm not on requested channel
        #   1 - reset meter and proceed
        #   2 - wait for meter to return
        #   3 - abandon request
        response = self._transmit('set_w_meter_channel',{'channel':[channel],'recover':[recovery]})
        if response['status'] == 1:
            raise Exception('Command failed.')
        elif response['status'] == 2:
            raise Exception('Channel out of range.')
        else:
            return response

    def set_wavelength_open(self,wavelength,timeout=60):
        # Fails if wavemeter (poll and abort not implemented here; recommend using timeout)
        if timeout:
            return self._transmit('move_wave_t',{'wavelength':[wavelength]},report='finished',report_timeout=timeout)
        else:
            return self._transmit('move_wave_t',{'wavelength':[wavelength]})

    def set_wavelength(self,wavelength,timeout=60):
        # This will also lock the etalon and resonator
        if timeout:
            return self._transmit('set_wave_m',{'wavelength':[wavelength]},report='finished',report_timeout=timeout)
        else:
            return self._transmit('set_wave_m',{'wavelength':[wavelength]})
        
    def lock_wavelength_to(self,wavelength,lock_status='on'):
    	##### NOTE: This might not work; msquared said this is for "developmental purposes" and might not be on newer firmware
        # Locks laser to given wavelength if lock_status = "on", else removes lock
        assert lock_status in ['on','off'], 'lock_status must be either "on" or "off".'
        return self._transmit('lock_wave_m_fixed',{'operation':lock_status,'lock_wavelength':[wavelength]})

    def lock_wavelength(self,lock_status='on'):
        # Locks laser to given wavelength if lock_status = "on", else removes lock
        assert lock_status in ['on','off'], 'lock_status must be either "on" or "off".'
        response = self._transmit('lock_wave_m',{'operation':lock_status})
        assert response['status'][0] == 0, 'No link to wavelength meter.'
        return response

    def abort_tune(self):
        # This will unlock the resonator, leaving the etalon
        response = self._transmit('stop_wave_m')
        assert response['status'][0] == 0, 'No link to wavelength meter.'
        return response

    def get_wavelength(self):
        return self._transmit('poll_wave_m')

    def get_wavelength_range(self):
        return self._transmit('get_wavelength_range')

    def set_etalon_val(self,percent):
        # Not sure how to get current percent val, but voltage val will be returned in status
        assert (0<=percent and percent<=100), 'Must be percent between [0,100]'
        return self._transmit('tune_etalon',{'setting':[percent]})

    def set_etalon_lock(self,status,timeout=60):
        assert status in ['on','off'], 'Status must be either "on" or "off".'
        if timeout:
            return self._transmit('etalon_lock',{'operation':status},report='finished',report_timeout=timeout)
        else:
            return self._transmit('etalon_lock',{'operation':status})

    def etalon_lock_status(self):
        response = self._transmit('etalon_lock_status')
        assert response['status']==0, 'Operation Failed.'
        return response

    def set_resonator_val(self,percent,timeout=60):
        # Not sure how to get current percent val, but voltage val will be returned in status
        # Seems that you can only set percent and can only get voltage.
        assert (0<=percent and percent<=100), 'Must be percent between [0,100]'
        if timeout:
            return self._transmit('tune_resonator',{'setting':[percent]},report='finished',report_timeout=timeout)
        else:
            return self._transmit('tune_resonator',{'setting':[percent]})

    def status(self):
        response = self._transmit('get_status')
        return response


if __name__=='__main__':
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    print(_help())


    # with EMM() as e:
    #     print('Ready: %s'%str(e.ready())) # Let it connect to man-in-the-middle
    #     print(e.set_wavelength(610))

    # with solstis() as s:
    #     print(s.abort_tune())
    #     steps = 6
    #     for i in range(steps):
    #         percent = 100.0/(steps-1)*i # inclusive [0 100]
    #         print(percent)
    #         print(s.set_resonator_val(percent)) # Blocks
    #         print(s.get_wavelength())
    #         time.sleep(0.5)

    # Return msquared to "solstis" state
    # with EMM() as e:
    #     print('Ready: %s'%str(e.ready()))
    #     #print(e.set_wavelength(615))
    #     #time.sleep(5)
    #     #print(e.set_wavelength(900,60,'infrared')) # Non-blocking call
    #     print(e.abort_tune())