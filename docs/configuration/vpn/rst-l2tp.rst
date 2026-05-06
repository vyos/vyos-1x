.. _l2tp:

####
L2TP
####

VyOS utilizes accel-ppp_ to provide L2TP server functionality. It can be used
with local authentication or a connected RADIUS server.

***********************
Configuring L2TP Server
***********************

.. code-block:: none

  set vpn l2tp remote-access authentication mode local
  set vpn l2tp remote-access authentication local-users username test password 'test'
  set vpn l2tp remote-access client-ip-pool L2TP-POOL range 192.168.255.2-192.168.255.254
  set vpn l2tp remote-access default-pool 'L2TP-POOL'
  set vpn l2tp remote-access outside-address 192.0.2.2
  set vpn l2tp remote-access gateway-address 192.168.255.1


.. cfgcmd:: set vpn l2tp remote-access authentication mode <local | radius>

  Set authentication backend. The configured authentication backend is used
  for all queries.

  * **radius**: All authentication queries are handled by a configured RADIUS
    server.
  * **local**: All authentication queries are handled locally.

.. cfgcmd:: set vpn l2tp remote-access authentication local-users username <user> password
   <pass>

  Create `<user>` for local authentication on this system. The users password
  will be set to `<pass>`.

.. cfgcmd:: set vpn l2tp remote-access client-ip-pool <POOL-NAME> range <x.x.x.x-x.x.x.x | x.x.x.x/x>

   Use this command to define the first IP address of a pool of
   addresses to be given to l2tp clients. If notation ``x.x.x.x-x.x.x.x``,
   it must be within a /24 subnet. If notation ``x.x.x.x/x`` is
   used there is possibility to set host/netmask.

.. cfgcmd:: set vpn l2tp remote-access default-pool <POOL-NAME>

   Use this command to define default address pool name.

.. cfgcmd:: set vpn l2tp remote-access gateway-address <gateway>

  Specifies single `<gateway>` IP address to be used as local address of PPP
  interfaces.

*****************
Configuring IPsec
*****************

.. code-block:: none

  set vpn ipsec interface eth0
  set vpn l2tp remote-access ipsec-settings authentication mode pre-shared-secret
  set vpn l2tp remote-access ipsec-settings authentication pre-shared-secret secret


.. cfgcmd:: set vpn ipsec interface <INTERFACE>

   Use this command to define IPsec interface.

.. cfgcmd:: set vpn l2tp remote-access ipsec-settings authentication mode <pre-shared-secret | x509>

   Set mode for IPsec authentication between VyOS and L2TP clients.

.. cfgcmd:: set vpn l2tp remote-access ipsec-settings authentication pre-shared-secret <secret>

   Set predefined shared secret phrase.


If a local firewall policy is in place on your external interface you will need
to allow the ports below:

* UDP port 500 (IKE)
* IP protocol number 50 (ESP)
* UDP port 1701 for IPsec

As well as the below to allow NAT-traversal (when NAT is detected by the
VPN client, ESP is encapsulated in UDP for NAT-traversal):

* UDP port 4500 (NAT-T)

Example:

.. code-block:: none

  set firewall ipv4 name OUTSIDE-LOCAL rule 40 action 'accept'
  set firewall ipv4 name OUTSIDE-LOCAL rule 40 protocol 'esp'
  set firewall ipv4 name OUTSIDE-LOCAL rule 41 action 'accept'
  set firewall ipv4 name OUTSIDE-LOCAL rule 41 destination port '500'
  set firewall ipv4 name OUTSIDE-LOCAL rule 41 protocol 'udp'
  set firewall ipv4 name OUTSIDE-LOCAL rule 42 action 'accept'
  set firewall ipv4 name OUTSIDE-LOCAL rule 42 destination port '4500'
  set firewall ipv4 name OUTSIDE-LOCAL rule 42 protocol 'udp'
  set firewall ipv4 name OUTSIDE-LOCAL rule 43 action 'accept'
  set firewall ipv4 name OUTSIDE-LOCAL rule 43 destination port '1701'
  set firewall ipv4 name OUTSIDE-LOCAL rule 43 ipsec 'match-ipsec'
  set firewall ipv4 name OUTSIDE-LOCAL rule 43 protocol 'udp'

To allow VPN-clients access via your external address, a NAT rule is required:


