__[pniMonitor.py](https://github.com/onur-zengin/laphroaig)__

#__1. DESCRIPTION__
    
   A Python code that monitors the available egress bandwidth of selected PNI interfaces and status of the pertinent
    eBGP sessions on a Cisco IOS-XR router acting as an ASBR, and make selective decisions to block / unblock the 
    ingress traffic at its source if it is on a local interface (typically a CDN cache directly-connected to the router)


#__2. DEPENDENCIES__

   __Python__
   
   There are certain modules / functions inside the code that are only available in Python 2.7 or later releases. Any
    developer who wishes to run the code on an older Python release will have to override these functions and replace
    them with functional equivalents as applicable.

   __OS__
   
   The code has been written and tested solely on a Debian Linux distribution (rel 7.4). And its portability to other
    (specifically non-Linux) operating systems may be limited.

   __NetSNMP__
   
   The code has been tested with NetSNMP rel 5.4.3.
    MIB translation must be enabled in the snmp.conf file (This is due to the output formatting of NetSNMP with and
    without MIB translation enabled. And does not mean vendor MIBs have to be loaded on the local machine).


#__3. CONFIGURATION__

   The program can optionally be run with a configuration file (`pniMonitor.conf`) that resides inside the same folder.
    If started without a configuration file or with any or all of the configuration lines missing or commented out, the 
    program will apply its default configuration settings to the missing parameter(s) and continue.

  __3.1. STARTUP CONFIGURATION__

  __inventory_file=[`<filename>`(_default_:`inventory.txt`)]__

   The inventory details (list of node names) __must__ be provided in a text file with each node written on a separate
    line. Example:
    
    ###inventory.txt
    er12.enslo
    er12.thlon
    #er13.thlon

   As shown above, the pound sign (`#`) can be used to create comment lines or comment out a selected node.

   The program does not perform - nor was seen necessary to do - regex checks to the provided node names. Hence,
    invalid entries in the inventory file will not be ignored straight away, however they will be retried in every
    polling cycle and then ignored due to DNS lookup failures. _(This behaviour will be modified in the next release, 
    where the name resolution check will be accompanied by system OS validation during startup.)_
    
   __pni_interface_tag=[`<string>`(_default_:`CDPautomation_PNI`)]__

   A user-defined label to identify the PNI interfaces that are intended for monitoring. The label will be searched 
    within the description strings of all Ethernet Bundle interfaces of a router, when the discovery function is run.
    
   A `no-mon` string can be used to exclude an interface from monitoring. _(This requires a manual discovery trigger
   in the current release.)_

   __cdn_interface_tag=[`<string>`(_default_:`CDPautomation_CDN`)]__

   A user-defined label to identify the PNI interfaces that are intended for monitoring. The label will be searched 
    within the description strings of all Ethernet Bundle or HundredGigabit Ethernet interfaces of a router, when the 
    discovery function is run. It is important __NOT__ to label the interfaces that are members of an Ethernet Bundle.
    
   A `no-mon` string can be used to exclude an interface from monitoring. (_This requires a manual discovery trigger
   in the current release._)
    
   __acl_name=[`<string>`(_default_:`CDPautomation_UdpRhmBlock`)]__

   User-defined name of the IPv4 access-list as configured on the router(s). Missing ACL configuration on the router
    will trigger a `CRITICAL` alert indicating 'interface blocking attempt failure'. A user receiving this alert may ...

  __3.2. RUNTIME CONFIGURATION__

   The following parameters can be modified while the program is running, and any changes will be acted on accordingly
    in the next polling cycle. Invalid configurations will be ignored, accompanied with a `WARNING` alert, and the 
    program will revert back to either default (during startup) or last known good configuration.

   If started with any or all of the configuration lines missing or commented out, the program will continue with its
    default configuration settings. However, commenting out a configuration line or removing it while the program is
    running will NOT revert it back to its default configuration.
   
   __risk_factor=[`<0-100>`(_default_:`95`)]__
   
   `actualPniOut / usablePniOut * 100`
    
   __ipv4_min_prefixes=[`<integer>`(_default_:`0`)]__

   Minimum number of prefixes 'accepted' from a BGPv4 peer with unicast IPv4 AFI. Default value is '0', which means
    the PNI interface will be considered 'usable' until ALL accepted prefixes are withdrawn by the peer.

   __ipv6_min_prefixes=[`<integer>`(_default_:`100`)]__

   Minimum number of prefixes 'accepted' from a BGPv6 peer with unicast IPv6 AFI. Default value is '100', which is
    intentionally set high, in order to avoid a PNI interface running with a single IPv6 stack from being considered
    usable.

   __cdn_serving_cap=[`<0-100>`(_default_:`90`)]__

   Maximum serving capacity of a CDN node relative to its wire rate. Default value is '90'.

   While working with Akamai MCDN regions, this parameter must be configured to the lowest of the _bit-cap_ or _flit-
    limit_ values. For instance; if the maximum expected throughput from a CDN region with 200 Gbps physical capacity
    is 160 Gbps due to its manually overridden bit-limit, then the cdn_serving_cap must be set to '80'. When the bit-
    limit is removed, it should be reset to a value (typically >90) that is indicative of the highest achievable
    throughput without the region being flit-limited.

   __log_level=[`<INFO|WARNING|ERROR|CRITICAL|DEBUG>`(_default_:`INFO`)]__

   The log_level can be specified as one of `INFO`, `WARNING`, `ERROR`, `CRITICAL` or `DEBUG`. If none specified, the 
    program will run with default level INFO.

   Log files saved on disk will be rotated and compressed with Gzip daily at midnight local time.

   __log_retention=[`<0-90>`(_default_:`7`)]__

   The number of days for the rotated log files to be kept on disk.

   __email_distribution_list=[`name.surname@sky.uk,group_name@bskyb.com`(_default_:`None`)]__

   The list of email addresses to be notified when an event occurs. Email addresses that are outside the @sky.uk or 
   @bskyb.com domains will NOT be accepted. Multiple entries must be separated by a comma (`,`).
   
   Emails alerts will be sent stateless and will not be retried or repeated.
   
   __email_alert_severity=[`<WARNING|ERROR|CRITICAL>`(_default_:`ERROR`)]__

   The minimum level of event severity to trigger an email alert.
   
   __runtime=[`<integer>`(_default_:`infinite`)]__

   An integer value, if configured, is used to calculate the number of polling cycles left before the program terminates
    itself. It could be useful in scenarios where it is desired to gracefully exit the program after a certain amount
    of time, such as C-Auth password expiry.

   __simulation_mode=[`<on|off>`(_default_:`off`)]__

   If switched on, node discovery and probing will continue, however no configuration changes will be made to the
    router(s).


__4. MULTI-THREADING__

   The program will initiate a subThread for each node (router) specified in the inventory file, so that the interface
    status on multiple routers can be managed simultaneously and independently.
   
   If for any reason a single subThread takes too long (i.e. longer than the pre-defined running frequency of the
    mainThread) to complete, than the other threads will wait. Although this may incur unintended delays to the 
    monitoring of the other nodes, it would otherwise constitute a greater risk to allow the program to run while the 
    reason of the delay / hang is unknown.


__5. NODE DISCOVERY__

   The program has a built-in discovery function which will be auto-triggered either during the first run or any time
    the inventory file is updated.
    
   Addition or removal of an interface to / from the monitoring (once the interfaces are labeled correctly) can be 
    achieved by running the `pniDiscovery.py` script which can be found inside the same directory.
   
   __Note:__ The first release of the code do not have persistence enabled. At any time the discovery function is 
   triggered to run, which should not be too frequent, it will cause the previously collected data to be lost.
   

__6. PROBE__

If an SSH connection attempt fails, SNMP won't be tried either. 

__7. OPERATION__

The entire decision making logic resides in a function called _process(). The main function will constantly run in the
background (as a daemon-like process) and use subThreads to recalculate the following parameters in the preferred 
polling frequency, simultaneously for every router as found in the inventory file;

   __physicalCdnIn:__   text  
   __actualCdnIn:__     text  
   __maxCdnIn:__ 
   __unblockedMaxCdnIn:__  
   __physicalPniOut:__  
   __actualPniOut:__  
   __usablePniOut:__  

  __7.1. SCENARIOS__

   NO USABLE PNI CAPACITY LEFT

   THE RATIO OF ACTUAL PNI EGRESS TO USABLE PNI CAPACITY IS EQUAL OR GREATER THAN THE RISK FACTOR

   __7.2. UNBLOCK__

   __7.3. NO ACTION__


__8. LOGGING__

Level	    When it’s used  
__DEBUG__	    Detailed information, typically of interest only when diagnosing problems.  
__INFO__	    Confirmation that things are working as expected.  
__WARNING__	    An indication that something unexpected happened, or indicative of some problem in the near future (e.g.
            ‘disk space low’). The program is still working as expected.  
__ERROR__	    Due to a more serious problem, the software has not been able to perform some function.  
__CRITICAL__	A serious error, indicating that the program itself may be unable to continue running.  


__TO BE COMPLETED BEFORE THE FIRST RELEASE__

- Test non Cisco / non IOSXR router in the inventory file
- Test discovery of a new interface during runtime (pni & cdn)
- Test removal of an interface during runtime (pni & cdn)
- Test removal of a node during runtime
- Test non-existent acl configuration on the router
- Test int util. of a 100G interface
- Test the main() function and operation under simulation_mode

- Compare int util. formula against RFC2819 (obsoletes RFC1757)
- Check mem util. after long run

- Revise critical logging for interface block / unblock failures. Include interface name(s) in the alert. - Done. && Output? - not tested.
- And what happens to int util calculations when probing fails intermittently - prb file doesn't get updated. Relying on the timeDelta function.

__9. PLANNED FOR FUTURE RELEASES__

- __P1__ Multi-ASN support
- __P1__ IPv6 ACL for RHM Blocking
- __P1__ Netcool integration (might outsource this)
- __P1__ Dying gasp
- __P1__ Catch SIGTERM KILL and report in logging
- __P2__ Persistence (of the previously recorded interface utilization data upon a new node or interface discovery)
- __P2__ Automated discovery of new interfaces (In the current release it is manually triggered)
- __P3__ Per-region cdn_serving_cap setting (It is available as a Global parameter in the current release)
- __P3__ Nokia 7750 support
- __P3__ IOS-XR / SROS version check
- __P4__ Activate node reachability checks for improved logging
- __P4__ Graphical email updates with interface utilisation charts
- __P4__ Ordered directory structure (/logs, /data, /conf, etc.)
- __P4__ Replace SNMP & SSH with more reliable & convenient alternatives (eg. Netconf/RestAPI)

[pniMonitor.py](https://github.com/onur-zengin/laphroaig)
