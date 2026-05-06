:lastproofread: 2021-06-30

.. _high-availability:

#################
High availability
#################

VRRP (Virtual Router Redundancy Protocol) provides active/backup redundancy for
routers. Every VRRP router has a physical IP/IPv6 address, and a virtual
address. On startup, routers elect the master, and the router with the highest
priority becomes the master and assigns the virtual address to its interface.
All routers with lower priorities become backup routers. The master then starts
sending keepalive packets to notify other routers that it's available. If the
master fails and stops sending keepalive packets, the router with the next
highest priority becomes the new master and takes over the virtual address.

VRRP keepalive packets use multicast, and VRRP setups are limited to a single
datalink layer segment. You can setup multiple VRRP groups
(also called virtual routers). Virtual routers are identified by a
VRID (Virtual Router IDentifier). If you setup multiple groups on the same
interface, their VRIDs must be unique if they use the same address family,
but it's possible (even if not recommended for readability reasons) to use
duplicate VRIDs on different interfaces.

Basic setup
-----------

VRRP groups are created with the
``set high-availability vrrp group $GROUP_NAME`` commands. The required
parameters are interface, vrid, and address.

minimal config

.. code-block:: none

  set high-availability vrrp group Foo vrid 10
  set high-availability vrrp group Foo interface eth0
  set high-availability vrrp group Foo address 192.0.2.1/24

You can verify your VRRP group status with the operational mode
``run show vrrp`` command:

.. code-block:: none

  vyos@vyos# run show vrrp
  Name        Interface      VRID  State    Last Transition
  ----------  -----------  ------  -------  -----------------
  Foo         eth1             10  MASTER   2s

IPv6 support
------------

The ``address`` parameter can be either an IPv4 or IPv6 address, but you can
not mix IPv4 and IPv6 in the same group, and will need to create groups with
different VRIDs specially for IPv4 and IPv6.
If you want to use IPv4 + IPv6 address you can use option ``excluded-address``

Address
-------
The ``address`` can be configured either on the VRRP interface or on not VRRP
interface.

.. code-block:: none

  set high-availability vrrp group Foo address 192.0.2.1/24
  set high-availability vrrp group Foo address 203.0.113.22/24 interface eth2
  set high-availability vrrp group Foo address 198.51.100.33/24 interface eth3

Disabling a VRRP group
----------------------

You can disable a VRRP group with ``disable`` option:

.. code-block:: none

  set high-availability vrrp group Foo disable

A disabled group will be removed from the VRRP process and your router will not
participate in VRRP for that VRID. It will disappear from operational mode
commands output, rather than enter the backup state.

Exclude address
---------------

Exclude IP addresses from ``VRRP packets``. This option ``excluded-address`` is
used when you want to set IPv4 + IPv6 addresses on the same virtual interface
or when used more than 20 IP addresses.

.. code-block:: none

  set high-availability vrrp group Foo excluded-address '203.0.113.254/24'
  set high-availability vrrp group Foo excluded-address '2001:db8:aa::1/64'
  set high-availability vrrp group Foo excluded-address '2001:db8:22::1/64'

Setting VRRP group priority
---------------------------

VRRP priority can be set with ``priority`` option:

.. code-block:: none

  set high-availability vrrp group Foo priority 200

The priority must be an integer number from 1 to 255. Higher priority value
increases router's precedence in the master elections.

Sync groups
-----------

A sync group allows VRRP groups to transition together.

.. code-block:: none

    edit high-availability vrrp
    set sync-group MAIN member VLAN9
    set sync-group MAIN member VLAN20

In the following example, when VLAN9 transitions, VLAN20 will also transition:

.. code-block:: none

    vrrp {
        group VLAN9 {
            interface eth0.9
            address 10.9.1.1/24
            priority 200
            vrid 9
        }
        group VLAN20 {
            interface eth0.20
            priority 200
            address 10.20.20.1/24
            vrid 20
        }
        sync-group MAIN {
            member VLAN20
            member VLAN9
        }
    }


.. warning:: All items in a sync group should be similarly configured.
   If one VRRP group is set to a different preemption delay or priority,
   it would result in an endless transition loop.


Preemption
----------