.. code-block:: none

  set nat source rule 110 outbound-interface name 'eth0'
  set nat source rule 110 source address '192.168.255.0/24'
  set nat source rule 110 translation address masquerade

*********************************
Configuring RADIUS authentication
*********************************

To enable RADIUS based authentication, the authentication mode needs to be
changed within the configuration. Previous settings like the local users, still
exists within the configuration, however they are not used if the mode has been
changed from local to radius. Once changed back to local, it will use all local
accounts again.

.. code-block:: none

  set vpn l2tp remote-access authentication mode radius

.. cfgcmd:: set vpn l2tp remote-access authentication radius server <server> key <secret>

  Configure RADIUS `<server>` and its required shared `<secret>` for
  communicating with the RADIUS server.

Since the RADIUS server would be a single point of failure, multiple RADIUS
servers can be setup and will be used subsequentially.
For example:

.. code-block:: none

  set vpn l2tp remote-access authentication radius server 10.0.0.1 key 'foo'
  set vpn l2tp remote-access authentication radius server 10.0.0.2 key 'foo'

.. note:: Some RADIUS_ severs use an access control list which allows or denies
   queries, make sure to add your VyOS router to the allowed client list.

RADIUS source address
=====================

If you are using OSPF as your IGP, use the interface connected closest to the
RADIUS server. You can bind all outgoing RADIUS requests to a single source IP
e.g. the loopback interface.

.. cfgcmd:: set vpn l2tp remote-access authentication radius source-address <address>

  Source IPv4 address used in all RADIUS server queires.

.. note:: The ``source-address`` must be configured to that of an interface.
   Best practice would be a loopback or dummy interface.

RADIUS advanced options
=======================

.. cfgcmd:: set vpn l2tp remote-access authentication radius server <server> port <port>

  Configure RADIUS `<server>` and its required port for authentication requests.

.. cfgcmd:: set vpn l2tp remote-access authentication radius server <server> fail-time <time>

  Mark RADIUS server as offline for this given `<time>` in seconds.

.. cfgcmd:: set vpn l2tp remote-access authentication radius server <server> disable

  Temporary disable this RADIUS server.

.. cfgcmd:: set vpn l2tp remote-access authentication radius acct-timeout <timeout>

  Timeout to wait reply for Interim-Update packets. (default 3 seconds)

.. cfgcmd:: set vpn l2tp remote-access authentication radius dynamic-author server <address>

  Specifies IP address for Dynamic Authorization Extension server (DM/CoA). 
  This IP must exist on any VyOS interface or it can be ``0.0.0.0``.

.. cfgcmd:: set vpn l2tp remote-access authentication radius dynamic-author port <port>

  UDP port for Dynamic Authorization Extension server (DM/CoA)

.. cfgcmd:: set vpn l2tp remote-access authentication radius dynamic-author key <secret>

  Secret for Dynamic Authorization Extension server (DM/CoA)

.. cfgcmd:: set vpn l2tp remote-access authentication radius max-try <number>

  Maximum number of tries to send Access-Request/Accounting-Request queries

.. cfgcmd:: set vpn l2tp remote-access authentication radius timeout <timeout>

  Timeout to wait response from server (seconds)

.. cfgcmd:: set vpn l2tp remote-access authentication radius nas-identifier <identifier>

  Value to send to RADIUS server in NAS-Identifier attribute and to be matched
  in DM/CoA requests.

.. cfgcmd:: set vpn l2tp remote-access authentication radius nas-ip-address <address>

  Value to send to RADIUS server in NAS-IP-Address attribute and to be matched
  in DM/CoA requests. Also DM/CoA server will bind to that address.

.. cfgcmd:: set vpn l2tp remote-access authentication radius source-address <address>

  Source IPv4 address used in all RADIUS server queires.

.. cfgcmd:: set vpn l2tp remote-access authentication radius rate-limit attribute <attribute>

  Specifies which RADIUS server attribute contains the rate limit information.
  The default attribute is `Filter-Id`.

.. note:: If you set a custom RADIUS attribute you must define it on both
   dictionaries on the RADIUS server and client.

.. cfgcmd:: set vpn l2tp remote-access authentication radius rate-limit enable

  Enables bandwidth shaping via RADIUS.

.. cfgcmd:: set vpn l2tp remote-access authentication radius rate-limit vendor

  Specifies the vendor dictionary. This dictionary needs to be present in
  /usr/share/accel-ppp/radius.

