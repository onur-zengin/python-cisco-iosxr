#!/usr/bin/python

import paramiko

node = 'er10.bllab'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(node, username='onur.zengin', password='Qtbhm55t!')

stdin, stdout, stderr = ssh.exec_command("sh version")
type(stdin)

a = stdout.readlines()
print a