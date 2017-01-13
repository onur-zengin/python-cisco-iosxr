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
import os
from datetime import datetime as dt



def tstamp(format):
    if format == 'hr':
        return time.asctime()
    elif format == 'mr':
        return dt.now()

oidlist = ['.1.3.6.1.2.1.31.1.1.1.1',  #IF-MIB::ifName
           '.1.3.6.1.2.1.4.34.1.3',  #IP-MIB::ipAddressIfIndex
           '.1.3.6.1.4.1.9.9.187.1.2.5.1.6',  # cbgpPeer2LocalAddr
           '.1.3.6.1.4.1.9.9.187.1.2.5.1.11', # cbgpPeer2RemoteAs
           ".1.3.6.1.2.1.2.2.1.7",  # ifAdminStatus 1up 2down 3testing
           ".1.3.6.1.2.1.2.2.1.8",  # ifOperStatus 1up 2down 3testing 4unknown ...
           ".1.3.6.1.2.1.31.1.1.1.15",  # ifHighSpeed
           ".1.3.6.1.2.1.31.1.1.1.6",  # ifHCInOctets
           ".1.3.6.1.2.1.31.1.1.1.10",  # ifHCOutOctets
           ".1.3.6.1.4.1.9.9.187.1.2.5.1.3.1.4.2.120.9.120"
           ]

