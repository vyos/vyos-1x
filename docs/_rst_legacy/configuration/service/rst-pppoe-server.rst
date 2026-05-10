:lastproofread: 2022-09-17

.. _pppoe-server:

############
PPPoE Server
############

VyOS utilizes `accel-ppp`_ to provide PPPoE server functionality. It can
be used with local authentication or a connected RADIUS server.

.. note:: Please be aware, due to an upstream bug, config
   changes/commits will restart the ppp daemon and will reset existing
   PPPoE connections from connected users, in order to become effective.

************************
Configuring PPPoE Server
************************

.. code-block:: none

  set service pppoe-server access-concentrator PPPoE-Server
  set service pppoe-server authentication mode local
  set service pppoe-server authentication local-users username test password 'test'
  set service pppoe-server client-ip-pool PPPOE-POOL range 192.168.255.2-192.168.255.254
  set service pppoe-server default-pool 'PPPOE-POOL'
  set service pppoe-server gateway-address 192.168.255.1
  set service pppoe-server interface eth0

.. cfgcmd:: set service pppoe-server access-concentrator <name>

   Use this command to set a name for this PPPoE-server access
   concentrator.

.. cfgcmd:: set service pppoe-server authentication mode <local | radius>

  Set authentication backend. The configured authentication backend is used
  for all queries.

  * **radius**: All authentication queries are handled by a configured RADIUS
    server.
  * **local**: All authentication queries are handled locally.
  * **noauth**: Authentication disabled.

.. cfgcmd:: set service pppoe-server authentication local-users username
   <name> password <password>

  Create `<user>` for local authentication on this system. The users password
  will be set to `<pass>`.

.. cfgcmd:: set service pppoe-server client-ip-pool <POOL-NAME>
   range <x.x.x.x-x.x.x.x | x.x.x.x/x>

   Use this command to define the first IP address of a pool of
   addresses to be given to pppoe clients. If notation ``x.x.x.x-x.x.x.x``,
   it must be within a /24 subnet. If notation ``x.x.x.x/x`` is
   used there is possibility to set host/netmask.

.. cfgcmd:: set service pppoe-server default-pool <POOL-NAME>

   Use this command to define default address pool name.

.. cfgcmd:: set service pppoe-server interface <interface>

   Use this command to define the interface the PPPoE server will use to
   listen for PPPoE clients.

.. cfgcmd:: set service pppoe-server gateway-address <address>

   Specifies single `<gateway>` IP address to be used as local address of PPP
   interfaces.


*********************************
Configuring RADIUS authentication
*********************************

To enable RADIUS based authentication, the authentication mode needs to be
changed within the configuration. Previous settings like the local users, still
exists within the configuration, however they are not used if the mode has been
changed from local to radius. Once changed back to local, it will use all local
accounts again.

.. code-block:: none

  set service pppoe-server authentication mode radius

.. cfgcmd:: set service pppoe-server authentication radius
   server <server> key <secret>

  Configure RADIUS `<server>` and its required shared `<secret>` for
  communicating with the RADIUS server.

Since the RADIUS server would be a single point of failure, multiple RADIUS
servers can be setup and will be used subsequentially.
For example:

.. code-block:: none

  set service pppoe-server authentication radius server 10.0.0.1 key 'foo'
  set service pppoe-server authentication radius server 10.0.0.2 key 'foo'

.. note:: Some RADIUS severs use an access control list which allows or denies
   queries, make sure to add your VyOS router to the allowed client list.

RADIUS source address
=====================

If you are using OSPF as IGP, always the closest interface connected to the
RADIUS server is used. With VyOS 1.2 you can bind all outgoing RADIUS requests
to a single source IP e.g. the loopback interface.

.. cfgcmd:: set service pppoe-server authentication radius
   source-address <address>

  Source IPv4 address used in all RADIUS server queires.

.. note:: The ``source-address`` must be configured on one of VyOS interface.
   Best practice would be a loopback or dummy interface.

RADIUS advanced options
=======================

