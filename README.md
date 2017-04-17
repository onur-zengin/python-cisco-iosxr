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
    
   __Note__: Although the main program can operate without a configuration file, the utility scripts `pniDiscovery.py` 
    and `pniMonitory_livenessCheck.py` do require it.
    

  __3.1. STARTUP CONFIGURATION__
  
  The following parameters can be configured during startup only. Any modifications during runtime will be silently 
   ignored. 

   __inventory_file=[`<filename>`(_default_:`inventory.txt`)]__

   The inventory details (list of node names) __MUST__ be provided in a text file with each node written on a separate
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
    `CRITICAL` alert. _(see Section-5 'Multi-Threading' for further details)_  
    

  __3.2. RUNTIME CONFIGURATION__

   The following parameters can be modified while the program is running, and any changes will be acted on accordingly
    in the next polling cycle. Invalid configurations will be ignored, accompanied with a `WARNING` alert, and the 
    program will revert back to either default (during startup) or last known good configuration.

   __Note:__ Commenting out a configuration line or removing it while the program is running will __NOT__ revert it 
   back to its default configuration. Once the program is running, preferred settings must be configured explicitly.
   
   __frequency=[`<30-300>`(_default_:`30`)]__
   
   The running frequency of the mainThread, configured in seconds, defining how frequently the subThreads should be 
    re-initialized when the system time is __within__ the _peak hours_. Also referred to as the _polling cycle_ in the 
    other sections of this document.
   
   __off_peak_frequency=[`<30-300>`(_default_:`180`)]__
   
   The running frequency of the mainThread, configured in seconds, defining how frequently the subThreads should be 
    re-initialized when the system time is __outside__ the _peak hours_. Also referred to as the _polling cycle_ in the 
    other sections of this document.
   
   __peak_hours=[`<start_time(hh:mm)-end_time(hh:mm)>`(_default_:`17:30-23:59`)]__
   
   The _peak hours_ during the day where the PNI links are expected more likely to be congested due to higher than 
    normal utilization caused by the increased subscriber demand on the CDN caches.
   
   __risk_factor=[`<0-100>`(_default_:`95`)]__
   
   Calculated as `actualPniOut / usablePniOut * 100`. See section-8 'Process (Decision Making)' for further details.
    
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

   __email_distribution_list=[`name.surname@sky.uk,group_name@bskyb.com`(_default_:`cdnsupport@sky.uk`)]__

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

   __data_retention=[`<2-60>`(_default_:`2`)]__

   The number of polling cycles for the collected probe data to be kept on disk. Setting this value too high might
    cause increased memory utilisation, which might lead to program terminations (by the self-protection mechanism) 
    on a relatively busy or under-spec'd server.


__4. USAGE__

  __4.1. HOW TO RUN__
  
  - Verify the configuration and inventory files.
  - Verify the environment settings:
    - Python version must be 2.7.x; `python -V`
    - If the correct version not found, add the following line to the `.bash_profile` file in user `$HOME` directory;
        - `source ~nadt/nadt-aliases.include.bash`
        - Re-verify the Python version; `vrun python -V`
  - Browse to the script directory; `cd /scripts/laphroaig/`
  - Run the script:
    - If using the native Python installation on the system; `./pniMonitor.py`  
    OR
    - If using the virtualized NADT environment as described above; `vrun ./pniMonitor.py`
  - Wait for the prompt and enter C-Auth password
  - Once the `Authentication Successful` message is displayed:
    - Pause the script; `ctrl^z`
    - Send it to background; `bg`
    - And finally de-attach it from your terminal session; `disown -h %1`

  __4.2. HOW TO TERMINATE__

  __Graceful:__
  
  Set the `runtime` parameter in the `pniMonitor.conf` file to `1`. The program will gracefully terminate itself once 
   the next threading cycle is completed.
   
  __Forced:__
  
  Browse to the working directory and run the following command:
   `kill -9 "$(<pniMonitor.pid)"`
   This will terminate the mainThread and all subThreads immediately.
  

__5. MULTI-THREADING__

   The program will initiate a subThread for each node (router) specified in the inventory file, so that the interface
    status on multiple routers can be managed simultaneously and independently. 
   
   For convenience in operations and diagnostics, a subThread's name will be comprised of the hostname of the router 
    that it is relevant to. And the thread names will be included in every log line and alert produced by the program.
   
   If for any reason (such as a stalled SSH session or high CPU / Memory utilisation on the host system) one or more 
    of the subThreads take too long (i.e. longer than the pre-defined running frequency of the mainThread) to complete, 
    then the program will no longer terminate (_new in release 1.4_), but hibernate itself along with all inactive 
    subThreads that are waiting in the queue. The hibernation will be preceded by a `WARNING` severity alert, issued by 
    the MainThread, including the name of all subThread(s) that were detected to be in _hung state_. This behaviour is 
    designed intentionally. Although this may incur unintended delays to monitoring, it would otherwise constitute a 
    greater risk to allow the program to continue while the reason of the hang is unknown.  
    
    
