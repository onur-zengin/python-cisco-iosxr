#!/usr/bin/env python

import logging
import logging.handlers
import sys
import re
import getopt

FORMAT = '%(asctime)-15s %(clientip)s %(user)-8s %(message)s'
logging.basicConfig(format=FORMAT)
d = {'clientip': '192.168.0.1', 'user': 'fbloggs'}
logger = logging.getLogger(__main__)
logger.warning('Protocol problem: %s', 'connection reset', extra=d)


format = logging.Formatter('%(asctime)-15s [%(levelname)s]: %(message)s')
eh = logging.handlers.SMTPHandler('localhost', 'no-reply@automation.skycdp.com', email_distro,
                                  'CRITICAL: PNI Monitor Liveness Check Failed')
eh.setFormatter(format)
eh.setLevel(logging.CRITICAL)
logger.addHandler(eh)

def main(args):
    email_distro = []
    try:
        options, remainder = getopt.getopt(args[1:], "c:", ["config="])
    except getopt.GetoptError as getopterr:
        print getopterr
        sys.exit(2)
    else:
        for opt, arg in options:
            if opt in ('-c', '--config'):
                config_file = arg
            else:
                print "Invalid option specified on the command line: %s" % opt
                sys.exit(2)
    try:
        with open(config_file) as pf:
            parameters = [tuple(i.split('=')) for i in
                          filter(lambda line: line[0] != '#', [n.strip('\n')
                                                               for n in pf.readlines() if n != '\n'])]
    except IOError as ioerr:
        print ioerr
        rg = re.search(r'(\'.+\')', str(ioerr))
        print "%r" % rg.group(1)[3:]
        #logging.CRITICAL("Liveness Check could not run. %r could not be located.", rg.group(1)[3:])
    else:
        try:
            for opt, arg in parameters:
                if opt == 'email_alert_severity':
                    if arg.lower() in ('warning', 'error', 'critical'):
                        if email_alert_severity != arg.upper():
                            logging.info('Email alert severity has been updated: %s' % arg.upper())
                        email_alert_severity = arg.upper()
                    else:
                        logging.warning('Invalid severity specified for email alerts. Resetting to last '
                                                'known good configuration: %s' % email_alert_severity)

                elif opt == 'email_distribution_list':
                    split_lst = arg.split(',')
                    try:
                        for email in split_lst:
                            match = re.search(r"[\w.-]+@(sky.uk|bskyb.com)", email)
                            match.group()
                    except AttributeError:
                        logging.warning('Invalid email address found in the distribution list. Resetting '
                                                'to last known good configuration: %s' % email_distro)
                    else:
                        if email_distro != split_lst:
                            logging.info('Email distribution list has been updated: %s' % split_lst)
                        email_distro = split_lst
                elif opt.lower() in ('pni_interface_tag', 'cdn_interface_tag', 'ssh_loglevel',
                                     'acl_name', 'persistence', 'inventory_file', 'ssh_timeout'):
                    pass
                else:
                   logging.warning("Invalid parameter found in the configuration file: (%s). The program "
                                            "will continue with the last known good configuration. Use '%s -m' or '%s "
                                            "--manual' to see detailed usage instructions." % (opt, args[0], args[0]))
        except ValueError:
            logging.warning("Invalid configuration line detected and ignored. All configuration parameters must "
                                "be provided as key value pairs separated by an equal sign (=). Use '%s -m' or '%s "
                                "--manual' for more details." % (args[0], args[0]))
    finally:
        #logging.debug("\tFrequency: %s\n\tRisk Factor: %s\n\tCDN Serving Cap: %s\n\tIPv4 Min Prefixes: %s"
         #                 "\n\tIPv6 Min Prefixes: %s\n\tLog Level: %s\n\tLog Retention: %s\n\tEmail Alert Sev: %s"
          #                "\n\tSimulation Mode: %s\n\tRuntime: %s\n\tEmail distribution list: %s"
           #               % (frequency, risk_factor, cdn_serving_cap, ipv4_min_prefixes, ipv6_min_prefixes,
            #                 log_retention, email_alert_severity, runtime, email_distro))


if __name__ == '__main__':
    main(sys.argv)