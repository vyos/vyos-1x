:lastproofread: 2024-09-11

###########################
Bridge and firewall example
###########################

Scenario and requirements
^^^^^^^^^^^^^^^^^^^^^^^^^

This example shows how to configure a VyOS router with bridge interfaces and
firewall rules.

Three non VLAN-aware bridges are going to be configured, and each one has its
own requirements.

* Bridge br0:
   * Isolated layer 2 bridge.
   * Accept only IPv6 communication whithin the bridge.

* Bridge br1:
   * Drop all DHCP discover packets.
   * Accept all ARP packets.
   * Within the bridge, accept only new IPv4 connections from host 10.1.1.102
   * Drop all other IPv4 connections.
   * Drop all IPv6 connections.
   * Accept access to router itself.
   * Allow connections to internet
   * Drop connections to other LANs.

* Bridge br2:
   * Accept all DHCP discover packets.
   * Accept only DHCP offers from valid server and|or trusted bridge port.
   * Accept all ARP packets.
   * Accept all IPv4 connections.
   * Drop all IPv6 connections.
   * Deny access to the router.
   * Allow connections to internet.
   * Allow connections to bridge br1.

Configuration
^^^^^^^^^^^^^

Bridges and interfaces configuration
""""""""""""""""""""""""""""""""""""

First, we need to configure the interfaces and bridges:

.. code-block:: none

  # Brige br0
  set interfaces bridge br0 description 'Isolated L2 bridge'
  set interfaces bridge br0 member interface eth1
  set interfaces bridge br0 member interface eth2
  set interfaces ethernet eth1 description 'br0'
  set interfaces ethernet eth2 description 'br0'

  # Bridge br1:
  set interfaces bridge br1 address '10.1.1.1/24'
  set interfaces bridge br1 description 'L3 bridge br1'
  set interfaces bridge br1 member interface eth3
  set interfaces bridge br1 member interface eth4
  set interfaces ethernet eth3 description 'br1'
  set interfaces ethernet eth4 description 'br1'

  # Bridge br2:
  set interfaces bridge br2 address '10.2.2.1/24'
  set interfaces bridge br2 description 'L3 bridge br2'
  set interfaces bridge br2 member interface eth5
  set interfaces bridge br2 member interface eth6
  set interfaces bridge br2 member interface eth7
  set interfaces ethernet eth5 description 'br2 - Host'
  set interfaces ethernet eth6 description 'br2 - Trusted DHCP Server'
  set interfaces ethernet eth7 description 'br2'

