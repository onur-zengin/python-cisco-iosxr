#!/usr/bin/env python

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import subprocess
import sys
import select


def _tail():
    args = ['tail', '-F', 'pniMonitor.log']
    try:
        tup = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    except:
        pass
        #main_logger.warning("Unexpected error - Popen function _tail(): %s\t%s" % sys.exc_info()[:2])
    else:
        p = select.poll()
        p.register(tup.stdout)
        print p
        if tup[1] == '':
            pass
        elif "No such file or directory" in tup[1]:
            pass
            #send alert email
            #main_logger.info("")
        else:
            pass
            #send alert email
            #main_logger.warning("Unexpected output in the probe() function" % (str(ptup)))
    return p

print _tail()
"""
class _sendemail(object):
    sen = 'PNI Monitor <no-reply@automation.skycdp.com>'
    # rec = ['DL-ContentDeliveryPlatform@sky.uk']
    rec = ['onur.zengin@bskyb.com']

    def frmttr(self, format='txt'): #format: 'html' / 'txt'
        with open('pniMonitor.log') as logs:
            loglines = [line.strip('\n') for line in logs.readlines()]
        attachment = ''
        if format == 'html':
            attachment = 'attachment.html'
        elif format == 'txt':
            for i in loglines:
                attachment += i+'\n'
        return attachment

if __name__ == '__main__':
    email = _sendemail()
    print email.frmttr()
"""
"""
    def mssg(self): #"type:'mixed' / 'alternative' / 'related'"
        message = MIMEMultipart('mixed')
        message['From'] = self.sen
        message['To'] = ",".join(self.rec)
        message['Subject'] = 'PNI Monitor | %s | %s' % (severity, log_message)
        with open(self.frmttr('html'),"r") as f:
            p1 = MIMEText(f.read(),'html')
        #with open(self.frmttr('txt'),"r") as f:
            # #	p2 = MIMEText(f.read(),'plain')
        message.attach(p1)
        message.attach(p1)
        return message

    def send(self):
        message = self.mssg()
        try:
            smtpObj = smtplib.SMTP('localhost')
            smtpObj.sendmail(self.sen,self.rec,message.as_string())
            smtpObj.quit()
            print "Done."
        except:
            print "Failed."

if __name__ == '__main__':
    email = Sendemail()
    message = email.send()
"""