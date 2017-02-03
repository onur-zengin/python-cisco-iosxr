#!/usr/bin/env python

import sys
import getopt
import socket
import threading
import logging
import time
import subprocess
import re
import resource
import gc
import os
import paramiko
import getpass
from datetime import datetime as dt

ssh_formatter = logging.Formatter('%(asctime)-15s [%(levelname)s]: %(message)s')
ssh_ch = logging.StreamHandler()
ssh_ch.setFormatter(ssh_formatter)
ssh_logger = logging.getLogger('paramiko')
ssh_logger.addHandler(ssh_ch)
ssh_logger.setLevel(logging.DEBUG)

def _logger(loglevel):
    formatter = logging.Formatter('%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s')
    main_ch = logging.StreamHandler()
    main_ch.setFormatter(formatter)
    main_logger = logging.getLogger(__name__)
    main_logger.setLevel(logging.getLevelName(loglevel))
    main_logger.addHandler(main_ch)
    return main_logger


hd = os.environ['HOME']
#un = getpass.getuser()
un = 'onur'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def tstamp(format):
    if format == 'hr':
        return time.asctime()
    elif format == 'mr':
        return dt.now()

class Router(threading.Thread):
    def __init__(self, threadID, node, pw, dswitch, risk_factor, cdn_serving_cap,
                 acl_name, dryrun, int_identifiers, pfx_thresholds, main_logger):
        threading.Thread.__init__(self, name='thread-%d_%s' % (threadID, node))
        self.node = node
        self.pw = pw
        self.switch = dswitch
        self.risk_factor = risk_factor
        self.pni_identifier, self.cdn_identifier = int_identifiers
        self.ipv4_minPfx, self.ipv6_minPfx = pfx_thresholds
        self.serving_cap = cdn_serving_cap
        self.acl_name = acl_name
        self.dryrun = dryrun
        self.logger = main_logger
    def run(self):
        self.logger.debug("Starting")
        self.tstamp = tstamp('mr')
        print self.tstamp

def usage(arg,opt=False):
    if opt is True:
        try:
            with open("README.md") as readme_file:
                print readme_file.read()
        except IOError:
            print "README file could not be located. Printing the basic help menu instead"
            usage(arg)
            sys.exit(2)
    else:
        print 'USAGE:\n\t%s\t[-i <filename>] [--inputfile <filename>] [-f <value>] [--frequency <value>] [-r <value>]' \
          '\n\t\t\t[--risk_factor <value>] [-l <info|warning|debug>] [--loglevel <info|warning|debug>]' % (arg)


def get_pw(c=3):
    #hn = socket.gethostname()
    hn = '127.0.0.1'
    while c > 0:
        try:
            pw = getpass.getpass('Enter cauth password for user %s:' % un, stream=None)
        except KeyboardInterrupt:
            sys.exit(0)
        except getpass.GetPassWarning as echo_warning:
            print echo_warning
        finally:
            try:
                ssh.connect(hn, 2281, username=un, password=pw, look_for_keys=False, allow_agent=False)
            except paramiko.ssh_exception.AuthenticationException as auth_failure:
                ssh.close()
                print auth_failure
                c -= 1
            except:
                print 'Unexpected error: %s' % sys.exc_info()[:2]
                sys.exit(1)
            else:
                ssh.close()
                return True, pw
    else:
        print "Too many failed attempts"
        return False, None

