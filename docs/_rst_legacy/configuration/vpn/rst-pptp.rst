.. _pptp:

###########
PPTP-Server
###########

The Point-to-Point Tunneling Protocol (PPTP_) has been implemented in VyOS only
for backwards compatibility. PPTP has many well known security issues and you 
should use one of the many other new VPN implementations.

***********************
Configuring PPTP Server
***********************

.. code-block:: none

  set vpn pptp remote-access authentication mode local
  set vpn pptp remote-access authentication local-users username test password 'test'
  set vpn pptp remote-access client-ip-pool PPTP-POOL range 192.168.255.2-192.168.255.254
  set vpn pptp remote-access default-pool 'PPTP-POOL'
  set vpn pptp remote-access outside-address 192.0.2.2
  set vpn pptp remote-access gateway-address 192.168.255.1


.. cfgcmd:: set vpn pptp remote-access authentication mode <local | radius>

  Set authentication backend. The configured authentication backend is used
  for all queries.

  * **radius**: All authentication queries are handled by a configured RADIUS
    server.
  * **local**: All authentication queries are handled locally.
  * **noauth**: Authentication disabled.

.. cfgcmd:: set vpn pptp remote-access authentication local-users username <user> password
   <pass>

  Create `<user>` for local authentication on this system. The users password
  will be set to `<pass>`.

.. cfgcmd:: set vpn pptp remote-access client-ip-pool <POOL-NAME> range <x.x.x.x-x.x.x.x | x.x.x.x/x>

   Use this command to define the first IP address of a pool of
   addresses to be given to PPTP clients. If notation ``x.x.x.x-x.x.x.x``,
   it must be within a /24 subnet. If notation ``x.x.x.x/x`` is
   used there is possibility to set host/netmask.

.. cfgcmd:: set vpn pptp remote-access default-pool <POOL-NAME>

   Use this command to define default address pool name.

.. cfgcmd:: set vpn pptp remote-access gateway-address <gateway>

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

  set vpn pptp remote-access authentication mode radius

.. cfgcmd:: set vpn pptp remote-access authentication radius server <server> key <secret>

  Configure RADIUS `<server>` and its required shared `<secret>` for
  communicating with the RADIUS server.

Since the RADIUS server would be a single point of failure, multiple RADIUS
servers can be setup and will be used subsequentially.
For example:

.. code-block:: none

  set vpn pptp remote-access authentication radius server 10.0.0.1 key 'foo'
  set vpn pptp remote-access authentication radius server 10.0.0.2 key 'foo'

.. note:: Some RADIUS severs use an access control list which allows or denies
   queries, make sure to add your VyOS router to the allowed client list.

RADIUS source address
=====================

If you are using OSPF as IGP, always the closest interface connected to the
RADIUS server is used. You can bind all outgoing RADIUS requests
to a single source IP e.g. the loopback interface.

.. cfgcmd:: set vpn pptp remote-access authentication radius source-address <address>

  Source IPv4 address used in all RADIUS server queires.

.. note:: The ``source-address`` must be configured on one of VyOS interface.
   Best practice would be a loopback or dummy interface.

RADIUS advanced options
=======================

.. cfgcmd:: set vpn pptp remote-access authentication radius server <server> port <port>

  Configure RADIUS `<server>` and its required port for authentication requests.

.. cfgcmd:: set vpn pptp remote-access authentication radius server <server> fail-time <time>

  Mark RADIUS server as offline for this given `<time>` in seconds.

.. cfgcmd:: set vpn pptp remote-access authentication radius server <server> disable

  Temporary disable this RADIUS server.

.. cfgcmd:: set vpn pptp remote-access authentication radius acct-timeout <timeout>

  Timeout to wait reply for Interim-Update packets. (default 3 seconds)

.. cfgcmd:: set vpn pptp remote-access authentication radius dynamic-author server <address>

  Specifies IP address for Dynamic Authorization Extension server (DM/CoA). 
  This IP must exist on any VyOS interface or it can be ``0.0.0.0``.

.. cfgcmd:: set vpn pptp remote-access authentication radius dynamic-author port <port>

  UDP port for Dynamic Authorization Extension server (DM/CoA)

.. cfgcmd:: set vpn pptp remote-access authentication radius dynamic-author key <secret>

  Secret for Dynamic Authorization Extension server (DM/CoA)

.. cfgcmd:: set vpn pptp remote-access authentication radius max-try <number>

  Maximum number of tries to send Access-Request/Accounting-Request queries