Received RADIUS attributes have a higher priority than parameters defined within
the CLI configuration, refer to the explanation below.

Allocation clients ip addresses by RADIUS
=========================================

If the RADIUS server sends the attribute ``Framed-IP-Address`` then this IP
address will be allocated to the client and the option ``default-pool`` within
the CLI config will be ignored.

If the RADIUS server sends the attribute ``Framed-Pool``, then the IP address
will be allocated from a predefined IP pool whose name equals the attribute
value.

If the RADIUS server sends the attribute ``Stateful-IPv6-Address-Pool``, the
IPv6 address will be allocated from a predefined IPv6 pool ``prefix`` whose
name equals the attribute value.

If the RADIUS server sends the attribute ``Delegated-IPv6-Prefix-Pool``, an
IPv6 delegation prefix will be allocated from a predefined IPv6 pool
``delegate`` whose name equals the attribute value.

.. note:: ``Stateful-IPv6-Address-Pool`` and ``Delegated-IPv6-Prefix-Pool`` are defined in
          RFC6911. If they are not defined in your RADIUS server, add new dictionary_.

The client's interface can be put into a VRF context via a RADIUS Access-Accept
packet, or changed via RADIUS CoA. ``Accel-VRF-Name`` is used for these
purposes. This is a custom `ACCEL-PPP attribute`_. Define it in your RADIUS
server.

Renaming clients interfaces by RADIUS
=====================================

If the RADIUS server uses the attribute ``NAS-Port-Id``, ppp tunnels will be
renamed.

.. note:: The value of the attribute ``NAS-Port-Id`` must be less than 16
   characters, otherwise the interface won't be renamed.

*************************************
Configuring LNS (L2TP Network Server)
*************************************

LNS are often used to connect to a LAC (L2TP Access Concentrator).

.. cfgcmd:: set vpn l2tp remote-access lns host-name <hostname>

  Sent to the client (LAC) in the Host-Name attribute

.. cfgcmd:: set vpn l2tp remote-access lns shared-secret <secret>

   Tunnel password used to authenticate the client (LAC)

To explain the usage of LNS follow our blueprint :ref:`examples-lac-lns`.

****
IPv6
****
.. cfgcmd:: set vpn l2tp remote-access ppp-options ipv6 <require | prefer | allow | deny>

  Specifies IPv6 negotiation preference.

  * **require** - Require IPv6 negotiation
  * **prefer** - Ask client for IPv6 negotiation, do not fail if it rejects
  * **allow** - Negotiate IPv6 only if client requests
  * **deny** - Do not negotiate IPv6 (default value)

.. cfgcmd:: set vpn l2tp remote-access client-ipv6-pool <IPv6-POOL-NAME> prefix <address>
   mask <number-of-bits>

  Use this comand to set the IPv6 address pool from which an l2tp client will
  get an IPv6 prefix of your defined length (mask) to terminate the l2tp 
  endpoint at their side. The mask length can be set between 48 and 128 bits
  long, the default value is 64.

.. cfgcmd:: set vpn l2tp remote-access client-ipv6-pool <IPv6-POOL-NAME> delegate <address>
   delegation-prefix <number-of-bits>

  Use this command to configure DHCPv6 Prefix Delegation (RFC3633) on l2tp.
  You will have to set your IPv6 pool and the length of the delegation 
  prefix. From the defined IPv6 pool you will be handing out networks of the
  defined length (delegation-prefix). The length of the delegation prefix can
  be between 32 and 64 bits long.

.. cfgcmd:: set vpn l2tp remote-access default-ipv6-pool <IPv6-POOL-NAME>

   Use this command to define default IPv6 address pool name.

.. code-block:: none

  set vpn l2tp remote-access ppp-options ipv6 allow
  set vpn l2tp remote-access client-ipv6-pool IPv6-POOL delegate '2001:db8:8003::/48' delegation-prefix '56'
  set vpn l2tp remote-access client-ipv6-pool IPv6-POOL prefix '2001:db8:8002::/48' mask '64'
  set vpn l2tp remote-access default-ipv6-pool IPv6-POOL

IPv6 Advanced Options
=====================
.. cfgcmd:: set vpn l2tp remote-access ppp-options ipv6-accept-peer-interface-id

  Accept peer interface identifier. By default this is not defined.

