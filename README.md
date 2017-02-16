################################################ pniMonitor.py #########################################################

1. DESCRIPTION

    A Python code that monitors the available egress bandwidth on the selected PNI interfaces and the pertinent eBGP
    sessions of a Cisco IOS-XR router acting as an ASBR, and make selective decisions to block / unblock the ingress
    traffic at its source (if the traffic source is directly-connected).


2. DEPENDENCIES

    Python
    There are certain modules / functions inside the code that are only available in Python 2.7 or later releases. Any
    developer who wishes to run the code on an older Python release will have to override these functions and replace
    them with functional equivalents as applicable.

    OS
    The code has been written and tested solely on a Debian Linux distribution (rel 7.4). And its portability to other
    (specifically non-Linux) operating systems may be limited.

    NetSNMP
    The code has been tested with NetSNMP rel 5.4.3.
    MIB translation must be enabled in the snmp.conf file (This is due to the output formatting of NetSNMP with and
    without MIB translation enabled. And does not mean vendor MIBs have to be loaded on the local machine).


3. CONFIGURATION

    The program can optionally be run with a configuration file (pniMonitor.conf) that resides inside the same folder.

    [inventory_file=<filename>]

    Default: inventory.txt

    The inventory details (list of node names) must be provided in a text file with each node written on a separate
    line. Example:

    ### inventory.txt ###
    er12.enslo
    er12.thlon
    #er13.thlon

    As shown above, # character can be used to create comment lines or comment out a selected node.

    The program does not perform - nor was seen necessary to do - regex checks to the provided node names. Hence,
    invalid entries in the inventory file will not be ignored straight away. However they will be retried in every
    polling cycle and then ignored due to DNS lookup failures. This behaviour will be modified in the next release,
    where the name resolution check will be accompanied by a system OS validation check and will be done only once
    during startup.

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

    [cdn_serving_cap]

    Maximum serving capacity of a CDN node relative to its wire rate. Default value is '90'.

    While working Akamai MCDN regions, this parameter must be configured to the lowest of the 'bit-cap' or 'flit-limit'.
    For instance; if the maximum expected throughput from a CDN region with 200Gbps physical capacity is 160Gbps due to
    its manually overridden bit-limit, even though the region could serve up to a higher throughput under normal
    conditions without being flit-limited, then the cdn_serving_cap must be set to '80'.

    [simulation_mode=<on|off>]

    Node discovery (SNMPWALK) and probing (SNMPGET) will continue, however all configuration changes (over SSH) will
    be frozen.


4. MULTI-THREADING

The program will initiate a subThread for each node (router) specified in the inventory file, so that the interface
status on multiple routers can be managed simultaneously and independently.
If for any reason a single subThread takes too long (i.e. longer than the pre-defined running frequency of the
mainThread) to complete, than the other threads will wait. Although this may incur unintended delays to the monitoring
of the other nodes, it would otherwise constitute a greater risk to allow the program to run while the reason of the
delay is unknown.

5. NODE DISCOVERY

The program has a built-in discovery function which will be auto-triggered either during the first run or any time
the inventory file is updated.

The first release of the code do not have persistence enabled. At any time the discovery function is triggered to run,
which should not be too frequent, it will cause the previously collected data to be lost.


6. OPERATION

The entire decision making logic resides in a function called _process(). The main program will constantly run in the
background (as a deamon-like process) and will recalculate the following parameters in a specific polling frequency
as pre-defined in the configuration file, and from each router found in the inventory file simultaneously;

    actualCdnIn:
    physicalCdnIn:
    maxCdnIn:
    actualPniOut:
    usablePniOut:

    4.1. SCENARIOS

    NO USABLE PNI CAPACITY LEFT

    THE RATIO OF ACTUAL PNI EGRESS TO USABLE PNI CAPACITY IS EQUAL OR GREATER THAN THE RISK FACTOR

    4.2. UNBLOCK

    4.3. NO ACTION


7. LOGGING

Level	    When it’s used
DEBUG	    Detailed information, typically of interest only when diagnosing problems.
INFO	    Confirmation that things are working as expected.
WARNING	    An indication that something unexpected happened, or indicative of some problem in the near future (e.g.
            ‘disk space low’). The software is still working as expected.
ERROR	    Due to a more serious problem, the software has not been able to perform some function.
CRITICAL	A serious error, indicating that the program itself may be unable to continue running.


TO BE COMPLETED BEFORE THE FIRST RELEASE

- Compare int util. formula against RFC2819 (obsoletes RFC1757)
- Verify interface speed in a partial bundle failure
- Check mem util. after long run
- Send ssh logs to file
- Revise the main() function (--dryrun doesn't work - test it again, inventory file and interface tags should be
    configurable at the start-time only)
- Gzip / bz rotated log files
- Provide a script to trigger interface discovery
- Test non Cisco / non IOSXR router in the inventory file
- Test discovery of a new interface during runtime (pni & cdn)
- Test removal of an interface during runtime (pni & cdn)
- Test removal of a node during runtime
- Test non-existent acl configuration on the router
- Revise critical logging for interface block / unblock failures. Include interface name(s) in the alert.
Send the CLI output to ?
- SSH failure alerts need to indicate where exactly it failed. Probing or Configuration. And what happens to int util
calculations when probing fails intermittently

PLANNED FOR FUTURE RELEASES

- Netcool integration (might outsource this)
- IPv6 ACL for RHM Blocking
- Multi-ASN support
- Per-region cdn_serving_cap setting (It is available as a Global parameter in the current release)
- Automated discovery of new interfaces (In the current release it is manually triggered)
- Persistence (of the previously recorded interface utilization data upon a new node or interface discovery)
- Graphical email updates with interface utilisation charts
- Ordered directory structure (/logs, /data, /conf, etc.)
- Dying gasp
- Nokia 7750 support
- IOS-XR / SROS version check
- Replace SNMP & SSH with something more reliable & convenient (eg. Netconf/RestAPI)