def main(args):
    bool, pw = get_pw()
    if not bool:
        sys.exit(1)
    else:
        print "Authentication successful"
    asctime = tstamp('hr')
    acl_name = 'CDPautomation_RhmUdpBlock'
    pni_interface_tag = '[CDPautomation:PNI]'
    cdn_interface_tag = '[CDPautomation:CDN]'
    ipv4_min_prefixes = 0
    ipv6_min_prefixes = 50
    cdn_serving_cap = 90
    dryrun = 'off'
    ssh_loglevel = 'DEBUG'
    try:
        options, remainder = getopt.getopt(args[1:], "i:hl:r:f:", ["inputfile=", "help", "loglevel=",
                                                                   "risk_factor=", "frequency=", "runtime="])
    except getopt.GetoptError:
        sys.exit(2)
    else:
            rg = re.search(r'(\'.+\')', str(ioerr))
            if options == []:
                print "'%s could not be located and no command line arguments provided.\nUse '%s --help' " \
                      "to see usage instructions \n" % (rg.group(1)[3:], args[0])
                sys.exit(2)
            elif '-h' in str(options) or '--help' in str(options):
                usage(args[0], opt=True)
                sys.exit(1)


        for opt, arg in options:
            if opt in ('-h', '--help'):
                pass
            elif opt in ('-i', '--inputfile'):
                inputfile = arg
            elif opt in ('-l', '--loglevel'):
                if arg.lower() in ('info', 'warning', 'debug'):
                    loglevel = arg.upper()
                else:
                    print 'Invalid value specified for loglevel, program will continue with its default ' \
                          'setting: "info"'
                    loglevel = 'INFO'
            elif opt == '--runtime':
                if arg.lower() == 'infinite':
                    runtime = 'infinite'
                else:
                    try:
                        runtime = int(arg)
                    except ValueError:
                        print 'The value of the runtime (-r) argument must be either be "infinite" or an integer'
                        sys.exit(2)
            elif opt == '--dryrun':
                dryrun = 'on'
            else:
                print "Invalid option specified on the command line: %s" % (opt)
                sys.exit(2)
    try:
        inputfile = inputfile
        frequency = frequency
        risk_factor = risk_factor
        loglevel = loglevel
        runtime = runtime
    except UnboundLocalError as missing_arg:
        rg = re.search(r'(\'.+\')', str(missing_arg))
        print "%s is a mandatory argument" % rg.group(1)
        sys.exit(2)
    else:
        lastChanged = ""
        while True:
            try:
                with open(args[0][:-3] + ".conf") as pf:
                    parameters = [tuple(i.split('=')) for i in
                                  filter(lambda line: line[0] != '#', [n.strip('\n') for n in pf.readlines()])]
            except IOError as ioerr:
                print ioerr
                pass
            else:
                try:
                    for opt, arg in parameters:
                        if opt == 'inputfile':
                            inputfile = arg
                        elif opt == 'loglevel':
                            if arg.lower() in ('info', 'warning', 'debug'):
                                loglevel = arg.upper()
                            else:
                                print 'Invalid value specified for loglevel, program will continue with its default ' \
                                      'setting: "info"'
                                loglevel = 'info'
                        elif opt == 'risk_factor':
                            try:
                                risk_factor = int(arg)
                            except ValueError:
                                print 'The value of the risk_factor argument must be an integer'
                                sys.exit(2)
                            else:
                                if not 0 <= risk_factor and risk_factor <= 100:
                                    print 'The value of the risk_factor argument must be an integer between 0 and 100'
                                    sys.exit(2)
                        elif opt == 'frequency':
                            try:
                                frequency = int(arg)
                            except ValueError:
                                print 'The value of the frequency argument must be an integer'
                                sys.exit(2)
                        elif opt == 'runtime':
                            if arg.lower() == 'infinite':
                                runtime = 'infinite'
                            else:
                                try:
                                    runtime = int(arg)
                                except ValueError:
                                    print 'The value of the runtime argument must be either be "infinite" or an integer'
                                    sys.exit(2)
                        elif opt.lower() == 'pni_interface_tag':
                            pni_interface_tag = str(arg)
                        elif opt.lower() == 'cdn_interface_tag':
                            cdn_interface_tag = str(arg)
                        else:
                            print "Invalid parameter found in the configuration file: %s" % (opt)
                            sys.exit(2)
                except ValueError:
                    print "Configuration parameters must be provided in key value pairs separated by an equal sign (=)" \
                          "\nUse '%s --help' for more details" % (args[0])
                    sys.exit(2)
            try:
                with open(inputfile) as sf:
                    inventory = filter(lambda line: line[0] != '#', [n.strip('\n') for n in sf.readlines()])
                if lastChanged != os.stat(inputfile).st_mtime:
                    dswitch = True
                else:
                    dswitch = False
            except IOError as ioerr:
                print ioerr
                sys.exit(1)
            except OSError as oserr:
                print oserr
                sys.exit(1)
            else:
                threads = []
                main_logger.debug("Initializing subThreads")
                for n, node in enumerate(inventory):
                    t = Router(n + 1, node, pw, dswitch, risk_factor, cdn_serving_cap, acl_name, dryrun,
                               (pni_interface_tag, cdn_interface_tag), (ipv4_min_prefixes, ipv6_min_prefixes), main_logger)
                    threads.append(t)
                    t.start()
                for t in threads:
                    t.join()
                lastChanged = os.stat(inputfile).st_mtime
                if type(runtime) == int:
                    runtime -= 1
            finally:
                #n = gc.collect()
                #print "unreachable:", n
                if runtime == 0:
                    break
                try:
                    time.sleep(frequency)
                except KeyboardInterrupt as kb_int:
                    print kb_int
                    sys.exit(1)


if __name__ == '__main__':
    main(sys.argv)