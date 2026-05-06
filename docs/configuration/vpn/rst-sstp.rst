.. _sstp:

###########
SSTP Server
###########

:abbr:`SSTP (Secure Socket Tunneling Protocol)` is a form of :abbr:`VPN
(Virtual Private Network)` tunnel that provides a mechanism to transport PPP
traffic through an SSL/TLS channel. SSL/TLS provides transport-level security
with key negotiation, encryption and traffic integrity checking. The use of
SSL/TLS over TCP port 443 allows SSTP to pass through virtually all firewalls
and proxy servers except for authenticated web proxies.

SSTP is available for Linux, BSD, and Windows.

VyOS utilizes accel-ppp_ to provide SSTP server functionality. We support both
local and RADIUS authentication.

As SSTP provides PPP via a SSL/TLS channel the use of either publicly signed
certificates or private PKI is required.

***********************
Configuring SSTP Server
***********************

Certificates
============

Using our documentation chapter - :ref:`pki` generate and install CA and Server certificate

.. code-block:: none

    vyos@vyos:~$ generate pki ca install CA

.. code-block:: none

    vyos@vyos:~$ generate pki certificate sign CA install Server

Configuration
=============
.. code-block:: none

    set vpn sstp authentication local-users username test password 'test'
    set vpn sstp authentication mode 'local'
    set vpn sstp client-ip-pool SSTP-POOL range '10.0.0.2-10.0.0.100'
    set vpn sstp default-pool 'SSTP-POOL'
    set vpn sstp gateway-address '10.0.0.1'
    set vpn sstp ssl ca-certificate 'CA1'
    set vpn sstp ssl certificate 'Server'

.. cfgcmd:: set vpn sstp authentication mode <local | radius>

  Set authentication backend. The configured authentication backend is used
  for all queries.

  * **radius**: All authentication queries are handled by a configured RADIUS
    server.
  * **local**: All authentication queries are handled locally.

.. cfgcmd:: set vpn sstp authentication local-users username <user> password
   <pass>

  Create `<user>` for local authentication on this system. The users password
  will be set to `<pass>`.

.. cfgcmd:: set vpn sstp client-ip-pool <POOL-NAME> range <x.x.x.x-x.x.x.x | x.x.x.x/x>

   Use this command to define the first IP address of a pool of
   addresses to be given to SSTP clients. If notation ``x.x.x.x-x.x.x.x``,
   it must be within a /24 subnet. If notation ``x.x.x.x/x`` is
   used there is possibility to set host/netmask.

.. cfgcmd:: set vpn sstp default-pool <POOL-NAME>

   Use this command to define default address pool name.

.. cfgcmd:: set vpn sstp gateway-address <gateway>

  Specifies single `<gateway>` IP address to be used as local address of PPP
  interfaces.

.. cfgcmd:: set vpn sstp ssl ca-certificate <file>

  Name of installed certificate authority certificate.

.. cfgcmd:: set vpn sstp ssl certificate <file>

  Name of installed server certificate.

*********************************
Configuring RADIUS authentication
*********************************

To enable RADIUS based authentication, the authentication mode needs to be
changed within the configuration. Previous settings like the local users still
exist within the configuration, however they are not used if the mode has been
changed from local to radius. Once changed back to local, it will use all local
accounts again.

.. code-block:: none

  set vpn sstp authentication mode radius

.. cfgcmd:: set vpn sstp authentication radius server <server> key <secret>

  Configure RADIUS `<server>` and its required shared `<secret>` for
  communicating with the RADIUS server.

Since the RADIUS server would be a single point of failure, multiple RADIUS
servers can be setup and will be used subsequentially.
For example:

.. code-block:: none

  set vpn sstp authentication radius server 10.0.0.1 key 'foo'
  set vpn sstp authentication radius server 10.0.0.2 key 'foo'

.. note:: Some RADIUS severs use an access control list which allows or denies
   queries, make sure to add your VyOS router to the allowed client list.

RADIUS source address
=====================

If you are using OSPF as your IGP, use the interface connected closest to the
RADIUS server. You can bind all outgoing RADIUS requests to a single source IP
e.g. the loopback interface.

