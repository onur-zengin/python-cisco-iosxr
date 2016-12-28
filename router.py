#!/usr/bin/python

import sys
import getopt
import csv
import socket
import threading
import logging
import time

logging.basicConfig(level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s) %(message)s',
                    )

#class Router(object):
 #   def __init__(self, name):
  #      self.name = name
        #self.ipaddr = socket.gethostbyname(name)


class Router(threading.Thread):
    def __init__(self, threadID, node, interfaces):
        threading.Thread.__init__(self, name='thread-%d_%s' % (threadID, node))
        self.hostname = node
        self.interfaces = interfaces
    def run(self):
        logging.debug("starting")
        print self.hostname
        print self.interfaces




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
    for n,node in enumerate(inventory):
        t = Router(n+1,node,inventory[node])
        threads.append(t)
        t.start()
    print threads

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1:])
    else:
        usage(sys.argv)
        sys.exit(2)