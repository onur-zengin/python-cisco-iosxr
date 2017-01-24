#!/usr/bin/python

import paramiko
import getpass

un = getpass.getuser()
pw = getpass.getpass('Cauth Password:', stream=None)

print pw

"""
node = 'er10.bllab'


ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(node, un, pw)

stdin, stdout, stderr = ssh.exec_command("sh version")
type(stdin)

a = stdout.readlines()
print a
"""