##################
Connectivity Tests
##################

************************
Basic Connectivity Tests
************************

Verifying connectivity can be done with the familiar `ping` and `traceroute`
commands. The options for each are shown (the options for each command were
displayed using the built-in help as described in the :ref:`cli`
section and are omitted from the output here):

.. opcmd:: ping <destination>

   Send ICMP echo requests to destination host. There are multiple options to
   ping, including VRF support.

   .. code-block:: none

     vyos@vyos:~$ ping 10.1.1.1
     Possible completions:
       <Enter>       Execute the current command
       adaptive      Ping options
       allow-broadcast
       audible
       bypass-route
       count
       deadline
       do-not-fragment
       flood
       interface
       interval
       mark
       no-loopback
       numeric
       pattern
       quiet
       record-route
       size
       timestamp
       tos
       ttl
       verbose
       vrf


.. opcmd:: traceroute <destination>

   Trace path to target.

   .. code-block:: none

     vyos@vyos:~$ traceroute
     Possible completions:
       <hostname>    Track network path to specified node
       <x.x.x.x>
       <h:h:h:h:h:h:h:h>
       ipv4          Track network path to <hostname|IPv4 address>
       ipv6          Track network path to <hostname|IPv6 address>


***************************
Advanced Connectivity Tests
***************************

.. opcmd:: monitor traceroute <destination>

   However, another helper is available which combines ping and traceroute
   into a single tool. An example of its output is shown:

   .. code-block:: none

     vyos@vyos:~$ mtr 10.62.212.12

                                My traceroute  [v0.85]
     vyos (0.0.0.0)
     Keys:  Help   Display mode   Restart statistics   Order of fields   quit
                                       Packets               Pings
     Host                            Loss%   Snt   Last   Avg  Best  Wrst StDev
     1. 10.11.110.4                   0.0%    34    0.5   0.5   0.4   0.8   0.1
     2. 10.62.255.184                 0.0%    34    1.1   1.0   0.9   1.4   0.1
     3. 10.62.255.71                  0.0%    34    1.4   1.4   1.3   2.0   0.1
     4. 10.62.212.12                  0.0%    34    1.6   1.6   1.6   1.7   0.0

   .. note:: The output consumes the screen and will replace your command
      prompt.

   Several options are available for changing the display output. Press `h` to
   invoke the built in help system. To quit, just press `q` and you'll be
   returned to the VyOS command prompt.

***********************
IPv6 Topology Discovery
***********************

IPv6 uses different techniques to discover its Neighbors/topology.

Router Discovery
================

.. opcmd:: force ipv6-rd interface <interface> [address <ipv6-address>]

   Discover routers via eth0.

   Example:

   .. code-block:: none

     vyos@vyos:~$ force ipv6-rd interface eth0
     Soliciting ff02::2 (ff02::2) on eth0...

     Hop limit                 :           60 (      0x3c)
     Stateful address conf.    :           No
     Stateful other conf.      :           No
     Mobile home agent         :           No
     Router preference         :         high
     Neighbor discovery proxy  :           No
     Router lifetime           :         1800 (0x00000708) seconds
     Reachable time            :  unspecified (0x00000000)
     Retransmit time           :  unspecified (0x00000000)
      Prefix                   : 240e:fe:8ca7:ea01::/64
       On-link                 :          Yes
       Autonomous address conf.:          Yes
       Valid time              :      2592000 (0x00278d00) seconds
       Pref. time              :        14400 (0x00003840) seconds
      Prefix                   : fc00:470:f1cd:101::/64
       On-link                 :          Yes
       Autonomous address conf.:          Yes
       Valid time              :      2592000 (0x00278d00) seconds
       Pref. time              :        14400 (0x00003840) seconds
      Recursive DNS server     : fc00:470:f1cd::ff00
       DNS server lifetime     :          600 (0x00000258) seconds
      Source link-layer address: 00:98:2B:F8:3F:11
      from fe80::298:2bff:fef8:3f11

Neighbor Discovery
==================

.. opcmd:: force ipv6-nd interface <interface> address <ipv6-address>


   Example:

   .. code-block:: none

     vyos@vyos:~$ force ipv6-nd interface eth0 address fc00:470:f1cd:101::1

     Soliciting fc00:470:f1cd:101::1 (fc00:470:f1cd:101::1) on eth0...
     Target link-layer address: 00:98:2B:F8:3F:11 from fc00:470:f1cd:101::1
