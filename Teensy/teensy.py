import serial, time
from serial.tools import list_ports
'''
http://assets.newport.com/webDocuments-EN/images/15224.pdf
page 47
'''
class teensy:
    def __init__(self,baudrate=9600):
        ui = None  # add your unique identifier! format: '0000:0000'
        if not ui:
            raise FilterWheelIOError('No unique identifier set')
        port = [port.device for port in list_ports.comports() if ui in port.usb_info()]
        if not len(port)==1:
            raise FilterWheelIOError('Found %i ports matching the unique identifier'%len(port))

        self.serial = serial.Serial(port[0],baudrate,timeout=3)

    # General methods for the server class
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self._Close()

    def _Close(self):
        if self.serial.isOpen():
            self.serial.close()

    # Specific methods to talk to the Teensy

    def idn(self):
        self.serial.write('^')

    def change_filter(self, filter):
        try:
            filter_number = int(filter)
        except ValueError:
            raise IncorrectInputError('Expected a string with an integer filter number')
        if filter_number not in list(range(1, 7)):
            raise IncorrectInputError('Not in the range [1, 6]')
        self.serial.write('*' + filter)
        # '*' tells the Teensy we're starting to send a motor command. 
        # So we should send something like '*4' to tell the motor to turn to 
        # filter position 4.

    def get_filter(self):
        self.serial.write('@') # '@' tells the Teensy to return the filter position
        r = self.serial.readline().strip()
        if r == '-1':
            raise UnknownPositionError('Position of wheel has not been calibrated. Please reset first.')
        elif r == '0':
            raise UnknownPositionError('Cannot figure out which filter we are at. Try resetting?')
        else:
            return r

    def reset(self): # '!' tells the Teensy to run the reset operation
        self.serial.write('!')

    def check_position_state(self): 
        self.serial.write('?')
        r = self.serial.readline().strip()
        return r
        # '?' queries the Teensy to see if the wheel knows where it is (i.e. if a reset
        # operation has already been conducted on the Teensy or not)

    def set_digital_output(self, pin, out):
        try:
            pin_number = int(pin)
        except ValueError:
            raise IncorrectInputError('Expected a string with an integer pin number')

        try:
            out_number = int(out)
        except ValueError:
            raise IncorrectInputError('Expected either a string "1" (high) or "0" (low)')

        if out_number not in [0, 1]:
            raise IncorrectInputError('Expected either a string "1" (high) or "0" (low)')

        self.serial.write('#' + pin + ';' + out)

        # Inputs: pin is a string with a valid pin number, e.g. '12'
        # out is a string with a valid output, either '0' (low) or '1' (high)

class FilterWheelIOError(IOError):
    pass

class UnknownPositionError(Exception):
    pass

class IncorrectInputError(Exception):
    pass

if __name__ == '__main__':
    with teensy() as t:
        print(t.serial.port)
        t.idn()
        t.check_position_state()
        t.set_digital_output('11','1')