.. cfgcmd:: set vpn l2tp remote-access ppp-options ipv6-interface-id <random | x:x:x:x>

  Specifies if a fixed or random interface identifier is used for IPv6. The
  default is fixed.

  * **random** - Random interface identifier for IPv6
  * **x:x:x:x** - Specify interface identifier for IPv6

.. cfgcmd:: set vpn l2tp remote-access ppp-options ipv6-interface-id <random | x:x:x:x>

  Specifies the peer interface identifier for IPv6. The default is fixed.

  * **random** - Random interface identifier for IPv6
  * **x:x:x:x** - Specify interface identifier for IPv6
  * **ipv4-addr** - Calculate interface identifier from IPv4 address.
  * **calling-sid** - Calculate interface identifier from calling-station-id.

*********
Scripting
*********

.. cfgcmd:: set vpn l2tp remote-access extended-scripts on-change <path_to_script>

  Script to run when the session interface is changed by RADIUS CoA handling

.. cfgcmd:: set vpn l2tp remote-access extended-scripts on-down <path_to_script>

  Script to run when the session interface is about to terminate

.. cfgcmd:: set vpn l2tp remote-access extended-scripts on-pre-up <path_to_script>

  Script to run before the session interface comes up

.. cfgcmd:: set vpn l2tp remote-access extended-scripts on-up <path_to_script>

  Script to run when the session interface is completely configured and started

****************
Advanced Options
****************

Authentication Advanced Options
===============================

.. cfgcmd:: set vpn l2tp remote-access authentication local-users username <user> disable

  Disable `<user>` account.

.. cfgcmd:: set vpn l2tp remote-access authentication local-users username <user> static-ip
   <address>

  Assign a static IP address to `<user>` account.

.. cfgcmd:: set vpn l2tp remote-access authentication local-users username <user> rate-limit
   download <bandwidth>

  Rate limit the download bandwidth for `<user>` to `<bandwidth>` kbit/s.

.. cfgcmd:: set vpn l2tp remote-access authentication local-users username <user> rate-limit
   upload <bandwidth>

  Rate limit the upload bandwidth for `<user>` to `<bandwidth>` kbit/s

.. cfgcmd:: set vpn l2tp remote-access authentication protocols
   <pap | chap | mschap | mschap-v2>

  Require the peer to authenticate itself using one of the following protocols:
  pap, chap, mschap, mschap-v2.

Client IP Pool Advanced Options
===============================

.. cfgcmd:: set vpn l2tp remote-access client-ip-pool <POOL-NAME> next-pool <NEXT-POOL-NAME>

   Use this command to define the next address pool name.

PPP Advanced Options
====================

.. cfgcmd:: set vpn l2tp remote-access ppp-options disable-ccp

  Disable Compression Control Protocol (CCP).
  CCP is enabled by default.

.. cfgcmd:: set vpn l2tp remote-access ppp-options interface-cache <number>

  Specifies number of interfaces to cache. This prevents interfaces from being
  removed once the corresponding session is destroyed. Instead, interfaces are
  cached for later use in new sessions. This should reduce the kernel-level
  interface creation/deletion rate.
  Default value is **0**.

.. cfgcmd:: set vpn l2tp remote-access ppp-options ipv4 <require | prefer | allow | deny>

  Specifies IPv4 negotiation preference.

  * **require** - Require IPv4 negotiation
  * **prefer** - Ask client for IPv4 negotiation, do not fail if it rejects
  * **allow** - Negotiate IPv4 only if client requests (Default value)
  * **deny** - Do not negotiate IPv4

.. cfgcmd:: set vpn l2tp remote-access ppp-options lcp-echo-failure <number>

  Defines the maximum `<number>` of unanswered echo requests. Upon reaching the
  value `<number>`, the session will be reset. Default value is **3**.

.. cfgcmd:: set vpn l2tp remote-access ppp-options lcp-echo-interval <interval>

  If this option is specified and is greater than 0, then the PPP module will
  send LCP echo requests every `<interval>` seconds.
  Default value is **30**.

.. cfgcmd:: set vpn l2tp remote-access ppp-options lcp-echo-timeout

  Specifies timeout in seconds to wait for any peer activity. If this option is
  specified it turns on adaptive lcp echo functionality and "lcp-echo-failure"
  is not used. Default value is **0**.

