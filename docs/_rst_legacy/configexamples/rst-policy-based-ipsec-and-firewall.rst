.. _examples-policy-based-ipsec-and-firewall:


########################################################
Policy-Based Site-to-Site VPN and Firewall Configuration
########################################################

This guide shows an example policy-based IKEv2 site-to-site VPN between two
VyOS routers, and firewall configuration.

For simplicity, configuration and tests are done only using IPv4, and firewall
configuration is done only on one router.

Network Topology and requirements
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This configuration example and the requirements consists of:

- Two VyOS routers with public IP address.

- 2 private subnets on each site.

- Local subnets should be able to reach internet using source NAT.

- Communication between private subnets should be done through IPSec tunnel
  without NAT.

- Configuration of basic firewall in one site, in order to:

    - Protect the router on 'WAN' interface, allowing only IPSec connections
      and SSH access from trusted IPs.

    - Allow access to the router only from trusted networks.
    
    - Allow DNS requests only only for local networks.

    - Allow ICMP on all interfaces.

    - Allow all new connections from local subnets.

    - Allow connections from LANs to LANs through the tunnel.


.. image:: /_static/images/policy-based-ipsec-and-firewall.*


Configuration
^^^^^^^^^^^^^

Interface and routing configuration:

.. code-block:: none

    # LEFT router:
    set interfaces ethernet eth0 address '198.51.100.14/30'
    set interfaces ethernet eth1 vif 111 address '10.1.11.1/24'
    set interfaces ethernet eth2 vif 112 address '10.1.12.1/24'
    set protocols static route 0.0.0.0/0 next-hop 198.51.100.13

    # RIGHT router:
    set interfaces ethernet eth0 address '192.0.2.130/30'
    set interfaces ethernet eth1 vif 221 address '10.2.21.1/24'
    set interfaces ethernet eth2 vif 222 address '10.2.22.1/24'


IPSec configuration:

.. code-block:: none

    # LEFT router:
    set vpn ipsec authentication psk RIGHT id '198.51.100.14'
    set vpn ipsec authentication psk RIGHT id '192.0.2.130'
    set vpn ipsec authentication psk RIGHT secret 'p4ssw0rd'
    set vpn ipsec esp-group ESP-GROUP mode 'tunnel'
    set vpn ipsec esp-group ESP-GROUP proposal 1 encryption 'aes256'
    set vpn ipsec esp-group ESP-GROUP proposal 1 hash 'sha256'
    set vpn ipsec ike-group IKE-GROUP key-exchange 'ikev2'
    set vpn ipsec ike-group IKE-GROUP proposal 1 dh-group '14'
    set vpn ipsec ike-group IKE-GROUP proposal 1 encryption 'aes256'
    set vpn ipsec ike-group IKE-GROUP proposal 1 hash 'sha256'
    set vpn ipsec interface 'eth0'
    set vpn ipsec site-to-site peer RIGHT authentication mode 'pre-shared-secret'
    set vpn ipsec site-to-site peer RIGHT connection-type 'initiate'
    set vpn ipsec site-to-site peer RIGHT default-esp-group 'ESP-GROUP'
    set vpn ipsec site-to-site peer RIGHT ike-group 'IKE-GROUP'
    set vpn ipsec site-to-site peer RIGHT local-address '198.51.100.14'
    set vpn ipsec site-to-site peer RIGHT remote-address '192.0.2.130'
    set vpn ipsec site-to-site peer RIGHT tunnel 0 local prefix '10.1.11.0/24'
    set vpn ipsec site-to-site peer RIGHT tunnel 0 remote prefix '10.2.21.0/24'
    set vpn ipsec site-to-site peer RIGHT tunnel 1 local prefix '10.1.11.0/24'
    set vpn ipsec site-to-site peer RIGHT tunnel 1 remote prefix '10.2.22.0/24'
    set vpn ipsec site-to-site peer RIGHT tunnel 2 local prefix '10.1.12.0/24'
    set vpn ipsec site-to-site peer RIGHT tunnel 2 remote prefix '10.2.21.0/24'
    set vpn ipsec site-to-site peer RIGHT tunnel 3 local prefix '10.1.12.0/24'
    set vpn ipsec site-to-site peer RIGHT tunnel 3 remote prefix '10.2.22.0/24'

    # RIGHT router:
    set vpn ipsec authentication psk LEFT id '192.0.2.130'
    set vpn ipsec authentication psk LEFT id '198.51.100.14'
    set vpn ipsec authentication psk LEFT secret 'p4ssw0rd'
    set vpn ipsec esp-group ESP-GROUP mode 'tunnel'
    set vpn ipsec esp-group ESP-GROUP proposal 1 encryption 'aes256'
    set vpn ipsec esp-group ESP-GROUP proposal 1 hash 'sha256'
    set vpn ipsec ike-group IKE-GROUP key-exchange 'ikev2'
    set vpn ipsec ike-group IKE-GROUP proposal 1 dh-group '14'
    set vpn ipsec ike-group IKE-GROUP proposal 1 encryption 'aes256'
    set vpn ipsec ike-group IKE-GROUP proposal 1 hash 'sha256'
    set vpn ipsec interface 'eth0'
    set vpn ipsec site-to-site peer LEFT authentication mode 'pre-shared-secret'
    set vpn ipsec site-to-site peer LEFT connection-type 'none'
    set vpn ipsec site-to-site peer LEFT default-esp-group 'ESP-GROUP'
    set vpn ipsec site-to-site peer LEFT ike-group 'IKE-GROUP'
    set vpn ipsec site-to-site peer LEFT local-address '192.0.2.130'
    set vpn ipsec site-to-site peer LEFT remote-address '198.51.100.14'
    set vpn ipsec site-to-site peer LEFT tunnel 0 local prefix '10.2.21.0/24'
    set vpn ipsec site-to-site peer LEFT tunnel 0 remote prefix '10.1.11.0/24'
    set vpn ipsec site-to-site peer LEFT tunnel 1 local prefix '10.2.22.0/24'
    set vpn ipsec site-to-site peer LEFT tunnel 1 remote prefix '10.1.11.0/24'
    set vpn ipsec site-to-site peer LEFT tunnel 2 local prefix '10.2.21.0/24'
    set vpn ipsec site-to-site peer LEFT tunnel 2 remote prefix '10.1.12.0/24'
    set vpn ipsec site-to-site peer LEFT tunnel 3 local prefix '10.2.22.0/24'
    set vpn ipsec site-to-site peer LEFT tunnel 3 remote prefix '10.1.12.0/24'

