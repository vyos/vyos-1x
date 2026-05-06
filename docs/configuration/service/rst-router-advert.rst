.. _router-advert:

#####################
Router Advertisements
#####################

:abbr:`RAs (Router advertisements)` are described in :rfc:`4861#section-4.6.2`.
They are part of what is known as :abbr:`SLAAC (Stateless Address
Autoconfiguration)`.

Supported interface types:

    * bonding
    * bridge
    * ethernet
    * geneve
    * l2tpv3
    * openvpn
    * pseudo-ethernet
    * tunnel
    * vxlan
    * wireguard
    * wireless
    * wwan

*************
Configuration
*************

.. cfgcmd:: set service router-advert interface <interface> ...

.. stop_vyoslinter

.. csv-table::
   :header: "Field", "VyOS Option", "Description"
   :widths: 10, 10, 20

   "Cur Hop Limit", "hop-limit", "Hop count field of the outgoing RA packets"
   """Managed address configuration"" flag", "managed-flag", "Tell hosts to use the administered stateful protocol (i.e. DHCP) for autoconfiguration"
   """Other configuration"" flag", "other-config-flag", "Tell hosts to use the administered (stateful) protocol (i.e. DHCP) for autoconfiguration of other (non-address) information"
   "MTU","link-mtu","Link MTU value placed in RAs, excluded in RAs if unset"
   "Router Lifetime","default-lifetime","Lifetime associated with the default router in units of seconds"
   "Reachable Time","reachable-time","Time, in milliseconds, that a node assumes a neighbor is reachable after having received a reachability confirmation"
   "Retransmit Timer","retrans-timer","Time in milliseconds between retransmitted Neighbor Solicitation messages"
   "Default Router Preference","default-preference","Preference associated with the default router"
   "Interval", "interval", "Min and max intervals between unsolicited multicast RAs"
   "DNSSL", "dnssl", "DNS search list to advertise"
   "Name Server", "name-server", "Advertise DNS server per https://tools.ietf.org/html/rfc6106"
   "Auto Ignore Prefix", "auto-ignore", "Exclude a prefix from being advertised when the wildcard ::/64 prefix is used"
   "Captive Portal", "captive-portal", "Advertise a URL pointing to an RFC 8908-compliant API to tell hosts that they are behind a captive portal"

.. start_vyoslinter


Advertising a Prefix
--------------------

.. cfgcmd:: set service router-advert interface <interface> prefix <prefix/mask>

   .. note:: You can also opt for using `::/64` as prefix for your :abbr:`RAs (Router
    Advertisements)`. This is a special wildcard prefix that will emit :abbr:`RAs (Router Advertisements)` for every prefix assigned to the interface.
    This comes in handy when using dynamically obtained prefixes from DHCPv6-PD.

.. stop_vyoslinter

.. csv-table::
    :header: "VyOS Field", "Description"
    :widths: 10,30

    "decrement-lifetime", "Lifetime is decremented by the number of seconds since the last RA - use in conjunction with a DHCPv6-PD prefix"
    "deprecate-prefix", "Upon shutdown, this option will deprecate the prefix by announcing it in the shutdown RA"
    "no-autonomous-flag","Prefix can not be used for stateless address auto-configuration"
    "no-on-link-flag","Prefix can not be used for on-link determination"
    "preferred-lifetime","Time in seconds that the prefix will remain preferred (default 4 hours)"
    "valid-lifetime","Time in seconds that the prefix will remain valid (default: 30 days)"

.. start_vyoslinter

Advertising a NAT64 Prefix
--------------------------

.. cfgcmd:: set service router-advert interface <interface> nat64prefix <prefix/mask>

   Enable PREF64 option as outlined in :rfc:`8781`.

   NAT64 prefix mask must be one of: /32, /40, /48, /56, /64 or 96.

   .. note:: The well known NAT64 prefix is ``64:ff9b::/96``

.. stop_vyoslinter

.. csv-table::
    :header: "VyOS Field", "Description"
    :widths: 10,30

    "valid-lifetime","Time in seconds that the prefix will remain valid (default: 65528 seconds)"

.. start_vyoslinter

Disabling Advertisements
------------------------

To disable advertisements without deleting the configuration:

.. cfgcmd:: set service router-advert interface <interface> no-send-advert

   If set, the router will no longer send periodic router advertisements and
   will not respond to router solicitations.

.. cfgcmd:: set service router-advert interface <interface> no-send-interval

   Advertisement Interval Option (specified by Mobile IPv6) is always included in
   Router Advertisements unless this option is set.

*******
Example
*******

Your LAN connected on eth0 uses prefix ``2001:db8:beef:2::/64`` with the router
beeing ``2001:db8:beef:2::1``

.. code-block:: none

    set interfaces ethernet eth0 address 2001:db8:beef:2::1/64

    set service router-advert interface eth0 default-preference 'high'
    set service router-advert interface eth0 name-server '2001:db8::1'
    set service router-advert interface eth0 name-server '2001:db8::2'
    set service router-advert interface eth0 other-config-flag
    set service router-advert interface eth0 prefix 2001:db8:beef:2::/64
