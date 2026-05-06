.. _examples:

########################
Configuration Blueprints
########################

This chapter contains various configuration examples:

.. toctree::
   :maxdepth: 2

   firewall
   bgp-ipv6-unnumbered
   ospf-unnumbered
   azure-vpn-bgp
   azure-vpn-dual-bgp
   ha
   wan-load-balancing
   pppoe-ipv6-basic
   l3vpn-hub-and-spoke
   lac-lns
   inter-vrf-routing-vrf-lite
   dmvpn-dualhub-dualcloud
   qos
   segment-routing-isis
   nmp
   ansible
   ipsec-cisco-policy-based
   ipsec-cisco-route-based
   ipsec-pa-route-based
   policy-based-ipsec-and-firewall
   site-2-site-cisco


Configuration Blueprints (autotest)
===================================

The next pages contains automatic full tested configuration examples.

Each lab will build an test from an external script.
The page content will generate, so changes will not take an effect.

A host ``vyos-oobm`` will use as a ssh proxy. This host is just
necessary for the Lab test.

The process will do the following steps:

1. create the lab on a eve-ng server
2. configure each host in the lab
3. do some defined tests
4. optional do an upgrade to a higher version and do step 3 again.
5. generate the documentation and include files
6. shutdown and destroy the lab, if there is no error


.. toctree::
   :maxdepth: 1

   autotest/DHCPRelay_through_GRE/DHCPRelay_through_GRE
   autotest/tunnelbroker/tunnelbroker
   autotest/L3VPN_EVPN/L3VPN_EVPN
   autotest/Wireguard/Wireguard
   autotest/OpenVPN_with_LDAP/OpenVPN_with_LDAP