VRRP can use two modes: preemptive and non-preemptive. In the preemptive mode,
if a router with a higher priority fails and then comes back, routers with lower
priority will give up their master status. In non-preemptive mode, the newly
elected master will keep the master status and the virtual address indefinitely.

By default VRRP uses preemption. You can disable it with the "no-preempt"
option:

.. code-block:: none

  set high-availability vrrp group Foo no-preempt

You can also configure the time interval for preemption with the "preempt-delay"
option. For example, to set the higher priority router to take over in 180
seconds, use:

.. code-block:: none

  set high-availability vrrp group Foo preempt-delay 180

Track
-----

Track option to track non VRRP interface states. VRRP changes status to
``FAULT`` if one of the track interfaces in state ``down``.

.. code-block:: none

  set high-availability vrrp group Foo track interface eth0
  set high-availability vrrp group Foo track interface eth1

Ignore VRRP main interface faults

.. code-block:: none

  set high-availability vrrp group Foo track exclude-vrrp-interface

Unicast VRRP
------------

By default VRRP uses multicast packets. If your network does not support
multicast for whatever reason, you can make VRRP use unicast communication
instead.

.. code-block:: none

  set high-availability vrrp group Foo peer-address 192.0.2.10
  set high-availability vrrp group Foo hello-source-address 192.0.2.15

rfc3768-compatibility
---------------------

RFC 3768 defines a virtual MAC address to each VRRP virtual router.
This virtual router MAC address will be used as the source in all periodic VRRP
messages sent by the active node. When the rfc3768-compatibility option is set,
a new VRRP interface is created, to which the MAC address and the virtual IP
address is automatically assigned.

.. code-block:: none

   set high-availability vrrp group Foo rfc3768-compatibility

Verification

.. code-block:: none

   $show interfaces ethernet eth0v10
   eth0v10@eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue
   state UP group default qlen 1000
   link/ether 00:00:5e:00:01:0a brd ff:ff:ff:ff:ff:ff
   inet 172.25.0.247/16 scope global eth0v10
   valid_lft forever preferred_lft forever

.. warning:: RFC 3768 creates a virtual interface. If you want to apply 
   the destination NAT rule to the traffic sent to the virtual MAC, set 
   the created virtual interface as `inbound-interface`.

Global options
--------------

On most scenarios, there's no need to change specific parameters, and using
default configuration is enough. But there are cases were extra configuration
is needed.

.. cfgcmd:: set high-availability vrrp global-parameters startup_delay <1-600>

   This option specifies a delay in seconds before vrrp instances start up
   after keepalived starts.

Gratuitous ARP
--------------

These configuration is not mandatory and in most cases there's no
need to configure it. But if necessary, Gratuitous ARP can be configured in
``global-parameters`` and/or in ``group`` section.

.. cfgcmd:: set high-availability vrrp global-parameters garp interval
   <0.000-1000>

.. cfgcmd:: set high-availability vrrp group <name> garp interval <0.000-1000>

   Set delay between gratuitous ARP messages sent on an interface.

   0 if not defined.

.. stop_vyoslinter

.. cfgcmd:: set high-availability vrrp global-parameters garp master-delay <1-255>

.. start_vyoslinter

.. cfgcmd:: set high-availability vrrp group <name> garp master-delay <1-255>

   Set delay for second set of gratuitous ARPs after transition to MASTER.

   5 if not defined.

.. cfgcmd:: set high-availability vrrp global-parameters garp master-refresh
   <1-600>

.. cfgcmd:: set high-availability vrrp group <name> garp master-refresh
   <1-600>

   Set minimum time interval for refreshing gratuitous ARPs while MASTER.

   0 if not defined, which means no refreshing.

.. cfgcmd:: set high-availability vrrp global-parameters garp
   master-refresh-repeat <1-600>

.. cfgcmd:: set high-availability vrrp group <name> garp
   master-refresh-repeat <1-600>

   Set number of gratuitous ARP messages to send at a time while MASTER.

   1 if not defined.

.. cfgcmd:: set high-availability vrrp global-parameters garp master-repeat
   <1-600>

.. cfgcmd:: set high-availability vrrp group <name> garp master-repeat
   <1-600>

   Set number of gratuitous ARP messages to send at a time after transition to
   MASTER.

   5 if not defined.

