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
ssh_logger.setLevel(logging.WARNING)

main_formatter = logging.Formatter('%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s')
main_ch = logging.StreamHandler()
main_ch.setFormatter(main_formatter)
main_logger = logging.getLogger(__name__)
main_logger.addHandler(main_ch)
main_logger.setLevel(logging.INFO)

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
                 acl_name, dryrun, int_identifiers, pfx_thresholds):
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
    def run(self):
        main_logger.debug("Starting")
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
        print 'USAGE:\n\t%s\t[-h] [--help] [--documentation]' \
          '\n\t\t\t[--simulation] [-r <value>]' % (arg)

def get_pw(c=3):
    #hn = socket.gethostname()
    hn = '127.0.0.1'
    while c > 0:
        try:
            pw = getpass.getpass('Enter cauth password for user %s:' % un, stream=None)
        except KeyboardInterrupt:
            main_logger.info("Keyboard Interrupt")
            sys.exit(0)
        except getpass.GetPassWarning as echo_warning:
            print echo_warning
        else:
            try:
                ssh.connect(hn, 2281, username=un, password=pw, timeout=1, look_for_keys=False, allow_agent=False)
            except KeyboardInterrupt:
                main_logger.info("Keyboard Interrupt")
                sys.exit(0)
            except paramiko.ssh_exception.AuthenticationException as auth_failure:
                ssh.close()
                main_logger.warning(auth_failure)
                c -= 1
            except paramiko.ssh_exception.NoValidConnectionsError as conn_failure:
                ssh.close()
                main_logger.warning(conn_failure)
                sys.exit(1)
            except paramiko.ssh_exception.SSHException as sshexc:
                ssh.close()
                main_logger.warning('SSH connection timeout %s' % sshexc)
                sys.exit(1)
            except:
                main_logger.warning('Unexpected error: %s\t%s' % sys.exc_info()[:2])
                sys.exit(1)
            else:
                ssh.close()
                return True, pw
    else:
        print "Too many failed attempts"
        return False, None

