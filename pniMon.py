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
           ".1.3.6.1.4.1.9.9.187.1.2.8.1.1", #11 cbgpPeer2AcceptedPrefixes
           ".1.3.6.1.4.1.9.9.808.1.1.4" #12 caAclAccessGroupCfgTable
           ]

class Router(threading.Thread):
    dsc_oids = oidlist[:4]
    int_oids = oidlist[5:10]
    bw_oids = oidlist[7:10]
    bgp_oids = oidlist[10:]
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
            self._process(self.ipaddr, disc)
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
                                disc[interface]['peer_ipv4'] = [(peeraddr, cbgpPeer2index)]
                            else:
                                disc[interface]['peer_ipv4'] += [(peeraddr, cbgpPeer2index)]
                elif len(i) == 20:
                    locaddr = (':').join([str(i[n]) for n in range(3, 19)])
                    if disc[interface].has_key('local_ipv6'):
                        if locaddr in disc[interface]['local_ipv6']:
                            peeraddr = (':').join([format(int(n), '02x') for n in i[0].split('.')[-16:]])
                            cbgpPeer2index = ('.').join(i[0].split('.')[-18:])
                            if not disc[interface].has_key('peer_ipv6'):
                                disc[interface]['peer_ipv6'] = [(peeraddr, cbgpPeer2index)]
                            else:
                                disc[interface]['peer_ipv6'] += [(peeraddr, cbgpPeer2index)]
        with open('.do_not_modify_'.upper()+self.node+'.dsc', 'w') as tf:
            tf.write(str(disc))
        return disc

    def probe(self, ipaddr, disc):
        prv, nxt = {}, {}
        args = ['tail', '-1', '.do_not_modify_'.upper() + self.node + '.prb']
        try:
            ptup = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        except:
            logging.warning("Unexpected error - Popen function probe(): %s" % str(sys.exc_info()[:2]))
            sys.exit(3)
        else:
            if ptup[1] == '':
                prv = eval(ptup[0])
            elif "No such file or directory" in ptup[1]:
                logging.info("New Node")
            else:
                logging.warning("Unexpected output in the probe() function" % (str(ptup)))
                sys.exit(3)
        finally:
            raw_acl_status = self._ssh(ipaddr, ["sh access-lists CDPautomation_RhmUdpBlock usage pfilter loc all"])
            for interface in sorted(disc):
                int_status = self.snmp(ipaddr, [i + '.' + disc[interface]['ifIndex'] for i in
                                                self.int_oids], cmd='snmpget')
                nxt[interface] = {'ts': str(self.tstamp)}
                nxt[interface]['adminStatus'] = int_status[0]
                nxt[interface]['operStatus'] = int_status[1]
                nxt[interface]['ifSpeed'] = int_status[2]
                nxt[interface]['ifInOctets'] = int_status[3]
                nxt[interface]['ifOutOctets'] = int_status[4]
                if disc[interface]['type'] == 'pni':
                    nxt[interface]['peerStatus_ipv4'] = {}
                    nxt[interface]['peerStatus_ipv6'] = {}
                    if disc[interface].has_key('peer_ipv4'):
                        for n in disc[interface]['peer_ipv4']:
                            peer_status = self.snmp(ipaddr, [self.bgp_oids[0] + '.' + n[1]]
                                                    + [self.bgp_oids[1] + '.' + n[1] + '.1.1'], cmd='snmpget')
                            nxt[interface]['peerStatus_ipv4'][n[0]] = peer_status
                    if disc[interface].has_key('peer_ipv6'):
                        for n in disc[interface]['peer_ipv6']:
                            peer_status = self.snmp(ipaddr, [self.bgp_oids[0] + '.' + n[1]]
                                                    + [self.bgp_oids[1] + '.' + n[1] + '.2.1'], cmd='snmpget')
                            nxt[interface]['peerStatus_ipv6'][n[0]] = peer_status
                    if not disc[interface].has_key('peer_ipv4') and not disc[interface].has_key('peer_ipv6'):
                        logging.warning("PNI interface %s has no BGP sessions" % interface)
                if disc[interface]['type'] == 'cdn':
                    nxt[interface]['aclStatus'] = self.acl_check(raw_acl_status, interface, self.acl_name)
            with open('.do_not_modify_'.upper() + self.node + '.prb', 'a') as pf:
                pf.write(str(nxt)+'\n')
        return prv, nxt

    def acl_check(self, rawinput, interface, acl_name):
        result = 'off'
        rawinput = rawinput.split('\n')
        for i in rawinput:
            if re.search(r'Interface : (%s)$' % interface, i.strip('\r').strip(' ')) != None:
                acl = re.search(r'Output ACL : (%s)$' % acl_name, rawinput[rawinput.index(i) + 2].strip('\r').strip(' '))
                if acl != None:
                    if acl.group(1) == acl_name:
                        result = 'on'
        return result

    def _process(self, ipaddr, disc):
        prv, nxt = self.probe(ipaddr, disc)
        logging.debug("prev: %s" % prv)
        logging.debug("next: %s" % nxt)
        actualCdnIn, physicalCdnIn, servingCdnIn, actualPniOut, usablePniOut = 0, 0, 0, 0, 0
        dF = "%Y-%m-%d %H:%M:%S.%f"
        if prv != {} and len(prv) == len(nxt):
            for p , n in zip(sorted(prv), sorted(nxt)):
                if n in self.pni_interfaces:
                    if nxt[n]['operStatus'] == 'up' \
                            and reduce(lambda x, y: x[1] + y[1],
                                       filter(lambda x: x[0] == '6', nxt[n]['peerStatus_ipv4']), 0) > self.ipv4_minPfx \
                            or reduce(lambda x, y: x[1] + y[1],
                                      filter(lambda x: x[0] == '6', nxt[n]['peerStatus_ipv6']), 0) > self.ipv6_minPfx :
                        usablePniOut += int(nxt[n]['ifSpeed'])
                        if prv[p]['operStatus'] == 'up':
                            delta_time = (dt.strptime(nxt[n]['ts'], dF) - dt.strptime(prv[p]['ts'], dF)).total_seconds()
                            delta_ifOutOctets = int(nxt[n]['ifOutOctets']) - int(prv[p]['ifOutOctets'])
                            int_util = (delta_ifOutOctets * 800) / (delta_time * int(nxt[n]['ifSpeed']) * 10**6)
                            actualPniOut += int_util
                elif n in self.cdn_interfaces:
                    if nxt[n]['operStatus'] == 'up':
                        physicalCdnIn += int(nxt[n]['ifSpeed'])
                        servingCdnIn += int(nxt[n]['ifSpeed']) * self.serving_cap / 100
                        if prv[p]['operStatus'] == 'up':
                            delta_time = (dt.strptime(nxt[n]['ts'], dF) - dt.strptime(prv[p]['ts'], dF)).total_seconds()
                            delta_ifInOctets = int(nxt[n]['ifInOctets']) - int(prv[p]['ifInOctets'])
                            int_util = (delta_ifInOctets * 800) / (delta_time * int(nxt[n]['ifSpeed']) * 10**6)
                            #disc[n]['util'] = int_util
                            actualCdnIn += int_util
            logging.debug("Physical CDN Capacity: %.2f" % physicalCdnIn)
            logging.debug("Serving CDN Capacity: %.2f" % servingCdnIn)
            logging.debug("Actual CDN Ingress: %.2f" % actualCdnIn)
            logging.debug("Usable PNI Capacity: %.2f" % usablePniOut)
            logging.debug("Actual PNI Egress: %.2f" % actualPniOut)
            #print [util for util in [disc[interface]['util'] for interface in self.cdn_interfaces]]
            #print min([util for util in [disc[interface]['util'] for interface in self.cdn_interfaces]])
            if usablePniOut == 0:
                logging.warning('No usable PNI capacity available')
                for interface in self.cdn_interfaces:
                    if nxt[interface]['aclStatus'] == 'off':
                        result, output = self.acl(ipaddr, 'block', interface)
                        if result == 'on':
                            logging.info('Interface %s is now blocked' % interface)
                        else:
                            logging.warning('Interface blocking attempt failed:\n%s' % output)
                    else:
                        logging.info('Interface %s was already blocked' % interface)
            # We can't use actualCDNIn while calculating the risk_factor because it won't include P2P traffic and / or
            # the CDN overflow from the other site.
            elif actualPniOut / usablePniOut * 100 >= self.risk_factor:
                logging.warning('The ratio of actual CDN ingress traffic to available PNI egress capacity is equal to'
                                ' or greater than the pre-defined Risk Factor')
                for interface in self.cdn_interfaces:
                    if nxt[interface]['aclStatus'] == 'off':
                        result, output = self.acl(ipaddr, 'block', interface)
        elif prv == {} and len(nxt) > 0:
            logging.info("New node detected. _process() module will be activated in the next polling cycle")
        elif prv != {} and len(prv) < len(nxt):
            logging.info("New interface discovered.")
            # PRB FILES ARE REMOVED WHEN A NEW INT IS DISCOVERED, SO THE STATEMENT IS A PLACEHOLDER.
            # TO BE REVISITED IN VERSION-2 WHEN PRB PERSISTENCE IS ENABLED, SO THAT _process() CAN CONTINUE
            # FOR THE EXISTING INTERFACES.
        else:
            logging.warning("Unexpected error in the _process() function\nprev:%s\nnext:%s" % (prv, nxt))

    def acl(self, ipaddr, decision, interfaces):
        if self.dryrun == 'off':
            if decision == 'block':
                commands = ["configure", "commit", "end",
                            "sh access-lists CDPautomation_RhmUdpBlock usage pfilter loc all"]
                for interface in interfaces:
                    commands[1:1] = ["interface " + interface, "ipv4 access-group CDPautomation_RhmUdpBlock egress",
                                     "exit"]
                    logging.warning("%s will be blocked" % interface)
                output = self._ssh(ipaddr, commands)
                for interface in interfaces:
                    result = self.acl_check(output, interface, self.acl_name)
            else:
                logging.info("%s will be unblocked" % interface)
                output = self._ssh(ipaddr, ["configure","interface " + interface,
                                   "no ipv4 access-group CDPautomation_RhmUdpBlock egress",
                                   "commit","end"])
                raw_acl_status = self._ssh(ipaddr, ["sh access-lists CDPautomation_RhmUdpBlock usage pfilter loc all"])
                result = self.acl_check(raw_acl_status, interface, self.acl_name)
        else:
            logging.warning('Program operating in simulation mode. No configuration changes will be made on the router')
            if decision == 'block':
                logging.warning("%s will be blocked" % (interface))
                result = 'off'
                output = None
            else:
                logging.info("%s will be unblocked" % (interface))
                result = 'on'
                output = None
        return result, output

    def _ssh(self, ipaddr, commandlist):
        try:
            ssh.connect(ipaddr, username=un, password=self.pw, look_for_keys=False, allow_agent=False)
        except:
            logging.warning('Unexpected error while connecting to the node: %s' % sys.exc_info()[:2])
            sys.exit(1)
        else:
            logging.debug("SSH connection successful")
            try:
                session = ssh.invoke_shell()
            except paramiko.SSHException as ssh_exc:
                logging.warning(ssh_exc)
                sys.exit(1)
            except:
                logging.warning('Unexpected error while invoking SSH shell: %s' % sys.exc_info()[:2])
                sys.exit(1)
            else:
                logging.debug("SSH shell session successful")
                commandlist.insert(0, 'term len 0')
                output = ''
                for cmd in commandlist:
                    cmd_output = ''
                    try:
                        session.send(cmd + '\n')
                    except socket.error as sc_err:
                        logging.warning(sc_err)
                        # sys.exit(1)
                    else:
                        while not session.exit_status_ready():
                            while session.recv_ready():
                                cmd_output += session.recv(1024)
                            else:
                                if '/CPU0:' + self.node not in cmd_output:
                                    time.sleep(0.2)
                                else:
                                    break
                        else:
                            logging.warning("SSH connection closed prematurely")
                        output += cmd_output
                logging.debug("SSH connection closed")
                ssh.close()
        return output

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


hd = os.environ['HOME']
un = getpass.getuser()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def get_pw(c=3):
    hn = socket.gethostname()
    while c > 0:
        try:
            pw = getpass.getpass('Enter cauth password for user %s:' % un, stream=None)
        except getpass.GetPassWarning as echo_warning:
            print echo_warning
        except KeyboardInterrupt as kb_int:
            print kb_int
            sys.exit(0)
        finally:
            try:
                ssh.connect(hn, username=un, password=pw, look_for_keys=False, allow_agent=False)
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
        main_logger = logging.getLogger(__name__)
        main_logger.setLevel(logging.getLevelName(loglevel))
        logging.basicConfig(format='%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s')
        #paramiko_logger = logging.getLogger('paramiko')
        #paramiko_logger.setLevel(logging.INFO)
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
            else:
                threads = []
                logging.debug("Initializing subThreads")
                for n, node in enumerate(inventory):
                    t = Router(n + 1, node, pw, dswitch, risk_factor, cdn_serving_cap, acl_name, dryrun,
                               (pni_interface_tag, cdn_interface_tag), (ipv4_min_prefixes, ipv6_min_prefixes))
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