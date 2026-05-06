.. _vti-interface:

##############################
VTI (virtual tunnel interface)
##############################

:abbr:`VTIs (virtual tunnel interfaces)` let you create secure, encrypted 
tunnels between private networks or hosts across public infrastructure, such as 
the Internet. They operate alongside an underlying IPsec tunnel, which handles 
encapsulation and encryption, while VTIs function exclusively as routing 
interfaces.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-address.txt
   :var0: vti
   :var1: vti0

.. cmdinclude:: /_include/interface-description.txt
   :var0: vti
   :var1: vti0

.. cmdinclude:: /_include/interface-disable.txt
  :var0: vti
  :var1: vti0

.. cmdinclude:: /_include/interface-ip.txt
  :var0: vti
  :var1: vti0

.. cmdinclude:: /_include/interface-ipv6.txt
  :var0: vti
  :var1: vti0

.. cmdinclude:: /_include/interface-mtu.txt
  :var0: vti
  :var1: vti0

.. cfgcmd:: set interfaces vti <interface> mirror egress <monitor-interface>

   Configure mirroring of outgoing traffic from the specified VTI to the 
   designated monitor interface.

.. cfgcmd:: set interfaces vti <interface> mirror ingress <monitor-interface>
   
   Configure mirroring of incoming traffic from the specified VTI to the 
   designated monitor interface.

.. cfgcmd:: set interfaces vti <interface> redirect <interface>

   Enable redirection of incoming packets to the specified interface.

.. cmdinclude:: /_include/interface-vrf.txt
  :var0: vti
  :var1: vti0

*********
Operation
*********

.. opcmd:: show interfaces vti <vtiX>

   Show the operational status and traffic statistics for the specified VTI.

.. opcmd:: show interfaces vti <vtiX> brief

   Show a brief operational status summary for the specified VTI. 


*******
Example
*******

**Configure a VTI**

Assign IPv4 and IPv6 addresses to the VTI, along with a brief description:

.. code-block:: none

  set interfaces vti vti0 address 192.168.2.249/30
  set interfaces vti vti0 address 2001:db8:2::249/64
  set interfaces vti vti0 description "Description"

Resulting configuration:

.. code-block:: none

  vyos@vyos# show interfaces vti
  vti vti0 {
      address 192.168.2.249/30
      address 2001:db8:2::249/64
      description "Description"
  }

.. warning:: When configuring site-to-site IPsec with VTIs, ensure that route 
   autoinstall is disabled.

.. code-block:: none
  
  set vpn ipsec options disable-route-autoinstall

For more information about the IPsec and VTI issue, as well as the 
``disable-route-autoinstall`` option, see:
https://blog.vyos.io/vyos-1-dot-2-0-development-news-in-july.

The root cause of the problem is that VTI tunnels require their traffic 
selectors to be set to ``0.0.0.0/0`` for traffic to match the tunnel, even 
though routing decisions are based on netfilter marks. Unless route insertion 
is explicitly disabled, strongSWAN incorrectly inserts a default route through 
the VTI peer address, causing all traffic to be misrouted.
