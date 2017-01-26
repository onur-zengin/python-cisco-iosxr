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
                ssh.connect(hn, username=un, password=pw, look_for_keys=False)
            except paramiko.ssh_exception.AuthenticationException as auth_failure:
                print auth_failure
                c -= 1
            except:
                print 'Unexpected error'
                raise
            else:
                ssh.close()
                return True, pw
    else:
        print "Too many failed attempts"

bool, pw = get_pw()
if bool:
    print "continue"
    print pw
else:
    print "stop"

node = 'er10.bllab'

"""
stdin, stdout, stderr = ssh.exec_command("sh version")
type(stdin)

a = stdout.readlines()
for i in a:
    print i.strip('\n')
"""