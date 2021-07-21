import socket, sys, urllib

message = sys.argv[1]

DEFAULT_IP = 'localhost'
DEFAULT_PORT = 36577

def recv(connection,delim='\n',recv_buffer=4096):
    buffer = ''
    while True:
        data = connection.recv(recv_buffer)
        assert data, 'Client disconnected while receiving.'
        buffer += data
        if data[-1] == '\n':
            return buffer[0:-len(delim)]  # Remove delim

# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect the socket to the port where the server is listening
server_address = (DEFAULT_IP, DEFAULT_PORT)
print 'connecting to %s port %s' % server_address
sock.connect(server_address)

try:
    
    # Send data
    print 'sending "%s"' % message
    sock.sendall(urllib.quote_plus(message.strip())+'\n')

    # Look for the response
    resp = urllib.unqoute_plus(recv(sock))
       
    print 'received "%s"' % resp.strip()

finally:
    print 'closing socket'
    sock.close()