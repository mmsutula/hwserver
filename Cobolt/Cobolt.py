import os, logging, time
logger = logging.getLogger(__name__)

class Cobolt:
    def __init__(self,baudrate=9600):
        # Find comport
        ui = None  # add your unique identifier! format: '0000:0000'
        if not ui:
            raise LaserIOError('No unique identifier set')
        port = [port.device for port in list_ports.comports() if ui in port.usb_info()]
        if not len(port)==1:
            raise LaserIOError('Found %i ports matching the unique identifier'%len(port))

        # Save serial object
        self.serial = serial.Serial(port[0], baudrate, timeout=1)

    def dispatch(self, client_ip, fn_name, *args):
        logger.debug('Calling ' + fn_name + str(args))
        
        # Commands from documentation:
        #
        # "l?"            # Get laser ON/OFF state [0, 1]
        # "@cob1"         # Laser ON – Force autostart 
        # "@cob0"         # Laser OFF
        # "@cobasdr1"     # Enable 5V direct input (OEM only)
        # "@cobasdr0"     # Disable 5V direct input (OEM only)
        # "l1"            # Laser ON
        # "l0"            # Laser OFF
        # "@cobasks"      # Get key switch state [0, 1]
        # "cp"            # Enter constant power mode
        # "p?"            # Get output power set point Float (W)
        # "p"             # Set output power Float (W)
        # "pa?"           # Read actual output power Float (W)
        # "ci"            # Enter constant current mode
        # "slc"           # Set laser current Float (mA)
        # "glc?"          # Get laser current set point Float (mA)
        # ???? "rlc"           # Read actual laser current Float (mA)
        # "em"            # Enter modulation mode
        # "games?"        # Get analog modulation enable state [0, 1]
        # "sames"         # Set analog modulation enable state [0, 1]
        # "gdmes?"        # Get digital modulation enable state [0, 1]
        # "sdmes"         # Set digital modulation enable state [0, 1]
        # "gom?"          # Returns the operating mode [0 – Off, 1 – Waiting for key, 2 – Continuous, 3 – On/Off Modulation, 4 – Modulation, 5 – Fault, 6 – Aborted]
        # "ilk?"          # Get interlock state [0, 1]
        # "f?"            # Get operating fault [0 - no errors, 1 – temperature error, 3 - interlock error, 4 – constant power time]
        # "cf"            # Clear fault
        # "gsn?"          # Get serial number 32-bit unassigned integer
        # "hrs?"          # Get laser head operating hours Float
        # 
        # "glmp?"         # Get laser modulation power set point Float (mW)
        # "slmp"          # Set laser modulation power Float (mW)
        # "salis"         # Set analog low impedance (50 Ω) state [0, 1]
        # "galis?"        # Get analog low impedance (50 Ω) state [0, 1]
        
        # Commands from software (using these):
        #
        # ?           Are you there. Returns OK
        # l0          Laser OFF.
        # @cob0       Laser OFF.
        # l1          Laser ON
        # @cob1       Force laser into autostart mode.
        # @cobas      Enable/disable autostart.
        # @cobas?     Get autostart enable state.
        # @cobasks?   Get key switch state.
        # gom?        Get operating mode.
        # @cobast?    Get autostart program state.
        # cf          Clear fault.
        # ecc         Enter constant current mode.
        # ci          Enter constant current mode.
        # f?          Get error status.
        # hrs?        Get operating hours.
        # slc         Set laser current (mA).
        # i?          Read laser current.
        # ilk?        Read interlock state (inverted).
        # l?          Get laser ON/OFF state.
        # leds?       Get LED status as integer.
        # slp         Set laser power (mW).
        # glp?        Get laser power (mW).
        # p           Set laser power (W).
        # p?          Get laser power (W).
        # pa?         Read laser power (W).
        # @cobasp     Set laser power (W).
        # ps?         Get laser power (W).
        # gsn?        Get serial number
        # sn?         Get serial number
        # ver?        Get firmware version.
        # em          Enter modulation mode.
        # eoom        Enter on/off modulation mode.
        # xoom        Exit on/off modulation mode.
        # slmp        Set laser modulated power (mW).
        # glmp?       Get laser modulated power (mW).
        # rbpt?       Read baseplate temperature.
        # sdmes       Set digital modulation enabled state.
        # gdmes?      Get digital modulation enabled state.
        # sames       Set analog modulation enabled state.
        # games?      Get analog modulation enabled state.
        # salis       Set analog low imedance state.
        # galis?      Get analog low impedance state.
        # ecp         Enter constant power mode.
        # cp          Enter constant power mode.
        
        # commandArgs = ["p", "slc", "sames", "sdmes", "salis", "slmp", "salis"]   # Commands with input arguments.
        # commandInts = ["l?", "games?", "gdmes?", "gom?", "ilk?", "f?", "gsn?", "galis?"] # Commands that return integers.
        # commandFloats = ["p?", "pa?", "glc?", "hrs?", "glmp?"] # Commands that return numbers. # ???? "rlc"
        # commandOther = ["@cob1", "@cob0", "@cobasdr1", "@cobasdr0", "l1" , "l0", "@cobasks", "cp", "ci", "em"]
        
        commandArgs = ["@cobas", "slc", "slp", "p", "@cobasp", "slmp", "sdmes", "sames", "salis"]                                               # Commands with input arguments.
        commandInts = ["@cobas?", "@cobasks?", "gom?", "@cobast?", "f?", "ilk?", "l?", "leds?", "gsn?", "sn?", "gdmes?", "games?", "galis?"]    # Commands that return integers.
        commandFloats = ["hrs?", "i?", "glp?", "p?", "pa?", "ps?", "glmp?", "rbpt?"]                                                            # Commands that return floats. # ???? "rlc"
        commandOther = ["?", "l0", "@cob0", "l1", "@cob1", "cf", "ecc", "ci", "ver?", "em", "eoom", "xoom", "ecp", "cp"]
        
        if fn_name in commandArgs and len(argv) == 1:
            self.serial.write(fn_name + str(argv[0]))
            return self.serial.readline().strip()
        elif fn_name in commandInts and len(argv) == 0:
            self.serial.write(fn_name)
            return int(self.serial.readline().strip())
        elif fn_name in commandFloats and len(argv) == 0:
            self.serial.write(fn_name)
            return float(self.serial.readline().strip())
        elif fn_name in commandOther and len(argv) == 0:
            self.serial.write(fn_name)
            r = self.serial.readline().strip()
        else:
            return LaserIOError("Unrecognized command.")
        
        return 'You successfully called the dispatching method!'

class LaserIOError(IOError):
    pass
