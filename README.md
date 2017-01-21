################################################ pniMonitor.py #########################################################

1. USAGE

    The program can be run with either a configuration file (pniMonitor.conf) that resides inside the same folder or
    command-line arguments specified using the following syntax.

    1.1. Mandatory Parameters

    [-i <filename>], [--input <filename>]

    The inventory details must be provided in a text file structured in the following format, while each node being
    written on a separate line:

    Invalid entries will not be ignored. However they will be retried in every polling cycle and then ignored due to
    DNS lookup failures.

    [-l <loglevel>], [--logging <loglevel>]

    The loglevel must be specified as one of INFO, WARNING, DEBUG in capital letters.
    If none specified, the program will run with default level INFO.

    1.2. Optional Parameters

    Optional parameters can not be specified in the command line.

    pni_interface_tag

    A user-defined label that will be searched inside the description strings of all bundle-ether interfaces of a router.
    default: [CDPautomation:PNI]
    cdn_interface_tag = [CDPautomation:CDN]

    ipv4_min_prefixes

    Minimum number of prefixes 'accepted' from a BGPv4 peer with unicast IPv4 AFI. Default value is '0', which means
    the PNI interface will be considered 'usable' until all accepted prefixes are withdrawn by the peer.

    ipv6_min_prefixes

    Minimum number of prefixes 'accepted' from a BGPv6 peer with unicast IPv6 AFI. Default value is '100', which is
    intentionally set high, in order to avoid a PNI interface running with a single IPv6 stack from being considered
    'usable'.

    cdn_serving_cap

    Maximum serving capacity of a CDN node relative to its wire rate. Default value is '90'.

    While working Akamai MCDN regions, this parameter must be configured to the lowest of the 'bit-cap' or 'flit-limit'.
    For instance; if the maximum expected throughput from a CDN region with 200Gbps physical capacity is 160Gbps due to
    its manually overridden bit-limit, even though the region could serve up to a higher throughput under normal
    conditions without being flit-limited, then the cdn_serving_cap must be set to '80'.



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
Compare int util. formula against RFC2819 (obsoletes RFC1757)
Check mem util. after long run
Periodic rotation for *.prb files

PLANNED FOR NEXT RELEASES

- Per-region cdn_serving_cap setting as opposed to Global.
- Persistence of the previously recorded interface utilization data upon a new node or interface discovery.
- In-flight change to certain runtime parameters
- Email updates when an interface is blocked / unblocked
- Replace SNMP with Netconf(?)


