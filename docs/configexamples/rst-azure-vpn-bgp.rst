:lastproofread: 2021-06-28

.. _examples-azure-vpn-bgp:

############################################################
Route-Based Site-to-Site VPN to Azure (BGP over IKEv2/IPsec)
############################################################

This guide shows an example of a route-based IKEv2 site-to-site VPN to
Azure using VTI and BGP for dynamic routing updates.

For redundant / active-active configurations see
:ref:`examples-azure-vpn-dual-bgp`


Prerequisites
^^^^^^^^^^^^^

- A pair of Azure VNet Gateways deployed in active-passive
  configuration with BGP enabled.

- A local network gateway deployed in Azure representing
  the Vyos device, matching the below Vyos settings except for
  address space, which only requires the Vyos private IP, in
  this example 10.10.0.5/32

- A connection resource deployed in Azure linking the
  Azure VNet gateway and the local network gateway representing
  the Vyos device.

Example
^^^^^^^

+---------------------------------------+---------------------+
| WAN Interface                         | eth0                |
+---------------------------------------+---------------------+
| On-premises address space             | 10.10.0.0/16        |
+---------------------------------------+---------------------+
| Azure address space                   |  10.0.0.0/16        |
+---------------------------------------+---------------------+
| Vyos public IP                        | 198.51.100.3        |
+---------------------------------------+---------------------+
| Vyos private IP                       | 10.10.0.5           |
+---------------------------------------+---------------------+
| Azure VNet Gateway public IP          |  203.0.113.2        |
+---------------------------------------+---------------------+
| Azure VNet Gateway BGP IP             |  10.0.0.4           |
+---------------------------------------+---------------------+
| Pre-shared key                        | ch00s3-4-s3cur3-psk |
+---------------------------------------+---------------------+
| Vyos ASN                              | 64499               |
+---------------------------------------+---------------------+
| Azure ASN                             | 65540               |
+---------------------------------------+---------------------+

Vyos configuration
^^^^^^^^^^^^^^^^^^

- Configure the IKE and ESP settings to match a subset
  of those supported by Azure:

.. code-block:: none

  set vpn ipsec esp-group AZURE lifetime '3600'
  set vpn ipsec esp-group AZURE mode 'tunnel'
  set vpn ipsec esp-group AZURE pfs 'dh-group2'
  set vpn ipsec esp-group AZURE proposal 1 encryption 'aes256'
  set vpn ipsec esp-group AZURE proposal 1 hash 'sha1'

  set vpn ipsec ike-group AZURE dead-peer-detection action 'restart'
  set vpn ipsec ike-group AZURE dead-peer-detection interval '15'
  set vpn ipsec ike-group AZURE dead-peer-detection timeout '30'
  set vpn ipsec ike-group AZURE ikev2-reauth
  set vpn ipsec ike-group AZURE key-exchange 'ikev2'
  set vpn ipsec ike-group AZURE lifetime '28800'
  set vpn ipsec ike-group AZURE proposal 1 dh-group '2'
  set vpn ipsec ike-group AZURE proposal 1 encryption 'aes256'
  set vpn ipsec ike-group AZURE proposal 1 hash 'sha1'

- Enable IPsec on eth0

.. code-block:: none

  set vpn ipsec interface 'eth0'

- Configure a VTI with a dummy IP address

.. code-block:: none

  set interfaces vti vti1 address '10.10.1.5/32'
  set interfaces vti vti1 description 'Azure Tunnel'

- Clamp the VTI's MSS to 1350 to avoid PMTU blackholes.

.. code-block:: none

  set interfaces vti vti1 ip adjust-mss 1350

- Configure the VPN tunnel

.. code-block:: none

  set vpn ipsec authentication psk azure id '198.51.100.3'
  set vpn ipsec authentication psk azure id '203.0.113.2'
  set vpn ipsec authentication psk azure secret 'ch00s3-4-s3cur3-psk'
  set vpn ipsec site-to-site peer azure authentication local-id '198.51.100.3'
  set vpn ipsec site-to-site peer 203.0.113.2 authentication mode 'pre-shared-secret'
  set vpn ipsec site-to-site peer 203.0.113.2 authentication remote-id '203.0.113.2'
  set vpn ipsec site-to-site peer 203.0.113.2 connection-type 'initiate'
  set vpn ipsec site-to-site peer 203.0.113.2 description 'AZURE PRIMARY TUNNEL'
  set vpn ipsec site-to-site peer 203.0.113.2 ike-group 'AZURE'
  set vpn ipsec site-to-site peer 203.0.113.2 ikev2-reauth 'inherit'
  set vpn ipsec site-to-site peer 203.0.113.2 local-address '10.10.0.5'
  set vpn ipsec site-to-site peer azure remote-address '203.0.113.2'
  set vpn ipsec site-to-site peer 203.0.113.2 vti bind 'vti1'
  set vpn ipsec site-to-site peer 203.0.113.2 vti esp-group 'AZURE'

- **Important**: Add an interface route to reach Azure's BGP listener

.. code-block:: none

  set protocols static route 10.0.0.4/32 interface vti1

- Configure your BGP settings

.. code-block:: none

  set protocols bgp system-as 64499
  set protocols bgp neighbor 10.0.0.4 remote-as '65540'
  set protocols bgp neighbor 10.0.0.4 address-family ipv4-unicast soft-reconfiguration 'inbound'
  set protocols bgp neighbor 10.0.0.4 timers holdtime '30'
  set protocols bgp neighbor 10.0.0.4 timers keepalive '10'

- **Important**: Disable connected check \

.. code-block:: none

  set protocols bgp neighbor 10.0.0.4 disable-connected-check
