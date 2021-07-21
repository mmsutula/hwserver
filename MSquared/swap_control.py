import websocket, json, logging, requests
import time

logging.getLogger().addHandler(logging.NullHandler()) # websocket requires a handler

EMM = None #IP address of EMM, 'xxx.xxx.xxx.xxx'
MY_IP = None#'IP address of the computer running this server, 'xxx.xxx.xxx.xxx'

SOLSTIS = None #IP and port of SolsTiS, ('xxx.xxx.xxx.xxx',xxxxx)
URL = 'ws://%s:8088/network.htm'%SOLSTIS[0]

def wait_until_ready(socket):
    # Not completely sure about this, but seems to work
    i = 0
    while True:
        i += 1
        if i > 10: raise Exception('Failed to recv boot_file_error in 10 frames.')
        data = json.loads(socket.recv())
        if data['message_type'] == 'boot_file_error':
            return

def send_task_request (socket, task_name):       
        msg = {'message_type':'task_request','task':[task_name]}
        socket.send(json.dumps(msg).replace(' ',''))

def send_page_update (socket, msg):
        msg['message_type'] = 'page_update'
        socket.send(json.dumps(msg).replace(' ',''))

def set_remote_ip(IP):
    socket = websocket.create_connection(URL)
    try:
        wait_until_ready(socket)
        send_page_update(socket, {'remote_ip_address':MY_IP});
        send_task_request(socket, 'save_network_devices')
    finally:
        socket.close()

if __name__=='__main__':
    socket = websocket.create_connection(URL)
    try:
        wait_until_ready(socket)
        send_page_update(socket, {'remote_ip_address':MY_IP});
        send_task_request(socket, 'save_network_devices')
    finally:
        socket.close()