__6. DISCOVERY__

   The program has a built-in discovery function which will be auto-triggered either during the first run or any time
    the inventory file is updated. Collected data is stored in local files on disk; `.DO_NOT_MODIFY_<nodename>.dsc`.
    
   Discovery function uses the description tags configured on the router interfaces in order to build an inventory of 
    all interfaces to be included in the decision-making process, as well as their IP addresses and the relevant BGP 
    neighbors. For any BGP neighbor to be associated with a PNI, the session __MUST__ be sourced from the IP address 
    (IPv4 or IPv6) of the local interface.
    
   Addition or removal of an interface to / from the monitoring (once the interfaces are labeled correctly) can be 
    achieved by using the `pniDiscovery.py` script which can be found inside the same directory. The correct syntax 
    to run the script is as follows;
    
    `pniDiscovery [-c <filename>] [--config <filename>]`
    `pniDiscovery -c pniMonitor.conf`
   
   __Note:__ The first release of the code do not have persistence enabled. Hence, at any time the discovery function is 
   triggered to run, which should not be too frequent, it will cause the previously collected data to be lost. This does
   not incur any risk other than delaying the process (decision making) functions by one (1) polling period.  
   
   At the time of development, the original intent of the code was to make it operate over SNMP only, to keep it fast 
    and light-touch on the network equipment. However, since Cisco IOS-XR routers do not support the ACL-MIB; the 
    discovery function had to evolve in a hybrid mode of operation where the ACL status on the interfaces is verified 
    via an SSH session, while the rest of the inventory details are polled via SNMP.
    
   Once discovery is completed; ACL configuration status per-interface is saved on disk, and not re-checked in every 
    polling cycle. This behaviour is added in v1.1.0 to prevent overloading the management-plane on the routers with too
    many SSH connections. In the same release the script is also updated to keep the discovery file updated with any 
    ACL configuration change it performs on the router interface(s) and alert in the case of failure to update, 
    in order to prevent data inconsistencies.
   

__7. PROBE (_Data Collection_)__

   The probe function collects the administrative and operational interface status, in and out octets per interface, 
    state of the BGP sessions and the number of received and accepted routes per-neighbor from each node simultaneously
    and stores the data in local hidden files on disk; `.DO_NOT_MODIFY_<nodename>.prb`, while also tagging the data it
    collects with timestamps.   
   
   Since the process function (_see Section-8_) specifically relies on the timestamps of the previously collected data 
    and is capable of measuring the timeDelta in its operation, interface utilisation can always be reliably calculated 
    regardless of any interruptions in polling.   


__8. PROCESS (_Decision Making_)__

   The entire decision making logic resides in a function called _process(). The main function constantly runs in 
    the background (as a daemon-like process) and use subThreads to re-assess the usable PNI egress capacity and 
    recalculate the actual `risk_factor` in the preferred polling frequency, using the data collected by probe.
    
   For any PNI interface and its available physical egress capacity to be considered 'usable', it must satisfy the 
    following requirements;
    
    - Interface operational status MUST be `UP` (this will typically be a Ethernet Bundle interface, and in the 
      case of partial link failures, the total bandwidth of the remaining interfaces will be considered available)  
    
    AND  
    
    - State of the BGPv4 session sourced from the interface's local IPv4 address MUST be `ESTABLISHED` AND the 
      number of IPv4 prefixes received and `accepted` from the remote BGP peer MUST NOT be lower than the 
      configured `ipv4_min_prefixes`  
   
    OR
   
    - State of the BGPv6 session sourced from the interface's local IPv6 address MUST be `ESTABLISHED` AND the 
      number of IPv6 prefixes received and `accepted` from the remote BGP peer MUST NOT be lower than the 
      configured `ipv6_min_prefixes`  


Once the usable PNI egress capacity is calculated:
    
If at any time;

    - There is NO usable PNI egress capacity left on the local router:
   
    OR
   
    - There is a partial PNI failure scenario on the local router / traffic overflow from another site, which 
      causes the ratio of the actual PNI egress to usable PNI egress capacity to be equal or greater than the risk 
      factor:
     
    ALL DIRECTLY-ATTACHED CDN INTERFACES WILL BE BLOCKED
   