Version
-------

.. cfgcmd:: set high-availability vrrp global-parameters version 2|3

   Set the default VRRP version to use. This defaults to 2, but IPv6 instances
   will always use version 3.

Scripting
---------

VRRP functionality can be extended with scripts. VyOS supports two kinds of
scripts: health check scripts and transition scripts. Health check scripts
execute custom checks in addition to the master router reachability. Transition
scripts are executed when VRRP state changes from master to backup or fault and
vice versa and can be used to enable or disable certain services, for example.

.. note:: Simply placing script files in ``/config/scripts/`` does not mean the 
   system can execute them. To make custom scripts executable, grant them 
   **execute permissions**. Use the following command:

   .. code-block:: none

     chmod +x /config/scripts/script-name.sh

.. warning:: It is not recommended to change VRRP configuration
   inside health-check and transition scripts.

Health check scripts
^^^^^^^^^^^^^^^^^^^^

There is the ability to run an arbitrary script at regular intervals
according to health-check parameters. If a script returns 0, it
indicates success. If a script returns anything else, it will indicate
that the VRRP instance should enter the FAULT state.

This setup will make the VRRP process execute the
``/config/scripts/vrrp-check.sh script`` every 60 seconds, and transition the
group to the fault state if it fails (i.e. exits with non-zero status) three
times:

.. stop_vyoslinter

.. code-block:: none

  set high-availability vrrp group Foo health-check script /config/scripts/vrrp-check.sh
  set high-availability vrrp group Foo health-check interval 60
  set high-availability vrrp group Foo health-check failure-count 3

.. start_vyoslinter

An optional ``timeout`` can be set to define the maximum number of seconds the
script is allowed to run. This is useful for scripts that may hang or take
longer than expected — setting the timeout higher than the interval allows
longer-running scripts to complete before being considered failed.

.. stop_vyoslinter

.. code-block:: none

  set high-availability vrrp group Foo health-check script /config/scripts/vrrp-check.sh
  set high-availability vrrp group Foo health-check interval 20
  set high-availability vrrp group Foo health-check failure-count 3
  set high-availability vrrp group Foo health-check timeout 40

.. start_vyoslinter

When the vrrp group is a member of the sync group will use only
the sync group health check script.
This example shows how to configure it for the sync group:

.. stop_vyoslinter

.. code-block:: none

  set high-availability vrrp sync-group Bar health-check script /config/scripts/vrrp-check.sh
  set high-availability vrrp sync-group Bar health-check interval 60
  set high-availability vrrp sync-group Bar health-check failure-count 3

.. start_vyoslinter

Transition scripts
^^^^^^^^^^^^^^^^^^

Transition scripts can help you implement various fixups, such as starting and
stopping services, or even modifying the VyOS config on VRRP transition.
This setup will make the VRRP process execute the
``/config/scripts/vrrp-fail.sh`` with argument ``Foo`` when VRRP fails,
and the ``/config/scripts/vrrp-master.sh`` when the router becomes the master:

.. stop_vyoslinter

.. code-block:: none

  set high-availability vrrp group Foo transition-script backup "/config/scripts/vrrp-fail.sh Foo"
  set high-availability vrrp group Foo transition-script fault "/config/scripts/vrrp-fail.sh Foo"
  set high-availability vrrp group Foo transition-script master "/config/scripts/vrrp-master.sh Foo"

.. start_vyoslinter

To know more about scripting, check the :ref:`command-scripting` section.

Virtual-server
--------------
.. include:: /_include/need_improvement.txt

Virtual Server allows to Load-balance traffic destination virtual-address:port
between several real servers.

Algorithm
^^^^^^^^^
Load-balancing schedule algorithm:

* round-robin
* weighted-round-robin
* least-connection
* weighted-least-connection
* source-hashing
* destination-hashing
* locality-based-least-connection

.. code-block:: none

  set high-availability virtual-server 203.0.113.1 algorithm 'least-connection'

Forward method
^^^^^^^^^^^^^^
* NAT
* direct
* tunnel

.. code-block:: none

  set high-availability virtual-server 203.0.113.1 forward-method 'nat'

