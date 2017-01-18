################################################ pniMonitor.py #########################################################

DESCRIPTION:

    [-i <filename>], [--input <filename>]

    The inventory details must be provided in a text file structured in the following format, while each node being
    written on a separate line:
          '\n\t\t\t<nodename>:pni,<intname-1>,...,<intname-M>:cdn,<intname-1>,...,<intname-N>' \
          '\n\t\t\tEXAMPLE: er12.thlon:pni,Bundle-Ether1024,Bundle-Ether1040:cdn,Bundle-Ether1064' \

    [-l <loglevel>], [--logging <loglevel>]

    The loglevel must be specified as one of INFO, WARNING, DEBUG in capital letters.
    If none specified, the program will run with default level INFO.

MULTI-THREADING

The program will initiate a subThread for each node (router) specified in the inventory file, so that the interface
status on multiple routers can be managed simultaneously and independently.
If for any reason a single subThread takes too long (i.e. longer than the pre-defined running frequency of the
mainThread) to complete, than the other threads will wait. Although this may incur unintended delays to the monitoring
of the other nodes, it would otherwise constitue a greater risk to allow the program to run while the reason of the
delay is unknown.

DISCOVERY

The program has a built-in discovery function which

TODO
Check mem util. after continuous loop
Periodic rotation for *.prb files
