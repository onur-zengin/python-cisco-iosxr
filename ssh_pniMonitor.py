#!/usr/bin/python

import paramiko
import getpass
import os
import sys
import socket

hn = socket.gethostname()
hd = os.environ['HOME']
un = getpass.getuser()
try:
    pw = getpass.getpass('Enter cauth password for user %s:' % un, stream=None)
except getpass.GetPassWarning as pw_warning:
    print pw_warning
    raise

def pw_check():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(hn, username=un, password=pw)
    except paramiko.ssh_exception.PasswordRequiredException as pw_required:
        print pw_required
        sys.exit(1)
    except paramiko.ssh_exception.AuthenticationException as auth_failure:
        print auth_failure
        sys.exit(1)
    except:
        print 'unexpected error'
        raise
    else:
        ssh.close()
        return True


if pw_check() is True:
    print "continue"

node = 'er10.bllab'

"""
stdin, stdout, stderr = ssh.exec_command("sh version")
type(stdin)

a = stdout.readlines()
for i in a:
    print i.strip('\n')
"""