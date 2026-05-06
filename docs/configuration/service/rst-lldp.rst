.. _lldp:

####
LLDP
####

:abbr:`LLDP (Link Layer Discovery Protocol)` is a vendor-neutral link layer
protocol in the Internet Protocol Suite used by network devices for advertising
their identity, capabilities, and neighbors on an IEEE 802 local area network,
principally wired Ethernet. The protocol is formally referred to by the IEEE
as Station and Media Access Control Connectivity Discovery specified in IEEE
802.1AB and IEEE 802.3-2012 section 6 clause 79.

LLDP performs functions similar to several proprietary protocols, such as
:abbr:`CDP (Cisco Discovery Protocol)`,
:abbr:`FDP (Foundry Discovery Protocol)`,
:abbr:`NDP (Nortel Discovery Protocol)` and :abbr:`LLTD (Link Layer Topology
Discovery)`.

Information gathered with LLDP is stored in the device as a :abbr:`MIB
(Management Information Database)` and can be queried with :abbr:`SNMP (Simple
Network Management Protocol)` as specified in :rfc:`2922`. The topology of an
LLDP-enabled network can be discovered by crawling the hosts and querying this
database. Information that may be retrieved include:

* System Name and Description
* Port name and description
* VLAN name
* IP management address
* System capabilities (switching, routing, etc.)
* MAC/PHY information
* MDI power
* Link aggregation

Configuration
=============

.. cfgcmd:: set service lldp

   Enable LLDP service

.. cfgcmd:: set service lldp management-address <address>

   Define IPv4/IPv6 management address transmitted via LLDP. Multiple addresses
   can be defined. Only addresses connected to the system will be transmitted.

.. cfgcmd:: set service lldp interface <interface>

   Enable transmission of LLDP information on given `<interface>`. You can also
   say ``all`` here so LLDP is turned on on every interface.

.. cfgcmd:: set service lldp interface <interface> mode [disable|rx-tx|rx|tx]

    Configure the administrative status of the given port.

    By default, all ports are configured to be in rx-tx mode. This means they
    can receive and transmit LLDP frames.

    In rx mode, they won't emit any frames. In tx mode, they won't receive
    any frames. In disabled mode, no frame will be sent and any incoming frame
    will be discarded.

.. cfgcmd:: set service lldp snmp

   Enable SNMP queries of the LLDP database

.. cfgcmd:: set service lldp legacy-protocols <cdp|edp|fdp|sonmp>

   Enable given legacy protocol on this LLDP instance. Legacy protocols include:

   * ``cdp`` - Listen for CDP for Cisco routers/switches
   * ``edp`` - Listen for EDP for Extreme routers/switches
   * ``fdp`` - Listen for FDP for Foundry routers/switches
   * ``sonmp`` - Listen for SONMP for Nortel routers/switches

Operation
=========

.. opcmd:: show lldp neighbors

   Displays information about all neighbors discovered via LLDP.

   .. code-block:: none

     vyos@vyos:~$ show lldp neighbors
     Capability Codes: R - Router, B - Bridge, W - Wlan r - Repeater, S - Station
                       D - Docsis, T - Telephone, O - Other

     Device ID                 Local     Proto  Cap   Platform             Port ID
     ---------                 -----     -----  ---   --------             -------
     BR2.vyos.net              eth0      LLDP   R     VyOS 1.2.4           eth1
     BR3.vyos.net              eth0      LLDP   RB    VyOS 1.2.4           eth2
     SW1.vyos.net              eth0      LLDP   B     Cisco IOS Software   GigabitEthernet0/6

.. opcmd:: show lldp neighbors detail

   Get detailed information about LLDP neighbors.

   .. code-block:: none

     vyos@vyos:~$ show lldp neighbors detail
     -------------------------------------------------------------------------------
     LLDP neighbors:
     -------------------------------------------------------------------------------
     Interface:    eth0, via: LLDP, RID: 28, Time: 0 day, 00:24:33
       Chassis:
         ChassisID:    mac 00:53:00:01:02:c9
         SysName:      BR2.vyos.net
         SysDescr:     VyOS 1.3-rolling-201912230217
         MgmtIP:       192.0.2.1
         MgmtIP:       2001:db8::ffff
         Capability:   Bridge, on
         Capability:   Router, on
         Capability:   Wlan, off
         Capability:   Station, off
       Port:
         PortID:       mac 00:53:00:01:02:c9
         PortDescr:    eth0
         TTL:          120
         PMD autoneg:  supported: no, enabled: no
           MAU oper type: 10GigBaseCX4 - X copper over 8 pair 100-Ohm balanced cable
       VLAN:         201 eth0.201
       VLAN:         205 eth0.205
       LLDP-MED:
         Device Type:  Network Connectivity Device
         Capability:   Capabilities, yes
         Capability:   Policy, yes
         Capability:   Location, yes
         Capability:   MDI/PSE, yes
         Capability:   MDI/PD, yes
         Capability:   Inventory, yes
         Inventory:
           Hardware Revision: None
           Software Revision: 4.19.89-amd64-vyos
           Firmware Revision: 6.00
           Serial Number: VMware-42 1d 83 b9 fe c1 bd b2-7
           Manufacturer: VMware, Inc.
           Model:        VMware Virtual Platform
           Asset ID:     No Asset Tag
     -------------------------------------------------------------------------------

.. opcmd:: show lldp neighbors interface <interface>

   Show LLDP neighbors connected via interface `<interface>`.

.. opcmd:: show log lldp

   Used for troubleshooting.