.. cfgcmd:: set service pppoe-server authentication radius
   server <server> port <port>

  Configure RADIUS `<server>` and its required port for authentication requests.

.. cfgcmd:: set service pppoe-server authentication radius
   server <server> fail-time <time>

  Mark RADIUS server as offline for this given `<time>` in seconds.

.. cfgcmd:: set service pppoe-server authentication radius
   server <server> disable

  Temporary disable this RADIUS server.

.. cfgcmd:: set service pppoe-server authentication radius
   acct-timeout <timeout>

  Timeout to wait reply for Interim-Update packets. (default 3 seconds)

.. cfgcmd:: set service pppoe-server authentication radius
   dynamic-author server <address>

  Specifies IP address for Dynamic Authorization Extension server (DM/CoA). 
  This IP must exist on any VyOS interface or it can be ``0.0.0.0``.

.. cfgcmd:: set service pppoe-server authentication radius
   dynamic-author port <port>

  UDP port for Dynamic Authorization Extension server (DM/CoA)

.. cfgcmd:: set service pppoe-server authentication radius dynamic-author
   key <secret>

  Secret for Dynamic Authorization Extension server (DM/CoA)

.. cfgcmd:: set service pppoe-server authentication radius
   max-try <number>

  Maximum number of tries to send Access-Request/Accounting-Request queries

.. cfgcmd:: set service pppoe-server authentication radius
   timeout <timeout>

  Timeout to wait response from server (seconds)

.. cfgcmd:: set service pppoe-server authentication radius
   nas-identifier <identifier>

  Value to send to RADIUS server in NAS-Identifier attribute and to be matched
  in DM/CoA requests.

.. cfgcmd:: set service pppoe-server authentication radius
   nas-ip-address <address>

  Value to send to RADIUS server in NAS-IP-Address attribute and to be matched
  in DM/CoA requests. Also DM/CoA server will bind to that address.

.. cfgcmd:: set service pppoe-server authentication radius
   source-address <address>

  Source IPv4 address used in all RADIUS server queires.

.. cfgcmd:: set service pppoe-server authentication radius
   rate-limit attribute <attribute>

  Specifies which RADIUS server attribute contains the rate limit information.
  The default attribute is ``Filter-Id``.

.. note:: If you set a custom RADIUS attribute you must define it on both
   dictionaries at RADIUS server and client.

.. cfgcmd:: set service pppoe-server authentication radius
   rate-limit enable

  Enables bandwidth shaping via RADIUS.

.. cfgcmd:: set service pppoe-server authentication radius
   rate-limit vendor

  Specifies the vendor dictionary, dictionary needs to be in
  /usr/share/accel-ppp/radius.

Received RADIUS attributes have a higher priority than parameters defined within
the CLI configuration, refer to the explanation below.

Allocation clients ip addresses by RADIUS
=========================================

If the RADIUS server sends the attribute ``Framed-IP-Address`` then this IP
address will be allocated to the client and the option ``default-pool``
within the CLI config is being ignored.

If the RADIUS server sends the attribute ``Framed-Pool``, IP address will
be allocated from a predefined IP pool whose name equals the attribute value.

If the RADIUS server sends the attribute ``Stateful-IPv6-Address-Pool``,
IPv6 address will be allocated from a predefined IPv6 pool ``prefix``
whose name equals the attribute value.

If the RADIUS server sends the attribute ``Delegated-IPv6-Prefix-Pool``,
IPv6 delegation pefix will be allocated from a predefined IPv6 pool ``delegate``
whose name equals the attribute value.

.. note:: ``Stateful-IPv6-Address-Pool`` and ``Delegated-IPv6-Prefix-Pool``
          are defined in RFC6911. If they are not defined in your RADIUS server,
          add new dictionary_.

User interface can be put to VRF context via RADIUS Access-Accept packet,
or change it via RADIUS CoA. ``Accel-VRF-Name`` is used from these purposes.
It is custom `ACCEL-PPP attribute`_. Define it in your RADIUS server.

Renaming clients interfaces by RADIUS
=====================================

