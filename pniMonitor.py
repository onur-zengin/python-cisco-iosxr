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

oidlist = ['.1.3.6.1.2.1.31.1.1.1.1',  #0 IF-MIB::ifName
           '.1.3.6.1.2.1.31.1.1.1.18', #1 IF-MIB::ifDescr
           '.1.3.6.1.2.1.4.34.1.3',  #2 IP-MIB::ipAddressIfIndex
           '.1.3.6.1.4.1.9.9.187.1.2.5.1.6',  #3 cbgpPeer2LocalAddr
           '.1.3.6.1.4.1.9.9.187.1.2.5.1.11', #4 cbgpPeer2RemoteAs
           ".1.3.6.1.2.1.2.2.1.7",  #5 ifAdminStatus 1up 2down 3testing
           ".1.3.6.1.2.1.2.2.1.8",  #6 ifOperStatus 1up 2down 3testing 4unknown ...
           ".1.3.6.1.2.1.31.1.1.1.15",  #7 ifHighSpeed
           ".1.3.6.1.2.1.31.1.1.1.6",  #8 ifHCInOctets
           ".1.3.6.1.2.1.31.1.1.1.10",  #9 ifHCOutOctets
           ".1.3.6.1.4.1.9.9.187.1.2.5.1.3", #10 cbgpPeer2State 3active 6established
           ".1.3.6.1.4.1.9.9.187.1.2.8.1.1" #11 cbgpPeer2AcceptedPrefixes
           ]