def main(args):
    #asctime = tstamp('hr')
    inventory_file = 'inventory.txt'
    frequency = 20
    risk_factor = 97
    loglevel = 'WARNING'
    acl_name = 'CDPautomation:RhmUdpBlock'
    pni_interface_tag = 'CDPautomation:PNI'
    cdn_interface_tag = 'CDPautomation:CDN'
    ipv4_min_prefixes = 0
    ipv6_min_prefixes = 50
    cdn_serving_cap = 90
    dryrun = False
    runtime = 'infinite'
    try:
        options, remainder = getopt.getopt(args[1:], "hmr:s", ["help", "manual", "runtime=", "simulation"])
    except getopt.GetoptError as getopterr:
        print getopterr
        sys.exit(2)
    else:
        for opt, arg in options:
            if opt in ('-h', '--help'):
                usage(args[0])
                sys.exit(0)
            elif opt in ('-m', '--manual'):
                usage(args[0], opt=True)
                sys.exit(0)
            else:
                print "Invalid option specified on the command line: %s" % (opt)
                sys.exit(2)
        bool, pw = get_pw()
        if not bool:
            sys.exit(1)
        else:
            main_logger.info("Authentication successful")
    lastChanged = ""
    while True:
        try:
            with open(args[0][:-3] + ".conf") as pf:
                parameters = [tuple(i.split('=')) for i in
                              filter(lambda line: line[0] != '#', [n.strip('\n')
                                                                   for n in pf.readlines() if n != '\n'])]
        except KeyboardInterrupt:
            main_logger.info("Keyboard Interrupt")
            sys.exit(0)
        except IOError as ioerr:
            rg = re.search(r'(\'.+\')', str(ioerr))
            if lastChanged == "":
                main_logger.info("'%s could not be located. The program will continue with its default settings."
                                 "\nUse '%s -m or %s --manual to see detailed usage instructions."
                                 % (rg.group(1)[3:], args[0], args[0]))
            else:
                main_logger.info("'%s could not be located. The program will continue with the last known good "
                                 "configuration.\nUse '%s -m or %s --manual to see detailed usage instructions."
                                 % (rg.group(1)[3:], args[0], args[0]))
        else:
            try:
                for opt, arg in parameters:
                    if opt == 'inventory_file':
                        if inventory_file != arg:
                            main_logger.info('Inventory file has been updated')
                        inventory_file = arg
                    elif opt == 'loglevel':
                        if arg.lower() in ('info', 'warning', 'debug', 'critical'):
                            if loglevel != arg.upper():
                                main_logger.info('Log level has been updated: %s' % loglevel.upper())
                            loglevel = arg.upper()
                        else:
                            if lastChanged == "":
                                main_logger.info('Invalid value specified for loglevel. Resetting to default'
                                                 'setting: %s' % loglevel)
                            else:
                                main_logger.info('Invalid value specified for loglevel. Resetting to last known good '
                                                 'setting: %s' % loglevel)
                    elif opt == 'risk_factor':
                        try:
                            arg = int(arg)
                        except ValueError:
                            if lastChanged == "":
                                main_logger.info('The value of the risk_factor argument must be an integer. Resetting '
                                                 'to default setting: %s' % risk_factor)
                            else:
                                main_logger.info('The value of the risk_factor argument must be an integer. Resetting '
                                                 'to last known good setting: %s' % risk_factor)
                        else:
                            if arg >= 0 and arg <= 100:
                                if risk_factor != arg:
                                    main_logger.info('Risk Factor has been updated: %s' % arg)
                                risk_factor = arg
                            else:
                                if lastChanged == "":
                                    main_logger.info('The value of the risk_factor argument must be an integer between '
                                                     '0 and 100. Resetting to default setting: %s' % risk_factor)
                                else:
                                    main_logger.info('The value of the risk_factor argument must be an integer between '
                                                     '0 and 100. Resetting to last known good setting: %s' % risk_factor)
                    elif opt == 'frequency':
                        try:
                            arg = int(arg)
                        except ValueError:
                            if lastChanged == "":
                                main_logger.info('The value of the frequency argument must be an integer. Resetting '
                                                 'to default setting: %s' % frequency)
                            else:
                                main_logger.info('The value of the frequency argument must be an integer. Resetting '
                                                 'to last known good setting: %s' % frequency)
                        else:
                            if arg >= 5:
                                if frequency != arg:
                                    main_logger.info('Running frequency has been updated: %s' % arg)
                                frequency = arg
                            else:
                                if lastChanged == "":
                                    main_logger.info('The running frequency can not be shorter than 5 seconds. '
                                                     'Resetting to default setting: %s' % frequency)
                                else:
                                    main_logger.info('The running frequency can not be shorter than 5 seconds.'
                                                     'Resetting to last known good setting: %s' % frequency)
                    elif opt == 'runtime':
                        if arg.lower() == 'infinite':
                            if runtime != arg.lower():
                                main_logger.info('Runtime has been updated: "infinite"')
                            runtime = 'infinite'
                        else:
                            try:
                                arg = int(arg)
                            except ValueError:
                                main_logger.info('The value of the runtime argument must be either be "infinite" or '
                                                 'an integer')
                            else:
                                if runtime != arg:
                                    main_logger.info('Runtime has been updated: %s' % arg)
                                runtime = arg
                    elif opt.lower() == 'pni_interface_tag':
                        if pni_interface_tag != arg:
                            main_logger.info('pni_interface_tag has been updated')
                        pni_interface_tag = str(arg)
                    elif opt.lower() == 'cdn_interface_tag':
                        if cdn_interface_tag != arg:
                            main_logger.info('cdn_interface_tag has been updated')
                        cdn_interface_tag = str(arg)
                    elif opt.lower() == 'acl_name':
                        if acl_name != arg:
                            main_logger.info('acl_name has been updated')
                        acl_name = str(arg)
                    elif opt.lower() == 'ipv4_min_prefixes':
                        try:
                            arg = int(arg)
                        except ValueError:
                            if lastChanged == "":
                                main_logger.info('The value of the ipv4_min_prefixes must be an integer. Resetting '
                                                 'to default setting: %s' % ipv4_min_prefixes)
                            else:
                                main_logger.info('The value of the ipv4_min_prefixes must be an integer. Resetting '
                                                 'to last known good setting: %s' % ipv4_min_prefixes)
                        else:
                            if ipv4_min_prefixes != arg:
                                main_logger.info('ipv4_min_prefix count has been updated: %s' % arg)
                            ipv4_min_prefixes = arg
                    elif opt.lower() == 'ipv6_min_prefixes':
                        try:
                            arg = int(arg)
                        except ValueError:
                            if lastChanged == "":
                                main_logger.info('The value of the ipv6_min_prefixes must be an integer. Resetting '
                                                 'to default setting: %s' % ipv6_min_prefixes)
                            else:
                                main_logger.info('The value of the ipv6_min_prefixes must be an integer. Resetting '
                                                 'to last known good setting: %s' % ipv6_min_prefixes)
                        else:
                            if ipv6_min_prefixes != arg:
                                main_logger.info('ipv6_min_prefix count has been updated: %s' % arg)
                            ipv6_min_prefixes = arg
                    elif opt == 'simulation_mode':
                        if arg.lower() == 'on':
                            dryrun = True
                            main_logger.info('Program running in simulation mode')
                        elif arg.lower() == 'off':
                            if dryrun != False:
                                main_logger.info('Simulation mode turned off')
                            dryrun = False
                        else:
                            main_logger.info('The simulation parameter takes only two arguments: "on" or "off"')
                    else:
                        if lastChanged == "":
                            main_logger.info("Invalid parameter found in the configuration file: (%s). The program "
                                             "will continue with its default settings. Use '%s -m' or '%s --manual' "
                                             "to see detailed usage instructions." % (opt, args[0], args[0]))
                        else:
                            main_logger.info("Invalid parameter found in the configuration file: (%s). The program "
                                             "will continue with the last known good configuration. Use '%s -m' or '%s "
                                             "--manual' to see detailed usage instructions." % (opt, args[0], args[0]))
            except ValueError:
                main_logger.info("Invalid configuration line detected and ignored. All configuration parameters must "
                                 "be provided in key value pairs separated by an equal sign (=). Use '%s -m' or '%s "
                                 "--manual' for more details." % (args[0], args[0]))
        finally:
            main_logger.setLevel(logging.getLevelName(loglevel))
            main_logger.debug("\n\tInventory File: %s\n\tFrequency: %s\n\tRisk Factor: %s\n\tACL Name: %s\n\t"
                              "PNI Interface Tag: %s\n\tCDN Interface Tag: %s\n\tCDN Serving Cap: %s\n\t"
                              "IPv4 Min Prefixes: %s\n\tIPv6 Min Prefixes: %s\n\tLog Level: %s\n\tSimulation Mode: %s"
                              % (inventory_file, frequency, risk_factor, acl_name, pni_interface_tag, cdn_interface_tag,
                                 cdn_serving_cap, ipv4_min_prefixes, ipv6_min_prefixes, loglevel, dryrun))
            try:
                with open(inventory_file) as sf:
                    inventory = filter(lambda line: line[0] != '#', [n.strip('\n') for n in sf.readlines()])
                if lastChanged != os.stat(inventory_file).st_mtime:
                    dswitch = True
                else:
                    dswitch = False
            except IOError as ioerr:
                main_logger.critical('%s %s. Exiting.' % ioerr)
                sys.exit(1)
            except OSError as oserr:
                main_logger.critical('%s. Exiting.' % oserr)
                sys.exit(1)
            else:
                threads = []
                main_logger.info("Initializing subThreads")
                for n, node in enumerate(inventory):
                    t = Router(n + 1, node, pw, dswitch, risk_factor, cdn_serving_cap, acl_name, dryrun,
                               (pni_interface_tag, cdn_interface_tag), (ipv4_min_prefixes, ipv6_min_prefixes))
                    threads.append(t)
                    t.start()
                for t in threads:
                    t.join()
                lastChanged = os.stat(inventory_file).st_mtime
                if type(runtime) == int:
                    runtime -= 1
            finally:
                #n = gc.collect()
                #print "unreachable:", n
                if runtime == 0:
                    break
                try:
                    time.sleep(frequency)
                except KeyboardInterrupt:
                    main_logger.info("Keyboard Interrupt")
                    sys.exit(0)


if __name__ == '__main__':
    main(sys.argv)