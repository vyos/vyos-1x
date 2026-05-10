##########
Monitoring
##########

VyOS features several monitoring tools.

.. code-block:: none

  vyos@vyos:~$ monitor
  Possible completions:
    bandwidth     Monitor interface bandwidth in real time
    bandwidth-test
                  Initiate or wait for bandwidth test
    cluster       Monitor clustering service
    command       Monitor an operational mode command (refreshes every 2 seconds)
    conntrack-sync
                  Monitor conntrack-sync
    content-inspection
                  Monitor Content-Inspection
    dhcp          Monitor Dynamic Host Control Protocol (DHCP)
    dns           Monitor a Domain Name Service (DNS) daemon
    firewall      Monitor Firewall
    https         Monitor the Secure Hypertext Transfer Protocol (HTTPS) service
    lldp          Monitor Link Layer Discovery Protocol (LLDP) daemon
    log           Monitor last lines of messages file
    nat           Monitor network address translation (NAT)
    ndp           Monitor the NDP information received by the router through the device
    openvpn       Monitor OpenVPN
    protocol      Monitor routing protocols
    snmp          Monitor Simple Network Management Protocol (SNMP) daemon
    stop-all      Stop all current background monitoring processes
    traceroute    Monitor the path to a destination in realtime
    traffic       Monitor traffic dumps
    vpn           Monitor VPN
    vrrp          Monitor Virtual Router Redundancy Protocol (VRRP)
    webproxy      Monitor Webproxy service


*************
Traffic Dumps
*************

To monitor interface traffic, issue the :code:`monitor traffic interface <name>`
command, replacing `<name>` with your chosen interface.

.. code-block:: none

  vyos@vyos:~$ monitor traffic interface eth0
  tcpdump: verbose output suppressed, use -v or -vv for full protocol decode
  listening on eth0, link-type EN10MB (Ethernet), capture size 262144 bytes
  15:54:28.581601 IP 192.168.0.1 > vyos: ICMP echo request, id 1870, seq 3848, length 64
  15:54:28.581660 IP vyos > 192.168.0.1: ICMP echo reply, id 1870, seq 3848, length 64
  15:54:29.583399 IP 192.168.0.1 > vyos: ICMP echo request, id 1870, seq 3849, length 64
  15:54:29.583454 IP vyos > 192.168.0.1: ICMP echo reply, id 1870, seq 3849, length 64
  ^C
  4 packets captured
  4 packets received by filter
  0 packets dropped by kernel
  vyos@vyos:~$

To quit monitoring, press :kbd:`Ctrl-C` and you'll be returned to the VyOS command
prompt.

Traffic can be filtered and saved.

.. code-block:: none

  vyos@vyos:~$ monitor traffic interface eth0
  Possible completions:
    <Enter>       Execute the current command
    filter        Monitor traffic matching filter conditions
    save          Save traffic dump from an interface to a file


*************************
Interface Bandwidth Usage
*************************

To quickly view the bandwidth usage of an interface, use the ``monitor bandwidth`` command:

.. code-block:: none

  vyos@vyos:~$ monitor bandwidth interface eth0

This shows the following:

.. code-block:: none

         B                      (RX Bytes/second)
    198.00 .|....|.....................................................
    165.00 .|....|.....................................................
    132.00 ||..|.|.....................................................
     99.00 ||..|.|.....................................................
     66.00 |||||||.....................................................
     33.00 |||||||.....................................................
           1   5   10   15   20   25   30   35   40   45   50   55   60

       KiB                      (TX Bytes/second)
      3.67 ......|.....................................................
      3.06 ......|.....................................................
      2.45 ......|.....................................................
      1.84 ......|.....................................................
      1.22 ......|.....................................................
      0.61 :::::||.....................................................
           1   5   10   15   20   25   30   35   40   45   50   55   60

*********************
Interface Performance
*********************

To take a look on the network bandwidth between two nodes, the ``monitor
bandwidth-test`` command is used to run iperf.

.. code-block:: none

  vyos@vyos:~$ monitor bandwidth-test
  Possible completions:
    accept        Wait for bandwidth test connections (port TCP/5001)
    initiate      Initiate a bandwidth test

* The ``accept`` command opens a listening iperf server on TCP Port 5001
* The ``initiate`` command connects to that server to perform the test.

.. code-block:: none

  vyos@vyos:~$ monitor bandwidth-test initiate
  Possible completions:
    <hostname>    Initiate a bandwidth test to specified host (port TCP/5001)
    <x.x.x.x>
    <h:h:h:h:h:h:h:h>


***************
Monitor command
***************

The ``monitor command`` command allows you to repeatedly run a command to view
a continuously refreshed output. The command is run and output every 2 seconds,
allowing you to monitor the output continuously without having to re-run the
command. This can be useful to follow routing adjacency formation.

.. code-block:: none

  vyos@router:~$ monitor command "show interfaces"

Will clear the screen and show you the output of ``show interfaces`` every
2 seconds.

.. code-block:: none

  Every 2.0s: /opt/vyatta/bin/vyatta-op-cmd-wrapper    Sun Mar 26 02:49:46 2019

  Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
  Interface        IP Address                        S/L  Description
  ---------        ----------                        ---  -----------
  eth0             192.168.1.1/24                    u/u
  eth0.5           198.51.100.4/24                   u/u  WAN
  lo               127.0.0.1/8                       u/u
                   ::1/128
  vti0             172.25.254.2/30                   u/u
  vti1             172.25.254.9/30                   u/u
