.. _flow-accounting:

###############
Flow Accounting
###############

VyOS supports flow-accounting for both IPv4 and IPv6 traffic. The system acts
as a flow exporter, and you are free to use it with any compatible collector.

Flows can be exported via protocol NetFlow (versions 5, 9 and
10/IPFIX). Additionally, you may save flows to an in-memory table
internally in a router.

.. warning:: You need to disable the in-memory table in production environments!
   Using :abbr:`IMT (In-Memory Table)` may lead to heavy CPU overloading and
   unstable flow-accounting behavior.


NetFlow / IPFIX
===============
NetFlow is a feature that was introduced on Cisco routers around 1996 that
provides the ability to collect IP network traffic as it enters or exits an
interface. By analyzing the data provided by NetFlow, a network administrator
can determine things such as the source and destination of traffic, class of
service, and the causes of congestion. A typical flow monitoring setup (using
NetFlow) consists of three main components:

* **exporter**: aggregates packets into flows and exports flow records towards
  one or more flow collectors
* **collector**: responsible for reception, storage and pre-processing of flow
  data received from a flow exporter
* **application**: analyzes received flow data in the context of intrusion
  detection or traffic profiling, for example

For connectionless protocols as like ICMP and UDP, a flow is considered
complete once no more packets for this flow appear after configurable timeout.

NetFlow is usually enabled on a per-interface basis to limit load on the router
components involved in NetFlow, or to limit the amount of NetFlow records
exported.

Configuration
=============

.. warning:: Using NetFlow on routers with high traffic levels may lead to
   high CPU usage and may affect the router's performance. In such cases,
   consider using sFlow instead.

In order for flow accounting information to be collected and displayed for an
interface, the interface must be configured for flow accounting.

.. cfgcmd:: set system flow-accounting interface <interface>

   Configure and enable collection of flow information for the interface
   identified by `<interface>`.

   You can configure multiple interfaces which would participate in flow
   accounting.

.. note:: Will be recorded only packets/flows on **incoming** direction in
   configured interfaces by default.


By default, recorded flows will be saved internally and can be listed with the
CLI command. You may disable using the local in-memory table with the command:

.. cfgcmd:: set system flow-accounting disable-imt

   If you need to sample also egress traffic, you may want to
   configure egress flow-accounting:

.. cfgcmd:: set system flow-accounting enable-egress

   Internally, in flow-accounting processes exist a buffer for data exchanging
   between core process and plugins (each export target is a separated plugin).
   If you have high traffic levels or noted some problems with missed records
   or stopping exporting, you may try to increase a default buffer size (10
   MiB) with the next command:

.. cfgcmd:: set system flow-accounting buffer-size <buffer size>

   In case, if you need to catch some logs from flow-accounting daemon, you may
   configure logging facility:

.. cfgcmd:: set system flow-accounting syslog-facility <facility>

   Set the syslog facility for flow-accounting log messages. Supported values
   include ``daemon``, ``local0`` through ``local7``, and other standard syslog
   facilities.

Flow Export
-----------

In addition to displaying flow accounting information locally, one can also
exported them to a collection server.

NetFlow
^^^^^^^

.. cfgcmd:: set system flow-accounting netflow version <version>

   There are multiple versions available for the NetFlow data. The `<version>`
   used in the exported flow data can be configured here. The following
   versions are supported:

   * **5** - Most common version, but restricted to IPv4 flows only
   * **9** - NetFlow version 9 (default)
   * **10** - :abbr:`IPFIX (IP Flow Information Export)` as per :rfc:`3917`

.. cfgcmd:: set system flow-accounting netflow server <address>

   Configure address of NetFlow collector. NetFlow server at `<address>` can
   be both listening on an IPv4 or IPv6 address.

.. cfgcmd:: set system flow-accounting netflow source-ip <address>

   IPv4 or IPv6 source address of NetFlow packets

.. cfgcmd:: set system flow-accounting netflow engine-id <id>

   NetFlow engine-id which will appear in NetFlow data. The range is 0 to 255.

