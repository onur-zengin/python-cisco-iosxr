#!/usr/bin/python

import sys
import getopt

class Router():
    def __init__(self, ipadd):
        self.ipadd = ipadd

def usage(args):
    print 'USAGE:\n\t%s [-i <filename>] [--input <filename>]' % (args[0])

def main(args):
    try:
        options, remainder = getopt.getopt(args, "i:", ["input="])
    except getopt.GetoptError as err:
        print err
        usage(sys.argv)
        exit()
    for opt, arg in options:
        if opt in ('-i','--input'):
            inputfile = arg
        else:
            assert False, "unhandled option"
    try:
        with open(inputfile) as sf:
            nodes = [n.strip('\n') for n in sf.readlines()]
            print nodes
    except IOError:
        print 'Input file (%s) could not be located.' % (inputfile)
        exit()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1:])
    else:
        usage(sys.argv)
        exit() #sys.exit(2)