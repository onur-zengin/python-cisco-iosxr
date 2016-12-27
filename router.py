#!/usr/bin/python

import sys
import getopt

class Router():
    def __init__(self, ipadd):
        self.ipadd = ipadd

def main(args):
    inputfile = 'abc'
    print getopt.getopt(args, "hi:", "inputfile")
    try:
        with open(inputfile) as sf:
            nodes = [n.strip('\n') for n in sf.readlines()]
        print nodes
    except IOError:
        print 'Input file (%s) could not be located.' % (inputfile)
        exit()


if __name__ == '__main__':
    main(sys.argv[1:])