:lastproofread: 2026-01-23

.. _dummy-interface:

#####
Dummy
#####

A dummy interface is a virtual network interface that operates like the 
loopback interface, accepting traffic and routing it back to the local host. 
Unlike the loopback interface, which is limited to one per system and reserved 
for internal system use, multiple dummy interfaces can be created, removed, and 
managed without impacting core operations.

As a software-based interface, the dummy interface does not depend on physical 
link state and remains active as long as the operating system is running.

Dummy interfaces are commonly used in environments with multiple redundant 
uplinks (e.g., a server connected to two different switches), where assigning a 
management IP address to a specific physical interface is risky. If that 
interface fails, the management IP address becomes unreachable.

Assigning the management IP address to a dummy interface and advertising it 
over all available physical links ensures the address remains reachable as long 
as at least one physical path is active.

Dummy interfaces are also used for testing and simulation purposes.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-address.txt
   :var0: dummy
   :var1: dum0

.. cmdinclude:: /_include/interface-description.txt
   :var0: dummy
   :var1: dum0

.. cmdinclude:: /_include/interface-disable.txt
   :var0: dummy
   :var1: dum0

.. cmdinclude:: /_include/interface-vrf.txt
   :var0: dummy
   :var1: dum0

*********
Operation
*********

.. opcmd:: show interfaces dummy

   Show brief interface information.

   .. code-block:: none

     vyos@vyos:~$ show interfaces dummy
     Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
     Interface        IP Address                        S/L  Description
     ---------        ----------                        ---  -----------
     dum0             172.18.254.201/32                 u/u

.. opcmd:: show interfaces dummy <interface>

   Show detailed interface information.

   .. code-block:: none

     vyos@vyos:~$ show interfaces dummy dum0
     dum0: <BROADCAST,NOARP,UP,LOWER_UP> mtu 1500 qdisc noqueue state UNKNOWN group default qlen 1000
         link/ether 26:7c:8e:bc:fc:f5 brd ff:ff:ff:ff:ff:ff
         inet 172.18.254.201/32 scope global dum0
            valid_lft forever preferred_lft forever
         inet6 fe80::247c:8eff:febc:fcf5/64 scope link
            valid_lft forever preferred_lft forever

         RX:  bytes    packets     errors    dropped    overrun      mcast
                  0          0          0          0          0          0
         TX:  bytes    packets     errors    dropped    carrier collisions
            1369707       4267          0          0          0          0