class Router(threading.Thread):
    dsc_oids = oidlist[:3]
    int_oids = oidlist[4:9]
    bw_oids = oidlist[6:9]
    bgp_oids = oidlist[9:]
    def __init__(self, threadID, node, interfaces, dswitch):
        threading.Thread.__init__(self, name='thread-%d_%s' % (threadID, node))
        self.node = node
        self.pni_interfaces = interfaces['pni']
        self.cdn_interfaces = interfaces['cdn']
        self.interfaces = self.pni_interfaces + self.cdn_interfaces
        self.switch = dswitch
    def run(self):
        logging.info("Starting")
        self.tstamp = tstamp('mr')
        self.ipaddr = self.dns(self.node)
        #self.ping(self.ipaddr)
        if self.switch is True:
            logging.info("New inventory file detected. Initializing node discovery")
            for f in os.listdir('.'):
                if self.node+'.dsc' in f or self.node+'.prb' in f:
                    os.remove(f)
            disc = self.discovery(self.ipaddr)
        else:
            try:
                with open('do_not_modify_'.upper() + self.node + '.dsc') as tf:
                    disc = eval(tf.read())
            except IOError:
                logging.info("Discovery file(s) could not be located. Initializing node discovery")
                disc = self.discovery(self.ipaddr)
        self.process(self.ipaddr, disc)
        logging.info("Completed")
    def dns(self,node):
        try:
            ipaddr = socket.gethostbyname(node)
        except socket.gaierror as gaierr:
            logging.warning("Operation halted: %s" % (str(gaierr)))
            sys.exit(3)
        except:
            logging.warning("Unexpected error while resolving hostname")
            logging.debug("Unexpected error while resolving hostname: %s" % (str(sys.exc_info()[:2])))
            sys.exit(3)
        return ipaddr
    def ping(self,ipaddr):
        try:
            ptup = subprocess.Popen(['ping', '-i', '0.2', '-w', '2', '-c', '500', ipaddr, '-q'], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE).communicate()
        except:
            logging.warning("Unexpected error during ping test")
            logging.debug("Unexpected error - Popen function ping(): %s" % (str(sys.exc_info()[:2])))
            sys.exit(3)
        else:
            if ptup[1] == '':
                n = re.search(r'(\d+)\%\spacket loss', ptup[0])
                if n is not None:
                    if int(n.group(1)) == 0:
                        pingr = 0
                    elif 0 < int(n.group(1)) < 100:
                        logging.warning("Operation halted. Packet loss detected")
                        sys.exit(3)
                    elif int(n.group(1)) == 100:
                        logging.warning("Operation halted. Node unreachable")
                        sys.exit(3)
                    else:
                        logging.warning("Unexpected error during ping test")
                        logging.debug("Unexpected regex error during ping test: ### %s ###" % (str(n)))
                        sys.exit(3)
                else:
                    logging.warning("Unexpected error during ping test")
                    logging.debug("Unexpected regex error during ping test: ### %s ###" % (str(ptup[0])))
                    sys.exit(3)
            else:
                logging.warning("Unexpected error during ping test")
                logging.debug("Unexpected error during ping test: ### %s ###" % (str(ptup)))
                sys.exit(3)
        return pingr
    def discovery(self, ipaddr):
        ifTable, ipTable, peerTable = tuple([i.split(' ') for i in n] for n in
                                            map(lambda oid: self.snmp(self.ipaddr, [oid], quiet='off'), self.dsc_oids))
        disc = {}
        for interface in self.interfaces:
            for i in ifTable:
                if interface == i[3]:
                    disc[interface] = {'ifIndex':i[0].split('.')[1]}
        for interface in self.pni_interfaces:
            for i in ipTable:
                if disc[interface]['ifIndex'] == i[3]:
                    type = i[0].split('"')[0].split('.')[1]
                    if type == 'ipv4' or type == 'ipv6':
                        if not disc[interface].has_key('local_' + type):
                            disc[interface]['local_' + type] = [i[0].split('"')[1]]
                        else:
                            disc[interface]['local_' + type] += [i[0].split('"')[1]]
        for interface in self.pni_interfaces:
            for i in peerTable:
                if len(i) == 8:
                    locaddr = ('.').join([str(int(i[n], 16)) for n in range(3, 7)])
                    if disc[interface].has_key('local_ipv4'):
                        if locaddr in disc[interface]['local_ipv4']:
                            peeraddr = ('.').join(i[0].split('.')[-4:])
                            if not disc[interface].has_key('peer_ipv4'):
                                disc[interface]['peer_ipv4'] = [peeraddr]
                            else:
                                disc[interface]['peer_ipv4'] += [peeraddr]
                elif len(i) == 20:
                    locaddr = (':').join([str(i[n]) for n in range(3, 19)])
                    if disc[interface].has_key('local_ipv6'):
                        if locaddr in disc[interface]['local_ipv6']:
                            peeraddr = (':').join([format(int(n), '02x') for n in i[0].split('.')[-16:]])
                            if not disc[interface].has_key('peer_ipv6'):
                                disc[interface]['peer_ipv6'] = [peeraddr]
                            else:
                                disc[interface]['peer_ipv6'] += [peeraddr]
        with open('do_not_modify_'.upper()+self.node+'.dsc', 'w') as tf:
            tf.write(str(disc))
        return disc
    def probe(self, ipaddr, disc):
        old = []
        new = []
        args = ['tail', '-1']
        args.append('do_not_modify_'.upper() + self.node + '.prb')
        try:
            ptup = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        except:
            logging.warning("Unexpected error during probe operation")
            logging.debug("Unexpected error - Popen function probe(): %s" % (str(sys.exc_info()[:2])))
            sys.exit(3)
        else:
            if ptup[1] == '':
                old = eval(ptup[0])
                logging.info("Existing Node")
                # d = (b-a).total_seconds()
            elif "No such file or directory" in ptup[1]:
                logging.info("New Node")
            else:
                logging.warning("Unexpected error during %s operation" % (str(ptup)))
                logging.debug("Unexpected error during %s operation: ### %s ###" % (str(ptup)))
                sys.exit(3)
        finally:
            for interface in disc:
                int_new = self.snmp(self.ipaddr, [i + '.' + disc[interface]['ifIndex'] for i in self.int_oids], cmd='snmpget')
                int_new.insert(0, str(self.tstamp))
                int_new.insert(0, interface)
                new.append(int_new)
            with open('do_not_modify_'.upper() + self.node + '.prb', 'a') as pf:
                pf.write(str(new)+'\n')
        return old, new
    def snmp(self, ipaddr, oids, cmd='snmpwalk', quiet='on'):
        args = [cmd, '-v2c', '-c', 'kN8qpTxH', ipaddr]
        if quiet is 'on':
            args.insert(1, '-Oqv')
        args += oids
        try:
            stup = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        except:
            logging.warning("Unexpected error during %s operation" % (cmd))
            logging.debug("Unexpected error - Popen function snmp(): %s" % (str(sys.exc_info()[:2])))
            sys.exit(3)
        else:
            if stup[1] == '':
                snmpr = stup[0].strip('\n').split('\n')
            else:
                logging.warning("Unexpected error during %s operation" % (cmd))
                logging.debug("Unexpected error during %s operation: ### %s ###" % (cmd, str(stup)))
                sys.exit(3)
        return snmpr
    def process(self, ipaddr, disc):
        old, new = self.probe(ipaddr, disc)
        if old is not '':
            for o , n in zip(old, new):
                if n[0] in self.cdn_interfaces:
                    print "cdn",n[0]
                    if o[3] is "up" and n[3] is "up":
                        tdelta = (dt.strptime(n[1], "%Y-%m-%d %H:%M:%S.%f") - dt.strptime(o[1], "%Y-%m-%d %H:%M:%S.%f")).total_seconds()
                elif n[0] in self.pni_interfaces:
                    print "pni",n[0]
                else:
                    for i in self.interfaces:
                        print i
                    print n[0]
        else:
            pass


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
    asctime = tstamp('hr')
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
                print 'The value of the repeat (-r) argument must be an integer'
                sys.exit(2)
        elif opt in ('-f','--frequency'):
            try:
                frequency = int(arg)
            except ValueError:
                print 'The value of the frequency (-f) argument must be an integer'
                sys.exit(2)
        else:
            assert False, "unhandled option"
    logging.basicConfig(level=logging.getLevelName(loglevel),
                        format='%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s')  # FIXME
                                                                                            # revisit formatting %-Ns
    lastChanged = ""
    while True:
        try:
            with open(inputfile) as sf:
                inventory = parser([n.strip('\n') for n in sf.readlines()])
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
            logging.debug("Initializing subThreads")
            for n,node in enumerate(inventory):
                t = Router(n+1, node, inventory[node], dswitch)
                threads.append(t)
                t.start()
            for t in threads:
                t.join()
            lastChanged = os.stat(inputfile).st_mtime
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