.. cfgcmd:: set system flow-accounting netflow sampling-rate <rate>

   Use this command to configure the  sampling rate for flow accounting. The
   system samples one in every `<rate>` packets, where `<rate>` is the value
   configured for the sampling-rate option. The advantage of sampling every n
   packets, where n > 1, allows you to decrease the amount of processing
   resources required for flow accounting. The disadvantage of not sampling
   every packet is that the statistics produced are estimates of actual data
   flows.

   Per default every packet is sampled (that is, the sampling rate is 1).

.. cfgcmd:: set system flow-accounting netflow timeout expiry-interval
   <interval>

   Specifies the interval at which Netflow data will be sent to a collector. As
   per default, Netflow data will be sent every 60 seconds.

   You may also additionally configure timeouts for different types of
   connections.

.. cfgcmd:: set system flow-accounting netflow max-flows <n>

   If you want to change the maximum number of flows, which are tracking
   simultaneously, you may do this with this command (default 8192).

Example:
--------

NetFlow v5 example:

.. code-block:: none

  set system flow-accounting netflow engine-id 100
  set system flow-accounting netflow version 5
  set system flow-accounting netflow server 192.168.2.10 port 2055

Operation
=========

Once flow accounting is configured on an interfaces it provides the ability to
display captured network traffic information for all configured interfaces.

.. opcmd:: show flow-accounting interface <interface>

   Show flow accounting information for given `<interface>`.

   .. stop_vyoslinter

   .. code-block:: none

     vyos@vyos:~$ show flow-accounting interface eth0
     IN_IFACE    SRC_MAC            DST_MAC            SRC_IP                     DST_IP             SRC_PORT    DST_PORT  PROTOCOL      TOS    PACKETS    FLOWS    BYTES
     ----------  -----------------  -----------------  ------------------------  ---------------  ----------  ----------  ----------  -----  ---------  -------  -------
     eth0        00:53:01:a8:28:ac  ff:ff:ff:ff:ff:ff  192.0.2.2                 255.255.255.255        5678        5678  udp             0          1        1      178
     eth0        00:53:01:b2:2f:34  33:33:ff:00:00:00  fe80::253:01ff:feb2:2f34  ff02::1:ff00:0            0           0  ipv6-icmp       0          2        1      144
     eth0        00:53:01:1a:b4:53  33:33:ff:00:00:00  fe80::253:01ff:fe1a:b453  ff02::1:ff00:0            0           0  ipv6-icmp       0          1        1       72
     eth0        00:53:01:b2:22:48  00:53:02:58:a2:92  192.0.2.100               192.0.2.14            40152          22  tcp            16         39        1     2064
     eth0        00:53:01:c8:33:af  ff:ff:ff:ff:ff:ff  192.0.2.3                 255.255.255.255        5678        5678  udp             0          1        1      154
     eth0        00:53:01:b2:22:48  00:53:02:58:a2:92  192.0.2.100               192.0.2.14            40006          22  tcp            16        146        1     9444
     eth0        00:53:01:b2:22:48  00:53:02:58:a2:92  192.0.2.100               192.0.2.14                0           0  icmp          192         27        1     4455

   .. start_vyoslinter

.. opcmd:: show flow-accounting interface <interface> host <address>

   Show flow accounting information for given `<interface>` for a specific host
   only.

   .. stop_vyoslinter

   .. code-block:: none

     vyos@vyos:~$ show flow-accounting interface eth0 host 192.0.2.14
     IN_IFACE    SRC_MAC            DST_MAC            SRC_IP       DST_IP        SRC_PORT    DST_PORT  PROTOCOL      TOS    PACKETS    FLOWS    BYTES
     ----------  -----------------  -----------------  -----------  ----------  ----------  ----------  ----------  -----  ---------  -------  -------
     eth0        00:53:01:b2:22:48  00:53:02:58:a2:92  192.0.2.100  192.0.2.14       40006          22  tcp            16        197        2    12940
     eth0        00:53:01:b2:22:48  00:53:02:58:a2:92  192.0.2.100  192.0.2.14       40152          22  tcp            16         94        1     4924
     eth0        00:53:01:b2:22:48  00:53:02:58:a2:92  192.0.2.100  192.0.2.14           0           0  icmp          192         36        1     5877

   .. start_vyoslinter
