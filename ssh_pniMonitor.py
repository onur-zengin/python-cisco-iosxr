#!/usr/bin/env python

import paramiko
import getpass
import os
import sys
import socket
import time
import re
import threading
import logging

loglevel = 'DEBUG'

logging.Formatter('%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s')

main_logger = logging.getLogger(__name__)
main_logger.setLevel(logging.getLevelName(loglevel))
paramiko_logger = logging.getLogger('paramiko')
paramiko_logger.setLevel(logging.INFO)



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
        finally:
            try:
                ssh.connect(hn, username=un, password=pw, look_for_keys=False, allow_agent=False)
            except paramiko.ssh_exception.AuthenticationException as auth_failure:
                print ssh.get_transport().is_active()
                print auth_failure
                ssh.close()
                #print ssh.get_transport().is_active()
                c -= 1
            except:
                print 'Unexpected error in get_pw()', sys.exc_info()[:2]
                sys.exit(1)
            else:
                ssh.close()
                return True, pw
    else:
        print "Too many failed attempts"
        main_logger.debug("Too many failed attempts")
        return False, None


def _ssh(node, pw, commandlist):
    try:
        ssh.connect(node, username=un, password=pw, look_for_keys=False, allow_agent=False)
    except:
        print 'Unexpected error while connecting to the node:', sys.exc_info()[:2]
        ssh.close()
        sys.exit(1)
    else:
        try:
            session = ssh.invoke_shell()
        except paramiko.SSHException as sshexc:
            print sshexc
            sys.exit(1)
        except:
            print 'Unexpected error in _ssh()', sys.exc_info()[:2]
            sys.exit(1)
        else:
            commandlist.insert(0,'term len 0')
            output = []
            for cmd in commandlist:
                cmd_output = ''
                try:
                    session.send(cmd + '\n')
                except socket.error as sc_err:
                    print sc_err
                    #sys.exit(1)
                else:
                    while not session.exit_status_ready():
                        while session.recv_ready():
                            cmd_output += session.recv(1024)
                        else:
                            if '/CPU0:' + node not in cmd_output:
                                time.sleep(0.2)
                            else:
                                break
                    else:
                        print "SSH session closed prematurely"
                    output.append(cmd_output)
            main_logger.debug("closing")
            ssh.close()
    return output[1:]

main_logger.debug("starting")
bool, pw = get_pw()


if bool:
    raw = _ssh("er10.bllab", pw, ["sh access-lists CDPautomation_RhmUdpBlock usage pfilter loc all"])
    print raw
    print len(raw)
    for r in raw:
        print r
else:
    sys.exit(1)


#for i in raw_output:
#    print i.strip('\n')
#raw = ['\r', '                    _____\r', '                ___/  |  \\___\r', '             __/      |      \\__\r', '          __/         |         \\__\r', '         /|           |           |\\\r', '        | |           |           | |\r', '        | |           |           | |\r', '       |  |           |           |  |\r', '       |  |        ___|___        |  |\r', '      /   |    ___/  ___  \\___    |   \\\r', '      |   |___/  ___/| |\\___  \\___|   |\r', '      |   /   __/_ \\_| |_/ _\\__   \\   |\r', '     |   |___/\\_  \\_______/  _/\\___|   |\r', '    /   /___/   \\___\\___/___/   \\___\\   \\\r', '   /    |   |       |   |       |   |    \\\r', '  /     |   |_      |   |      _|   |     \\\r', ' |___   |___|_\\   _/|___|\\_   /_|___|   ___|\r', ' |_  \\    |   |\\ /  |___|  \\ /|   |    /  _|\r', ' ||| |    |   | |  _______  | |   |    | |||\r', ' ||| |    |   | |  \\_____/  | |   |    | |||\r', ' ||| |    |   | |    ___    | |   |    | |||\r', ' ||| |    |   | |           | |   |    | |||\r', ' ||| |    |   | |           | |   |    | |||\r', ' ||| |    |   | |           | |   |    | |||\r', ' ||| |    |   |\\|           |/|   |    | |||\r', ' \\||_|____|___|-\\___________/-|___|____|_||/\r', '\r', 'Welcome to your friendly local Megatron Chassis.\r', '         Enjoy your stay.\r', '\r', '\r', '\r', '\r', 'RP/0/RP0/CPU0:er10.bllab#term len 0\r', '\rSun Jan 29 21:10:03.082 GMT\r', 'RP/0/RP0/CPU0:er10.bllab#sh access-lists CDPautomation_RhmUdpBlock usage pfilte\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08$n_RhmUdpBlock usage pfilter                          \x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08 location all\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08sh access-lists CDPautomation_RhmUdpBlock usage pfilt$\x08\x08\x08\x08\r', '\rSun Jan 29 21:10:03.266 GMT\r', 'Interface : Bundle-Ether212 \r', '    Input ACL : N/A\r', '    Output ACL : CDPautomation_RhmUdpBlock \r', 'Interface : Bundle-Ether214 \r', '    Input Common-ACL : N/A  ACL : N/A  \r', '    Output ACL : N/A \r', 'RP/0/RP0/CPU0:er10.bllab#']

def acl_check(rawinput, interface, aclname):
    result = 'off'
    for i in rawinput:
        if re.search(r'Interface : (%s)$' % interface, i.strip('\r').strip(' ')) != None:
            acl = re.search(r'Output ACL : (%s)$' % aclname, rawinput[rawinput.index(i)+2].strip('\r').strip(' '))
            if acl != None:
                if acl.group(1) == aclname:
                    result = 'on'
    return result

print acl_check(raw, 'Bundle-Ether214', 'CDPautomation_RhmUdpBlock')