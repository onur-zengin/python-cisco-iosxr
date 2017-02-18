################################################ [pniMonitor.py] #######################################################

1. [DESCRIPTION]

   A Python code that monitors the available egress bandwidth on the selected PNI interfaces and the pertinent eBGP
    sessions of a Cisco IOS-XR router acting as an ASBR, and make selective decisions to block / unblock the ingress
    traffic at its source (if the traffic source is directly-connected).


2. [DEPENDENCIES]

   [Python]
   There are certain modules / functions inside the code that are only available in Python 2.7 or later releases. Any
    developer who wishes to run the code on an older Python release will have to override these functions and replace
    them with functional equivalents as applicable.

   [OS]
   The code has been written and tested solely on a Debian Linux distribution (rel 7.4). And its portability to other
    (specifically non-Linux) operating systems may be limited.

   [NetSNMP]
   The code has been tested with NetSNMP rel 5.4.3.
    MIB translation must be enabled in the snmp.conf file (This is due to the output formatting of NetSNMP with and
    without MIB translation enabled. And does not mean vendor MIBs have to be loaded on the local machine).


3. [CONFIGURATION]

   The program can optionally be run with a configuration file (pniMonitor.conf) that resides inside the same folder.
    If started with any or all of the configuration lines missing or commented out, the program will apply its default
    configuration settings to the missing parameter(s) and continue.

  [3.1 STARTUP CONFIGURATION]

   [inventory_file=<filename|inventory.txt(Default)>]

   The inventory details (list of node names) must be provided in a text file with each node written on a separate
    line. Example:
    
    ### [inventory.txt] ###
    er12.enslo
    er12.thlon
    #er13.thlon

   As shown above, the # character can be used to create comment lines or comment out a selected node.

   The program does not perform - nor was seen necessary to do - regex checks to the provided node names. Hence,
    invalid entries in the inventory file will not be ignored straight away. However they will be retried in every
    polling cycle and then ignored due to DNS lookup failures. This behaviour will be modified in the next release,
    where the name resolution check will be accompanied by a system OS validation check during startup.
    
    
   [pni_interface_tag=<random_string|CDPautomation_PNI(Default)>]

   A user-defined label that will be searched within the description strings of all Ethernet Bundle interfaces of a
    router, when the discovery function is run.

   [cdn_interface_tag=<random_string|CDPautomation_CDN(Default)>]

   A user-defined label that will be searched within the description strings of all Ethernet Bundle or HundredGigabit
    Ethernet interfaces of a router, when the discovery function is run. It is important NOT to label the interfaces
    that are members of an Ethernet Bundle.
    
   [acl_name=<random_string|CDPautomation_UdpRhmBlock(Default)>]

   User-defined name of the IPv4 access-list as configured on the router(s).

  [3.2 RUNTIME CONFIGURATION]

   The following parameters can be modified while the program is running, and any changes will be acted on accordingly
    in the next polling cycle. Invalid configurations will be ignored, accompanied with a WARNING alert, and the program
    will revert back to either default (during startup) or last known good configuration.

   If started with any or all of the configuration lines missing or commented out, the program will continue with its
    default configuration settings. However, commenting out a configuration line or removing it while the program is
    running will NOT revert it back to its default configuration.

   [log_level=<INFO(Default)|WARNING|ERROR|CRITICAL|DEBUG>]

   The log_level can be specified as one of INFO, WARNING, DEBUG in capital letters.
    If none specified, the program will run with default level INFO.

   Log files saved on disk will be rotated and compressed with Gzip daily at midnight local time.

   [log_retention=<0-90|7(Default)>]

   The number of days the rotated log files should be kept on disk.

   [ipv4_min_prefixes=0(Default)]

   Minimum number of prefixes 'accepted' from a BGPv4 peer with unicast IPv4 AFI. Default value is '0', which means
    the PNI interface will be considered 'usable' until ALL accepted prefixes are withdrawn by the peer.

   [ipv6_min_prefixes=100(Default)]

   Minimum number of prefixes 'accepted' from a BGPv6 peer with unicast IPv6 AFI. Default value is '100', which is
    intentionally set high, in order to avoid a PNI interface running with a single IPv6 stack from being considered
    usable.

   [cdn_serving_cap]

   Maximum serving capacity of a CDN node relative to its wire rate. Default value is '90'.

   While working with Akamai MCDN regions, this parameter must be configured to the lowest of the 'bit-cap' or 'flit-
    limit' values. For instance; if the maximum expected throughput from a CDN region with 200 Gbps physical capacity
    is 160 Gbps due to its manually overridden bit-limit, then the cdn_serving_cap must be set to '80'. When the bit-
    limit is removed, it should be reset to a value (typically >90) that is indicative of the highest achievable
    throughput without the region being flit-limited.

   [runtime=<infinite(Default)|random_integer>]

   An integer value, if configured, is used to calculate the number polling cycles left before the program terminates
    itself. It could be useful in scenarios where it is desired to gracefully exit the program after a certain amount
    of time, such as C-Auth password expiry.

   [simulation_mode=<on|off(Default)>]

   If switched on, node discovery and probing will continue, however no configuration changes will be made to the
    router(s).


