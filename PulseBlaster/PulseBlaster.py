import os, logging, fnmatch
from subprocess import check_output
logger = logging.getLogger(__name__)

# PulseBlaster boards from SpinCore stream digital pulses on many RF channels.
# TODO: Add more documentation, make client robust to crashes by stashing in file

def find_files(directory, pattern):
    '''Recursively go through directory to find pattern'''

    for root, _, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename

def decode(message):
    return message.decode("utf-8").strip()

class PulseBlaster:
    numlines = 21           # This is true for PulseBlasterESR-PRO boards, but not necessary for others
    pathSpinCore = os.path.join('C:', os.sep, 'SpinCore')
    program = ''            # Currently-loaded program.
    defaultClock = 500      # MHz
    static = False          # Whether the board is not currently running a program and is in the staticlines idle state.
    client = None           # Allow client to exclusively request access

    def __init__(self):
        logger.debug("Initializing PulseBlaster!")

        # Find where the PulseBlaster executable is.
        self.pathEXE = ''
        try:
            potentialFiles = [fname for fname in find_files(self.pathSpinCore,'spbicl.exe')]
            if len(potentialFiles) == 1:
                logger.debug("Found SpinCore's spbicl.exe at:\n    " + potentialFiles[0])
            elif len(potentialFiles) > 1:
                logger.warning("Found multiple candidates for SpinCore's spbicl.exe, choosing the first:\n    " + str(potentialFiles))

            self.pathEXE = potentialFiles[0]
        except:
            pass

        if not self.pathEXE:
            raise RuntimeError("Could not find SpinCore's spbicl.exe. Are you sure that you installed SpinCore?")

        # Choose a location for PulseBlaster .pb program files to be stored.
        self.pathProgram = os.path.join(self.pathSpinCore,'temp.pb')
        logger.debug("Program files (.pb) will be stored at:\n    " + self.pathProgram)

        # Make a list to keep track of the lines of the PulseBlaster when in StaticLines mode.
        self.lines = [False] * self.numlines
        logger.debug("Lines initialized to " + self._linesStr())

        # Start the staticlines idle state (this will overwrite any program from a previous session; change?).
        self._loadStaticLines()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return  # Do not change current state.

    def _linesStr(self):
        '''Returns string format for the interpreter to understand'''

        return '0b ' + ''.join(['1' if v else '0' for v in reversed(self.lines)])   # Line order reversed due to interpreter little endian convention.

    def _loadStaticLines(self, lines=None):
        '''Load staticlines program using lines specified in input.

        If lines are None, the last programmed lines are reloaded.
        If lines are unchanged to currently running set, no action is taken.
        '''

        logger.debug("Loading StaticLines")

        abortset = False

        if lines:   # If not None, something was passed
            assert(len(lines) == self.numlines)

            abortset = True     # By default, assume that lines == self.lines, and plan to not do anything.
            for ii in range(len(self.lines)):
                if self.lines[ii] != bool(lines[ii]):   # If at least one line is changed, then decide to do something (don't abort the set).
                    self.lines[ii] = bool(lines[ii])
                    abortset = False

            if not abortset:
                self.lines = lines

        if not abortset:
            program = 'START: '  + self._linesStr() + ', 100 ms\n' \
                                 + self._linesStr() + ', 100 ms, BRANCH, START'    # Branch acts like GOTO in C or assembly. i.e. go back to start. Do not pass jail.
            self._load(program, None, True, True)
            self.static = True

        return self.lines

    def _com(self, command):
        '''Helper function to communicate with the executable.'''

        logger.debug("Sending command: " + str(command))
        return decode(check_output([self.pathEXE] + command, shell=True))

    def _load(self, program, clock=None, startImmediately=False, isStaticLines=False):
        '''Load a text program onto the board via a temp file.'''

        logger.debug("Loading program:\n" + program)

        if not clock:
            clock = self.defaultClock

        self.program = program

        with open(self.pathProgram,'w') as f:  # This will overwrite an existing file
            f.write(self.program)

        try:
            out = self._com(['load', self.pathProgram, str(clock)])
            logger.debug(out)
            if startImmediately:
                self.start()
            return out
        except:
            if not isStaticLines:
                self._loadStaticLines()
            raise

    def _validate(self):
        '''validate a request in case another client has requested full access.'''

        if self.client and self._ModuleServer_Client[1][0] != self.client:
            raise RuntimeError('Another client has requested exclusive access: ' + self.client)

    ## Access Control methods (will only work when loaded by ModuleServer)

    def checkout(self):
        '''Request exclusive access to device.'''

        self._validate()
        self.client = self._ModuleServer_Client[1][0] # IP address

    def checkin(self):
        '''Return general access to other clients.'''

        self._validate()
        self.client = None

    def force_reset_client(self):
        '''Force the client to reset. This could interrupt someone's experiment. Be careful.'''

        logger.warning('Client %s forced client %s off.'%(self._ModuleServer_Client[1][0], self.client))
        self.client = None

    ## Set methods

    def start(self):
        '''Starts the PulseBlaster.'''

        self._validate()
        out = self._com(['start'])
        logger.debug(out)
        return out

    def stop(self):
        '''Stop the PulseBlaster.'''

        self._validate()
        out = self._com(['stop'])
        logger.debug(out)
        return out

    def load(self, program, clock=None):
        '''Load a text program onto the PulseBlaster.'''

        self._validate()
        logger.info('Loading new program to pulseblaster!')
        self.static = False
        return self._load(program, clock)

    def setAllLines(self, lines):
        '''Sets the output to the values of the boolean array `lines` which must have dimension 1x21.'''

        self._validate()
        return self._loadStaticLines(lines)

    def setLines(self, indices=None, values=None):
        '''Sets the output of the (1-indexed) `indices` to the boolean state of `values`.'''

        self._validate()
        if indices is not None and values is not None:
            if not isinstance(indices, list):
                indices = [indices]
            if not isinstance(values, list):
                values = [values] * len(indices)

            assert len(indices) == len(values)
            assert max(indices) <= self.numlines and min(indices) > 0, \
                "Line indices must integers between 1 and " + str(self.numlines) + ". Was given " + str(self.lines)

            newlines = self.lines.copy()

            for (i,v) in zip(indices, values):
                newlines[i-1] = bool(v)

            return self._loadStaticLines(newlines)
        else:   # Refresh staticlines state.
            return self._loadStaticLines()

    ## Get methods (no need to validate)

    def isStatic(self):
        '''Whether the board is not currently running a program and is in the staticLines idle state.'''

        return self.static

    def getProgram(self):
        '''Returns the currently-loaded program.'''

        return self.program

    def getLines(self):
        '''Returns the current state of staticLines. If a user program is running, then the state of the lines is unknown (NaN/None returned).'''

        if self.static:
            return self.lines
        else:
            return [None] * self.numlines

if __name__=='__main__':
    with PulseBlaster() as pb:
        print("TODO: Add tests.")