If the RADIUS server uses the attribute ``NAS-Port-Id``, ppp tunnels will be
renamed.

.. note:: The value of the attribute ``NAS-Port-Id`` must be less than 16
   characters, otherwise the interface won't be renamed.


***********************
Automatic VLAN Creation
***********************

.. cfgcmd:: set service pppoe-server interface <interface> vlan <id | range>

   VLAN's can be created by Accel-ppp on the fly via the use of a Kernel module
   named ``vlan_mon``, which is monitoring incoming vlans and creates the
   necessary VLAN if required and allowed. VyOS supports the use of either
   VLAN ID's or entire ranges, both values can be defined at the same time for
   an interface.

   When configured, PPPoE will create the necessary VLANs when required. Once
   the user session has been cancelled and the VLAN is not needed anymore, VyOS
   will remove it again.

.. code-block:: none

  set service pppoe-server interface eth3 vlan 100
  set service pppoe-server interface eth3 vlan 200
  set service pppoe-server interface eth3 vlan 500-1000
  set service pppoe-server interface eth3 vlan 2000-3000

*****************
Bandwidth Shaping
*****************

Bandwidth rate limits can be set for local users or RADIUS based
attributes.

For Local Users
===============

.. cfgcmd:: set service pppoe-server authentication local-users username
   <user> rate-limit download <bandwidth>

  Download bandwidth limit in kbit/s for `<user>`.

.. cfgcmd:: set service pppoe-server authentication local-users username
   <user> rate-limit upload <bandwidth>

  Upload bandwidth limit in kbit/s for `<user>`.


.. code-block:: none

  set service pppoe-server access-concentrator 'ACN'
  set service pppoe-server authentication local-users username foo password 'bar'
  set service pppoe-server authentication local-users username foo rate-limit download '20480'
  set service pppoe-server authentication local-users username foo rate-limit upload '10240'
  set service pppoe-server authentication mode 'local'
  set service pppoe-server client-ip-pool IP-POOL range '10.1.1.100/24'
  set service pppoe-server default-pool 'IP-POOL'
  set service pppoe-server name-server '10.100.100.1'
  set service pppoe-server name-server '10.100.200.1'
  set service pppoe-server interface 'eth1'
  set service pppoe-server gateway-address '10.1.1.2'


Once the user is connected, the user session is using the set limits and
can be displayed via ``show pppoe-server sessions``.

.. code-block:: none

  show pppoe-server sessions
  ifname | username |     ip     |    calling-sid    | rate-limit  | state  |  uptime  | rx-bytes | tx-bytes
  -------+----------+------------+-------------------+-------------+--------+----------+----------+----------
  ppp0   | foo      | 10.1.1.100 | 00:53:00:ba:db:15 | 20480/10240 | active | 00:00:11 | 214 B    | 76 B


For RADIUS users
================

The current attribute ``Filter-Id`` is being used as default and can be
setup within RADIUS:

Filter-Id=2000/3000 (means 2000Kbit down-stream rate and 3000Kbit
up-stream rate)

The command below enables it, assuming the RADIUS connection has been
setup and is working.

.. cfgcmd:: set service pppoe-server authentication radius rate-limit enable

   Use this command to enable bandwidth shaping via RADIUS.

Other attributes can be used, but they have to be in one of the
dictionaries in */usr/share/accel-ppp/radius*.

**************
Load Balancing
**************


.. cfgcmd:: set service pppoe-server pado-delay <number-of-ms>
   sessions <number-of-sessions>

   Use this command to enable the delay of PADO (PPPoE Active Discovery
   Offer) packets, which can be used as a session balancing mechanism
   with other PPPoE servers.

.. code-block:: none

  set service pppoe-server pado-delay 50 sessions '500'
  set service pppoe-server pado-delay 100 sessions '1000'
  set service pppoe-server pado-delay 300 sessions '3000'

In the example above, the first 499 sessions connect without delay. PADO
packets will be delayed 50 ms for connection from 500 to 999, this trick
allows other PPPoE servers send PADO faster and clients will connect to
other servers. Last command says that this PPPoE server can serve only
3000 clients.

