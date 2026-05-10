:lastproofread: 2024-06-14

.. _examples-zone-policy:

###################
Zone-Policy example
###################

.. note:: In :vytask:`T2199` the syntax of the zone configuration was changed.
   The zone configuration moved from ``zone-policy zone <name>`` to ``firewall
   zone <name>``.

Native IPv4 and IPv6
^^^^^^^^^^^^^^^^^^^^

We have three networks.

.. code-block:: none

  WAN - 172.16.10.0/24, 2001:0DB8:0:9999::0/64
  LAN - 192.168.100.0/24, 2001:0DB8:0:AAAA::0/64
  DMZ - 192.168.200.0/24, 2001:0DB8:0:BBBB::0/64


**This specific example is for a router on a stick, but is very easily
adapted for however many NICs you have**:


* Internet - 192.168.200.100 - TCP/80
* Internet - 192.168.200.100 - TCP/443
* Internet - 192.168.200.100 - TCP/25
* Internet - 192.168.200.100 - TCP/53
* VyOS acts as DHCP, DNS forwarder, NAT, router and firewall.
* 192.168.200.200/2001:0DB8:0:BBBB::200 is an internal/external DNS, web
  and mail (SMTP/IMAP) server.
* 192.168.100.10/2001:0DB8:0:AAAA::10 is the administrator's console. It
  can SSH to VyOS.
* LAN and DMZ hosts have basic outbound access: Web, FTP, SSH.
* LAN can access DMZ resources.
* DMZ cannot access LAN resources.
* Inbound WAN connect to DMZ host.

.. image:: /_static/images/zone-policy-diagram.*
   :width: 80%
   :align: center
   :alt: Network Topology Diagram

The VyOS interface is assigned the .1/:1 address of their respective
networks. WAN is on VLAN 10, LAN on VLAN 20, and DMZ on VLAN 30.

It will look something like this:

.. code-block:: none

  interfaces {
      ethernet eth0 {
          duplex auto
          hw-id 00:53:ed:6e:2a:92
          smp_affinity auto
          speed auto
          vif 10 {
              address 172.16.10.1/24
              address 2001:db8:0:9999::1/64
          }
          vif 20 {
              address 192.168.100.1/24
              address 2001:db8:0:AAAA::1/64
          }
          vif 30 {
              address 192.168.200.1/24
              address 2001:db8:0:BBBB::1/64
          }
      }
      loopback lo {
      }
  }


Zones Basics
^^^^^^^^^^^^

Each interface is assigned to a zone. The interface can be physical or
virtual such as tunnels (VPN, PPTP, GRE, etc) and are treated exactly
the same.

Traffic flows from zone A to zone B. That flow is what I refer to as a
zone-pair-direction. eg. A->B and B->A are two zone-pair-destinations.

Ruleset are created per zone-pair-direction.

I name rule sets to indicate which zone-pair-direction they represent.
eg. ZoneA-ZoneB or ZoneB-ZoneA. LAN-DMZ, DMZ-LAN.

In VyOS, you have to have unique Ruleset names. In the event of overlap,
I add a "-6" to the end of v6 rulesets. eg. LAN-DMZ, LAN-DMZ-6. This
allows for each auto-completion and uniqueness.

In this example we have 4 zones. LAN, WAN, DMZ, Local. The local zone is
the firewall itself.

If your computer is on the LAN and you need to SSH into your VyOS box,
you would need a rule to allow it in the LAN-Local ruleset. If you want
to access a webpage from your VyOS box, you need a rule to allow it in
the Local-LAN ruleset.

In rules, it is good to keep them named consistently. As the number of
rules you have grows, the more consistency you have, the easier your
life will be.

.. code-block:: none

  Rule 1 - State Established, Related
  Rule 2 - State Invalid
  Rule 100 - ICMP
  Rule 200 - Web
  Rule 300 - FTP
  Rule 400 - NTP
  Rule 500 - SMTP
  Rule 600 - DNS
  Rule 700 - DHCP
  Rule 800 - SSH
  Rule 900 - IMAPS

The first two rules are to deal with the idiosyncrasies of VyOS and
iptables.

Zones and Rulesets both have a default action statement. When using
Zone-Policies, the default action is set by the zone-policy statement
and is represented by rule 10000.

It is good practice to log both accepted and denied traffic. It can save
you significant headaches when trying to troubleshoot a connectivity
issue.

To add logging to the default rule, do:

.. code-block:: none

  set firewall name <ruleSet> default-log


By default, iptables does not allow traffic for established sessions to
return, so you must explicitly allow this. I do this by adding two rules
to every ruleset. 1 allows established and related state packets through
and rule 2 drops and logs invalid state packets. We place the
established/related rule at the top because the vast majority of traffic
on a network is established and the invalid rule to prevent invalid
state packets from mistakenly being matched against other rules. Having
the most matched rule listed first reduces CPU load in high volume
environments. Note: I have filed a bug to have this added as a default
action as well.

''It is important to note, that you do not want to add logging to the
established state rule as you will be logging both the inbound and
outbound packets for each session instead of just the initiation of the
session. Your logs will be massive in a very short period of time.''

In VyOS you must have the interfaces created before you can apply it to
the zone and the rulesets must be created prior to applying it to a
zone-policy.

I create/configure the interfaces first. Build out the rulesets for each
zone-pair-direction which includes at least the three state rules. Then
I setup the zone-policies.

Zones do not allow for a default action of accept; either drop or
reject. It is important to remember this because if you apply an
interface to a zone and commit, any active connections will be dropped.
Specifically, if you are SSH’d into VyOS and add local or the interface
you are connecting through to a zone and do not have rulesets in place
to allow SSH and established sessions, you will not be able to connect.

