#!/usr/bin/python

import sys
import getopt
import socket
import threading
import logging
import time
import subprocess
import re
import resource

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
        logging.info("Starting")
        self.ipaddr = ''
        try:
            self.ipaddr = socket.gethostbyname(self.node)
        except socket.gaierror as gaierr:
            logging.warning("Operation halted: %s" % (str(gaierr)))
            sys.exit(3) #wait for the event
        except:
            logging.warning("Unexpected error while resolving hostname")
            logging.debug("Unexpected error while resolving hostname: %s" % (str(sys.exc_info()[:2])))
            #raise
            sys.exit(3) #wait for the event
        #print "I'm still alive!"
        ping = self.ping(self.ipaddr)
        if ping[0] == 0:
            self.snmpwalk(self.ipaddr, self.oid)
        else:
            logging.warning("Unexpected error during ping test")
            logging.debug("Unexpected error during ping test: ### %s ###" % (str(ping[1])))
            sys.exit(3)  # wait for the event
        logging.info("Completed")
    def ping(self,ipaddr):
        pingr = 1
        ptup = None
        try:
            ptup = subprocess.Popen(['ping', '-i', '0.2', '-w', '2', '-c', '5', ipaddr, '-q'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE).communicate()
        except:
            logging.warning("Unexpected error during ping test")
            logging.debug("Unexpected error - Popen function (ping): %s" % (str(sys.exc_info()[:2])))
        else:
            if ptup[1] == '':
                n = re.search(r'(\d+)\%\spacket loss', ptup[0])
                if n != None:
                    if int(n.group(1)) == 0:
                        pingr = 0
                    elif 0 < int(n.group(1)) < 100:
                        logging.warning("Operation halted. Packet loss detected")
                    elif int(n.group(1)) == 100:
                        logging.warning("Operation halted. Node unreachable")
        return pingr, ptup
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
    print 'USAGE:\n\t%s\t[-i <filename>] [--input <filename>] [-l <loglevel>] [--logging <loglevel>]' \
          '\n\t\t\t[-f <value>] [--frequency <value>] [-r <value>] [--repeat <value>]' % (args[0])
    print '\nDESCRIPTION:\n\t[-i <filename>], [--input <filename>]' \
          '\n\t\tThe inventory details must be provided in a text file structured in the following format,' \
          'while each node being written on a separate line:' \
          '\n\t\t\t<nodename>:pni,<intname-1>,...,<intname-M>:cdn,<intname-1>,...,<intname-N>' \
          '\n\t\t\tEXAMPLE: er12.thlon:pni,Bundle-Ether1024,Bundle-Ether1040:cdn,Bundle-Ether1064' \
          '\n\t[-l <loglevel>], [--logging <loglevel>]' \
          '\n\t\tThe loglevel must be specified as one of INFO, WARNING, DEBUG in capital letters. ' \
          'If none specified, the program will run with default level INFO.'

def main(args):
    asctime = time.asctime()
    loglevel = 'INFO'
    runtime = 'infinite'
    frequency = 5
    try:
        options, remainder = getopt.getopt(args, "i:hl:r:f:", ["input=", "help", "logging=", "repeat=", "frequency="])
    except getopt.GetoptError as err:
        print err
        usage(sys.argv)
        sys.exit(2)
    for opt, arg in options:
        if opt in ('-h','--help'):
            usage(sys.argv)
            sys.exit(2)
        elif opt in ('-i', '--input'):
            inputfile = arg
        elif opt in ('-l','--logging'):
            if arg in ('INFO','WARNING','DEBUG'):
                loglevel = arg
            else:
                loglevel = 'INFO'
        elif opt in ('-r','--repeat'):
            try:
                runtime = int(arg)
            except ValueError:
                print 'The value of repeat (-r) argument must be an integer'
                sys.exit(1)
        elif opt in ('-f','--frequency'):
            try:
                frequency = int(arg)
            except ValueError:
                print 'The value of frequency (-f) argument must be an integer'
                sys.exit(1)
        else:
            assert False, "unhandled option"
    logging.basicConfig(level=logging.getLevelName(loglevel),
                        format='%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s')  # FIXME revisit formatting %-Ns
    while True:
        try:
            with open(inputfile) as sf:
                inventory = parser([n.strip('\n') for n in sf.readlines()])
        except IOError:
            print 'Input file (%s) could not be located.' % (inputfile)
            sys.exit(1)
        else:
            threads = []
            logging.debug("Initializing subThreads")
            for n,node in enumerate(inventory):
                t = Router(n+1,node,inventory[node])
                #threads.append(t)
                t.start()
                time.sleep(1)
            if type(runtime) == int:
                runtime -= 1
        finally:
            if runtime == 0:
                break
            time.sleep(frequency)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1:])
    else:
        usage(sys.argv)
        sys.exit(2)