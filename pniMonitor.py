#!/usr/bin/env python2.7

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
from logging import handlers

ssh_formatter = logging.Formatter('%(asctime)-15s [%(levelname)s]: %(message)s')
ssh_ch = logging.StreamHandler()
ssh_ch.setFormatter(ssh_formatter)
ssh_logger = logging.getLogger('paramiko')
ssh_logger.addHandler(ssh_ch)
ssh_logger.setLevel(logging.WARNING)

main_logger = logging.getLogger(__name__)
main_formatter = logging.Formatter('%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s')
main_fh = handlers.TimedRotatingFileHandler('pniMonitor.log', when='midnight', backupCount=30)
main_fh.setFormatter(main_formatter)
main_logger.setLevel(logging.INFO)
main_logger.addHandler(main_fh)


def tstamp(format):
    if format == 'hr':
        return time.asctime()
    elif format == 'mr':
        return dt.now()

hd = os.environ['HOME']
un = getpass.getuser()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

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
        main_logger.info("Starting")
        self.tstamp = tstamp('mr')
        self.ipaddr = self.dns(self.node)
        if self.switch is True:
            main_logger.info("Inventory updated. Initializing node discovery")
            for f in os.listdir('.'):
                if self.node+'.dsc' in f or self.node+'.prb' in f:
                    os.remove(f)
            disc = self.discovery(self.ipaddr)
        else:
            try:
                with open('.do_not_modify_'.upper() + self.node + '.dsc') as tf:
                    disc = eval(tf.read())
            except IOError:
                main_logger.info("Discovery file(s) could not be located. Initializing node discovery")
                disc = self.discovery(self.ipaddr)
        main_logger.debug("DISC successfully loaded: %s" % disc)
        self.pni_interfaces = [int for int in disc if disc[int]['type'] == 'pni']
        self.cdn_interfaces = [int for int in disc if disc[int]['type'] == 'cdn']
        self.interfaces = self.pni_interfaces + self.cdn_interfaces
        if self.interfaces != []:
            main_logger.debug("Discovered interfaces: PNI %s\tCDN %s" % (self.pni_interfaces, self.cdn_interfaces))
            self._process(self.ipaddr, disc)
        else:
            main_logger.warning("No interfaces eligible for monitoring")
        main_logger.info("Completed")

    def dns(self,node):
        try:
            ipaddr = socket.gethostbyname(node)
        except socket.gaierror as gaierr:
            main_logger.warning("Operation halted: %s" % (str(gaierr)))
            sys.exit(3)
        except:
            main_logger.warning("Unexpected error while resolving hostname")
            main_logger.debug("Unexpected error while resolving hostname: %s\t%s" % sys.exc_info()[:2])
            sys.exit(3)
        return ipaddr

    def discovery(self, ipaddr):
        pni_interfaces = []
        cdn_interfaces = []
        disc = {}
        ifNameTable, ifDescrTable, ipTable, peerTable = tuple([i.split(' ') for i in n] for n in
                                            map(lambda oid: self.snmp(ipaddr, [oid], quiet='off'), self.dsc_oids))
        for i, j in zip(ifDescrTable, ifNameTable):
            if 'no-mon' not in (' ').join(i[3:]) and self.pni_identifier in (' ').join(i[3:]) \
                    and 'Bundle-Ether' in j[3]:
                pni_interfaces.append(j[3])
                disc[j[3]] = {'ifIndex': j[0].split('.')[1]}
                disc[j[3]]['type'] = 'pni'
            elif 'no-mon' not in (' ').join(i[3:]) and self.cdn_identifier in (' ').join(i[3:]) \
                    and ('Bundle-Ether' in j[3] or 'HundredGigE' in j[3]):
                cdn_interfaces.append(j[3])
                disc[j[3]] = {'ifIndex': j[0].split('.')[1]}
                disc[j[3]]['type'] = 'cdn'
        #main_logger.debug("ipTable %s" % ipTable)
        for interface in pni_interfaces:
            for i in ipTable:
                if disc[interface]['ifIndex'] == i[3]:
                    type = i[0].split('"')[0].split('.')[1]
                    if type == 'ipv4' or type == 'ipv6':
                        if not disc[interface].has_key('local_' + type):
                            disc[interface]['local_' + type] = [i[0].split('"')[1]]
                        else:
                            disc[interface]['local_' + type] += [i[0].split('"')[1]]
        #main_logger.debug("peerTable %s" % peerTable)
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
            main_logger.warning("Unexpected error - Popen function probe(): %s\t%s" % sys.exc_info()[:2])
            sys.exit(3)
        else:
            if ptup[1] == '':
                prv = eval(ptup[0])
            elif "No such file or directory" in ptup[1]:
                main_logger.info("New node detected")
            else:
                main_logger.warning("Unexpected output in the probe() function" % (str(ptup)))
                sys.exit(3)
        finally:
            raw_acl_status = self._ssh(ipaddr, ["sh access-lists %s usage pfilter loc all" % self.acl_name])
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
                        main_logger.warning("PNI interface %s has no BGP sessions" % interface)
                if disc[interface]['type'] == 'cdn':
                    nxt[interface]['aclStatus'] = self.acl_check(raw_acl_status[-1], interface, self.acl_name)
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
        main_logger.debug("prev: %s" % prv)
        main_logger.debug("next: %s" % nxt)
        actualCdnIn, physicalCdnIn, maxCdnIn, unblocked_maxCdnIn, actualPniOut, usablePniOut = 0, 0, 0, 0, 0, 0
        unblocked, blocked = [], []
        dF = "%Y-%m-%d %H:%M:%S.%f"
        if prv != {} and len(prv) == len(nxt):
            for p , n in zip(sorted(prv), sorted(nxt)):
                if n in self.pni_interfaces:
                    if nxt[n]['operStatus'] == 'up' \
                            and reduce(lambda x, y: int(x) + int(y),
                                       [nxt[n]['peerStatus_ipv4'][x][1] for x in nxt[n]['peerStatus_ipv4']
                                        if nxt[n]['peerStatus_ipv4'][x][0] == '6'], 0) > self.ipv4_minPfx \
                            or reduce(lambda x, y: int(x) + int(y),
                                      [nxt[n]['peerStatus_ipv6'][x][1] for x in nxt[n]['peerStatus_ipv6']
                                       if nxt[n]['peerStatus_ipv6'][x][0] == '6'], 0) > self.ipv6_minPfx:
                        usablePniOut += int(nxt[n]['ifSpeed'])
                        if prv[p]['operStatus'] == 'up':
                            delta_time = (dt.strptime(nxt[n]['ts'], dF) - dt.strptime(prv[p]['ts'], dF)).total_seconds()
                            delta_ifOutOctets = int(nxt[n]['ifOutOctets']) - int(prv[p]['ifOutOctets'])
                            int_util = (delta_ifOutOctets * 800) / (delta_time * int(nxt[n]['ifSpeed']) * 10**6)
                            actualPniOut += int_util
                elif n in self.cdn_interfaces:
                    if nxt[n]['operStatus'] == 'up':
                        physicalCdnIn += int(nxt[n]['ifSpeed'])
                        maxCdnIn += int(nxt[n]['ifSpeed']) * self.serving_cap / 100
                        if prv[p]['operStatus'] == 'up':
                            delta_time = (dt.strptime(nxt[n]['ts'], dF) - dt.strptime(prv[p]['ts'], dF)).total_seconds()
                            delta_ifInOctets = int(nxt[n]['ifInOctets']) - int(prv[p]['ifInOctets'])
                            int_util = (delta_ifInOctets * 800) / (delta_time * int(nxt[n]['ifSpeed']) * 10**6)
                            disc[n]['util'] = int_util
                            actualCdnIn += int_util
                        if nxt[n]['aclStatus'] == 'off':
                            unblocked.append(n)
                            unblocked_maxCdnIn += int(nxt[n]['ifSpeed']) * self.serving_cap / 100
                        elif nxt[n]['aclStatus'] == 'on':
                            blocked.append(n)
            main_logger.debug("Physical CDN Capacity: %.2f" % physicalCdnIn)
            main_logger.debug("Serving CDN Capacity: %.2f" % maxCdnIn)
            main_logger.debug("Actual CDN Ingress: %.2f" % actualCdnIn)
            main_logger.debug("Usable PNI Capacity: %.2f" % usablePniOut)
            main_logger.debug("Actual PNI Egress: %.2f" % actualPniOut)
            if usablePniOut == 0:
                if unblocked != []:
                    main_logger.warning('No usable PNI capacity available. Disabling all CDN interfaces')
                    results, output = self._acl(ipaddr, 'block', unblocked)
                    if results == ['on' for i in range(len(unblocked))]:
                        for interface in unblocked:
                            main_logger.info('Interface %s is now blocked' % interface)
                    else:
                        main_logger.critical('Interface blocking attempt failed:\n%s' % output)
                        # SEND THIS TO NETCOOL
                    for interface in blocked:
                        main_logger.info('Interface %s was already blocked' % interface)
                else:
                    main_logger.debug('No usable PNI egress capacity available. But all CDN interfaces blocked already, '
                                  'there is nothing more to be done')
            # We can't use actualCDNIn while calculating the risk_factor because it won't include P2P traffic
            # and / or the CDN overflow from the other site. It is worth revisiting for Sky Germany though.
            elif actualPniOut / usablePniOut * 100 >= self.risk_factor:
                if unblocked != []:
                    main_logger.warning('The ratio of actual PNI egress traffic to available egress capacity is equal to'
                                    ' or greater than the pre-defined Risk Factor')
                    results, output = self._acl(ipaddr, 'block', unblocked)
                    if results == ['on' for i in range(len(unblocked))]:
                        for interface in unblocked:
                            main_logger.info('Interface %s is now blocked' % interface)
                    else:
                        main_logger.critical('Interface blocking attempt failed:\n%s' % output)
                    for interface in blocked:
                        main_logger.info('Interface %s was already blocked' % interface)
                else:
                    main_logger.debug('Risk Factor hit. But all CDN interfaces blocked already, '
                                  'there is nothing more to be done')
            elif blocked != [] and actualPniOut / usablePniOut * 100 < self.risk_factor:
                if maxCdnIn + actualPniOut < usablePniOut:
                    main_logger.info('Risk mitigated. Re-enabling all CDN interfaces')
                    results, output = self._acl(ipaddr, 'unblock', blocked)
                    if results == ['off' for i in range(len(blocked))]:
                        for interface in blocked:
                            main_logger.info('Interface %s is now unblocked' % interface)
                    else:
                        main_logger.critical('Interface unblocking attempt failed:\n%s' % output)
                    for interface in unblocked:
                        main_logger.info('Interface %s was already unblocked' % interface)
                else:
                    for value in sorted([util for util in [disc[interface]['util'] for interface in disc]], reverse=True):
                        candidate_interface = filter(lambda interface: disc[interface]['util'] == value, disc)[0]
                        self_maxCdnIn = nxt[candidate_interface]['ifSpeed'] * self.serving_cap / 100
                        if actualPniOut - actualCdnIn + unblocked_maxCdnIn + self_maxCdnIn < usablePniOut:
                            main_logger.info('Risk partially mitigated. Re-enabling one interface: %s' % candidate_interface)
                            results, output = self._acl(ipaddr, 'unblock', [candidate_interface])
                            if results == ['off']:
                                main_logger.info('Interface %s is now unblocked' % candidate_interface)
                            else:
                                main_logger.critical('Interface unblocking attempt failed:\n%s' % output)
                            break
            else:
                main_logger.info('_process() completed. No action taken nor was necessary.')
        elif prv == {} and len(nxt) > 0:
            main_logger.info("New node detected. _process() module will be activated in the next polling cycle")
        elif prv != {} and len(prv) < len(nxt):
            main_logger.info("New interface discovered.")
            # There is no persistence in this release (*.prb files are removed whene a new interface is discovered)
            # So the elif statement is a placeholder.
            # This will be revisited in version-2 when persistence is enabled, so that _process() function can
            # continue running for the already existing interfaces.
        else:
            main_logger.critical("Unexpected error in the _process() function\nprev:%s\nnext:%s" % (prv, nxt))

    def _acl(self, ipaddr, decision, interfaces):
        results = []
        commands = ["configure", "commit", "end", "sh access-lists %s usage pfilter loc all" % self.acl_name]
        if self.dryrun == False:
            if decision == 'block':
                for interface in interfaces:
                    commands[1:1] = ["interface " + interface, "ipv4 access-group %s egress" % self.acl_name, "exit"]
                    main_logger.warning("%s will be blocked" % interface)
                output = self._ssh(ipaddr, commands)
                for interface in interfaces:
                    results.append(self.acl_check(output[-1], interface, self.acl_name))
            else:
                for interface in interfaces:
                    commands[1:1] = ["interface " + interface, "no ipv4 access-group %s egress" % self.acl_name, "exit"]
                    main_logger.info("%s will be unblocked" % interface)
                output = self._ssh(ipaddr, commands)
                for interface in interfaces:
                    results.append(self.acl_check(output[-1], interface, self.acl_name))
        elif self.dryrun == True:
            main_logger.warning('Program operating in simulation mode. No configuration changes will be made to the '
                                'router')
            if decision == 'block':
                for interface in interfaces:
                    main_logger.warning("%s will be blocked" % interface)
                    results = ['on' for x in range(len(interfaces))]
                output = None
            else:
                for interface in interfaces:
                    main_logger.warning("%s will be blocked" % interface)
                    results = ['off' for x in range(len(interfaces))]
                output = None
        return results, output

    def _ssh(self, ipaddr, commandlist):
        try:
            ssh.connect(ipaddr, username=un, password=self.pw, timeout=3, look_for_keys=False, allow_agent=False)
        except KeyboardInterrupt:
            main_logger.info("Keyboard Interrupt")
            sys.exit(0)
        except paramiko.ssh_exception.AuthenticationException as auth_failure:
            ssh.close()
            main_logger.warning(auth_failure)
            sys.exit(1)
        except paramiko.ssh_exception.NoValidConnectionsError as conn_failure:
            ssh.close()
            main_logger.critical(conn_failure)
            sys.exit(1)
        except paramiko.ssh_exception.SSHException as sshexc:
            ssh.close()
            main_logger.critical('SSH connection timeout %s' % sshexc)
            sys.exit(1)
        except:
            main_logger.critical('Unexpected error while connecting to the node: %s\t%s' % sys.exc_info()[:2])
            sys.exit(1)
        else:
            main_logger.debug("SSH connection successful")
            try:
                session = ssh.invoke_shell()
            except paramiko.SSHException as ssh_exc:
                main_logger.warning(ssh_exc)
                sys.exit(1)
            except:
                main_logger.warning('Unexpected error while invoking SSH shell: %s\t%s' % sys.exc_info()[:2])
                sys.exit(1)
            else:
                main_logger.debug("SSH shell session successful")
                commandlist.insert(0, 'term len 0')
                output = []
                for cmd in commandlist:
                    cmd_output = ''
                    try:
                        session.send(cmd + '\n')
                    except socket.error as sc_err:
                        main_logger.warning(sc_err)
                        sys.exit(1)
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
                            main_logger.warning("SSH connection closed prematurely")
                        output.append(cmd_output)
                try:
                    session.send('exit\n')
                except socket.error as sc_err:
                    main_logger.warning(sc_err)
                    ssh.close()
                else:
                    #ssh.close()
                    main_logger.debug("SSH connection closed")
        return output[1:]

    def snmp(self, ipaddr, oids, cmd='snmpwalk', quiet='on'):
        args = [cmd, '-v2c', '-c', 'kN8qpTxH', ipaddr]
        if quiet is 'on':
            args.insert(1, '-Oqv')
        args += oids
        try:
            stup = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        except:
            main_logger.warning("Unexpected error during %s operation" % (cmd))
            main_logger.debug("Unexpected error - Popen function snmp(): %s\t%s" % sys.exc_info()[:2])
            sys.exit(3)
        else:
            if stup[1] == '':
                snmpr = stup[0].strip('\n').split('\n')
                # elif timeout self.ping(self.ipaddr)
            else:
                main_logger.warning("Unexpected error during %s operation" % (cmd))
                main_logger.debug("Unexpected error during %s operation: ### %s ###" % (cmd, str(stup)))
                sys.exit(3)
        return snmpr

    def ping(self,ipaddr):
        try:
            ptup = subprocess.Popen(['ping', '-i', '0.2', '-w', '2', '-c', '500', ipaddr, '-q'], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE).communicate()
        except:
            logging.warning("Unexpected error during ping test")
            logging.debug("Unexpected error - Popen function ping(): %s\t%s" % sys.exc_info()[:2])
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