.. cfgcmd:: set vpn sstp authentication radius source-address <address>

  Source IPv4 address used in all RADIUS server queires.

.. note:: The ``source-address`` must be configured to that of an interface.
   Best practice would be a loopback or dummy interface.

RADIUS advanced options
=======================

.. cfgcmd:: set vpn sstp authentication radius server <server> port <port>

  Configure RADIUS `<server>` and its required port for authentication requests.

.. cfgcmd:: set vpn sstp authentication radius server <server> fail-time <time>

  Mark RADIUS server as offline for this given `<time>` in seconds.

.. cfgcmd:: set vpn sstp authentication radius server <server> disable

  Temporary disable this RADIUS server.

.. cfgcmd:: set vpn sstp authentication radius acct-timeout <timeout>

  Timeout to wait reply for Interim-Update packets. (default 3 seconds)

.. cfgcmd:: set vpn sstp authentication radius dynamic-author server <address>

  Specifies IP address for Dynamic Authorization Extension server (DM/CoA).
  This IP must exist on any VyOS interface or it can be ``0.0.0.0``.

.. cfgcmd:: set vpn sstp authentication radius dynamic-author port <port>

  UDP port for Dynamic Authorization Extension server (DM/CoA)

.. cfgcmd:: set vpn sstp authentication radius dynamic-author key <secret>

  Secret for Dynamic Authorization Extension server (DM/CoA)

.. cfgcmd:: set vpn sstp authentication radius max-try <number>

  Maximum number of tries to send Access-Request/Accounting-Request queries

.. cfgcmd:: set vpn sstp authentication radius timeout <timeout>

  Timeout to wait response from server (seconds)

.. cfgcmd:: set vpn sstp authentication radius nas-identifier <identifier>

  Value to send to RADIUS server in NAS-Identifier attribute and to be matched
  in DM/CoA requests.

.. cfgcmd:: set vpn sstp authentication radius nas-ip-address <address>

  Value to send to RADIUS server in NAS-IP-Address attribute and to be matched
  in DM/CoA requests. Also DM/CoA server will bind to that address.

.. cfgcmd:: set vpn sstp authentication radius source-address <address>

  Source IPv4 address used in all RADIUS server queires.

.. cfgcmd:: set vpn sstp authentication radius rate-limit attribute <attribute>

  Specifies which RADIUS server attribute contains the rate limit information.
  The default attribute is `Filter-Id`.

.. note:: If you set a custom RADIUS attribute you must define it on both
   dictionaries on the RADIUS server and client.

.. cfgcmd:: set vpn sstp authentication radius rate-limit enable

  Enables bandwidth shaping via RADIUS.

.. cfgcmd:: set vpn sstp authentication radius rate-limit vendor

  Specifies the vendor dictionary, This dictionary needs to be present in
  /usr/share/accel-ppp/radius.

Received RADIUS attributes have a higher priority than parameters defined within
the CLI configuration, refer to the explanation below.

Allocation clients ip addresses by RADIUS
=========================================

If the RADIUS server sends the attribute ``Framed-IP-Address`` then this IP
address will be allocated to the client and the option ``default-pool`` within
the CLI config will being ignored.

If the RADIUS server sends the attribute ``Framed-Pool``, then the IP address
will be allocated from a predefined IP pool whose name equals the attribute
value.

If the RADIUS server sends the attribute ``Stateful-IPv6-Address-Pool``, the
IPv6 address will be allocated from a predefined IPv6 pool ``prefix`` whose
name equals the attribute value.

If the RADIUS server sends the attribute ``Delegated-IPv6-Prefix-Pool``, an
IPv6 delegation prefix will be allocated from a predefined IPv6 pool ``delegate``
whose name equals the attribute value.

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


****
IPv6
****
.. cfgcmd:: set vpn sstp ppp-options ipv6 <require | prefer | allow | deny>

  Specifies IPv6 negotiation preference.

  * **require** - Require IPv6 negotiation
  * **prefer** - Ask client for IPv6 negotiation, do not fail if it rejects
  * **allow** - Negotiate IPv6 only if client requests
  * **deny** - Do not negotiate IPv6 (default value)

