# laphroaig
- Multi-Threaded
	The program will initiate a subThread for each node (router) specified in the inventory file, so that the PNI status on multiple routers can be monitored simultaneously.
	If for any reason a single subThread takes too long (i.e. longer than the pre-defined running frequency of the mainThread) to complete, than the other threads will wait. Although this may incur unintended delays to the monitoring of the other nodes, it would otherwise constitue a greater risk to allow the program to run while the reason of the delay is unknown.
TODO
- Check memory util after long loop