Bridge firewall configuration
"""""""""""""""""""""""""""""

In this section, we are going to configure the firewall rules that will be used
in bridge firewall, and will control the traffic within each bridge.

We are going to use custom firewall rulesets, one for each bridge that will
be used in ``prerouting``, and one for each bridge that will be used in the
``forward`` chain.

Also, we are going to use firewall interface groups in order to simplify the
firewall configuration.

So first, let's create the required firewall interface groups:

.. code-block:: none

  # Bridge br0 interface-group:
  set firewall group interface-group br0-ifaces interface 'br0'
  set firewall group interface-group br0-ifaces interface 'eth1'
  set firewall group interface-group br0-ifaces interface 'eth2'
  
  # Bridge br1 interface-group:
  set firewall group interface-group br1-ifaces interface 'br1'
  set firewall group interface-group br1-ifaces interface 'eth3'
  set firewall group interface-group br1-ifaces interface 'eth4'
  
  # Bridge br2 interface-group:
  set firewall group interface-group br2-ifaces interface 'br2'
  set firewall group interface-group br2-ifaces interface 'eth5'
  set firewall group interface-group br2-ifaces interface 'eth6'
  set firewall group interface-group br2-ifaces interface 'eth7'

As said before, we are going to create custom firewall rulesets for each
bridge, that will be used in the ``prerouting`` chain, in order to drop as much
unwanted traffic as early as possible. So, custom rulesets used in
``prerouting`` chain are going to be ``br0-pre``, ``br1-pre``, and ``br2-pre``:

.. code-block:: none

  # Prerouting - Catch all traffic for br0
  set firewall bridge prerouting filter rule 10 action 'jump'
  set firewall bridge prerouting filter rule 10 description 'br0 traffic'
  set firewall bridge prerouting filter rule 10 inbound-interface group 'br0-ifaces'
  set firewall bridge prerouting filter rule 10 jump-target 'br0-pre'

  # Prerouting - Catch all traffic for br1
  set firewall bridge prerouting filter rule 20 action 'jump'
  set firewall bridge prerouting filter rule 20 description 'br1 traffic'
  set firewall bridge prerouting filter rule 20 inbound-interface group 'br1-ifaces'
  set firewall bridge prerouting filter rule 20 jump-target 'br1-pre'

  # Prerouting - Catch all traffic for br2
  set firewall bridge prerouting filter rule 30 action 'jump'
  set firewall bridge prerouting filter rule 30 description 'br2 traffic'
  set firewall bridge prerouting filter rule 30 inbound-interface group 'br2-ifaces'
  set firewall bridge prerouting filter rule 30 jump-target 'br2-pre'

And then create the custom rulesets:

.. code-block:: none

  ### br0 - br0-pre
    # Requirements: accept only IPv6 communication within the bridge
  set firewall bridge name br0-pre rule 10 description 'Accept IPv6 traffic'
  set firewall bridge name br0-pre rule 10 action 'accept'
  set firewall bridge name br0-pre rule 10 ethernet-type 'ipv6'
    # And drop everything else
  set firewall bridge name br0-pre default-action 'drop'

  ### br1 - br1-pre
    # Requirements: drop all DHCP discover packets
  set firewall bridge name br1-pre rule 10 description 'Drop DHCP discover'
  set firewall bridge name br1-pre rule 10 action 'drop'
  set firewall bridge name br1-pre rule 10 protocol 'udp'
  set firewall bridge name br1-pre rule 10 source port '68'
  set firewall bridge name br1-pre rule 10 destination port '67'
  set firewall bridge name br1-pre rule 10 destination mac-address 'ff:ff:ff:ff:ff:ff'
  set firewall bridge name br1-pre rule 10 log
    # Requirement: drop all IPv6 connections
  set firewall bridge name br1-pre rule 20 description 'Drop IPv6 traffic'
  set firewall bridge name br1-pre rule 20 action 'drop'
  set firewall bridge name br1-pre rule 20 ethernet-type 'ipv6'
    # Accept everything else so it can be parsed later
  set firewall bridge name br1-pre default-action 'accept'

  ### br2 - br2-pre
    # Requirements: drop all IPv6 connections
  set firewall bridge name br2-pre rule 10 description 'Drop IPv6 traffic'
  set firewall bridge name br2-pre rule 10 action 'drop'
  set firewall bridge name br2-pre rule 10 ethernet-type 'ipv6'
    # Accept everything else so it can be parsed later
  set firewall bridge name br2-pre default-action 'accept'

Now, in the ``forward`` chain, we are going to define state policies, and
custom rulesets for each bridge that would be used in the ``forward`` chain.
These rulesets are ``br0-fwd``, ``br1-fwd``, and ``br2-fwd``:

.. code-block:: none

  # Forward - State policies if not defined globally
  set firewall bridge forward filter rule 5 action 'accept'
  set firewall bridge forward filter rule 5 state 'established'
  set firewall bridge forward filter rule 5 state 'related'
  set firewall bridge forward filter rule 10 action 'drop'
  set firewall bridge forward filter rule 10 state 'invalid'

  # Forward - Catch all traffic for br0
  set firewall bridge forward filter rule 110 description 'br0 traffic'
  set firewall bridge forward filter rule 110 action 'jump'
  set firewall bridge forward filter rule 110 inbound-interface group 'br0-ifaces'
  set firewall bridge forward filter rule 110 jump-target 'br0-fwd'

  # Forward - Catch all traffic for br1
  set firewall bridge forward filter rule 120 description 'br1 traffic'
  set firewall bridge forward filter rule 120 action 'jump'
  set firewall bridge forward filter rule 120 inbound-interface group 'br1-ifaces'
  set firewall bridge forward filter rule 120 jump-target 'br1-fwd'

  # Forward - Catch all traffic for br2
  set firewall bridge forward filter rule 130 description 'br2 traffic'
  set firewall bridge forward filter rule 130 action 'jump'
  set firewall bridge forward filter rule 130 inbound-interface group 'br2-ifaces'
  set firewall bridge forward filter rule 130 jump-target 'br2-fwd'

  # Forward - Default action drop:
  set firewall bridge forward filter default-action 'drop'

And the content of the custom rulesets:

.. code-block:: none

  ### br0 - br0-fwd
    # Accept everything that wasn't dropped in prerouting
  set firewall bridge name br0-fwd default-action 'accept'

  ### br1 - br1-fwd
    # Requirement: Accept all ARP packets
  set firewall bridge name br1-fwd rule 10 description 'Accept ARP'
  set firewall bridge name br1-fwd rule 10 action 'accept'
  set firewall bridge name br1-fwd rule 10 ethernet-type 'arp'
    # Requirement: Accept only new IPv4 connections from host 10.1.1.102
  set firewall bridge name br1-fwd rule 20 description 'Accept ipv4 from host'
  set firewall bridge name br1-fwd rule 20 action 'accept'
  set firewall bridge name br1-fwd rule 20 source address '10.1.1.102'
  set firewall bridge name br1-fwd rule 20 state 'new'
    # Drop everythin else within the bridge:
  set firewall bridge name br1-fwd default-action 'drop'

  ### br2 - br2-fwd
    # Requirement: Accept all DHCP discover packets
  set firewall bridge name br2-fwd rule 10 description 'Accept DHCP discover'
  set firewall bridge name br2-fwd rule 10 action 'accept'
  set firewall bridge name br2-fwd rule 10 protocol 'udp'
  set firewall bridge name br2-fwd rule 10 source port '68'
  set firewall bridge name br2-fwd rule 10 destination port '67'
  set firewall bridge name br2-fwd rule 10 destination mac-address 'ff:ff:ff:ff:ff:ff'
    # Requirement: Accept only DHCP offers from valid server on port eth6
  set firewall bridge name br2-fwd rule 20 description 'Accept DHCP offers from trusted interface'
  set firewall bridge name br2-fwd rule 20 action 'accept'
  set firewall bridge name br2-fwd rule 20 protocol 'udp'
  set firewall bridge name br2-fwd rule 20 source port '67'
  set firewall bridge name br2-fwd rule 20 destination port '68'
  set firewall bridge name br2-fwd rule 20 inbound-interface name 'eth6'
  set firewall bridge name br2-fwd rule 22 description 'Drop all other DHCP offers'
  set firewall bridge name br2-fwd rule 22 action 'drop'
  set firewall bridge name br2-fwd rule 22 protocol 'udp'
  set firewall bridge name br2-fwd rule 22 source port '67'
  set firewall bridge name br2-fwd rule 22 destination port '68'
  set firewall bridge name br2-fwd rule 22 log

    # Accept all ARP packets
  set firewall bridge name br2-fwd rule 30 description 'Accept ARP'
  set firewall bridge name br2-fwd rule 30 action 'accept'
  set firewall bridge name br2-fwd rule 30 ethernet-type 'arp'
    # Accept all IPv4 connections
  set firewall bridge name br2-fwd rule 40 description 'Accept ipv4'
  set firewall bridge name br2-fwd rule 40 action 'accept'
  set firewall bridge name br2-fwd rule 40 ethernet-type 'ipv4'
    # Drop everything else
  set firewall bridge name br2-fwd default-action 'drop'


IP firewall configuration
"""""""""""""""""""""""""

Since some of the requirements listed above exceed the capabilities of the
bridge firewall, we need to use the IP firewall to implement them.
For bridge br1 and br2, we need to control the traffic that is going to the
router itself, to other local networks, and to the Internet.

As a reminder, here's a link to the :doc:`firewall documentation
</configuration/firewall/index>`, where you can find more information about
the packet flow for traffic that comes from bridge layer and should be analized
by the IP firewall.

Access to the router itself is controlled by the base chain ``input``, and
rules to accomplish all the requirements are:

.. code-block:: none

  # First of all, if not using global state policies, we need to define them:
  set firewall ipv4 input filter rule 10 state 'established' 
  set firewall ipv4 input filter rule 10 state 'related'
  set firewall ipv4 input filter rule 10 action 'accept'
  set firewall ipv4 input filter rule 20 state 'invalid'
  set firewall ipv4 input filter rule 20 action 'drop'

  # Input - br1 - Accept access to router itself
  set firewall ipv4 input filter rule 110 description "Accept access from br1"
  set firewall ipv4 input filter rule 110 action 'accept'
  set firewall ipv4 input filter rule 110 inbound-interface group 'br1-ifaces'

  # Input - br2 - Deny access to the router
  set firewall ipv4 input filter rule 120 description "Deny access from br2"
  set firewall ipv4 input filter rule 120 action 'drop'
  set firewall ipv4 input filter rule 120 inbound-interface group 'br2-ifaces'

And for traffic that is going to other local networks, and to he Internet, we
need to use the base chain ``forward``. As in the bridge firewall, we are
going to use custom rulesets for each bridge, that would be used in the
``forward`` chain. Those rulesets are ``ip-br1-fwd`` and ``ip-br2-fwd``:

.. code-block:: none

  # First of all, if not using global state policies, we need to define them:
  set firewall ipv4 forward filter rule 5 action 'accept'
  set firewall ipv4 forward filter rule 5 state 'established'
  set firewall ipv4 forward filter rule 5 state 'related'
  set firewall ipv4 forward filter rule 10 action 'drop'
  set firewall ipv4 forward filter rule 10 state 'invalid'

  # Forward - Catch all traffic for br1
  set firewall ipv4 forward filter rule 110 description 'br1 traffic'
  set firewall ipv4 forward filter rule 110 action 'jump'
  set firewall ipv4 forward filter rule 110 inbound-interface group 'br1-ifaces'
  set firewall ipv4 forward filter rule 110 jump-target 'ip-br1-fwd'

  # Forward - Catch all traffic for br2
  set firewall ipv4 forward filter rule 120 description 'br2 traffic'
  set firewall ipv4 forward filter rule 120 action 'jump'
  set firewall ipv4 forward filter rule 120 inbound-interface group 'br2-ifaces'
  set firewall ipv4 forward filter rule 120 jump-target 'ip-br2-fwd'

  # Forward - Default action drop:
  set firewall ipv4 forward filter default-action 'drop'

And the content of the custom rulesets:

.. code-block:: none

  ### br1 - ip-br1-fwd
    # Requirement: Allow connections to internet
  set firewall ipv4 name ip-br1-fwd rule 10 description 'br1 - allow internet access'
  set firewall ipv4 name ip-br1-fwd rule 10 action 'accept'
  set firewall ipv4 name ip-br1-fwd rule 10 outbound-interface name 'eth0'
    # Requirement: Drop all other connections
  set firewall ipv4 name ip-br1-fwd default-action 'drop'

  ### br2 - ip-br2-fwd
    # Requirement: Allow connections to internet
  set firewall ipv4 name ip-br2-fwd rule 10 description 'br2 - allow internet access'
  set firewall ipv4 name ip-br2-fwd rule 10 action 'accept'
  set firewall ipv4 name ip-br2-fwd rule 10 outbound-interface name 'eth0'
    # Requirement: Allow connections to br1
  set firewall ipv4 name ip-br2-fwd rule 20 description 'br2 - allow access to br1'
  set firewall ipv4 name ip-br2-fwd rule 20 action 'accept'
  set firewall ipv4 name ip-br2-fwd rule 20 outbound-interface group 'br1-ifaces'
    # Requirement: Drop all other connections
  set firewall ipv4 name ip-br2-fwd default-action 'drop'


Validation
^^^^^^^^^^

While testing the configuration, we can check logs in order to ensure that
we are accepting and/or blocking the correct traffic.

For example, while a host tries to get an IP address from a DHCP server in
br1 all DHCP discover are dropped, and in br2, we can see that DHCP offers from
untrusted servers are dropped:

.. stop_vyoslinter

.. code-block:: none

  vyos@bridge:~$ show log firewall bridge
  Sep 17 14:22:35 kernel: [bri-NAM-br2-fwd-22-D]IN=eth7 OUT=eth5 MAC=50:00:00:09:00:00:50:00:00:04:00:00:08:00 SRC=10.2.2.199 DST=10.2.2.92 LEN=322 TOS=0x10 PREC=0x00 TTL=128 ID=0 DF PROTO=UDP SPT=67 DPT=68 LEN=302
  Sep 17 14:28:18 kernel: [bri-NAM-br1-pre-10-D]IN=eth3 OUT= MAC=ff:ff:ff:ff:ff:ff:00:50:79:66:68:0c:08:00 SRC=0.0.0.0 DST=255.255.255.255 LEN=392 TOS=0x10 PREC=0x00 TTL=16 ID=0 PROTO=UDP SPT=68 DPT=67 LEN=372
  Sep 17 14:28:19 kernel: [bri-NAM-br1-pre-10-D]IN=eth3 OUT= MAC=ff:ff:ff:ff:ff:ff:00:50:79:66:68:0c:08:00 SRC=0.0.0.0 DST=255.255.255.255 LEN=392 TOS=0x10 PREC=0x00 TTL=16 ID=0 PROTO=UDP SPT=68 DPT=67 LEN=372

.. start_vyoslinter


And with operational mode commands, we can check rules matchers, actions, and
counters.

Bridge firewall rulset:

.. code-block:: none

  vyos@bri:~$ show firewall bridge
  Rulesets bridge Information

  ---------------------------------
  bridge Firewall "forward filter"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  -----------------------------------------
  5        accept    all                19     1916  ct state { established, related }  accept
  10       drop      all                 0        0  ct state invalid
  110      jump      all                 2      208  iifname @I_br0-ifaces  jump NAME_br0-fwd
  120      jump      all                10      670  iifname @I_br1-ifaces  jump NAME_br1-fwd
  130      jump      all                12     3086  iifname @I_br2-ifaces  jump NAME_br2-fwd
  default  drop      all                 0        0

  ---------------------------------
  bridge Firewall "name br0-fwd"

  Rule     Action    Protocol      Packets    Bytes
  -------  --------  ----------  ---------  -------
  default  accept    all                 2      208

  ---------------------------------
  bridge Firewall "name br0-pre"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  ----------------------
  10       accept    all                18     1872  ether type ip6  accept
  default  drop      all                 9     1476

  ---------------------------------
  bridge Firewall "name br1-fwd"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  ----------------------------------------
  10       accept    all                 5      250  ether type arp  accept
  20       accept    all                 3      252  ct state new ip saddr 10.1.1.102  accept
  default  drop      all                 2      168

  ---------------------------------
  bridge Firewall "name br1-pre"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  ----------------------------------------------------------------------------------------
  10       drop      udp                 3     1176  ether daddr ff:ff:ff:ff:ff:ff udp sport 68 udp dport 67  prefix "[bri-NAM-br1-pre-10-D]"
  20       drop      all                 0        0  ether type ip6
  default  accept    all                58     4430

  ---------------------------------
  bridge Firewall "name br2-fwd"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  ---------------------------------------------------------------
  10       accept    udp                 4     1312  ether daddr ff:ff:ff:ff:ff:ff udp sport 68 udp dport 67  accept
  20       accept    udp                 2      656  udp sport 67 udp dport 68 iifname "eth6"  accept
  22       drop      udp                 1      322  udp sport 67 udp dport 68  prefix "[bri-NAM-br2-fwd-22-D]"
  30       accept    all                 2       92  ether type arp  accept
  40       accept    all                 3      704  ether type ip  accept
  default  drop      all                 0        0

  ---------------------------------
  bridge Firewall "name br2-pre"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  --------------
  10       drop      all                 7      728  ether type ip6
  default  accept    all                77     7548

  ---------------------------------
  bridge Firewall "prerouting filter"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  ----------------------------------------
  10       jump      all                27     3348  iifname @I_br0-ifaces  jump NAME_br0-pre
  20       jump      all                61     5606  iifname @I_br1-ifaces  jump NAME_br1-pre
  30       jump      all                84     8276  iifname @I_br2-ifaces  jump NAME_br2-pre
  default  drop      all                 0        0

  vyos@bridge:~$ 

IPv4 firewall rulset:

.. code-block:: none

  vyos@bridge:~$ show firewall ipv4
  Rulesets ipv4 Information

  ---------------------------------
  ipv4 Firewall "forward filter"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  -------------------------------------------
  5        accept    all                76     6384  ct state { established, related }  accept
  10       drop      all                 0        0  ct state invalid
  110      jump      all                13     1092  iifname @I_br1-ifaces  jump NAME_ip-br1-fwd
  120      jump      all                 3      252  iifname @I_br2-ifaces  jump NAME_ip-br2-fwd
  default  drop      all                 0        0

  ---------------------------------
  ipv4 Firewall "input filter"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  -----------------------------------------
  10       accept    all                 0        0  ct state { established, related }  accept
  20       drop      all                 0        0  ct state invalid
  110      accept    all                10      720  iifname @I_br1-ifaces  accept
  120      drop      all                26     2672  iifname @I_br2-ifaces
  default  accept    all              3037   991621

  ---------------------------------
  ipv4 Firewall "name ip-br1-fwd"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  ----------------------
  10       accept    all                 5      420  oifname "eth0"  accept
  default  drop      all                 8      672

  ---------------------------------
  ipv4 Firewall "name ip-br2-fwd"

  Rule     Action    Protocol      Packets    Bytes  Conditions
  -------  --------  ----------  ---------  -------  -----------------------------
  10       accept    all                 1       84  oifname "eth0"  accept
  20       accept    all                 2      168  oifname @I_br1-ifaces  accept
  default  drop      all                 0        0

  vyos@bridge:~$ 
