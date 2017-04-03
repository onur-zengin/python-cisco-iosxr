#!/usr/bin/env python

import sys
import logging
import logging.handlers
import argparse
import getopt
import os
import fcntl

def main(args):
    loglevel = 'CRITICAL'
    email_distro = []
    fp = open(args[0][:-3] + ".pid", 'w')
    fp.write(str(os.getpid()))
    print os.getpid()
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print "Another instance is already running."
        sys.exit(1)
    #fp.read()


if __name__ == '__main__':
    main(sys.argv)