#!/usr/bin/env python

import sys
import logging
import logging.handlers
import argparse
import getopt
import os

def main(args):
    loglevel = 'CRITICAL'
    email_distro = []
    fp = open(args[0][:-3] + ".pid", 'w')
    fp.write(str(os.getpid()))
    print os.getpid()
    #fp.read()


if __name__ == '__main__':
    main(sys.argv)