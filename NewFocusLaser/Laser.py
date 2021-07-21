import serial, time, logging
from serial.tools import list_ports
logger = logging.getLogger(__name__)
'''
http://assets.newport.com/webDocuments-EN/images/15224.pdf
page 47
http://prologix.biz/downloads/PrologixGpibUsbManual-6.0.pdf
'''
class laser:
    def __init__(self,baudrate=9600):
        # Find comport
        ui = None  # add your unique identifier! format: '0000:0000'
        if not ui:
            raise LaserIOError('No unique identifier set')
        port = [port.device for port in list_ports.comports() if ui in port.usb_info()]
        if not len(port)==1:
            raise LaserIOError('Found %i ports matching the unique identifier'%len(port))

        # Save serial object
        self.serial = serial.Serial(port[0],baudrate,timeout=1)

    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self._Close()

    def _Close(self):
        if self.serial.isOpen():
            self.serial.close()

    def _wait(self,timeout):
        tstart = time.time()
        while not self.opc():
            if time.time() - tstart > timeout:
                raise Exception('Timeout before operation finished.')
            time.sleep(0.1)

    def opc(self):
        self.serial.write(b'*OPC?\n')
        self.serial.write(b'++read eoi\n')
        r = self.serial.readline().strip()
        return r == b'1'

    def idn(self):
        self.serial.write(b'*IDN?\n')
        self.serial.write(b'++read eoi\n')
        r = self.serial.readline().strip()
        return r.decode('utf-8')

    def getDiodeState(self):
        self.serial.write(b':OUTP?\n');
        self.serial.write(b'++read eoi\n')
        r = self.serial.readline().strip()
        return r==b'1'

    def getPiezoPercent(self):
        self.serial.write(b':SOURce:VOLTage:LEVEL:PIEZO?\n')
        self.serial.write(b'++read eoi\n')
        r = self.serial.readline().strip()
        return float(r.decode('utf-8'))

    def getWavelength(self):
        self.serial.write(b':SENSE:WAVELENGTH?\n')
        self.serial.write(b'++read eoi\n')
        r = self.serial.readline().strip()
        return float(r.decode('utf-8'))
        
    def getPower(self):
        self.serial.write(b':SENSE:POWER:LEVEL:FRONT\n')
        self.serial.write(b'++read eoi\n')
        r = self.serial.readline().strip()
        return float(r.decode('utf-8'))

    def on(self):
        self.serial.write(b':OUTPUT:STATE ON\n')
        self.serial.write(b'++read eoi\n')
        r = self.serial.readline().strip().decode('utf-8')
        assert r=='OK', 'Failed to turn on'

    def off(self):
        self.serial.write(b':OUTPUT:STATE OFF\n')
        self.serial.write(b'++read eoi\n')
        r = self.serial.readline().strip().decode('utf-8')
        assert r=='OK', 'Failed to turn off'

    def setPower(self,val):
        self.serial.write(b':SOURCE:POWER:LEVEL %f\n'%val)

    def setTrackMode(self,val):
        val = val.upper()
        assert val in ['ON','OFF'], 'Track mode options are on/off'
        self.serial.write(b':OUTPUT:TRACK %s\n'%val.encode('utf-8'))
        
    def setConstantPowerMode(self,val):
        val = val.upper()
        assert val in ['ON','OFF'], 'ConstantPower mode options are on/off'
        self.serial.write(b':SOURCE:CPOWER %s\n'%val.encode('utf-8'))
    
    def setWavelength(self,val,timeout=60):
        self.serial.write(b':SOURCE:WAVELENGTH %f\n'%val)
        self.serial.write(b'++read eoi\n')
        r = self.serial.readline().strip().decode('utf-8')
        assert r=='OK', r
        if timeout:
            self._wait(timeout)

    def setPiezoPercent(self,val):
        assert 0 <= val and val <= 100, 'Piezo percent must be between 0 and 100, received %0.2f'%val
        self.serial.write(b':SOURce:VOLTage:LEVEL:PIEZO %f\n'%val)

class LaserIOError(IOError):
    pass

if __name__=='__main__':
    with laser() as l:
        print(l.idn())
        print(l.getDiodeState())