.. cfgcmd:: set vpn sstp client-ipv6-pool <IPv6-POOL-NAME> prefix <address>
   mask <number-of-bits>

  Use this comand to set the IPv6 address pool from which an SSTP client will
  get an IPv6 prefix of your defined length (mask) to terminate the SSTP
  endpoint at their side. The mask length can be set between 48 and 128 bits
  long, the default value is 64.

.. cfgcmd:: set vpn sstp client-ipv6-pool <IPv6-POOL-NAME> delegate <address>
   delegation-prefix <number-of-bits>

  Use this command to configure DHCPv6 Prefix Delegation (RFC3633) on SSTP. You
  will have to set your IPv6 pool and the length of the delegation prefix. From
  the defined IPv6 pool you will be handing out networks of the defined length
  (delegation-prefix). The length of the delegation prefix can be set between 
  32 and 64 bits long.

.. cfgcmd:: set vpn sstp default-ipv6-pool <IPv6-POOL-NAME>

   Use this command to define default IPv6 address pool name.

.. code-block:: none

  set vpn sstp ppp-options ipv6 allow
  set vpn sstp client-ipv6-pool IPv6-POOL delegate '2001:db8:8003::/48' delegation-prefix '56'
  set vpn sstp client-ipv6-pool IPv6-POOL prefix '2001:db8:8002::/48' mask '64'
  set vpn sstp default-ipv6-pool IPv6-POOL

IPv6 Advanced Options
=====================
.. cfgcmd:: set vpn sstp ppp-options ipv6-accept-peer-interface-id

  Accept peer interface identifier. By default this is not defined.

.. cfgcmd:: set vpn sstp ppp-options ipv6-interface-id <random | x:x:x:x>

  Specifies if a fixed or random interface identifier is used for IPv6. The
  default is fixed.

  * **random** - Random interface identifier for IPv6
  * **x:x:x:x** - Specify interface identifier for IPv6

.. cfgcmd:: set vpn sstp ppp-options ipv6-interface-id <random | x:x:x:x>

  Specifies the peer interface identifier for IPv6. The default is fixed.

  * **random** - Random interface identifier for IPv6
  * **x:x:x:x** - Specify interface identifier for IPv6
  * **ipv4-addr** - Calculate interface identifier from IPv4 address.
  * **calling-sid** - Calculate interface identifier from calling-station-id.

*********
Scripting
*********

.. cfgcmd:: set vpn sstp extended-scripts on-change <path_to_script>

  Script to run when the session interface is changed by RADIUS CoA handling

.. cfgcmd:: set vpn sstp extended-scripts on-down <path_to_script>

  Script to run when the session interface about to terminate

.. cfgcmd:: set vpn sstp extended-scripts on-pre-up <path_to_script>

  Script to run before the session interface comes up

.. cfgcmd:: set vpn sstp extended-scripts on-up <path_to_script>

  Script to run when the session interface is completely configured and started

****************
Advanced Options
****************

Authentication Advanced Options
===============================

.. cfgcmd:: set vpn sstp authentication local-users username <user> disable

  Disable `<user>` account.

.. cfgcmd:: set vpn sstp authentication local-users username <user> static-ip
   <address>

  Assign a static IP address to `<user>` account.

.. cfgcmd:: set vpn sstp authentication local-users username <user> rate-limit
   download <bandwidth>

  Rate limit the download bandwidth for `<user>` to `<bandwidth>` kbit/s.

.. cfgcmd:: set vpn sstp authentication local-users username <user> rate-limit
   upload <bandwidth>

  Rate limit the upload bandwidth for `<user>` to `<bandwidth>` kbit/s.

.. cfgcmd:: set vpn sstp authentication protocols
   <pap | chap | mschap | mschap-v2>

  Require the peer to authenticate itself using one of the following protocols:
  pap, chap, mschap, mschap-v2.

Client IP Pool Advanced Options
===============================

.. cfgcmd:: set vpn sstp client-ip-pool <POOL-NAME> next-pool <NEXT-POOL-NAME>

   Use this command to define the next address pool name.

PPP Advanced Options
====================

.. cfgcmd:: set vpn sstp ppp-options disable-ccp

  Disable Compression Control Protocol (CCP).
  CCP is enabled by default.