.. cfgcmd:: set vpn pptp remote-access authentication radius timeout <timeout>

  Timeout to wait response from server (seconds)

.. cfgcmd:: set vpn pptp remote-access authentication radius nas-identifier <identifier>

  Value to send to RADIUS server in NAS-Identifier attribute and to be matched
  in DM/CoA requests.

.. cfgcmd:: set vpn pptp remote-access authentication radius nas-ip-address <address>

  Value to send to RADIUS server in NAS-IP-Address attribute and to be matched
  in DM/CoA requests. Also DM/CoA server will bind to that address.

.. cfgcmd:: set vpn pptp remote-access authentication radius source-address <address>

  Source IPv4 address used in all RADIUS server queires.

.. cfgcmd:: set vpn pptp remote-access authentication radius rate-limit attribute <attribute>

  Specifies which RADIUS server attribute contains the rate limit information.
  The default attribute is `Filter-Id`.

.. note:: If you set a custom RADIUS attribute you must define it on both
   dictionaries at RADIUS server and client.

.. cfgcmd:: set vpn pptp remote-access authentication radius rate-limit enable

  Enables bandwidth shaping via RADIUS.

.. cfgcmd:: set vpn pptp remote-access authentication radius rate-limit vendor

  Specifies the vendor dictionary, dictionary needs to be in
  /usr/share/accel-ppp/radius.

Received RADIUS attributes have a higher priority than parameters defined within
the CLI configuration, refer to the explanation below.

Allocation clients ip addresses by RADIUS
=========================================

If the RADIUS server sends the attribute ``Framed-IP-Address`` then this IP
address will be allocated to the client and the option ``default-pool`` within the CLI
config is being ignored.

If the RADIUS server sends the attribute ``Framed-Pool``, IP address will be allocated
from a predefined IP pool whose name equals the attribute value.

If the RADIUS server sends the attribute ``Stateful-IPv6-Address-Pool``, IPv6 address
will be allocated from a predefined IPv6 pool ``prefix`` whose name equals the attribute value.

If the RADIUS server sends the attribute ``Delegated-IPv6-Prefix-Pool``, IPv6
delegation pefix will be allocated from a predefined IPv6 pool ``delegate``
whose name equals the attribute value.

.. note:: ``Stateful-IPv6-Address-Pool`` and ``Delegated-IPv6-Prefix-Pool`` are defined in
          RFC6911. If they are not defined in your RADIUS server, add new dictionary_.

User interface can be put to VRF context via RADIUS Access-Accept packet, or change
it via RADIUS CoA. ``Accel-VRF-Name`` is used from these purposes. It is custom `ACCEL-PPP attribute`_.
Define it in your RADIUS server.

Renaming clients interfaces by RADIUS
=====================================

If the RADIUS server uses the attribute ``NAS-Port-Id``, ppp tunnels will be
renamed.

.. note:: The value of the attribute ``NAS-Port-Id`` must be less than 16
   characters, otherwise the interface won't be renamed.

****
IPv6
****
.. cfgcmd:: set vpn pptp remote-access ppp-options ipv6 <require | prefer | allow | deny>

  Specifies IPv6 negotiation preference.

  * **require** - Require IPv6 negotiation
  * **prefer** - Ask client for IPv6 negotiation, do not fail if it rejects
  * **allow** - Negotiate IPv6 only if client requests
  * **deny** - Do not negotiate IPv6 (default value)

.. cfgcmd:: set vpn pptp remote-access client-ipv6-pool <IPv6-POOL-NAME> prefix <address>
   mask <number-of-bits>

  Use this comand to set the IPv6 address pool from which an PPTP client
  will get an IPv6 prefix of your defined length (mask) to terminate the
  PPTP endpoint at their side. The mask length can be set from 48 to 128
  bit long, the default value is 64.

.. cfgcmd:: set vpn pptp remote-access client-ipv6-pool <IPv6-POOL-NAME> delegate <address>
   delegation-prefix <number-of-bits>

  Use this command to configure DHCPv6 Prefix Delegation (RFC3633) on
  PPTP. You will have to set your IPv6 pool and the length of the
  delegation prefix. From the defined IPv6 pool you will be handing out
  networks of the defined length (delegation-prefix). The length of the
  delegation prefix can be set from 32 to 64 bit long.

.. cfgcmd:: set vpn pptp remote-access default-ipv6-pool <IPv6-POOL-NAME>

   Use this command to define default IPv6 address pool name.

