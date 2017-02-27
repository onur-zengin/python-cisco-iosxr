__[pniMonitor.py](https://github.com/onur-zengin/laphroaig)__

__1. DESCRIPTION__
    
   A Python code that monitors the available egress bandwidth of selected PNI interfaces and status of the pertinent
    eBGP sessions on a Cisco IOS-XR router acting as an ASBR, and make selective decisions to block / unblock the 
    ingress traffic at its source if it is on a local interface (typically a CDN cache directly-connected to the router)


__2. DEPENDENCIES__

   __Python__
   
   The code contains certain modules / functions that are only available in Python 2.7 or later minor releases (< 3.x). 
    Any developer who wishes to run the code on an older Python release will have to override these functions and / or
    replace them with their functional equivalents as applicable.

   __OS__
   
   The code has been written and tested solely on a Debian Linux distribution (rel 7.4). And its portability to other
    (specifically non-Linux) operating systems may be limited.

   __NetSNMP__
   
   The code has been tested with NetSNMP rel 5.4.3.
    MIB translation __MUST__ be enabled in the `snmp.conf` file. This is due to the differences in output formatting of 
    NetSNMP with and without MIB translation enabled. The program does __NOT__ require the vendor MIB files to operate.


__3. CONFIGURATION__

   The program can optionally be run with a configuration file (`pniMonitor.conf`) that resides inside the same
    directory with the Python file. If the program is started without a configuration file or with any or all of the 
    configuration lines missing or commented out, it will then apply its default configuration settings for the missing 
    parameter(s) and continue running.  
    

  __3.1. STARTUP CONFIGURATION__
  
  The following parameters can be configured during startup only. Any modifications during runtime will be silently 
   ignored. 

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
    polling cycle and then ignored due to DNS lookup failures. _(This behaviour will be modified in the next releases, 
    where the name resolution check will be accompanied by system OS validation during startup.)_
   
   __pni_interface_tag=[`<string>`(_default_:`CDPautomation_PNI`)]__

   A user-defined label to identify the PNI interfaces that are intended for monitoring. The label will be searched 
    within the description strings of all Ethernet Bundle interfaces of a router, when the discovery function is run.
    
   Interfaces with a `no-mon` string applied will be excluded from monitoring. _(Including a new interface or 
   excluding an existing one from monitoring requires a manual discovery trigger in the current release.)_

   __cdn_interface_tag=[`<string>`(_default_:`CDPautomation_CDN`)]__

   A user-defined label to identify the PNI interfaces that are intended for monitoring. The label will be searched 
    within the description strings of all Ethernet Bundle and HundredGigabit Ethernet interfaces of a router, when the 
    discovery function is run. It is important __NOT__ to label the interfaces that are members of an Ethernet Bundle.
    
   Interfaces with a `no-mon` string applied will be excluded from monitoring. _(Including a new interface or 
   excluding an existing one from monitoring requires a manual discovery trigger in the current release.)_
    
   __acl_name=[`<string>`(_default_:`CDPautomation_UdpRhmBlock`)]__

   User-defined name of the IPv4 access-list as configured on the router(s). Missing ACL configuration on the router
    or misconfiguration of the acl_name in the pniMonitor.conf file will cause the SSH session(s) to be stalled, until 
    the protection mechanism in the MainThread kicks in terminates all threads, including itself. This will trigger a 
    `CRITICAL` alert. _(see Section-4 'Multi-Threading' for further details)_  
    

  __3.2. RUNTIME CONFIGURATION__

   The following parameters can be modified while the program is running, and any changes will be acted on accordingly
    in the next polling cycle. Invalid configurations will be ignored, accompanied with a `WARNING` alert, and the 
    program will revert back to either default (during startup) or last known good configuration.

   __Note:__ Commenting out a configuration line or removing it while the program is running will __NOT__ revert it 
   back to its default configuration. Once the program is running, preferred settings must be configured explicitly.
   
   __risk_factor=[`<0-100>`(_default_:`95`)]__
   
   Calculated as `actualPniOut / usablePniOut * 100`. See section-7 for further details.
    
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

   The list of email addresses to be notified when an event occurs. Email addresses that are outside the `@sky.uk` or 
   `@bskyb.com` domains will __NOT__ be accepted. Multiple entries must be separated by a comma (`,`).
   
   Emails alerts will be sent stateless and will not be retried or repeated.
   
   __email_alert_severity=[`<WARNING|ERROR|CRITICAL>`(_default_:`ERROR`)]__

   The minimum level of event severity to trigger an email alert.
   
   __runtime=[`<integer>`(_default_:`infinite`)]__

   An integer value, if configured, is used to calculate the number of polling cycles left before the program terminates
    itself. It could be useful in scenarios where it is desired to gracefully exit the program after a certain amount
    of time, such as C-Auth password expiry.

   __simulation_mode=[`<on|off>`(_default_:`off`)]__

   If switched on; node discovery, probing and decision-making functions will continue, however __NO__ configuration 
    changes will be made to the router(s).   



__4. MULTI-THREADING__

   The program will initiate a subThread for each node (router) specified in the inventory file, so that the interface
    status on multiple routers can be managed simultaneously and independently. 
   
   For convenience in operations and diagnostics, a subThread's name will be comprised of the hostname of the router 
    that it is relevant to. And the thread names will be included in every log line and alert produced by the program.
   
   If for any reason (such as a stalled SSH session) one or more of the subThreads take too long (i.e. longer than the 
    pre-defined running frequency of the mainThread) to complete, then the program will send out a dying gasp and 
    terminate itself along with all active subThreads. The dying gasp will be issued by the MainThread as a `CRITICAL` 
    severity alert including the name of all subThread(s) that were detected to be in _hung state_. This behaviour is 
    designed intentionally. Although this may incur unintended interruptions to monitoring, it would otherwise 
    constitute a greater risk to allow the program to continue while the reason of the delay / hang is unknown.  
    
    
__5. DISCOVERY__

   The program has a built-in discovery function which will be auto-triggered either during the first run or any time
    the inventory file is updated. Collected data is stored in a local file on disk; `.DO_NOT_MODIFY_<nodename>.dsc`.
    
   Addition or removal of an interface to / from the monitoring (once the interfaces are labeled correctly) can be 
    achieved by running the `pniDiscovery.py` script which can be found inside the same directory.
   
   __Note:__ The first release of the code do not have persistence enabled. Hence, at any time the discovery function is 
   triggered to run, which should not be too frequent, it will cause the previously collected data to be lost. This does
   not incur any risk other than delaying the process (decision making) functions by one (1) polling period.  
   

__6. PROBE (_Data Collection_)__

   The probe function collects data from each node statelessly and stores it in a local hidden file on disk; 
   `.DO_NOT_MODIFY_<nodename>.prb`, while tagging the data it collects with timestamps.   
   
   At the time of development, the original intent of the code was to make it operate over SNMP only, to keep it fast 
    and light-touch on the network equipment. However, since Cisco routers do not support the ACL-MIB; the probe 
    function had to evolve in a hybrid mode of operation where the ACL status on the interfaces is verified via an SSH 
    session, while Interface and BGP status are polled via SNMP.

   As it can be anticipated from the description above; interface ACL status is not saved on disk or stored in memory,
    but re-checked in every polling cycle. This is to prevent data inconsistencies in the case of manual intervention 
    to the router configuration via CLI.
   
   During data collection; if an SSH connection attempt fails for any reason, then SNMP read functions won't be 
    attempted either. This will result in the relevant `*.prb` file not being updated, which is the intentional 
    behaviour to prevent data inconsistencies between two polling cycles. Since the process function specifically relies
    on the timestamps of the previously collected data and is capable of measuring the timeDelta in its calculations,
    interface utilisation can still be reliably calculated regardless of any interruptions in polling.   


__7. PROCESS (_Decision Making_)__

   The entire decision making logic resides in a function called _process(). The main function constantly runs in 
    the background (as a daemon-like process) and use subThreads to re-assess the usable PNI egress capacity and 
    recalculate the actual `risk_factor` in the preferred polling frequency, using the data collected by probe.
    
For any PNI interface and its available physical egress capacity to be considered as 'usable', it must satisfy the 
    following requirements;
    
    - Interface operational status __MUST__ be `UP` (this will typically be a Ethernet Bundle interface, and in the 
      case of partial link failures, the total bandwidth of the remaining interfaces will be considered available)  
    
    __AND__  
    
    - State of the BGPv4 session sourced from the interface's local IPv4 address __MUST__ be `ESTABLISHED` __AND__ the 
      number of IPv4 prefixes received and __accepted__ from the remote BGP peer __MUST NOT__ be lower than the 
      configured `ipv4_min_prefixes`  
   
    __OR__
   
    - State of the BGPv6 session sourced from the interface's local IPv6 address __MUST__ be `ESTABLISHED` __AND__ the 
      number of IPv6 prefixes received and __accepted__ from the remote BGP peer __MUST NOT__ be lower than the 
      configured `ipv6_min_prefixes`  


Once the usable PNI egress capacity is calculated:
    
If at any time;

    - __There is no usable PNI egress capacity left on the local router:__
   
    __OR__
   
    - __There is a partial PNI failure scenario on the local router / traffic overflow from another site, which 
        causes the ratio of the actual PNI egress to usable PNI egress capacity to be equal or greater than the risk 
        factor:__
     
    __ALL DIRECTLY-ATTACHED CDN INTERFACES WILL BE BLOCKED.__
   
Else, if at any time;

    - __Usable PNI egress capacity is present on the local router 
    
    
    __AND__ 
    
    
    the ratio of the actual PNI egress to usable PNI 
        egress capacity is smaller than the risk factor:__
     
    __AND__

    - __The sum of the maximum serving capacity of the unblocked local CDN caches and the actual non-local traffic (P2P 
        + Overflow) egressing the local PNI and the maximum serving capacity of any directly-attached (but blocked) CDN 
        region is smaller than the usable PNI egress capacity on the local router:__

    __DIRECTLY-ATTACHED CDN INTERFACES WILL START BEING UNBLOCKED, ONE BY ONE, AS SOON AS THE AFOREMENTIONED RULE IS 
        SATISFIED.__

Otherwise;
   
    __NO ACTION WILL BE TAKEN.__  


__8. LOGGING__

  The program saves its logs in two separate local files saved on the disk and rotated daily;
   
   - __pniMonitor_main.log:__ All events produced by the MainThread and its subThreads. Configurable severity.
   - __pniMonitor_ssh.log:__ All events that are logged by the SSH module. Has a fixed severity setting; WARNING. 
   
In addition to local log files, high severity events are also available to be distributed as email alerts (_see
    Section-3 for configuration details_).
   
Definition of available log / alert severities are as follows:
    
    __DEBUG__     
    Detailed information, typically of interest only when diagnosing problems.  
   
    __INFO__      
    Confirmation that things are working as expected.  
   
    __WARNING__   
    An indication that something unexpected happened (such as a misconfiguration), or indicative of event (PNI failure, 
    BGP prefix withdrawal, etc) which will soon trigger automated recovery actions. The program is still working as 
    expected.  
       
    __ERROR__     
    Due to a more serious problem, the program has not been able to perform some function (such as a _Data Collection_ 
    or _Configuration Attempt_ failures). 
                  
    __CRITICAL__  
    A serious error, indicating that the program itself will be unable to continue running (_Dying gasp_).   



__TO BE COMPLETED BEFORE THE FIRST RELEASE__

- Test discovery of a new interface during runtime (pni & cdn)
- Test removal of an interface during runtime (pni & cdn)
- Test removal of a node during runtime
- Test int util. of an 100G interface
- Test the main() function and operation under simulation_mode
- Check mem util. after continuous run
- Revise critical logging for interface block / unblock failures. Include interface name(s) in the alerts. - Done. 
&& Output? - not tested.  


__9. PLANNED FOR FUTURE RELEASES__

- __P1__ Multi-ASN support
- __P1__ IPv6 ACL for RHM Blocking
- __P1__ Netcool integration (might outsource this)
- __P2__ Dying gasp (Catch SIGTERM KILL and report in logging)
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