class Router(threading.Thread):
    dsc_oids = oidlist[:4]
    int_oids = oidlist[5:10]
    bw_oids = oidlist[7:10]
    bgp_oids = oidlist[10:]
    def __init__(self, threadID, node, dswitch, risk_factor, int_identifiers):
        threading.Thread.__init__(self, name='thread-%d_%s' % (threadID, node))
        self.node = node
        self.switch = dswitch
        self.risk_factor = risk_factor
        self.pni_identifier, self.cdn_identifier = int_identifiers
    def run(self):
        logging.debug("Starting")
        self.tstamp = tstamp('mr')
        self.ipaddr = self.dns(self.node)
        if self.switch is True:
            logging.info("Inventory updated. Initializing node discovery")
            for f in os.listdir('.'):
                if self.node+'.dsc' in f or self.node+'.prb' in f:
                    os.remove(f)
            disc = self.discovery(self.ipaddr)
        else:
            try:
                with open('.do_not_modify_'.upper() + self.node + '.dsc') as tf:
                    disc = eval(tf.read())
            except IOError:
                logging.info("Discovery file(s) could not be located. Initializing node discovery")
                disc = self.discovery(self.ipaddr)
        logging.debug("DISC successfully loaded: %s" % disc)
        self.pni_interfaces = [int for int in disc if disc[int]['type'] == 'pni']
        self.cdn_interfaces = [int for int in disc if disc[int]['type'] == 'cdn']
        self.interfaces = self.pni_interfaces + self.cdn_interfaces
        if self.interfaces != []:
            logging.debug("Discovered interfaces: %s" % str(self.interfaces))
            self._processor(self.ipaddr, disc)
        else:
            logging.info("No interfaces eligible for monitoring")
        logging.debug("Completed")
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
        pni_interfaces = []
        cdn_interfaces = []
        disc = {}
        ifNameTable, ifDescrTable, ipTable, peerTable = tuple([i.split(' ') for i in n] for n in
                                            map(lambda oid: self.snmp(ipaddr, [oid], quiet='off'), self.dsc_oids))
        for i, j in zip(ifDescrTable, ifNameTable):
            if 'no-mon' not in (' ').join(i[3:]) and self.pni_identifier in (' ').join(i[3:]) and 'Bundle-Ether' in j[3]:
                pni_interfaces.append(j[3])
                disc[j[3]] = {'ifIndex': j[0].split('.')[1]}
                disc[j[3]]['type'] = 'pni'
            elif 'no-mon' not in (' ').join(i[3:]) and self.cdn_identifier in (' ').join(i[3:]) and 'Bundle-Ether' in j[3]:
                cdn_interfaces.append(j[3])
                disc[j[3]] = {'ifIndex': j[0].split('.')[1]}
                disc[j[3]]['type'] = 'cdn'
        #logging.debug("ipTable %s" % ipTable)
        for interface in pni_interfaces:
            for i in ipTable:
                if disc[interface]['ifIndex'] == i[3]:
                    type = i[0].split('"')[0].split('.')[1]
                    if type == 'ipv4' or type == 'ipv6':
                        if not disc[interface].has_key('local_' + type):
                            disc[interface]['local_' + type] = [i[0].split('"')[1]]
                        else:
                            disc[interface]['local_' + type] += [i[0].split('"')[1]]
        #logging.debug("peerTable %s" % peerTable)
        for interface in pni_interfaces:
            for i in peerTable:
                if len(i) == 8:
                    locaddr = ('.').join([str(int(i[n], 16)) for n in range(3, 7)])
                    if disc[interface].has_key('local_ipv4'):
                        if locaddr in disc[interface]['local_ipv4']:
                            peeraddr = ('.').join(i[0].split('.')[-4:])
                            cbgpPeer2index = ('.').join(i[0].split('.')[-6:])
                            if not disc[interface].has_key('peer_ipv4'):
                                disc[interface]['peer_ipv4'] = [peeraddr]
                            else:
                                disc[interface]['peer_ipv4'] += [peeraddr]
                            if not disc[interface].has_key('cbgpPeer2index'):
                                disc[interface]['cbgpPeer2index'] = [cbgpPeer2index]
                            else:
                                disc[interface]['cbgpPeer2index'] += [cbgpPeer2index]
                elif len(i) == 20:
                    locaddr = (':').join([str(i[n]) for n in range(3, 19)])
                    if disc[interface].has_key('local_ipv6'):
                        if locaddr in disc[interface]['local_ipv6']:
                            peeraddr = (':').join([format(int(n), '02x') for n in i[0].split('.')[-16:]])
                            cbgpPeer2index = ('.').join(i[0].split('.')[-18:])
                            #peeraddr_decimal = ('.').join(i[0].split('.')[-16:])
                            if not disc[interface].has_key('peer_ipv6'):
                                disc[interface]['peer_ipv6'] = [peeraddr]
                            else:
                                disc[interface]['peer_ipv6'] += [peeraddr]
                            if not disc[interface].has_key('cbgpPeer2index'):
                                disc[interface]['cbgpPeer2index'] = [cbgpPeer2index]
                            else:
                                disc[interface]['cbgpPeer2index'] += [cbgpPeer2index]
        with open('.do_not_modify_'.upper()+self.node+'.dsc', 'w') as tf:
            tf.write(str(disc))
        return disc
    def probe(self, ipaddr, disc):
        old, new = {}, {}
        args = ['tail', '-1', '.do_not_modify_'.upper() + self.node + '.prb']
        try:
            ptup = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        except:
            logging.warning("Unexpected error - Popen function probe(): %s" % (str(sys.exc_info()[:2])))
            sys.exit(3)
        else:
            if ptup[1] == '':
                old = eval(ptup[0])
            elif "No such file or directory" in ptup[1]:
                logging.info("New Node")
            else:
                logging.warning("Unexpected output in the probe() function" % (str(ptup)))
                sys.exit(3)
        finally:
            for interface in sorted(disc):
                int_status = self.snmp(ipaddr, [i + '.' + disc[interface]['ifIndex'] for i in
                                                self.int_oids], cmd='snmpget')
                new[interface] = {'timestamp': str(self.tstamp)}
                new[interface]['adminStatus'] = int_status[0]
                new[interface]['operStatus'] = int_status[1]
                new[interface]['ifSpeed'] = int_status[2]
                new[interface]['ifInOctets'] = int_status[3]
                new[interface]['ifOutOctets'] = int_status[4]
                bgpgetlist = []
                if disc[interface]['type'] == 'pni' and disc[interface].has_key('cbgpPeer2index'):
                    for n in disc[interface]['cbgpPeer2index']:
                        if len(n.split('.')) == 6:
                            bgpgetlist.append(self.bgp_oids[0] + '.' + n)
                            bgpgetlist.append(self.bgp_oids[1] + '.' + n + '.1.1')
                        else:
                            bgpgetlist.append(self.bgp_oids[0] + '.' + n)
                            bgpgetlist.append(self.bgp_oids[1] + '.' + n + '.2.1')
                    bgp_status = self.snmp(ipaddr, bgpgetlist, cmd='snmpget')
                    peer_bgp_status = [(i, bgp_status[bgp_status.index(i) + len(self.bgp_oids) - 1]) for i in
                                       bgp_status[::len(self.bgp_oids)]]
                    logging.debug("bgp status %s" % bgp_status)
                    logging.debug("peer bgp status %s" % peer_bgp_status)
                elif disc[interface]['type'] == 'pni' and not disc[interface].has_key('cbgpPeer2index'):
                    logging.warning("PNI interface %s has no BGP sessions" % interface)
                #['.1.3.6.1.4.1.9.9.187.1.2.5.1.333.1.4.2.120.9.120', '.1.3.6.1.4.1.9.9.187.1.2.5.1.444.1.4.2.120.9.120',
                # '.1.3.6.1.4.1.9.9.187.1.2.5.1.333.1.4.42.1.0.1', '.1.3.6.1.4.1.9.9.187.1.2.5.1.444.1.4.42.1.0.1',
                # '.1.3.6.1.4.1.9.9.187.1.2.5.1.333.1.4.89.200.133.241', '.1.3.6.1.4.1.9.9.187.1.2.5.1.444.1.4.89.200.133.241']
            with open('.do_not_modify_'.upper() + self.node + '.prb', 'a') as pf:
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
                # elif timeout self.ping(self.ipaddr)
            else:
                logging.warning("Unexpected error during %s operation" % (cmd))
                logging.debug("Unexpected error during %s operation: ### %s ###" % (cmd, str(stup)))
                sys.exit(3)
        return snmpr
    def _processor(self, ipaddr, disc):
        old, new = self.probe(ipaddr, disc)
        logging.debug("OLD: %s" % old)
        logging.debug("NEW: %s" % new)
        actCdnIn, aggCdnIn, actPniOut, aggPniOut = 0, 0, 0, 0
        dateFormat = "%Y-%m-%d %H:%M:%S.%f"
        """
        if old != [] and len(old) == len(new):
            for o , n in zip(old, new):
                if n[0] in self.pni_interfaces:
                    if o[3] == 'up' and n[3] == 'up': # ADD BGP STATE IN THE CONDITIONS
                        delta_time = (dt.strptime(n[1], dateFormat) - dt.strptime(o[1], dateFormat)).total_seconds()
                        delta_outOct = int(n[6]) - int(o[6])
                        print n[0], "octets" , delta_outOct , "time" , delta_time
                        int_util = (delta_outOct * 800) / (delta_time * int(n[4]) * 10**6)
                        actPniOut += int_util
                    if n[3] == 'up':
                        aggPniOut += int(n[4])
                elif n[0] in self.cdn_interfaces:
                    if o[3] == 'up' and n[3] == 'up':
                        delta_time = (dt.strptime(n[1], dateFormat) - dt.strptime(o[1], dateFormat)).total_seconds()
                        delta_inOct = int(n[5]) - int(o[5])
                        int_util = (delta_inOct * 800) / (delta_time * int(n[4]) * 10**6)
                        disc[n[0]]['util'] = int_util
                        actCdnIn += int_util
                    if n[3] == 'up':
                        aggCdnIn += int(n[4])
            print "Active CDN Capacity: %.2f" % aggCdnIn
            print "Actual CDN Ingress: %.2f" % actCdnIn
            print "Usable PNI Capacity: %.2f" % aggPniOut
            print "Actual PNI Egress: %.2f" % actPniOut
            print disc
            #print [util for util in [disc[interface]['util'] for interface in self.cdn_interfaces]]
            #print min([util for util in [disc[interface]['util'] for interface in self.cdn_interfaces]])
            # if actPniOut / aggPniOut * 100 >= self.risk_factor:
            #   self.acl('block', min([util for util in [disc[interface]['util'] for interface in self.cdn_interfaces]]))
        elif old == [] and new != []:
            logging.info("New node detected. _process() module will be activated in the next polling cycle")
        elif old != [] and len(old) < len(new):
            logging.info("New interface discovered.")
            # PRB FILES ARE REMOVED WHEN A NEW INT IS DISCOVERED, SO THE STATEMENT IS A PLACEHOLDER
            # REVISIT THIS IN VERSION-2 WHEN PRB PERSISTENCE IS ENABLED
            # _process() should continue for the old interfaces.
        else:
            logging.warning("Unexpected error in the _process() function\nprev:%s\nnext:%s" % (old, new))
        """
    def acl(self, decision, interface):
        if decision == 'block':
            logging.warning("%s will now be blocked" % (interface))
        else:
            logging.info("%s will now be unblocked" % (interface))

