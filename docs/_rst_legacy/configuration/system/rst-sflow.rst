#####
sFlow
#####

VyOS supports sFlow accounting for both IPv4 and IPv6 traffic. The system acts as a flow exporter, and you are free to use it with any compatible collector.

sFlow is a technology that enables monitoring of network traffic by sending sampled packets to a collector device.

The sFlow accounting based on hsflowd https://sflow.net/

Configuration
=============

.. cfgcmd:: set system sflow agent-address <address>

   Configure sFlow agent IPv4 or IPv6 address


.. cfgcmd:: set system sflow agent-interface <interface>

   Configure agent IP address associated with this interface.


.. cfgcmd:: set system sflow drop-monitor-limit <limit>

   Dropped packets reported on DROPMON Netlink channel by Linux kernel are exported via the standard sFlow v5 extension for reporting dropped packets

.. cfgcmd:: set system sflow interface <interface>

   Configure and enable collection of flow information for the interface identified by <interface>.

   You can configure multiple interfaces which would participate in sflow accounting.


.. cfgcmd:: set system sflow polling <sec>

   Configure schedule counter-polling in seconds (default: 30)

.. cfgcmd:: set system sflow sampling-rate <rate>

   Use this command to configure the sampling rate for sFlow accounting (default: 1000)

.. cfgcmd:: set system sflow server <address> port <port>

   Configure address of sFlow collector. sFlow server at <address> can be both listening on an IPv4 or IPv6 address.

.. cfgcmd:: set system sflow enable-egress

   Use this command to if you need to sample also egress traffic


Example
=======

.. code-block:: none

  set system sflow agent-address '192.0.2.14'
  set system sflow agent-interface 'eth0'
  set system sflow drop-monitor-limit '50'
  set system sflow interface 'eth0'
  set system sflow interface 'eth1'
  set system sflow polling '30'
  set system sflow sampling-rate '1000'
  set system sflow server 192.0.2.1 port '6343'
  set system sflow server 203.0.113.23 port '6343'
