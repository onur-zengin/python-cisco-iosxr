#!/usr/bin/env python

import sys
import getopt
import logging

logFormatter = logging.Formatter('%(asctime)-15s [%(levelname)s]: %(message)s')
rootLogger = logging.getLogger()

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
#consoleHandler.setLevel(logging.INFO)
rootLogger.addHandler(consoleHandler)
rootLogger.setLevel(logging.INFO)

def main(args):
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
        rootLogger.error("Configuration file %r could not be located.", config_file)
        sys.exit(2)
    else:
        try:
            for opt, arg in parameters:
                if opt == 'inventory_file':
                    inventory_file = arg
                else:
                    pass
        except ValueError:
            pass
        finally:
            try:
                with open(inventory_file) as sf:
                    inv = sf.read()
                with open(inventory_file, "w") as sf:
                    sf.write(inv)
            except IOError:
                rootLogger.error("%s could not be located." % inventory_file)
                sys.exit(2)
            except NameError:
                rootLogger.error("inventory_file is not defined in the %s" % config_file)
                sys.exit(2)
            else:
                rootLogger.info("Inventory Updated. Changes should take effect in the next polling cycle")


if __name__ == '__main__':
    main(sys.argv)