****
IPv6
****

.. cfgcmd:: set service pppoe-server ppp-options
   ipv6 <require | prefer | allow | deny>

  Specifies IPv6 negotiation preference.

  * **require** - Require IPv6 negotiation
  * **prefer** - Ask client for IPv6 negotiation, do not fail if it rejects
  * **allow** - Negotiate IPv6 only if client requests
  * **deny** - Do not negotiate IPv6 (default value)

.. cfgcmd:: set service pppoe-server client-ipv6-pool <IPv6-POOL-NAME>
   prefix <address> mask <number-of-bits>

  Use this comand to set the IPv6 address pool from which an PPPoE client
  will get an IPv6 prefix of your defined length (mask) to terminate the
  PPPoE endpoint at their side. The mask length can be set from 48 to 128
  bit long, the default value is 64.

.. cfgcmd:: set service pppoe-server client-ipv6-pool <IPv6-POOL-NAME>
   delegate <address> delegation-prefix <number-of-bits>

  Use this command to configure DHCPv6 Prefix Delegation (RFC3633) on
  PPPoE. You will have to set your IPv6 pool and the length of the
  delegation prefix. From the defined IPv6 pool you will be handing out
  networks of the defined length (delegation-prefix). The length of the
  delegation prefix can be set from 32 to 64 bit long.

.. cfgcmd:: set service pppoe-server default-ipv6-pool <IPv6-POOL-NAME>

   Use this command to define default IPv6 address pool name.

.. code-block:: none

  set service pppoe-server ppp-options ipv6 allow
  set service pppoe-server client-ipv6-pool IPv6-POOL delegate '2001:db8:8003::/48' delegation-prefix '56'
  set service pppoe-server client-ipv6-pool IPv6-POOL prefix '2001:db8:8002::/48' mask '64'
  set service pppoe-server default-ipv6-pool IPv6-POOL

IPv6 Advanced Options
=====================
.. cfgcmd:: set service pppoe-server ppp-options ipv6-accept-peer-interface-id

  Accept peer interface identifier. By default is not defined.

.. cfgcmd:: set service pppoe-server ppp-options ipv6-interface-id
   <random | x:x:x:x>

  Specifies fixed or random interface identifier for IPv6.
  By default is fixed.

  * **random** - Random interface identifier for IPv6
  * **x:x:x:x** - Specify interface identifier for IPv6

.. cfgcmd:: set service pppoe-server ppp-options ipv6-interface-id
   <random | x:x:x:x>

  Specifies peer interface identifier for IPv6. By default is fixed.

  * **random** - Random interface identifier for IPv6
  * **x:x:x:x** - Specify interface identifier for IPv6
  * **ipv4-addr** - Calculate interface identifier from IPv4 address.
  * **calling-sid** - Calculate interface identifier from calling-station-id.

*********
Scripting
*********

.. cfgcmd:: set service pppoe-server extended-scripts on-change <path_to_script>

  Script to run when session interface changed by RADIUS CoA handling

.. cfgcmd:: set service pppoe-server extended-scripts on-down <path_to_script>

  Script to run when session interface going to terminate

.. cfgcmd:: set service pppoe-server extended-scripts on-pre-up <path_to_script>

  Script to run before session interface comes up

.. cfgcmd:: set service pppoe-server extended-scripts on-up <path_to_script>

  Script to run when session interface is completely configured and started

****************
Advanced Options
****************

Authentication Advanced Options
===============================

.. cfgcmd:: set service pppoe-server authentication local-users
   username <user> disable

  Disable `<user>` account.

.. cfgcmd:: set service pppoe-server authentication local-users
   username <user> static-ip <address>

  Assign static IP address to `<user>` account.

.. cfgcmd:: set service pppoe-server authentication protocols
   <pap | chap | mschap | mschap-v2>

  Require the peer to authenticate itself using one of the following protocols:
  pap, chap, mschap, mschap-v2.

Client IP Pool Advanced Options
===============================

