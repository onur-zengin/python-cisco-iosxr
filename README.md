################################################ pniMonitor.py #########################################################

1. USAGE

    1.1. Mandatory Parameters

    [-i <filename>], [--input <filename>]

    The inventory details must be provided in a text file structured in the following format, while each node being
    written on a separate line:
          '\n\t\t\t<nodename>:pni,<intname-1>,...,<intname-M>:cdn,<intname-1>,...,<intname-N>' \
          '\n\t\t\tEXAMPLE: er12.thlon:pni,Bundle-Ether1024,Bundle-Ether1040:cdn,Bundle-Ether1064' \

    [-l <loglevel>], [--logging <loglevel>]

    The loglevel must be specified as one of INFO, WARNING, DEBUG in capital letters.
    If none specified, the program will run with default level INFO.

    1.2. Optional Parameters

    pni_interface_tag
    default: [CDPautomation:PNI]
    cdn_interface_tag = [CDPautomation:CDN]

    ipv4_min_prefixes

    Minimum number of prefixes 'accepted' from a BGPv4 peer with unicast IPv4 AFI. Default value is '0', which means
    the PNI interface will be considered 'usable' until all accepted prefixes are withdrawn by the peer.

    ipv6_min_prefixes

    Minimum number of prefixes 'accepted' from a BGPv6 peer with unicast IPv6 AFI. Default value is '100', which is
    intentionally set high, in order to avoid a PNI interface running with a single IPv6 stack from being considered
    'usable'.

2. MULTI-THREADING

The program will initiate a subThread for each node (router) specified in the inventory file, so that the interface
status on multiple routers can be managed simultaneously and independently.
If for any reason a single subThread takes too long (i.e. longer than the pre-defined running frequency of the
mainThread) to complete, than the other threads will wait. Although this may incur unintended delays to the monitoring
of the other nodes, it would otherwise constitue a greater risk to allow the program to run while the reason of the
delay is unknown.

3. DISCOVERY

The program has a built-in discovery function which

TODO
Check mem util. after continuous loop
Periodic rotation for *.prb files