Health-check
^^^^^^^^^^^^
Custom health-check script allows checking real-server availability

.. stop_vyoslinter

.. code-block:: none

  set high-availability virtual-server 203.0.113.1 real-server 192.0.2.11 health-check script <path-to-script>

.. start_vyoslinter

Fwmark
^^^^^^
Firewall mark. It possible to loadbalancing traffic based on ``fwmark`` value

.. code-block:: none

  set high-availability virtual-server 203.0.113.1 fwmark '111'

Real server
^^^^^^^^^^^
Real server IP address and port

.. stop_vyoslinter

.. code-block:: none

  set high-availability virtual-server 203.0.113.1 real-server 192.0.2.11 port '80'

.. start_vyoslinter


Example
^^^^^^^
Virtual-server can be configured with VRRP virtual address or without VRRP.

In the next example all traffic destined to ``203.0.113.1`` and port ``8280``
protocol TCP is balanced between 2 real servers ``192.0.2.11`` and
``192.0.2.12`` to port ``80``

Real server is auto-excluded if port check with this server fail.

.. stop_vyoslinter

.. code-block:: none

  set interfaces ethernet eth0 address '203.0.113.11/24'
  set interfaces ethernet eth1 address '192.0.2.1/24'
  set high-availability vrrp group FOO interface 'eth0'
  set high-availability vrrp group FOO no-preempt
  set high-availability vrrp group FOO priority '150'
  set high-availability vrrp group FOO address '203.0.113.1/24'
  set high-availability vrrp group FOO vrid '10'

  set high-availability virtual-server 203.0.113.1 algorithm 'source-hashing'
  set high-availability virtual-server 203.0.113.1 delay-loop '10'
  set high-availability virtual-server 203.0.113.1 forward-method 'nat'
  set high-availability virtual-server 203.0.113.1 persistence-timeout '180'
  set high-availability virtual-server 203.0.113.1 port '8280'
  set high-availability virtual-server 203.0.113.1 protocol 'tcp'
  set high-availability virtual-server 203.0.113.1 real-server 192.0.2.11 port '80'
  set high-availability virtual-server 203.0.113.1 real-server 192.0.2.12 port '80'

.. start_vyoslinter

A firewall mark ``fwmark`` allows using multiple ports for high-availability
virtual-server.
It uses fwmark value.

In this example all traffic destined to ports "80, 2222, 8888" protocol TCP
marks to fwmark "111" and balanced between 2 real servers.
Port "0" is required if multiple ports are used.

.. stop_vyoslinter

.. code-block:: none

  set interfaces ethernet eth0 address 'dhcp'
  set interfaces ethernet eth0 description 'WAN'
  set interfaces ethernet eth1 address '192.0.2.1/24'
  set interfaces ethernet eth1 description 'LAN'

  set policy route PR interface 'eth0'
  set policy route PR rule 10 destination port '80,2222,8888'
  set policy route PR rule 10 protocol 'tcp'
  set policy route PR rule 10 set mark '111'

  set high-availability virtual-server vyos fwmark '111'
  set high-availability virtual-server vyos protocol 'tcp'
  set high-availability virtual-server vyos real-server 192.0.2.11 health-check script '/config/scripts/check-real-server-first.sh'
  set high-availability virtual-server vyos real-server 192.0.2.11 port '0'
  set high-availability virtual-server vyos real-server 192.0.2.12 health-check script '/config/scripts/check-real-server-second.sh'
  set high-availability virtual-server vyos real-server 192.0.2.12 port '0'

  set nat source rule 100 outbound-interface name 'eth0'
  set nat source rule 100 source address '192.0.2.0/24'
  set nat source rule 100 translation address 'masquerade'

.. start_vyoslinter

Op-mode check virtual-server status

.. code-block:: none

  vyos@r14:~$ run show virtual-server
  IP Virtual Server version 1.2.1 (size=4096)
  Prot LocalAddress:Port Scheduler Flags
    -> RemoteAddress:Port           Forward Weight ActiveConn InActConn
  FWM  111 lc persistent 300
    -> 192.0.2.11:0                 Masq    1      0          0
    -> 192.0.2.12:0                 Masq    1      1          0