.. code-block:: none

  set vpn pptp remote-access ppp-options ipv6 allow
  set vpn pptp remote-access client-ipv6-pool IPv6-POOL delegate '2001:db8:8003::/48' delegation-prefix '56'
  set vpn pptp remote-access client-ipv6-pool IPv6-POOL prefix '2001:db8:8002::/48' mask '64'
  set vpn pptp remote-access default-ipv6-pool IPv6-POOL

IPv6 Advanced Options
=====================
.. cfgcmd:: set vpn pptp remote-access ppp-options ipv6-accept-peer-interface-id

  Accept peer interface identifier. By default is not defined.

.. cfgcmd:: set vpn pptp remote-access ppp-options ipv6-interface-id <random | x:x:x:x>

  Specifies fixed or random interface identifier for IPv6.
  By default is fixed.

  * **random** - Random interface identifier for IPv6
  * **x:x:x:x** - Specify interface identifier for IPv6

.. cfgcmd:: set vpn pptp remote-access ppp-options ipv6-interface-id <random | x:x:x:x>

  Specifies peer interface identifier for IPv6. By default is fixed.

  * **random** - Random interface identifier for IPv6
  * **x:x:x:x** - Specify interface identifier for IPv6
  * **ipv4-addr** - Calculate interface identifier from IPv4 address.
  * **calling-sid** - Calculate interface identifier from calling-station-id.

*********
Scripting
*********

.. cfgcmd:: set vpn pptp remote-access extended-scripts on-change <path_to_script>

  Script to run when session interface changed by RADIUS CoA handling

.. cfgcmd:: set vpn pptp remote-access extended-scripts on-down <path_to_script>

  Script to run when session interface going to terminate

.. cfgcmd:: set vpn pptp remote-access extended-scripts on-pre-up <path_to_script>

  Script to run before session interface comes up

.. cfgcmd:: set vpn pptp remote-access extended-scripts on-up <path_to_script>

  Script to run when session interface is completely configured and started

****************
Advanced Options
****************

Authentication Advanced Options
===============================

.. cfgcmd:: set vpn pptp remote-access authentication local-users username <user> disable

  Disable `<user>` account.

.. cfgcmd:: set vpn pptp remote-access authentication local-users username <user> static-ip
   <address>

  Assign static IP address to `<user>` account.

.. cfgcmd:: set vpn pptp remote-access authentication local-users username <user> rate-limit
   download <bandwidth>

  Download bandwidth limit in kbit/s for `<user>`.

.. cfgcmd:: set vpn pptp remote-access authentication local-users username <user> rate-limit
   upload <bandwidth>

  Upload bandwidth limit in kbit/s for `<user>`.

.. cfgcmd:: set vpn pptp remote-access authentication protocols
   <pap | chap | mschap | mschap-v2>

  Require the peer to authenticate itself using one of the following protocols:
  pap, chap, mschap, mschap-v2.

Client IP Pool Advanced Options
===============================

.. cfgcmd:: set vpn pptp remote-access client-ip-pool <POOL-NAME> next-pool <NEXT-POOL-NAME>

   Use this command to define the next address pool name.

PPP Advanced Options
====================

.. cfgcmd:: set vpn pptp remote-access ppp-options disable-ccp

  Disable Compression Control Protocol (CCP).
  CCP is enabled by default.

.. cfgcmd:: set vpn pptp remote-access ppp-options interface-cache <number>

  Specifies number of interfaces to keep in cache. It means that don’t
  destroy interface after corresponding session is destroyed, instead
  place it to cache and use it later for new sessions repeatedly.
  This should reduce kernel-level interface creation/deletion rate lack.
  Default value is **0**.

.. cfgcmd:: set vpn pptp remote-access ppp-options ipv4 <require | prefer | allow | deny>

  Specifies IPv4 negotiation preference.

  * **require** - Require IPv4 negotiation
  * **prefer** - Ask client for IPv4 negotiation, do not fail if it rejects
  * **allow** - Negotiate IPv4 only if client requests (Default value)
  * **deny** - Do not negotiate IPv4

.. cfgcmd:: set vpn pptp remote-access ppp-options lcp-echo-failure <number>

  Defines the maximum `<number>` of unanswered echo requests. Upon reaching the
  value `<number>`, the session will be reset. Default value is **3**.

.. cfgcmd:: set vpn pptp remote-access ppp-options lcp-echo-interval <interval>

  If this option is specified and is greater than 0, then the PPP module will
  send LCP pings of the echo request every `<interval>` seconds.
  Default value is **30**.