.. cfgcmd:: set vpn l2tp remote-access ppp-options min-mtu <number>

  Defines the minimum acceptable MTU. If a client tries to negotiate an MTU
  lower than this it will be NAKed, and disconnected if it rejects a greater 
  MTU.
  Default value is **100**.

.. cfgcmd:: set vpn l2tp remote-access ppp-options mppe <require | prefer | deny>

  Specifies :abbr:`MPPE (Microsoft Point-to-Point Encryption)` negotiation
  preference.

  * **require** - ask client for mppe, if it rejects drop connection
  * **prefer** - ask client for mppe, if it rejects don't fail. (Default value)
  * **deny** - deny mppe

  Default behavior - don't ask the client for mppe, but allow it if the client
  wants.
  Please note that RADIUS may override this option with the 
  MS-MPPE-Encryption-Policy attribute.

.. cfgcmd:: set vpn l2tp remote-access ppp-options mru <number>

  Defines preferred MRU. By default is not defined.

Global Advanced options
=======================

.. cfgcmd:: set vpn l2tp remote-access description <description>

  Set description.

.. cfgcmd::  set vpn l2tp remote-access limits burst <value>

  Burst count

.. cfgcmd:: set vpn l2tp remote-access limits connection-limit <value>

  Maximum accepted connection rate (e.g. 1/min, 60/sec)

.. cfgcmd:: set vpn l2tp remote-access limits timeout <value>

  Timeout in seconds

.. cfgcmd:: set vpn l2tp remote-access mtu

  Maximum Transmission Unit (MTU) (default: **1436**)

.. cfgcmd:: set vpn l2tp remote-access max-concurrent-sessions

  Maximum number of concurrent session start attempts

.. cfgcmd:: set vpn l2tp remote-access name-server <address>

  Connected clients should use `<address>` as their DNS server. This command
  accepts both IPv4 and IPv6 addresses. Up to two nameservers can be configured
  for IPv4, up to three for IPv6.

.. cfgcmd:: set vpn l2tp remote-access shaper fwmark <1-2147483647>

  Match firewall mark value

.. cfgcmd:: set vpn l2tp remote-access snmp master-agent

  Enable SNMP

.. cfgcmd:: set vpn l2tp remote-access wins-server <address>

  Windows Internet Name Service (WINS) servers propagated to client

**********
Monitoring
**********

.. code-block:: none

  vyos@vyos:~$ show l2tp-server sessions
   ifname | username |      ip       | ip6 | ip6-dp | calling-sid | rate-limit | state  |  uptime  | rx-bytes | tx-bytes
  --------+----------+---------------+-----+--------+-------------+------------+--------+----------+----------+----------
   l2tp0  | test     | 192.168.255.3 |     |        | 192.168.0.36 |            | active | 02:01:47 | 7.7 KiB  | 1.2 KiB

.. code-block:: none

    vyos@vyos:~$ show l2tp-server statistics
     uptime: 0.02:49:49
    cpu: 0%
    mem(rss/virt): 5920/100892 kB
    core:
      mempool_allocated: 133202
      mempool_available: 131770
      thread_count: 1
      thread_active: 1
      context_count: 5
      context_sleeping: 0
      context_pending: 0
      md_handler_count: 3
      md_handler_pending: 0
      timer_count: 0
      timer_pending: 0
    sessions:
      starting: 0
      active: 0
      finishing: 0
    l2tp:
      tunnels:
        starting: 0
        active: 0
        finishing: 0
      sessions (control channels):
        starting: 0
        active: 0
        finishing: 0
      sessions (data channels):
        starting: 0
        active: 0
        finishing: 0


.. _`Google Public DNS`: https://developers.google.com/speed/public-dns
.. _Quad9: https://quad9.net
.. _CloudFlare: https://blog.cloudflare.com/announcing-1111
.. _OpenNIC: https://www.opennic.org/
.. _RADIUS: https://en.wikipedia.org/wiki/RADIUS
.. _FreeRADIUS: https://freeradius.org
.. _`Network Policy Server`: https://en.wikipedia.org/wiki/Network_Policy_Server
.. _accel-ppp: https://accel-ppp.org/
.. _dictionary: https://github.com/accel-ppp/accel-ppp/blob/master/accel-pppd/radius/dict/dictionary.rfc6911
.. _`ACCEL-PPP attribute`: https://github.com/accel-ppp/accel-ppp/blob/master/accel-pppd/radius/dict/dictionary.accel