Firewall Configuration:

.. code-block:: none

    # Firewall Groups:
    set firewall group network-group LOCAL-NETS network '10.1.11.0/24'
    set firewall group network-group LOCAL-NETS network '10.1.12.0/24'
    set firewall group network-group REMOTE-NETS network '10.2.21.0/24'
    set firewall group network-group REMOTE-NETS network '10.2.22.0/24'
    set firewall group network-group TRUSTED network '198.51.100.125/32'
    set firewall group network-group TRUSTED network '203.0.113.0/24'
    set firewall group network-group TRUSTED network '10.1.11.0/24'
    set firewall group network-group TRUSTED network '192.168.70.0/24'

    # Forward traffic: default drop and only allow what is needed
    set firewall ipv4 forward filter default-action 'drop'
    
    # Forward traffic: global state policies
    set firewall ipv4 forward filter rule 1 action 'accept'
    set firewall ipv4 forward filter rule 1 state established 'enable'
    set firewall ipv4 forward filter rule 1 state related 'enable'
    set firewall ipv4 forward filter rule 2 action 'drop'
    set firewall ipv4 forward filter rule 2 state invalid 'enable'
    
    # Forward traffic: Accept all connections from local networks
    set firewall ipv4 forward filter rule 10 action 'accept'
    set firewall ipv4 forward filter rule 10 source group network-group 'LOCAL-NETS'
    
    # Forward traffic: accept connections from remote LANs to local LANs
    set firewall ipv4 forward filter rule 20 action 'accept'
    set firewall ipv4 forward filter rule 20 destination group network-group 'LOCAL-NETS'
    set firewall ipv4 forward filter rule 20 source group network-group 'REMOTE-NETS'

    # Input traffic: default drop and only allow what is needed
    set firewall ipv4 input filter default-action 'drop'

    # Input traffic: global state policies
    set firewall ipv4 input filter rule 1 action 'accept'
    set firewall ipv4 input filter rule 1 state established 'enable'
    set firewall ipv4 input filter rule 1 state related 'enable'
    set firewall ipv4 input filter rule 2 action 'drop'
    set firewall ipv4 input filter rule 2 state invalid 'enable'

    # Input traffic: add rules needed for ipsec connection
    set firewall ipv4 input filter rule 10 action 'accept'
    set firewall ipv4 input filter rule 10 destination port '500,4500'
    set firewall ipv4 input filter rule 10 inbound-interface name 'eth0'
    set firewall ipv4 input filter rule 10 protocol 'udp'
    set firewall ipv4 input filter rule 15 action 'accept'
    set firewall ipv4 input filter rule 15 inbound-interface name 'eth0'
    set firewall ipv4 input filter rule 15 protocol 'esp'

    # Input traffic: accept ssh connection from trusted ips
    set firewall ipv4 input filter rule 20 action 'accept'
    set firewall ipv4 input filter rule 20 destination port '22'
    set firewall ipv4 input filter rule 20 protocol 'tcp'
    set firewall ipv4 input filter rule 20 source group network-group 'TRUSTED'

    # Input traffic: accepd dns requests only from local networks.
    set firewall ipv4 input filter rule 25 action 'accept'
    set firewall ipv4 input filter rule 25 destination port '53'
    set firewall ipv4 input filter rule 25 protocol 'udp'
    set firewall ipv4 input filter rule 25 source group network-group 'LOCAL-NETS'

    # Input traffic: allow icmp
    set firewall ipv4 input filter rule 30 action 'accept'
    set firewall ipv4 input filter rule 30 protocol 'icmp'