"""
def parser(lst):
    dict = {}
    for node in [line.split(':') for line in lst]:
        dict[node[0]] = {}
        for i in range(len(node))[1:]:
            dict[node[0]][node[i].split(',')[0]] = [int for int in node[i].split(',')[1:]]
    return dict
"""

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


def main(args):
    asctime = tstamp('hr')
    pni_interface_tag = '[CDPautomation:PNI]'
    cdn_interface_tag = '[CDPautomation:CDN]'
    try:
        with open(args[0][:-3] + ".conf") as pf:
            parameters = [tuple(i.split('=')) for i in
                            filter(lambda line: line[0] != '#', [n.strip('\n') for n in pf.readlines()])]
    except IOError as ioerr:
        try:
            options, remainder = getopt.getopt(args[1:], "i:hl:r:f:", ["inputfile=", "help", "loglevel=",
                                                                       "risk_factor=", "frequency=", "runtime="])
        except getopt.GetoptError as err:
            print err
            usage(sys.argv[0])
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
            else:
                print "%s could not be located. The program will try to run with command line arguments.." \
                      % rg.group(1)
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
    finally:
        try:
            options, remainder = getopt.getopt(args[1:], "i:hl:r:f:", ["inputfile=", "help", "loglevel=",
                                                                       "risk_factor=", "frequency=", "runtime="])
        except getopt.GetoptError:
            sys.exit(2)
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
            elif opt in ('-r', '--risk_factor'):
                try:
                    risk_factor = int(arg)
                except ValueError:
                    print 'The value of the risk_factor argument must be an integer'
                    sys.exit(2)
                else:
                    if not 0 <= int(risk_factor) and int(risk_factor) <= 100:
                        print 'The value of the risk_factor argument must be an integer between 0 and 100'
                        sys.exit(2)
            elif opt in ('-f', '--frequency'):
                try:
                    frequency = int(arg)
                except ValueError:
                    print 'The value of the frequency (-f) argument must be an integer'
                    sys.exit(2)
            elif opt == '--runtime':
                if arg.lower() == 'infinite':
                    runtime = 'infinite'
                else:
                    try:
                        runtime = int(arg)
                    except ValueError:
                        print 'The value of the runtime (-r) argument must be either be "infinite" or an integer'
                        sys.exit(2)
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
        logging.basicConfig(level=logging.getLevelName(loglevel),
                            format='%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s')
        lastChanged = ""
        while True:
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
            except KeyboardInterrupt as kint:
                print kint
                sys.exit(1)
            else:
                threads = []
                logging.debug("Initializing subThreads")
                for n, node in enumerate(inventory):
                    t = Router(n + 1, node, dswitch, risk_factor, (pni_interface_tag, cdn_interface_tag))
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
                try:
                    time.sleep(frequency)
                except KeyboardInterrupt as kint:
                    print kint
                    sys.exit(1)


if __name__ == '__main__':
    main(sys.argv)