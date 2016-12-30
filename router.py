#!/usr/bin/python

import sys
import getopt
import socket
import threading
import logging
import time
import subprocess

asctime = time.asctime()
logging.basicConfig(level=logging.DEBUG, format='%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s') # FIXME revisit formatting %-Ns

oidw = [
	'IfName:','1.3.6.1.2.1.31.1.1.1.1', # :IfName
]

class Router(threading.Thread):
    oid = oidw[1]
    def __init__(self, threadID, node, interfaces):
        threading.Thread.__init__(self, name='thread-%d_%s' % (threadID, node))
        self.node = node
        self.interfaces = interfaces
    def run(self):
        logging.debug("starting")
        self.ipaddr = ''
        print self.node
        print self.interfaces
        try:
            self.ipaddr = socket.gethostbyname(self.node)
        except socket.gaierror:
            print "Hostname not found"
            logging.debug("exiting early")
            sys.exit(3)
        print self.ipaddr
        self.ping(self.ipaddr)
        self.snmpwalk(self.ipaddr, self.oid)
        logging.debug("exiting")
    def ping(self,ipaddr):
        itup = subprocess.Popen(['ping', '-i', '0.2', '-w', '2', '-c', '5', ipaddr, '-q'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE).communicate()
        print itup
    def snmpwalk(self,ipaddr,oid):
        stup = subprocess.Popen(['snmpwalk', '-Oqv', '-v2c', '-c', 'kN8qpTxH', ipaddr, oid], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE).communicate()
        print stup

def parser(lst):
    dict = {}
    for node in [line.split(':') for line in lst]:
        dict[node[0]] = {}
        for i in range(len(node))[1:]:
            dict[node[0]][node[i].split(',')[0]] = [int for int in node[i].split(',')[1:]]
    return dict

def usage(args):
    print 'USAGE:\n\t%s [-i <filename>] [--input <filename>]' % (args[0])

def main(args):
    try:
        options, remainder = getopt.getopt(args, "i:", ["input="])
    except getopt.GetoptError as err:
        print err
        usage(sys.argv)
        sys.exit(2)
    for opt, arg in options:
        if opt in ('-i','--input'):
            inputfile = arg
        else:
            assert False, "unhandled option"
    try:
        with open(inputfile) as sf:
            inventory = parser([n.strip('\n') for n in sf.readlines()])
    except IOError:
        print 'Input file (%s) could not be located.' % (inputfile)
        sys.exit(1)
    threads = []
    logging.debug("Initializing SubThreads")
    for n,node in enumerate(inventory):
        t = Router(n+1,node,inventory[node])
        #threads.append(t)
        t.start()
        time.sleep(1)
    #print threads

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1:])
    else:
        usage(sys.argv)
        sys.exit(2)