.. cfgcmd:: set service pppoe-server client-ip-pool <POOL-NAME>
   next-pool <NEXT-POOL-NAME>

   Use this command to define the next address pool name.

PPP Advanced Options
====================

.. cfgcmd:: set service pppoe-server ppp-options disable-ccp

  Disable Compression Control Protocol (CCP).
  CCP is enabled by default.

.. cfgcmd:: set service pppoe-server ppp-options interface-cache <number>

  Specifies number of interfaces to keep in cache. It means that don’t
  destroy interface after corresponding session is destroyed, instead
  place it to cache and use it later for new sessions repeatedly.
  This should reduce kernel-level interface creation/deletion rate lack.
  Default value is **0**.

.. cfgcmd:: set service pppoe-server ppp-options ipv4
   <require | prefer | allow | deny>

  Specifies IPv4 negotiation preference.

  * **require** - Require IPv4 negotiation
  * **prefer** - Ask client for IPv4 negotiation, do not fail if it rejects
  * **allow** - Negotiate IPv4 only if client requests (Default value)
  * **deny** - Do not negotiate IPv4

.. cfgcmd:: set service pppoe-server ppp-options lcp-echo-failure <number>

  Defines the maximum `<number>` of unanswered echo requests. Upon reaching the
  value `<number>`, the session will be reset. Default value is **3**.

.. cfgcmd:: set service pppoe-server ppp-options lcp-echo-interval <interval>

  If this option is specified and is greater than 0, then the PPP module will
  send LCP pings of the echo request every `<interval>` seconds.
  Default value is **30**.

.. cfgcmd:: set service pppoe-server ppp-options lcp-echo-timeout

  Specifies timeout in seconds to wait for any peer activity. If this option
  specified it turns on adaptive lcp echo functionality and "lcp-echo-failure"
  is not used. Default value is **0**.

.. cfgcmd:: set service pppoe-server ppp-options min-mtu <number>

  Defines minimum acceptable MTU. If client will try to negotiate less then
  specified MTU then it will be NAKed or disconnected if rejects greater MTU.
  Default value is **100**.

.. cfgcmd:: set service pppoe-server ppp-options mppe <require | prefer | deny>

  Specifies :abbr:`MPPE (Microsoft Point-to-Point Encryption)` negotiation
  preference.

  * **require** - ask client for mppe, if it rejects drop connection
  * **prefer** - ask client for mppe, if it rejects don't fail. (Default value)
  * **deny** - deny mppe

  Default behavior - don't ask client for mppe, but allow it if client wants.
  Please note that RADIUS may override this option by MS-MPPE-Encryption-Policy
  attribute.

.. cfgcmd:: set service pppoe-server ppp-options mru <number>

  Defines preferred MRU. By default is not defined.

Global Advanced options
=======================

.. cfgcmd:: set service pppoe-server description <description>

  Set description.

.. cfgcmd::  set service pppoe-server limits burst <value>

  Burst count

.. cfgcmd:: set service pppoe-server limits connection-limit <value>

  Acceptable rate of connections (e.g. 1/min, 60/sec)

.. cfgcmd:: set service pppoe-server limits timeout <value>

  Timeout in seconds

.. cfgcmd:: set service pppoe-server mtu

  Maximum Transmission Unit (MTU) (default: **1492**)

.. cfgcmd:: set service pppoe-server max-concurrent-sessions

  Maximum number of concurrent session start attempts

.. cfgcmd:: set service pppoe-server name-server <address>

  Connected client should use `<address>` as their DNS server. This
  command accepts both IPv4 and IPv6 addresses. Up to two nameservers
  can be configured for IPv4, up to three for IPv6.

.. cfgcmd:: set service pppoe-server service-name <names>

  Specifies Service-Name to respond. If absent any Service-Name is
  acceptable and client’s Service-Name will be sent back. Also possible
  set multiple service-names: `sn1,sn2,sn3`

Per default the user session is being replaced if a second
authentication request succeeds. Such session requests can be either
denied or allowed entirely, which would allow multiple sessions for a
user in the latter case. If it is denied, the second session is being
rejected even if the authentication succeeds, the user has to terminate
its first session and can then authentication again.