.. cfgcmd:: set vpn pptp remote-access ppp-options lcp-echo-timeout

  Specifies timeout in seconds to wait for any peer activity. If this option
  specified it turns on adaptive lcp echo functionality and "lcp-echo-failure"
  is not used. Default value is **0**.

.. cfgcmd:: set vpn pptp remote-access ppp-options min-mtu <number>

  Defines minimum acceptable MTU. If client will try to negotiate less then
  specified MTU then it will be NAKed or disconnected if rejects greater MTU.
  Default value is **100**.

.. cfgcmd:: set vpn pptp remote-access ppp-options mppe <require | prefer | deny>

  Specifies :abbr:`MPPE (Microsoft Point-to-Point Encryption)` negotiation
  preference.

  * **require** - ask client for mppe, if it rejects drop connection
  * **prefer** - ask client for mppe, if it rejects don't fail. (Default value)
  * **deny** - deny mppe

  Default behavior - don't ask client for mppe, but allow it if client wants.
  Please note that RADIUS may override this option by MS-MPPE-Encryption-Policy
  attribute.

.. cfgcmd:: set vpn pptp remote-access ppp-options mru <number>

  Defines preferred MRU. By default is not defined.

Global Advanced options
=======================

.. cfgcmd:: set vpn pptp remote-access description <description>

  Set description.

.. cfgcmd::  set vpn pptp remote-access limits burst <value>

  Burst count

.. cfgcmd:: set vpn pptp remote-access limits connection-limit <value>

  Acceptable rate of connections (e.g. 1/min, 60/sec)

.. cfgcmd:: set vpn pptp remote-access limits timeout <value>

  Timeout in seconds

.. cfgcmd:: set vpn pptp remote-access mtu

  Maximum Transmission Unit (MTU) (default: **1436**)

.. cfgcmd:: set vpn pptp remote-access max-concurrent-sessions

  Maximum number of concurrent session start attempts

.. cfgcmd:: set vpn pptp remote-access name-server <address>

  Connected client should use `<address>` as their DNS server. This
  command accepts both IPv4 and IPv6 addresses. Up to two nameservers
  can be configured for IPv4, up to three for IPv6.

.. cfgcmd:: set vpn pptp remote-access shaper fwmark <1-2147483647>

  Match firewall mark value

.. cfgcmd:: set vpn pptp remote-access snmp master-agent

  Enable SNMP

.. cfgcmd:: set vpn pptp remote-access wins-server <address>

  Windows Internet Name Service (WINS) servers propagated to client

**********
Monitoring
**********

.. opcmd:: show pptp-server sessions

   Use this command to locally check the active sessions in the PPTP
   server.

.. code-block:: none

    vyos@vyos:~$ show pptp-server sessions
     ifname | username |    ip    | ip6 | ip6-dp |   calling-sid  | rate-limit | state  |  uptime  | rx-bytes | tx-bytes
    --------+----------+----------+-----+--------+----------------+------------+--------+----------+----------+----------
     pptp0  | test     | 10.0.0.2 |     |        | 192.168.10.100 |            | active | 00:01:26 | 6.9 KiB  | 220 B

.. code-block:: none

    vyos@vyos:~$ show pptp-server statistics
     uptime: 0.00:04:52
    cpu: 0%
    mem(rss/virt): 5504/100176 kB
    core:
      mempool_allocated: 152007
      mempool_available: 149007
      thread_count: 1
      thread_active: 1
      context_count: 6
      context_sleeping: 0
      context_pending: 0
      md_handler_count: 6
      md_handler_pending: 0
      timer_count: 2
      timer_pending: 0
    sessions:
      starting: 0
      active: 1
      finishing: 0
    pptp:
      starting: 0
      active: 1

***************
Troubleshooting
***************

