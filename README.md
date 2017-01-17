# laphroaig
- Multi-Threaded
        The program will initiate a subThread for each node (router) specified in the inventory file, so that the PNI status on multiple routers can be monitored simultaneously.
        If for any reason a single subThread takes too long (i.e. longer than the pre-defined running frequency of the mainThread) to complete, than the other threads will wait. Although this may incur unintended delays to the monitoring of the other nodes, it would otherwise constitue a greater risk to allow the program to run while the reason of the delay is unknown.
TODO
- Check memory util after long loop

'\nDESCRIPTION:\n\t[-i <filename>], [--input <filename>]' \
          '\n\t\tThe inventory details must be provided in a text file structured in the following format,' \
          'while each node being written on a separate line:' \
          '\n\t\t\t<nodename>:pni,<intname-1>,...,<intname-M>:cdn,<intname-1>,...,<intname-N>' \
          '\n\t\t\tEXAMPLE: er12.thlon:pni,Bundle-Ether1024,Bundle-Ether1040:cdn,Bundle-Ether1064' \
          '\n\t[-l <loglevel>], [--logging <loglevel>]' \
          '\n\t\tThe loglevel must be specified as one of INFO, WARNING, DEBUG in capital letters. ' \
          'If none specified, the program will run with default level INFO.'