def usage(arg, opt=False):
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
    hn = socket.gethostname()
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
                ssh.connect(hn, username=un, password=pw, timeout=1, look_for_keys=False, allow_agent=False)
            except KeyboardInterrupt:
                main_logger.info("Keyboard Interrupt")
                sys.exit(0)
            except paramiko.ssh_exception.AuthenticationException as auth_failure:
                ssh.close()
                print 'Authentication Failure'
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
        main_logger.warning('Too many failed attempts')
        print "Too many failed attempts"
        return False, None


def main(args):
    #asctime = tstamp('hr')
    inventory_file = 'inventory.txt'
    frequency = 20
    risk_factor = 97
    loglevel = 'INFO'
    email_alert_severity = 'WARNING'
    acl_name = 'CDPautomation_RhmUdpBlock'
    pni_interface_tag = 'CDPautomation_PNI'
    cdn_interface_tag = 'CDPautomation_CDN'
    ipv4_min_prefixes = 0
    ipv6_min_prefixes = 50
    cdn_serving_cap = 90
    dryrun = False
    runtime = 'infinite'
    email_recipient_list = ['onur.zengin@sky.uk']
    try:
        options, remainder = getopt.getopt(args[1:], "hm", ["help", "manual"])
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
                main_logger.warning("'%s could not be located. The program will continue with its default settings."
                                 "\nUse '%s -m or %s --manual to see detailed usage instructions."
                                 % (rg.group(1)[3:], args[0], args[0]))
            else:
                main_logger.warning("'%s could not be located. The program will continue with the last known good "
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
                                main_logger.info('Loglevel has been updated: %s' % arg.upper())
                            loglevel = arg.upper()
                        else:
                            if lastChanged == "":
                                main_logger.warning('Invalid value specified for loglevel. Resetting to default '
                                                    'setting: %s' % loglevel)
                            else:
                                main_logger.warning('Invalid value specified for loglevel. Resetting to last known '
                                                    'good configuration: %s' % loglevel)
                    elif opt == 'email_alert_severity':
                        if arg.lower() in ('info', 'warning', 'critical'):
                            if email_alert_severity != arg.upper():
                                main_logger.info('Email alert severity has been updated: %s' % arg.upper())
                            email_alert_severity = arg.upper()
                        else:
                            if lastChanged == "":
                                main_logger.warning('Invalid severity specified for email alerts. Resetting to default '
                                                    'setting: %s' % email_alert_severity)
                            else:
                                main_logger.warning('Invalid severity specified for email alerts. Resetting to last '
                                                    'known good configuration: %s' % email_alert_severity)
                    elif opt == 'risk_factor':
                        try:
                            arg = int(arg)
                        except ValueError:
                            if lastChanged == "":
                                main_logger.warning('The value of the risk_factor argument must be an integer. '
                                                    'Resetting to default setting: %s' % risk_factor)
                            else:
                                main_logger.warning('The value of the risk_factor argument must be an integer. '
                                                    'Resetting to last known good configuration: %s' % risk_factor)
                        else:
                            if arg >= 0 and arg <= 100:
                                if risk_factor != arg:
                                    main_logger.info('Risk Factor has been updated: %s' % arg)
                                risk_factor = arg
                            else:
                                if lastChanged == "":
                                    main_logger.warning('The value of the risk_factor argument must be an integer '
                                                        'between 0 and 100. Resetting to default setting: %s'
                                                        % risk_factor)
                                else:
                                    main_logger.warning('The value of the risk_factor argument must be an integer '
                                                        'between 0 and 100. Resetting to last known good configuration: '
                                                        '%s' % risk_factor)
                    elif opt == 'frequency':
                        try:
                            arg = int(arg)
                        except ValueError:
                            if lastChanged == "":
                                main_logger.warning('The value of the frequency argument must be an integer. Resetting '
                                                 'to default setting: %s' % frequency)
                            else:
                                main_logger.warning('The value of the frequency argument must be an integer. Resetting '
                                                 'to last known good configuration: %s' % frequency)
                        else:
                            if arg >= 30 and arg <= 120:
                                if frequency != arg:
                                    main_logger.info('Running frequency has been updated: %s' % arg)
                                frequency = arg
                            else:
                                if lastChanged == "":
                                    main_logger.warning('The running frequency can not be shorter than 30 or longer '
                                                        'than 120 seconds. Resetting to default setting: %s'
                                                        % frequency)
                                else:
                                    main_logger.warning('The running frequency can not be shorter than 30 or longer '
                                                        'than 120 seconds. Resetting to last known good configuration: '
                                                        '%s' % frequency)
                    elif opt == 'runtime':
                        if arg.lower() == 'infinite':
                            if runtime != arg.lower():
                                main_logger.info('Runtime has been updated: "infinite"')
                            runtime = 'infinite'
                        else:
                            try:
                                arg = int(arg)
                            except ValueError:
                                main_logger.warning('The value of the runtime argument must be either be "infinite" or '
                                                 'an integer')
                            else:
                                if runtime != arg:
                                    main_logger.info('Runtime has been updated: %s' % arg)
                                runtime = arg
                    elif opt.lower() == 'ipv4_min_prefixes':
                        try:
                            arg = int(arg)
                        except ValueError:
                            if lastChanged == "":
                                main_logger.warning('The value of the ipv4_min_prefixes must be an integer. Resetting '
                                                 'to default setting: %s' % ipv4_min_prefixes)
                            else:
                                main_logger.warning('The value of the ipv4_min_prefixes must be an integer. Resetting '
                                                 'to last known good configuration: %s' % ipv4_min_prefixes)
                        else:
                            if ipv4_min_prefixes != arg:
                                main_logger.info('ipv4_min_prefix count has been updated: %s' % arg)
                            ipv4_min_prefixes = arg
                    elif opt.lower() == 'ipv6_min_prefixes':
                        try:
                            arg = int(arg)
                        except ValueError:
                            if lastChanged == "":
                                main_logger.warning('The value of the ipv6_min_prefixes must be an integer. Resetting '
                                                 'to default setting: %s' % ipv6_min_prefixes)
                            else:
                                main_logger.warning('The value of the ipv6_min_prefixes must be an integer. Resetting '
                                                 'to last known good configuration: %s' % ipv6_min_prefixes)
                        else:
                            if ipv6_min_prefixes != arg:
                                main_logger.info('ipv6_min_prefix count has been updated: %s' % arg)
                            ipv6_min_prefixes = arg
                    elif opt == 'email_recipient_list':
                        split_lst = arg.split(',')
                        try:
                            for email in split_lst:
                                match = re.search(r"[\w.-]+@(sky.uk|bskyb.com)", email)
                                match.group()
                        except AttributeError:
                            if lastChanged == "":
                                main_logger.warning('Invalid email address found in the recipient list. Resetting '
                                                    'to default setting: %s' % email_recipient_list)
                            else:
                                main_logger.warning('Invalid email address found in the recipient list. Resetting '
                                                    'to last known good configuration: %s' % email_recipient_list)
                        else:
                            if email_recipient_list != split_lst:
                                main_logger.info('Email recipient list has been updated: %s' % split_lst)
                            email_recipient_list = split_lst
                    elif opt == 'simulation_mode':
                        if arg.lower() == 'on':
                            dryrun = True
                            main_logger.info('Program running in simulation mode')
                        elif arg.lower() == 'off':
                            if dryrun != False:
                                main_logger.info('Simulation mode turned off')
                            dryrun = False
                        else:
                            main_logger.warning('The simulation parameter takes only two arguments: "on" or "off"')
                    elif opt.lower() in ('pni_interface_tag', 'cdn_interface_tag', 'ssh_loglevel', 'acl_name'):
                        pass
                    else:
                        if lastChanged == "":
                            main_logger.warning("Invalid parameter found in the configuration file: (%s). The program "
                                             "will continue with its default settings. Use '%s -m' or '%s --manual' "
                                             "to see detailed usage instructions." % (opt, args[0], args[0]))
                        else:
                            main_logger.warning("Invalid parameter found in the configuration file: (%s). The program "
                                             "will continue with the last known good configuration. Use '%s -m' or '%s "
                                             "--manual' to see detailed usage instructions." % (opt, args[0], args[0]))
            except ValueError:
                main_logger.warning("Invalid configuration line detected and ignored. All configuration parameters must "
                                 "be provided in key value pairs separated by an equal sign (=). Use '%s -m' or '%s "
                                 "--manual' for more details." % (args[0], args[0]))
        finally:
            main_logger.setLevel(logging.getLevelName(loglevel))
            main_eh = handlers.SMTPHandler('localhost', 'no-reply@automation.skycdp.com', email_recipient_list,
                                           'Virgin Media PNI Monitor')
            main_eh.setFormatter(main_formatter)
            main_eh.setLevel(logging.getLevelName(email_alert_severity))
            main_logger.addHandler(main_eh)
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
                main_logger.critical('%s. Exiting.' % ioerr)
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