.. cfgcmd:: set vpn sstp ppp-options interface-cache <number>

  Specifies number of interfaces to cache. This prevents interfaces from being
  removed once the corresponding session is destroyed. Instead, interfaces are
  cached for later use in new sessions. This should reduce the kernel-level
  interface creation/deletion rate.
  Default value is **0**.

.. cfgcmd:: set vpn sstp ppp-options ipv4 <require | prefer | allow | deny>

  Specifies IPv4 negotiation preference.

  * **require** - Require IPv4 negotiation
  * **prefer** - Ask client for IPv4 negotiation, do not fail if it rejects
  * **allow** - Negotiate IPv4 only if client requests (Default value)
  * **deny** - Do not negotiate IPv4

.. cfgcmd:: set vpn sstp ppp-options lcp-echo-failure <number>

  Defines the maximum `<number>` of unanswered echo requests. Upon reaching the
  value `<number>`, the session will be reset. Default value is **3**.

.. cfgcmd:: set vpn sstp ppp-options lcp-echo-interval <interval>

  If this option is specified and is greater than 0, then the PPP module will
  send LCP echo requests every `<interval>` seconds.
  Default value is **30**.

.. cfgcmd:: set vpn sstp ppp-options lcp-echo-timeout

  Specifies timeout in seconds to wait for any peer activity. If this option is
  specified it turns on adaptive lcp echo functionality and "lcp-echo-failure"
  is not used. Default value is **0**.

.. cfgcmd:: set vpn sstp ppp-options min-mtu <number>

  Defines the minimum acceptable MTU. If a client tries to negotiate an MTU
  lower than this it will be NAKed, and disconnected if it rejects a greater
  MTU.
  Default value is **100**.

.. cfgcmd:: set vpn sstp ppp-options mppe <require | prefer | deny>

  Specifies :abbr:`MPPE (Microsoft Point-to-Point Encryption)` negotiation
  preference.

  * **require** - ask client for mppe, if it rejects drop connection
  * **prefer** - ask client for mppe, if it rejects don't fail. (Default value)
  * **deny** - deny mppe

  Default behavior - don't ask the client for mppe, but allow it if the client
  wants.
  Please note that RADIUS may override this option by MS-MPPE-Encryption-Policy
  attribute.

.. cfgcmd:: set vpn sstp ppp-options mru <number>

  Defines preferred MRU. By default is not defined.

Global Advanced options
=======================

.. cfgcmd:: set vpn sstp description <description>

  Set description.

.. cfgcmd::  set vpn sstp limits burst <value>

  Burst count

.. cfgcmd:: set vpn sstp limits connection-limit <value>

  Maximum accepted connection rate (e.g. 1/min, 60/sec)

.. cfgcmd:: set vpn sstp limits timeout <value>

  Timeout in seconds

.. cfgcmd:: set vpn sstp mtu

  Maximum Transmission Unit (MTU) (default: **1500**)

.. cfgcmd:: set vpn sstp max-concurrent-sessions

  Maximum number of concurrent session start attempts

.. cfgcmd:: set vpn sstp name-server <address>

  Connected clients should use `<address>` as their DNS server. This command
  accepts both IPv4 and IPv6 addresses. Up to two nameservers can be configured
  for IPv4, up to three for IPv6.

.. cfgcmd:: set vpn sstp shaper fwmark <1-2147483647>

  Match firewall mark value

.. cfgcmd:: set vpn sstp snmp master-agent

  Enable SNMP

.. cfgcmd:: set vpn sstp wins-server <address>

  Windows Internet Name Service (WINS) servers propagated to client

.. cfgcmd:: set vpn sstp host-name <hostname>

  If this option is given, only SSTP connections to the specified host
  and with the same TLS SNI will be allowed.

***********************
Configuring SSTP client
***********************

Once you have setup your SSTP server there comes the time to do some basic
testing. The Linux client used for testing is called sstpc_. sstpc_ requires a
PPP configuration/peer file.

If you use a self-signed certificate, do not forget to install CA on the client side.

The following PPP configuration tests MSCHAP-v2:

