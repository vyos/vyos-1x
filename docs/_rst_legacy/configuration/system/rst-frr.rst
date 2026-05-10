.. _system_frr:

###
FRR
###

VyOS uses `FRRouting <https://frrouting.org/>`_ as the control plane for dynamic
and static routing. The routing daemon behavior can be adjusted during runtime,
but requires either a restart of the routing daemon, or a reboot of the system.

.. cfgcmd:: set system frr bmp

   Enable :abbr:`BMP (BGP Monitoring Protocol)` support.

.. cfgcmd:: set system frr descriptors <numer>

   This allows the operator to control the number of open file descriptors
   each daemon is allowed to start with. If the operator plans to run bgp with
   several thousands of peers then this is where we would modify FRR to allow
   this to happen.

.. cfgcmd:: set system frr irdp

   Enable ICMP Router Discovery Protocol support.

.. cfgcmd:: set system frr profile <traditional | datacenter>

   Select an FRR profile to adapt its default settings. If unset, the
   traditional profile is applied.

.. cfgcmd:: set system frr snmp <daemon>

   Enable SNMP support for an individual routing daemon.

   Supported daemons:

   - bgpd
   - isisd
   - ldpd
   - ospf6d
   - ospfd
   - ripd
   - zebra
