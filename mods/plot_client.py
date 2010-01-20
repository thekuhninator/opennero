#!/usr/bin/env python
"""Process and display log files from OpenNERO.

plot_client reads a file and sends it over the network for plot_server to process.
"""

import sys
import socket

HOST, PORT = "localhost", 9999
ADDR = (HOST, PORT)
BUFSIZE = 4096

class NetworkLogWriter:
    def __init__(self, host = 'localhost', port = 9999):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    def write(self, msg):
        msg = msg.strip()
        if msg:
            self.sock.sendto(msg, self.addr)
    def flush(self):
        pass
    def close(self):
        self.sock.sendto('', self.addr)
        self.sock.close()

def main():
    # open input
    f = sys.stdin
    if len(sys.argv) > 1:
        f = open(sys.argv[1])
    # Create writer
    output = NetworkLogWriter()
    # Send messages
    for line in f.xreadlines():
        print >>output, line,
    output.close()
    f.close()

if __name__ == "__main__":
    main()
