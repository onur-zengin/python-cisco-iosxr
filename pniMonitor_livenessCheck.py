#!/usr/bin/env python

import sys
import logging
import logging.handlers
import getopt
import os
import os.path
import re

#Specifies a default distribution list, in case the configuration file can't be located.
#email_distro = ['cdnsupport@sky.uk', 'dl-contentdeliveryplatform@bskyb.com']
email_distro = ['onur.zengin@sky.uk']

logFormatter = logging.Formatter('%(asctime)-15s [%(levelname)s]: %(message)s')
rootLogger = logging.getLogger()

emailHandler = logging.handlers.SMTPHandler('localhost', 'no-reply@automation.skycdp.com', email_distro,
                                            'CRITICAL: PNI Monitor Liveness Check Failed')
emailHandler.setFormatter(logFormatter)
emailHandler.setLevel(logging.CRITICAL)
rootLogger.addHandler(emailHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
consoleHandler.setLevel(logging.INFO)
rootLogger.addHandler(consoleHandler)


def main(args):
    global email_distro
    global emailHandler
    try:
        options, remainder = getopt.getopt(args[1:], "c:", ["config="])
    except getopt.GetoptError as getopterr:
        rootLogger.error(getopterr)
        sys.exit(2)
    else:
        for opt, arg in options:
            if opt in ('-c', '--config'):
                config_file = arg
            else:
                rootLogger.error("Invalid option specified on the command line: %s" % opt)
                sys.exit(2)
    try:
        config_file = config_file
    except UnboundLocalError:
        rootLogger.error("A configuration file must be specified. Syntax; [-c <filename>] or [--config <filename>]")
        sys.exit(2)
    try:
        with open(config_file) as pf:
            parameters = [tuple(i.split('=')) for i in
                          filter(lambda line: line[0] != '#', [n.strip('\n')
                                                               for n in pf.readlines() if n != '\n'])]
    except IOError:
        rootLogger.critical("Liveness Check Failed. Configuration File %r could not be located.", config_file)
        sys.exit(2)
    else:
        try:
            for opt, arg in parameters:
                if opt == 'email_distribution_list':
                    split_lst = arg.split(',')
                    try:
                        for email in split_lst:
                            match = re.search(r"[\w.-]+@(sky.uk|bskyb.com)", email)
                            match.group()
                    except AttributeError:
                        rootLogger.warning('Invalid email address found in the distribution list. Resetting to default '
                                           'configuration: %s' % email_distro)
                    else:
                        if email_distro != split_lst:
                            rootLogger.info('Email distribution list has been updated: %s' % split_lst)
                        email_distro = split_lst
                else:
                    pass
        except ValueError:
            pass
    finally:
        try:
            rootLogger.removeHandler(emailHandler)
        except NameError:
            pass
        emailHandler = logging.handlers.SMTPHandler('localhost', 'no-reply@automation.skycdp.com', email_distro,
                                                    'CRITICAL: PNI Monitor Liveness Check Failed')
        emailHandler.setFormatter(logFormatter)
        emailHandler.setLevel(logging.CRITICAL)
        rootLogger.addHandler(emailHandler)
    pid_file = config_file.split(".")[0] + '.pid'
    try:
        with open(pid_file) as pf:
            pid = pf.read()
    except IOError:
        rootLogger.critical("Liveness Check Failed. %s could not be located.", pid_file)
        sys.exit(2)
    except:
        rootLogger.critical("Liveness Check Failed. Unexpected error: %r %r", sys.exc_info()[0], sys.exc_info()[1])
        sys.exit(2)
    else:
        if len(pid) == 0:
            rootLogger.critical("Liveness Check Failed. (No process id found)")
        elif not os.path.exists("/proc/" + pid):
            rootLogger.critical("Liveness Check Failed. (No process found with PID#%s)", pid)
        elif os.path.exists("/proc/" + pid):
            print "Li C passed."
            rootLogger.critical("Liveness Check passed. (PID#%s)", pid)
            rootLogger.warning("Liveness Check passed. (PID#%s)", pid)
            rootLogger.error("Liveness Check passed. (PID#%s)", pid)
            rootLogger.info("Liveness Check passed. (PID#%s)", pid)
            rootLogger.debug("Liveness Check passed. (PID#%s)", pid)


if __name__ == '__main__':
    main(sys.argv)