.. code-block:: none

    vyos@vyos:~$sudo journalctl -u accel-ppp@pptp -b 0

    Feb 29 14:58:57 vyos accel-pptp[4629]: pptp: new connection from 192.168.10.100
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: recv [PPTP Start-Ctrl-Conn-Request <Version 1> <Framing 1> <Bearer 1> <Max-Chan 0>]
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: send [PPTP Start-Ctrl-Conn-Reply <Version 1> <Result 1> <Error 0> <Framing 3> <Bearer 3> <Max-Chan 1>]
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: recv [PPTP Outgoing-Call-Request <Call-ID 2961> <Call-Serial 2> <Min-BPS 300> <Max-BPS 100000000> <Bearer 3> <Framing 3> <Window-Size 64> <Delay 0>]
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: send [PPTP Outgoing-Call-Reply <Call-ID 2> <Peer-Call-ID 2961> <Result 1> <Error 0> <Cause 0> <Speed 100000000> <Window-Size 64> <Delay 0> <Channel 0>]
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: lcp_layer_init
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: auth_layer_init
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: ccp_layer_init
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: ipcp_layer_init
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: ipv6cp_layer_init
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: ppp establishing
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: lcp_layer_start
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: send [LCP ConfReq id=75 <auth PAP> <mru 1436> <magic 483920bd>]
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: recv [PPTP Set-Link-Info]
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: recv [LCP ConfReq id=0 <mru 1400> <magic 0142785a> <pcomp> <accomp> < d 3 6 >]
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: send [LCP ConfRej id=0 <pcomp> <accomp> < d 3 6 >]
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: recv [LCP ConfReq id=1 <mru 1400> <magic 0142785a>]
    Feb 29 14:58:57 vyos accel-pptp[4629]: :: send [LCP ConfAck id=1]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: fsm timeout 9
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: send [LCP ConfReq id=75 <auth PAP> <mru 1436> <magic 483920bd>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: recv [LCP ConfNak id=75 <auth MSCHAP-v2>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: send [LCP ConfReq id=76 <auth CHAP-md5> <mru 1436> <magic 483920bd>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: recv [LCP ConfNak id=76 <auth MSCHAP-v2>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: send [LCP ConfReq id=77 <auth MSCHAP-v1> <mru 1436> <magic 483920bd>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: recv [LCP ConfNak id=77 <auth MSCHAP-v2>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: send [LCP ConfReq id=78 <auth MSCHAP-v2> <mru 1436> <magic 483920bd>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: recv [LCP ConfAck id=78 <auth MSCHAP-v2> <mru 1436> <magic 483920bd>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: lcp_layer_started
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: auth_layer_start
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: send [MSCHAP-v2 Challenge id=1 <8aa758781676e6a8e85c11963ee010>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: recv [LCP Ident id=2 <MSRASV5.20>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: recv [LCP Ident id=3 <MSRAS-0-MSEDGEWIN10>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: [43B blob data]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: recv [PPTP Set-Link-Info]
    Feb 29 14:59:00 vyos accel-pptp[4629]: :: recv [MSCHAP-v2 Response id=1 <90c21af1091f745e8bf22388b058>, <e695ae5aae274c88a3fa1ee3dc9057aece4d53c87b9fea>, F=0, name="test"]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: connect: ppp0 <--> pptp(192.168.10.100)
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: ppp connected
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: send [MSCHAP-v2 Success id=1 "S=347F417CF04BEBBC7F75CFA7F43474C36FB218F9 M=Authentication succeeded"]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: test: authentication succeeded
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: auth_layer_started
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: ccp_layer_start
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: send [CCP ConfReq id=b9 <mppe +H -M +S -L -D -C>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: ipcp_layer_start
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: ipv6cp_layer_start
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: IPV6CP: discarding packet
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: send [LCP ProtoRej id=122 <8057>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: recv [IPCP ConfReq id=6 <addr 0.0.0.0> <dns1 0.0.0.0> <wins1 0.0.0.0> <dns2 0.0.0.0> <wins2 0.0.0.0>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: send [IPCP ConfReq id=3b <addr 10.0.0.1>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: send [IPCP ConfRej id=6 <dns1 0.0.0.0> <wins1 0.0.0.0> <dns2 0.0.0.0> <wins2 0.0.0.0>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: recv [LCP ProtoRej id=7 <80fd>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: ccp_layer_finished
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: recv [IPCP ConfAck id=3b <addr 10.0.0.1>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: recv [IPCP ConfReq id=8 <addr 0.0.0.0>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: send [IPCP ConfNak id=8 <addr 10.0.0.2>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: recv [IPCP ConfReq id=9 <addr 10.0.0.2>]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: send [IPCP ConfAck id=9]
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: ipcp_layer_started
    Feb 29 14:59:00 vyos accel-pptp[4629]: ppp0:test: rename interface to 'pptp0'
    Feb 29 14:59:00 vyos accel-pptp[4629]: pptp0:test: pptp: ppp started

.. _accel-ppp: https://accel-ppp.org/
.. _dictionary: https://github.com/accel-ppp/accel-ppp/blob/master/accel-pppd/radius/dict/dictionary.rfc6911
.. _`ACCEL-PPP attribute`: https://github.com/accel-ppp/accel-ppp/blob/master/accel-pppd/radius/dict/dictionary.accel
