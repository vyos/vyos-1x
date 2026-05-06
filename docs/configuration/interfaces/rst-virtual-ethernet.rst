:lastproofread: 2026-01-26

.. _virtual-ethernet:

################
Virtual Ethernet
################

Virtual Ethernet (veth) interfaces are software-based interfaces that operate 
in pairs, creating a tunnel between each other. Traffic transmitted into one 
interface of the pair (e.g., ``veth0``) is delivered directly to its peer 
interface (e.g., ``veth1``). 

Veth interfaces are commonly used to connect network namespaces or VRFs, but 
they can also function as standalone virtual network interfaces.

.. note:: Veth interfaces must be created in pairs, where each interface acts 
   as the peer of the other. 

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-address-with-dhcp.txt
   :var0: virtual-ethernet
   :var1: veth0

.. cmdinclude:: /_include/interface-description.txt
   :var0: virtual-ethernet
   :var1: veth0

VLAN
====

Regular VLANs (802.1q)
----------------------
.. cmdinclude:: /_include/interface-vlan-8021q.txt
   :var0: virtual-ethernet
   :var1: veth0

802.1ad (QinQ)
--------------

.. cmdinclude:: /_include/interface-vlan-8021ad.txt
   :var0: virtual-ethernet
   :var1: veth0

.. cmdinclude:: /_include/interface-disable.txt
   :var0: virtual-ethernet
   :var1: veth0

.. cmdinclude:: /_include/interface-vrf.txt
   :var0: virtual-ethernet
   :var1: veth0

*********
Operation
*********

.. opcmd:: show interfaces virtual-ethernet

   Show brief interface information.

   .. code-block:: none

     vyos@vyos:~$ show interfaces virtual-ethernet
     Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
     Interface        IP Address                        S/L  Description
     ---------        ----------                        ---  -----------
     veth10           100.64.0.0/31                     u/u
     veth11           100.64.0.1/31                     u/u

.. opcmd:: show interfaces virtual-ethernet <interface>

   Show detailed interface information.

   .. code-block:: none

     vyos@vyos:~$ show interfaces virtual-ethernet veth11
     10: veth11@veth10: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master red state UP group default qlen 1000
         link/ether b2:7b:df:47:e9:11 brd ff:ff:ff:ff:ff:ff
         inet 100.64.0.1/31 scope global veth11
            valid_lft forever preferred_lft forever
         inet6 fe80::b07b:dfff:fe47:e911/64 scope link
            valid_lft forever preferred_lft forever


         RX:  bytes    packets     errors    dropped    overrun      mcast
                  0          0          0          0          0          0
         TX:  bytes    packets     errors    dropped    carrier collisions
            1369707       4267          0          0          0          0

*******
Example
*******

The following example shows how to connect the global VRF to VRF ‘red ‘ using 
the ``veth10`` and ``veth11`` veth pair.

.. code-block:: none

  set interfaces virtual-ethernet veth10 address '100.64.0.0/31'
  set interfaces virtual-ethernet veth10 peer-name 'veth11'
  set interfaces virtual-ethernet veth11 address '100.64.0.1/31'
  set interfaces virtual-ethernet veth11 peer-name 'veth10'
  set interfaces virtual-ethernet veth11 vrf 'red'
  set vrf name red table '1000'

  vyos@vyos:~$ ping 100.64.0.1
  PING 100.64.0.1 (100.64.0.1) 56(84) bytes of data.
  64 bytes from 100.64.0.1: icmp_seq=1 ttl=64 time=0.080 ms
  64 bytes from 100.64.0.1: icmp_seq=2 ttl=64 time=0.119 ms


