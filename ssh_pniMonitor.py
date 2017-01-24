#!/usr/bin/python

import paramiko
import getpass
import os

hd = os.environ['HOME']
un = getpass.getuser()
try:
    pw = getpass.getpass('Enter the cauth password for user %s:' % un, stream=None)
except getpass.GetPassWarning as pw_warning:
    print pw_warning
    raise

print hd
print pw

node = 'er10.bllab'


ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(node, un, pw)

stdin, stdout, stderr = ssh.exec_command("sh version")
type(stdin)

a = stdout.readlines()
print a
