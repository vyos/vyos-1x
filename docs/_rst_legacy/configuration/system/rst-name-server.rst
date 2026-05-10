.. _system-dns:

##########
System DNS
##########

.. warning:: If you are configuring a VRF for management purposes, there is
   currently no way to force system DNS traffic via a specific VRF.

This section describes configuring DNS on the system, namely:

 * DNS name servers
 * Domain search order


DNS name servers
================

.. cfgcmd:: set system name-server <address>

   Use this command to specify a DNS server for the system to be used
   for DNS lookups. More than one DNS server can be added, configuring
   one at a time. Both IPv4 and IPv6 addresses are supported.



Example
-------

In this example, some *OpenNIC* servers are used, two IPv4 addresses
and two IPv6 addresses:

.. stop_vyoslinter

.. code-block:: none

   set system name-server 176.9.37.132
   set system name-server 195.10.195.195
   set system name-server 2a01:4f8:161:3441::1
   set system name-server 2a00:f826:8:2::195

.. start_vyoslinter

Domain search order
===================

In order for the system to use and complete unqualified host names, a
list can be defined which will be used for domain searches.


.. cfgcmd:: set system domain-search <domain>

   Use this command to define domains, one at a time, so that the system
   uses them to complete unqualified host names. Maximum: 6 entries.


.. note:: Domain names can include letters, numbers, hyphens and periods
   with a maximum length of 253 characters.

.. _name-server:domain-search-order_example:

Example
-------

The system is configured to attempt domain completion in the following
order: vyos.io (first), vyos.net (second) and vyos.network (last):


.. code-block:: none

   set system domain-search vyos.io
   set system domain-search vyos.net
   set system domain-search vyos.network