4. [MULTI-THREADING]

   The program will initiate a subThread for each node (router) specified in the inventory file, so that the interface
    status on multiple routers can be managed simultaneously and independently.
   
   If for any reason a single subThread takes too long (i.e. longer than the pre-defined running frequency of the
    mainThread) to complete, than the other threads will wait. Although this may incur unintended delays to the 
    monitoring of the other nodes, it would otherwise constitute a greater risk to allow the program to run while the 
    reason of the delay is unknown.

5. [NODE DISCOVERY]

   The program has a built-in discovery function which will be auto-triggered either during the first run or any time
    the inventory file is updated.

   The first release of the code do not have persistence enabled. At any time the discovery function is triggered to 
    run, which should not be too frequent, it will cause the previously collected data to be lost.

6. [PROBING]



7. [OPERATION]

The entire decision making logic resides in a function called _process(). The main program will constantly run in the
background (as a daemon-like process) and will recalculate the following parameters in a specific polling frequency
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


8. [LOGGING]

Level	    When it’s used
DEBUG	    Detailed information, typically of interest only when diagnosing problems.
INFO	    Confirmation that things are working as expected.
WARNING	    An indication that something unexpected happened, or indicative of some problem in the near future (e.g.
            ‘disk space low’). The software is still working as expected.
ERROR	    Due to a more serious problem, the software has not been able to perform some function.
CRITICAL	A serious error, indicating that the program itself may be unable to continue running.


TO BE COMPLETED BEFORE THE FIRST RELEASE

- Test non Cisco / non IOSXR router in the inventory file
- Test discovery of a new interface during runtime (pni & cdn)
- Test removal of an interface during runtime (pni & cdn)
- Test removal of a node during runtime
- Test non-existent acl configuration on the router
- Test int util. of a 100G interface

- Compare int util. formula against RFC2819 (obsoletes RFC1757)
- Check mem util. after long run

- Revise the main() function (--dryrun doesn't work - test it again)
- Revise critical logging for interface block / unblock failures. Include interface name(s) in the alert. Done - not tested.
- SSH failure alerts need to indicate where exactly it failed. Probing or Configuration. Done - not tested.
- Test sys.exc_info()[:2] logging with 3 parameters
- And what happens to int util calculations when probing fails intermittently - prb file doesn't get updated. Relying on the timeDelta function.

9. [PLANNED FOR FUTURE RELEASES]

- Netcool integration (might outsource this)
- IPv6 ACL for RHM Blocking
- Multi-ASN support
- Per-region cdn_serving_cap setting (It is available as a Global parameter in the current release)
- Automated discovery of new interfaces (In the current release it is manually triggered)
- Persistence (of the previously recorded interface utilization data upon a new node or interface discovery)
- Graphical email updates with interface utilisation charts
- Ordered directory structure (/logs, /data, /conf, etc.)
- Nokia 7750 support
- IOS-XR / SROS version check
- Dying gasp
- Catch SIGTERM KILL and report in logging
- Replace SNMP & SSH with something more reliable & convenient (eg. Netconf/RestAPI)


