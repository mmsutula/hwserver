import logging, os, sys
import ModuleServer.server as server

LOGLEVEL = logging.INFO
if len(sys.argv)>1:
    if sys.argv[1]:
        LOGLEVEL = logging.DEBUG

BASE_PATH = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_PATH,'server.config')
SERVER_IP = '0.0.0.0'
SERVER_PORT = 36577
LOGFILE = os.path.join(BASE_PATH,'server.log')

if __name__ == '__main__':
    server.main('HW Server',CONFIG_PATH,SERVER_IP,SERVER_PORT,LOGLEVEL,LOGFILE)