.. cfgcmd:: set service pppoe-server session-control

  * **disable**: Disables session control.
  * **deny**: Deny second session authorization.
  * **replace**: Terminate first session when second is authorized **(default)**

.. cfgcmd:: set service pppoe-server shaper fwmark <1-2147483647>

  Match firewall mark value

.. cfgcmd:: set service pppoe-server snmp master-agent

  Enable SNMP

.. cfgcmd:: set service pppoe-server wins-server <address>

  Windows Internet Name Service (WINS) servers propagated to client

**********
Monitoring
**********

.. opcmd:: show pppoe-server sessions

   Use this command to locally check the active sessions in the PPPoE
   server.


.. code-block:: none

  show pppoe-server sessions
  ifname | username |     ip     |    calling-sid    | rate-limit  | state  |  uptime  | rx-bytes | tx-bytes
  -------+----------+------------+-------------------+-------------+--------+----------+----------+----------
  ppp0   | foo      | 10.1.1.100 | 00:53:00:ba:db:15 | 20480/10240 | active | 00:00:11 | 214 B    | 76 B


********
Examples
********

IPv4
====

The example below uses ACN as access-concentrator name, assigns an
address from the pool 10.1.1.100-111, terminates at the local endpoint
10.1.1.1 and serves requests only on eth1.

.. code-block:: none

  set service pppoe-server access-concentrator 'ACN'
  set service pppoe-server authentication local-users username foo password 'bar'
  set service pppoe-server authentication mode 'local'
  set service pppoe-server client-ip-pool IP-POOL range '10.1.1.100-10.1.1.111'
  set service pppoe-server default-pool 'IP-POOL'
  set service pppoe-server interface eth1
  set service pppoe-server gateway-address '10.1.1.2'
  set service pppoe-server name-server '10.100.100.1'
  set service pppoe-server name-server '10.100.200.1'



Dual-Stack IPv4/IPv6 provisioning with Prefix Delegation
========================================================

The example below covers a dual-stack configuration.

.. code-block:: none

  set service pppoe-server authentication local-users username test password 'test'
  set service pppoe-server authentication mode 'local'
  set service pppoe-server client-ip-pool IP-POOL range '192.168.0.1/24'
  set service pppoe-server default-pool 'IP-POOL'
  set service pppoe-server client-ipv6-pool IPv6-POOL delegate '2001:db8:8003::/48' delegation-prefix '56'
  set service pppoe-server client-ipv6-pool IPV6-POOL prefix '2001:db8:8002::/48' mask '64'
  set service pppoe-server default-ipv6-pool IPv6-POOL
  set service pppoe-server ppp-options ipv6 allow
  set service pppoe-server name-server '10.1.1.1'
  set service pppoe-server name-server '2001:db8:4860::8888'
  set service pppoe-server interface 'eth2'
  set service pppoe-server gateway-address '10.100.100.1'

The client, once successfully authenticated, will receive an IPv4 and an
IPv6 /64 address to terminate the PPPoE endpoint on the client side and
a /56 subnet for the clients internal use.

.. code-block:: none

  vyos@pppoe-server:~$ sh pppoe-server sessions
   ifname | username |     ip      |            ip6           |       ip6-dp        |    calling-sid    | rate-limit | state  |  uptime  | rx-bytes | tx-bytes
  --------+----------+-------------+--------------------------+---------------------+-------------------+------------+--------+----------+----------+----------
   ppp0   | test     | 192.168.0.1 | 2001:db8:8002:0:200::/64 | 2001:db8:8003::1/56 | 00:53:00:12:42:eb |            | active | 00:00:49 | 875 B    | 2.1 KiB

.. include:: /_include/common-references.txt
.. _dictionary: https://github.com/accel-ppp/accel-ppp/blob/master/
   accel-pppd/radius/dict/dictionary.rfc6911
.. _`ACCEL-PPP attribute`: https://github.com/accel-ppp/accel-ppp/
   blob/master/accel-pppd/radius/dict/dictionary.accel