Else, if at any time;

    - Usable PNI egress capacity is present on the local router
    
    
    AND

    - There is usable PNI egress capacity is present on the local router,
    
    AND
    

    - The ratio of the actual PNI egress to usable PNI egress capacity is smaller than the risk factor,
     
    AND

    - The sum of the maximum serving capacity of the unblocked local CDN caches and the actual non-local traffic (P2P 
      + Overflow) egressing the local PNI and the maximum serving capacity of any directly-attached (but blocked) CDN 
      region is smaller than the usable PNI egress capacity on the local router:

    DIRECTLY-ATTACHED CDN INTERFACES WILL START BEING UNBLOCKED, ONE BY ONE, AS SOON AS THE AFOREMENTIONED RULE IS 
     SATISFIED

Otherwise;
   
    NO ACTION WILL BE TAKEN


__9. LOGGING__

  The program saves its logs in two separate local files saved on the disk and rotated daily;
   
   - __pniMonitor_main.log:__ All events produced by the MainThread and its subThreads. Configurable severity.
   - __pniMonitor_ssh.log:__ All events that are logged by the SSH module. Has a fixed severity setting; WARNING. 
   - __pniMonitor_cron.log:__ Generated and used by the livenessCheck script running on the crontab (_see Section-10_)
   
In addition to local log files, high severity events are also available to be distributed as email alerts (_see
    Section-3 for configuration details_).
   
Definition of available log / alert severities are as follows:
    
    DEBUG    
    Detailed information, typically of interest only when diagnosing problems.  
   
    INFO      
    Confirmation that things are working as expected.  
   
    WARNING   
    An indication that something unexpected happened (such as a misconfiguration), or indicative of event (PNI failure, 
    BGP prefix withdrawal, etc) which will soon trigger automated recovery actions. The program is still working as 
    expected.  
       
    ERROR     
    Due to a more serious problem, the program has not been able to perform some function (such as a `Data Collection` 
    or `Configuration Attempt` failures). 
                  
    CRITICAL  
    A serious error, indicating that the program itself will be unable to continue running (`Dying gasp`).   


__10. LIVENESS CHECKS__

  The distribution includes an audit script `pniMonitor_livenessCheck.py` which can be added into the operating 
  system's crontab configuration to verify the liveness of the main program at regular intervals. It reads the PID of 
  the main process from the `pniMonitor.pid` file, which is created by the main process during startup, and verifies 
  the existence of a matching entry in the operating system's `/proc/` folder.
  
  Any of the following conditions will cause the liveness check to _fail_ and send out an email alert with `CRITICAL` 
  severity to the email distribution list found in the `pniMonitor.conf` file;

    - A process with the given PID is not running,
    - A process ID could not be found in the pniMonitor.pid file,
    - The pniMonitor.pid file could not be located,
    - The pniMonitor.conf file could not be located. (This results in the email alerts being sent to a default 
    distribution list)
   
  Non-critical events (`INFO`, `WARNING` or `ERROR`) will be sent to console or a cronlog file (if one configured).  
  
  Sample crontab configuration to schedule the liveness checks to be run in every 5 minutes;
  
  `*/5 * * * * cd /<path>/laphroaig/; ./pniMonitor_livenessCheck.py -c pniMonitor.conf >> pniMonitor_cron.log 2>&1`
  
  __Note:__ Using the above log file naming convention (`pniMonitor_cron.log`) will allow the main script to handle the 
  rotation of the cronlogs with no additional configuration effort.


__11. PLANNED FOR FUTURE RELEASES__

- __P1__ Netcool integration (might outsource this)
- __P2__ Multi-ASN support
- __P2__ IPv6 ACL for RHM Blocking
- __P2__ Persistence (of the previously recorded interface utilization data upon a new node or interface discovery)
- __P2__ Automated discovery of new interfaces (In the current release it is manually triggered)
- __P3__ Per-region cdn_serving_cap setting (It is available as a Global parameter in the current release)
- __P3__ Nokia 7750 support
- __P3__ IOS-XR / SROS version check
- __P4__ Catch SIGTERM KILL and report in logging (SIGKILL cannot be caught & there is a seperate liveness check script) 
- __P4__ Activate node reachability checks upon SSH failures for improved logging (Currently available for SNMP failures)
- __P4__ Graphical email updates with interface utilisation charts
- __P4__ Ordered directory structure (/logs, /data, /conf, etc.)
- __P4__ Replace SNMP & SSH with more reliable & convenient alternatives (eg. Netconf/RestAPI)  

[pniMonitor.py](https://github.com/onur-zengin/laphroaig)