:description: Overview of the VyOS project's history, from its 2013 fork of Vyatta Core
              through each major LTS release. Covers release codenames, base Debian
              versions, and the headline features introduced in each version.
:keywords: vyos history, vyatta fork, lts release, scutum, circinus, sagitta, 
           equuleus, crux, debian

.. _history:

#######
History
#######

In the beginning...
===================

There was a network operating system based on Debian GNU/Linux, called 
Vyatta. [*]_ Introduced in 2006, it served as a great free-software alternative 
to proprietary products. Vyatta came in two editions: Vyatta Core 
(formerly known as Vyatta Community Edition), which was free software, and 
Vyatta Subscription Edition, which included proprietary features and was 
available only to paying customers.

Brocade Communications Systems acquired Vyatta in 2012. Shortly after, Brocade
renamed Vyatta Subscription Edition to Brocade vRouter, discontinued Vyatta 
Core, and shut down the community forum without notice. The bug tracker and Git 
repositories were closed the following year.

By the time Brocade acquired Vyatta, the development of Vyatta Core had 
already stagnated. The focus had shifted to Vyatta Subscription Edition, 
where core components were replaced with proprietary software. As a result, 
Vyatta Core received fewer new features, and some of those added faced issues.

In 2013, shortly after Vyatta Core was discontinued, the community forked its 
final version (6.6R1) to create the VyOS project. In 2014, the maintainers 
established a company to fund VyOS development through technical support, 
consulting services, and LTS release access subscriptions. The company was 
originally named Sentrium and was later reorganized under the VyOS brand.


Major releases
==============
VyOS originally named its major versions after elements by atomic number. 
Beginning with version 1.2, this naming scheme was changed. It now uses the 
Latin names of constellations recognized by the International Astronomical 
Union (`IAU
<https://en.wikipedia.org/wiki/IAU_designated_constellations_by_area>`_), 
ordered by their solid angle area, beginning with the smallest.

Hydrogen (1.0)
--------------
Released just in time for the holidays on 22 December 2013, Hydrogen was
the first major VyOS release. It fixed features that were broken in
Vyatta Core 6.6, such as IPv4 BGP peer groups and DHCPv6 relay, and
introduced command scripting, a task scheduler, and web proxy LDAP
authentication.

Helium (1.1)
------------
Helium, released on 9 October 2014, marked the first anniversary of the 
VyOS Project. The release introduced an event handler, L2TPv3 support, 
802.1ad (QinQ), and IGMP proxy, as well as experimental support for VXLAN 
and DMVPN. Notably, DMVPN remained non-functional in Vyatta Core due to its 
reliance on a proprietary NHRP implementation.

Crux (1.2)
----------
Crux (the Southern Cross) was released on 28 January 2019 and marked a 
departure from legacy Vyatta codebase and the start of the migration from 
Perl to Python as the primary language. The underlying base system was 
upgraded from Debian 6 (Squeeze) to Debian 8 (Jessie).

Crux introduced many new features, some of the most noteworthy are: 
an mDNS repeater, a broadcast relay, a high-performance PPPoE server, 
an HFSC scheduler, and support for Wireguard, unicast VRRP, RPKI for BGP, 
and fully 802.1ad-compliant QinQ ethertype. The telnet server and support 
for P2P filtering were removed.

Crux was the first VyOS release to feature a modular image build system.
CLI definitions were written using an XML syntax automatically checked 
against a schema at build time. Python APIs were introduced for command 
scripting and configuration migration. New Perl code and old-style (non-XML) 
command definition were no longer accepted from that point.

Crux reached the end of support in 2023.

Equuleus (1.3)
--------------
Equuleus (the Little Horse) was a long-term support version released 
on 21 December 2021, just in time for the winter holidays.

Equuleus brought many long-awaited features, most notably an SSTP VPN 
server, an IPoE server, an OpenConnect VPN server, and a serial console 
server. It also introduced reworked support for WWAN interfaces, support 
for GENEVE and MACSec interfaces, VRF, IS-IS routing, and preliminary support 
for MPLS and LDP.

Equuleus reached the end of support in 2025.

Sagitta (1.4)
-------------
Sagitta (the Arrow), the current LTS release, became generally available on 
4 June 2024. Its development began in late 2021 and focused on eliminating 
remaining legacy components and reworking core subsystems.

The transition to XML-defined command definitions and script refactoring with 
separate verify, update, and apply stages were completed. The firewall 
subsystem was rebuilt on nftables, introducing interface-independent rulesets 
and the reimplemented zone-based firewall model. The PKI subsystem was 
redesigned to manage cryptographic material directly within the configuration 
file.

Sagitta introduced rollback without reboot, support for Babel and PIM6 routing 
protocols, failover routes, segment routing, NAT64, an IKEv2 remote-access VPN 
server, Zabbix monitoring, HTTP load balancing, and configuration 
synchronization using the HTTP API.

The underlying base system was upgraded to Debian 12 (Bookworm).

Circinus (1.5)
--------------
Circinus (the Drawing Compass) became generally available as an LTS release on
31 March 2026. Its development began in 2024 and focused on major performance
upgrades and modernizing core subsystems.

Circinus introduces several major architectural improvements, most notably an
optional VPP-based accelerated dataplane. Using the DPDK driver, this dataplane
can offer performance up to 15x faster than the Linux kernel dataplane and
allows administrators to selectively enable hardware acceleration on a
per-interface and per-feature basis.

Other significant additions and updates include:

* A high-performance kernel-mode NetFlow sensor based on ipt-netflow,
  replacing the older pmacct implementation.
* Unification of sFlow to exclusively use the much faster hsflowd
  implementation.
* Transition of the DHCP server to a Kea-based implementation, replacing the
  legacy, end-of-life ISC DHCPD.
* A completely rewritten WAN load balancing implementation to resolve
  long-standing stability issues and introduce support for firewall groups in
  load balancing rules.
* A new ``execute`` operational mode command family to separate action commands
  that do not depend on or modify system configuration.

The release also cleans up several legacy and underutilized components.
FastNetMon was removed, OpenVPN support for Blowfish and Twofish ciphers was
dropped for security reasons, and the Salt minion integration was deprecated.

Like Sagitta (1.4), the underlying base system for Circinus remains Debian 12
(Bookworm).

Scutum (1.6)
--------------
Scutum (the Shield) is the codename for the upcoming development
branch. VyOS 1.6 Scutum has not been released yet.

A note on copyright
===================

Unlike Vyatta, VyOS has never had closed-source code and never will.
The only proprietary material in VyOS is non-code assets, such as
graphics and the trademark "VyOS". [*]_ 

Note that we do not provide support for images distributed by a third party. 
See the
`artwork license <https://github.com/vyos/vyos-build/blob/current/LICENSE.artwork>`_
and the end-user license agreement at ``/usr/share/vyos/EULA`` in
any pre-built image for more information.


.. [*] From the Sanskrit adjective "Vyātta" (व्यात्त), meaning opened.
.. [*] This is similar to how Linus Torvalds owns the Linux trademark.