.. code-block:: none

  $ cat /etc/ppp/peers/vyos
  usepeerdns
  #require-mppe
  #require-pap
  require-mschap-v2
  noauth
  lock
  refuse-pap
  refuse-eap
  refuse-chap
  refuse-mschap
  #refuse-mschap-v2
  nobsdcomp
  nodeflate
  debug


You can now "dial" the peer with the follwoing command: ``sstpc --log-level 4
--log-stderr --user vyos --password vyos vpn.example.com -- call vyos``.

A connection attempt will be shown as:

.. code-block:: none

  $ sstpc --log-level 4 --log-stderr --user vyos --password vyos vpn.example.com -- call vyos

  Mar 22 13:29:12 sstpc[12344]: Resolved vpn.example.com to 192.0.2.1
  Mar 22 13:29:12 sstpc[12344]: Connected to vpn.example.com
  Mar 22 13:29:12 sstpc[12344]: Sending Connect-Request Message
  Mar 22 13:29:12 sstpc[12344]: SEND SSTP CRTL PKT(14)
  Mar 22 13:29:12 sstpc[12344]:   TYPE(1): CONNECT REQUEST, ATTR(1):
  Mar 22 13:29:12 sstpc[12344]:     ENCAP PROTO(1): 6
  Mar 22 13:29:12 sstpc[12344]: RECV SSTP CRTL PKT(48)
  Mar 22 13:29:12 sstpc[12344]:   TYPE(2): CONNECT ACK, ATTR(1):
  Mar 22 13:29:12 sstpc[12344]:     CRYPTO BIND REQ(4): 40
  Mar 22 13:29:12 sstpc[12344]: Started PPP Link Negotiation
  Mar 22 13:29:15 sstpc[12344]: Sending Connected Message
  Mar 22 13:29:15 sstpc[12344]: SEND SSTP CRTL PKT(112)
  Mar 22 13:29:15 sstpc[12344]:   TYPE(4): CONNECTED, ATTR(1):
  Mar 22 13:29:15 sstpc[12344]:     CRYPTO BIND(3): 104
  Mar 22 13:29:15 sstpc[12344]: Connection Established

  $ ip addr show ppp0
  164: ppp0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1452 qdisc fq_codel state UNKNOWN group default qlen 3
       link/ppp  promiscuity 0
       inet 100.64.2.2 peer 100.64.1.1/32 scope global ppp0
          valid_lft forever preferred_lft forever

**********
Monitoring
**********

.. opcmd:: show sstp-server sessions

   Use this command to locally check the active sessions in the SSTP
   server.

.. code-block:: none

    vyos@vyos:~$ show sstp-server sessions
     ifname | username |    ip    | ip6 | ip6-dp |   calling-sid  | rate-limit | state  |  uptime  | rx-bytes | tx-bytes
    --------+----------+----------+-----+--------+----------------+------------+--------+----------+----------+----------
     sstp0  | test     | 10.0.0.2 |     |        | 192.168.10.100 |            | active | 00:15:46 | 16.3 KiB | 210 B

.. code-block:: none

    vyos@vyos:~$ show sstp-server statistics
     uptime: 0.01:21:54
    cpu: 0%
    mem(rss/virt): 6688/100464 kB
    core:
      mempool_allocated: 149420
      mempool_available: 146092
      thread_count: 1
      thread_active: 1
      context_count: 6
      context_sleeping: 0
      context_pending: 0
      md_handler_count: 7
      md_handler_pending: 0
      timer_count: 2
      timer_pending: 0
    sessions:
      starting: 0
      active: 1
      finishing: 0
    sstp:
      starting: 0
      active: 1

***************
Troubleshooting
***************

