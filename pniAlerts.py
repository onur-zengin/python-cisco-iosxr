#!/usr/bin/env python

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import subprocess
import sys
import select
import logging
from logging import handlers

"""
if __name__ == '__main__':
    f = subprocess.Popen(['tail','-F','pniMonitor.log'], stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    p = select.poll()
    p.register(f.stdout)
    while True:
        if p.poll(1):
             print f.stdout.readline()
        time.sleep(1)

"""


main_logger = logging.getLogger(__name__)
main_formatter = logging.Formatter('%(asctime)-15s [%(levelname)s] %(threadName)-10s: %(message)s')
main_fh = logging.StreamHandler()
#main_fh = handlers.TimedRotatingFileHandler('pniMonitor.log', when='midnight', backupCount=30)

main_logger.setLevel(logging.CRITICAL)
main_logger.addHandler(main_fh)



if __name__ == '__main__':
    main_logger.info('This is info')
    main_logger.debug('This is debug')
    main_logger.warning('this is warning')
    main_logger.error('this is error')
    main_logger.critical('this is critical')