And NAT Configuration:

.. code-block:: none

    set nat source rule 10 destination group network-group 'REMOTE-NETS'
    set nat source rule 10 exclude
    set nat source rule 10 outbound-interface name 'eth0'
    set nat source rule 10 source group network-group 'LOCAL-NETS'
    set nat source rule 20 outbound-interface name 'eth0'
    set nat source rule 20 source group network-group 'LOCAL-NETS'
    set nat source rule 20 translation address 'masquerade'

Checking through op-mode commands
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After some testing, we can check IPSec status, and counter on every tunnel:

.. code-block:: none

    vyos@LEFT:~$ show vpn ipsec sa
    Connection      State    Uptime    Bytes In/Out    Packets In/Out    Remote address    Remote ID    Proposal
    --------------  -------  --------  --------------  ----------------  ----------------  -----------  ---------------------------------------
    RIGHT-tunnel-0  up       36m24s    840B/840B       10/10             192.0.2.130       192.0.2.130  AES_CBC_256/HMAC_SHA2_256_128/MODP_2048
    RIGHT-tunnel-1  up       36m33s    588B/588B       7/7               192.0.2.130       192.0.2.130  AES_CBC_256/HMAC_SHA2_256_128/MODP_2048
    RIGHT-tunnel-2  up       35m50s    1K/1K           15/15             192.0.2.130       192.0.2.130  AES_CBC_256/HMAC_SHA2_256_128/MODP_2048
    RIGHT-tunnel-3  up       36m54s    2K/2K           32/32             192.0.2.130       192.0.2.130  AES_CBC_256/HMAC_SHA2_256_128/MODP_2048
    vyos@LEFT:~$ 


Also, we can check firewall counters:

.. code-block:: none

    vyos@LEFT:~$ show firewall
    Rulesets Information

    ---------------------------------
    IPv4 Firewall "forward filter"

    Rule     Action    Protocol      Packets    Bytes  Conditions
    -------  --------  ----------  ---------  -------  ------------------------------------------------------
    1        accept    all               681    96545  ct state { established, related }  accept
    2        drop      all                 0        0  ct state invalid
    10       accept    all               360    27205  ip saddr @N_LOCAL-NETS  accept
    20       accept    all                 8      648  ip daddr @N_LOCAL-NETS ip saddr @N_REMOTE-NETS  accept
    default  drop      all

    ---------------------------------
    IPv4 Firewall "input filter"

    Rule     Action    Protocol      Packets    Bytes  Conditions
    -------  --------  ----------  ---------  -------  ----------------------------------------------
    1        accept    all               901   123709  ct state { established, related }  accept
    2        drop      all                 0        0  ct state invalid
    10       accept    udp                 0        0  udp dport { 500, 4500 } iifname "eth0"  accept
    15       accept    esp                 0        0  meta l4proto esp iifname "eth0"  accept
    20       accept    tcp                 1       60  tcp dport 22 ip saddr @N_TRUSTED  accept
    25       accept    udp                 0        0  udp dport 53 ip saddr @N_LOCAL-NETS  accept
    30       accept    icmp                0        0  meta l4proto icmp  accept
    default  drop      all

    vyos@LEFT:~$ 
    vyos@LEFT:~$ show firewall statistics 
    Rulesets Statistics

    ---------------------------------
    IPv4 Firewall "forward filter"

    Rule     Packets    Bytes    Action    Source       Destination    Inbound-Interface    Outbound-interface
    -------  ---------  -------  --------  -----------  -------------  -------------------  --------------------
    1        681        96545    accept    any          any            any                  any
    2        0          0        drop      any          any            any                  any
    10       360        27205    accept    LOCAL-NETS   any            any                  any
    20       8          648      accept    REMOTE-NETS  LOCAL-NETS     any                  any
    default  N/A        N/A      drop      any          any            any                  any

    ---------------------------------
    IPv4 Firewall "input filter"

    Rule     Packets    Bytes    Action    Source      Destination    Inbound-Interface    Outbound-interface
    -------  ---------  -------  --------  ----------  -------------  -------------------  --------------------
    1        905        124213   accept    any         any            any                  any
    2        0          0        drop      any         any            any                  any
    10       0          0        accept    any         any            eth0                 any
    15       0          0        accept    any         any            eth0                 any
    20       1          60       accept    TRUSTED     any            any                  any
    25       0          0        accept    LOCAL-NETS  any            any                  any
    30       0          0        accept    any         any            any                  any
    default  N/A        N/A      drop      any         any            any                  any

    vyos@LEFT:~$ 