.. code-block:: none

    vyos@vyos:~$sudo journalctl -u accel-ppp@sstp -b 0

    Feb 28 17:03:04 vyos accel-sstp[2492]: sstp: new connection from 192.168.10.100:49852
    Feb 28 17:03:04 vyos accel-sstp[2492]: sstp: starting
    Feb 28 17:03:04 vyos accel-sstp[2492]: sstp: started
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: recv [HTTP <SSTP_DUPLEX_POST /sra_{BA195980-CD49-458b-9E23-C84EE0ADCD75}/ HTTP/1.1>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: recv [HTTP <SSTPCORRELATIONID: {48B82435-099A-4158-A987-052E7570CFAA}>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: recv [HTTP <Content-Length: 18446744073709551615>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: recv [HTTP <Host: vyos.io>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: send [HTTP <HTTP/1.1 200 OK>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: send [HTTP <Date: Wed, 28 Feb 2024 17:03:04 GMT>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: send [HTTP <Content-Length: 18446744073709551615>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: recv [SSTP SSTP_MSG_CALL_CONNECT_REQUEST]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: send [SSTP SSTP_MSG_CALL_CONNECT_ACK]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: lcp_layer_init
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: auth_layer_init
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: ccp_layer_init
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: ipcp_layer_init
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: ipv6cp_layer_init
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: ppp establishing
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: lcp_layer_start
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: send [LCP ConfReq id=56 <auth PAP> <mru 1452> <magic 1cd9ad05>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: recv [LCP ConfReq id=0 <mru 4091> <magic 345f64ca> <pcomp> <accomp> < d 3 6 >]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: send [LCP ConfRej id=0 <pcomp> <accomp> < d 3 6 >]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: recv [LCP ConfReq id=1 <mru 4091> <magic 345f64ca>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: send [LCP ConfNak id=1 <mru 1452>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: recv [LCP ConfReq id=2 <mru 1452> <magic 345f64ca>]
    Feb 28 17:03:04 vyos accel-sstp[2492]: :: send [LCP ConfAck id=2]
    Feb 28 17:03:07 vyos accel-sstp[2492]: :: fsm timeout 9
    Feb 28 17:03:07 vyos accel-sstp[2492]: :: send [LCP ConfReq id=56 <auth PAP> <mru 1452> <magic 1cd9ad05>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: :: recv [LCP ConfAck id=56 <auth PAP> <mru 1452> <magic 1cd9ad05>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: :: lcp_layer_started
    Feb 28 17:03:07 vyos accel-sstp[2492]: :: auth_layer_start
    Feb 28 17:03:07 vyos accel-sstp[2492]: :: recv [LCP Ident id=3 <MSRASV5.20>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: :: recv [LCP Ident id=4 <MSRAS-0-MSEDGEWIN10>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: [50B blob data]
    Feb 28 17:03:07 vyos accel-sstp[2492]: :: recv [PAP AuthReq id=3]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: connect: ppp0 <--> sstp(192.168.10.100:49852)
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: ppp connected
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: send [PAP AuthAck id=3 "Authentication succeeded"]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: test: authentication succeeded
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: auth_layer_started
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: ccp_layer_start
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: ipcp_layer_start
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: ipv6cp_layer_start
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: recv [SSTP SSTP_MSG_CALL_CONNECTED]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: IPV6CP: discarding packet
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: send [LCP ProtoRej id=88 <8057>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: recv [IPCP ConfReq id=7 <addr 0.0.0.0> <dns1 0.0.0.0> <wins1 0.0.0.0> <dns2 0.0.0.0> <wins2 0.0.0.0>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: send [IPCP ConfReq id=25 <addr 10.0.0.1>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: send [IPCP ConfRej id=7 <dns1 0.0.0.0> <wins1 0.0.0.0> <dns2 0.0.0.0> <wins2 0.0.0.0>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: recv [IPCP ConfAck id=25 <addr 10.0.0.1>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: recv [IPCP ConfReq id=8 <addr 0.0.0.0>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: send [IPCP ConfNak id=8 <addr 10.0.0.5>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: recv [IPCP ConfReq id=9 <addr 10.0.0.5>]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: send [IPCP ConfAck id=9]
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: ipcp_layer_started
    Feb 28 17:03:07 vyos accel-sstp[2492]: ppp0:test: rename interface to 'sstp0'
    Feb 28 17:03:07 vyos accel-sstp[2492]: sstp0:test: sstp: ppp: started

.. _sstpc: https://github.com/reliablehosting/sstp-client
.. _dictionary: https://github.com/accel-ppp/accel-ppp/blob/master/accel-pppd/radius/dict/dictionary.rfc6911
.. _`ACCEL-PPP attribute`: https://github.com/accel-ppp/accel-ppp/blob/master/accel-pppd/radius/dict/dictionary.accel
.. include:: /_include/common-references.txt
