
import sys

conf_file = 'pniMonitor.conf'

try:
    with open(conf_file) as pf:
        parameters = [tuple(i.split('=')) for i in filter(lambda line: line[0] != '#',
                                                          [n.strip('\n') for n in pf.readlines() if n != '\n'])]
except IOError as ioerr:
    print "%s could not be located." % conf_file
    sys.exit(0)
else:
    for opt, arg in parameters:
        if opt == 'inventory_file':
            inventory_file = arg

try:
    with open(inventory_file) as sf:
        inv = sf.read()
    with open(inventory_file, "w") as sf:
        sf.write(inv)
except IOError as ioerr:
    print "%s could not be located." % inventory_file
    sys.exit(0)
except NameError:
    print "inventory_file parameter is not defined in the %s" % conf_file