The following are the rules that were created for this example (may not
be complete), both in IPv4 and IPv6. If there is no IP specified, then
the source/destination address is not explicit.

.. code-block:: none

  WAN - DMZ:192.168.200.200 - tcp/80
  WAN - DMZ:192.168.200.200 - tcp/443
  WAN - DMZ:192.168.200.200 - tcp/25
  WAN - DMZ:192.168.200.200 - tcp/53
  WAN - DMZ:2001:0DB8:0:BBBB::200 - tcp/80
  WAN - DMZ:2001:0DB8:0:BBBB::200 - tcp/443
  WAN - DMZ:2001:0DB8:0:BBBB::200 - tcp/25
  WAN - DMZ:2001:0DB8:0:BBBB::200 - tcp/53

  DMZ - Local - tcp/53
  DMZ - Local - tcp/123
  DMZ - Local - tcp/67,68

  LAN - Local - tcp/53
  LAN - Local - tcp/123
  LAN - Local - tcp/67,68
  LAN:192.168.100.10 - Local - tcp/22
  LAN:2001:0DB8:0:AAAA::10 - Local - tcp/22

  LAN - WAN - tcp/80
  LAN - WAN - tcp/443
  LAN - WAN - tcp/22
  LAN - WAN - tcp/20,21

  DMZ - WAN - tcp/80
  DMZ - WAN - tcp/443
  DMZ - WAN - tcp/22
  DMZ - WAN - tcp/20,21
  DMZ - WAN - tcp/53
  DMZ - WAN - udp/53

  Local - WAN - tcp/80
  Local - WAN - tcp/443
  Local - WAN - tcp/20,21

  Local - DMZ - tcp/25
  Local - DMZ - tcp/67,68
  Local - DMZ - tcp/53
  Local - DMZ - udp/53

  Local - LAN - tcp/67,68

  LAN - DMZ - tcp/80
  LAN - DMZ - tcp/443
  LAN - DMZ - tcp/993
  LAN:2001:0DB8:0:AAAA::10 - DMZ:2001:0DB8:0:BBBB::200 - tcp/22
  LAN:192.168.100.10 - DMZ:192.168.200.200 - tcp/22

Since we have 4 zones, we need to setup the following rulesets.

.. code-block:: none

  Lan-wan
  Lan-local
  Lan-dmz
  Wan-lan
  Wan-local
  Wan-dmz
  Local-lan
  Local-wan
  Local-dmz
  Dmz-lan
  Dmz-wan
  Dmz-local

Even if the two zones will never communicate, it is a good idea to
create the zone-pair-direction rulesets and set default-log. This
will allow you to log attempts to access the networks. Without it, you
will never see the connection attempts.

This is an example of the three base rules.

.. code-block:: none

  name wan-lan {
    default-action drop
    default-log
    rule 1 {
      action accept
      state {
        established enable
        related enable
      }
    }
    rule 2 {
      action drop
      log enable
      state {
        invalid enable
      }
    }
  }


Here is an example of an IPv6 DMZ-WAN ruleset.

.. code-block:: none

  ipv6-name dmz-wan-6 {
    default-action drop
    default-log
    rule 1 {
      action accept
      state {
        established enable
        related enable
      }
    }
    rule 2 {
      action drop
      log enable
      state {
        invalid enable
    }
    rule 100 {
      action accept
      log enable
      protocol ipv6-icmp
    }
    rule 200 {
      action accept
      destination {
        port 80,443
      }
      log enable
      protocol tcp
    }
    rule 300 {
      action accept
      destination {
        port 20,21
      }
      log enable
      protocol tcp
    }
    rule 500 {
      action accept
      destination {
        port 25
      }
      log enable
      protocol tcp
      source {
        address 2001:db8:0:BBBB::200
      }
    }
    rule 600 {
      action accept
      destination {
        port 53
      }
      log enable
      protocol tcp_udp
      source {
        address 2001:db8:0:BBBB::200
      }
    }
    rule 800 {
      action accept
      destination {
      port 22
      }
      log enable
      protocol tcp
    }
  }

Once you have all of your rulesets built, then you need to create your
zone-policy.

Start by setting the interface and default action for each zone.

.. code-block:: none

  set firewall zone dmz default-action drop
  set firewall zone dmz interface eth0.30

In this case, we are setting the v6 ruleset that represents traffic
sourced from the LAN, destined for the DMZ. Because the zone-policy
firewall syntax is a little awkward, I keep it straight by thinking of
it backwards.

.. code-block:: none

  set firewall zone dmz from lan firewall ipv6-name lan-dmz-6

DMZ-LAN policy is LAN-DMZ. You can get a rhythm to it when you build out
a bunch at one time.

In the end, you will end up with something like this config. I took out
everything but the Firewall, Interfaces, and zone-policy sections. It is
long enough as is.


IPv6 Tunnel
^^^^^^^^^^^

If you are using a IPv6 tunnel from HE.net or someone else, the basis is
the same except you have two WAN interfaces. One for v4 and one for v6.

You would have 5 zones instead of just 4 and you would configure your v6
ruleset between your tunnel interface and your LAN/DMZ zones instead of
to the WAN.

LAN, WAN, DMZ, local and TUN (tunnel)

v6 pairs would be:

.. code-block:: none

  lan-tun
  lan-local
  lan-dmz
  tun-lan
  tun-local
  tun-dmz
  local-lan
  local-tun
  local-dmz
  dmz-lan
  dmz-tun
  dmz-local

Notice, none go to WAN since WAN wouldn't have a v6 address on it.

You would have to add a couple of rules on your wan-local ruleset to
allow protocol 41 in.

Something like:

.. code-block:: none

  rule 400 {
    action accept
    destination {
      address 172.16.10.1
    }
    log enable
    protocol 41
    source {
      address ip.of.tunnel.broker
    }
  }
