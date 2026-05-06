:lastproofread: 2021-06-29

.. _examples-ospf-unnumbered:

#########################
OSPF unnumbered with ECMP
#########################

General information can be found in the :ref:`routing-ospf` chapter.

Configuration
=============

- Router A:

.. code-block:: none

  set interfaces ethernet eth0 address '10.0.0.1/24'
  set interfaces ethernet eth1 address '192.168.0.1/32'
  set interfaces ethernet eth1 ip ospf authentication md5 key-id 1 md5-key 'yourpassword'
  set interfaces ethernet eth1 ip ospf network 'point-to-point'
  set interfaces ethernet eth2 address '192.168.0.1/32'
  set interfaces ethernet eth2 ip ospf authentication md5 key-id 1 md5-key 'yourpassword'
  set interfaces ethernet eth2 ip ospf network 'point-to-point'
  set interfaces loopback lo address '192.168.0.1/32'
  set protocols ospf area 0.0.0.0 authentication 'md5'
  set protocols ospf area 0.0.0.0 network '192.168.0.1/32'
  set protocols ospf parameters router-id '192.168.0.1'
  set protocols ospf redistribute connected

- Router B:

.. code-block:: none

  set interfaces ethernet eth0 address '10.0.0.2/24'
  set interfaces ethernet eth1 address '192.168.0.2/32'
  set interfaces ethernet eth1 ip ospf authentication md5 key-id 1 md5-key 'yourpassword'
  set interfaces ethernet eth1 ip ospf network 'point-to-point'
  set interfaces ethernet eth2 address '192.168.0.2/32'
  set interfaces ethernet eth2 ip ospf authentication md5 key-id 1 md5-key 'yourpassword'
  set interfaces ethernet eth2 ip ospf network 'point-to-point'
  set interfaces loopback lo address '192.168.0.2/32'
  set protocols ospf area 0.0.0.0 authentication 'md5'
  set protocols ospf area 0.0.0.0 network '192.168.0.2/32'
  set protocols ospf parameters router-id '192.168.0.2'
  set protocols ospf redistribute connected


Results
=======

- Router A:

.. code-block:: none

  vyos@vyos:~$ show interfaces
  Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
  Interface        IP Address                        S/L  Description
  ---------        ----------                        ---  -----------
  eth0             10.0.0.1/24                       u/u
  eth1             192.168.0.1/32                    u/u
  eth2             192.168.0.1/32                    u/u
  lo               127.0.0.1/8                       u/u
                   192.168.0.1/32
                   ::1/128

.. code-block:: none

  vyos@vyos:~$ show ip route
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
         F - PBR, f - OpenFabric,
         > - selected route, * - FIB route, q - queued route, r - rejected route

  S>* 0.0.0.0/0 [210/0] via 10.0.0.254, eth0, 00:57:34
  O   10.0.0.0/24 [110/20] via 192.168.0.2, eth1 onlink, 00:13:21
                              via 192.168.0.2, eth2 onlink, 00:13:21
  C>* 10.0.0.0/24 is directly connected, eth0, 00:57:35
  O   192.168.0.1/32 [110/0] is directly connected, lo, 00:48:53
  C * 192.168.0.1/32 is directly connected, eth2, 00:56:31
  C * 192.168.0.1/32 is directly connected, eth1, 00:56:31
  C>* 192.168.0.1/32 is directly connected, lo, 00:57:36
  O>* 192.168.0.2/32 [110/1] via 192.168.0.2, eth1 onlink, 00:29:03
    *                        via 192.168.0.2, eth2 onlink, 00:29:03

- Router B:

.. code-block:: none

  vyos@vyos:~$ show interfaces
  Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
  Interface        IP Address                        S/L  Description
  ---------        ----------                        ---  -----------
  eth0             10.0.0.2/24                       u/u
  eth1             192.168.0.2/32                    u/u
  eth2             192.168.0.2/32                    u/u
  lo               127.0.0.1/8                       u/u
                   192.168.0.2/32
                   ::1/128

.. code-block:: none

  vyos@vyos:~$ show ip route
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
         F - PBR, f - OpenFabric,
         > - selected route, * - FIB route, q - queued route, r - rejected route

  S>* 0.0.0.0/0 [210/0] via 10.0.0.254, eth0, 00:57:34
  O   10.0.0.0/24 [110/20] via 192.168.0.1, eth1 onlink, 00:13:21
                              via 192.168.0.1, eth2 onlink, 00:13:21
  C>* 10.0.0.0/24 is directly connected, eth0, 00:57:35
  O   192.168.0.2/32 [110/0] is directly connected, lo, 00:48:53
  C * 192.168.0.2/32 is directly connected, eth2, 00:56:31
  C * 192.168.0.2/32 is directly connected, eth1, 00:56:31
  C>* 192.168.0.2/32 is directly connected, lo, 00:57:36
  O>* 192.168.0.1/32 [110/1] via 192.168.0.1, eth1 onlink, 00:29:03
    *                        via 192.168.0.1, eth2 onlink, 00:29:03
