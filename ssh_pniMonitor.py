#!/usr/bin/python

import paramiko
import getpass
import os
import sys
import socket

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
                print auth_failure
                c -= 1
            except:
                print 'Unexpected error in get_pw()', sys.exc_info()[:2]
                sys.exit(1)
            else:
                ssh.close()
                return True, pw
    else:
        print "Too many failed attempts"
        return False, None


def _ssh(node, pw, command):
    output = None
    try:
        ssh.connect(node, username=un, password=pw, look_for_keys=False, allow_agent=False)
    except:
        print 'Unexpected error:', sys.exc_info()[:2]
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
            print 'shell opened'
            output = ''
            session.send(command + '\n')
            while not session.recv_exit_status():
            #while not session.exit_status_ready():
                while session.recv_ready():
                    print "recv-ready"
                    output += session.recv(1024)
            else:
                print "closing"
                ssh.close()
        #stdin, stdout, stderr = ssh.exec_command(command)
        #type(stdin)
        #output = stdout.readlines()
        #ssh.close()
    return output


bool, pw = get_pw()

if bool:
    #raw_output = _ssh("er10.bllab", pw, "sh access-lists CDPautomation_RhmUdpBlock usage pfilter location all")
    raw_output = _ssh("er10.bllab", pw, "sh version")
    print raw_output
else:
    sys.exit(1)


#for i in raw_output:
#    print i.strip('\n')


