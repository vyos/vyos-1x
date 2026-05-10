:lastproofread: 2026-03-30

.. _firewall-zone:

###################
Zone-Based Firewall
###################

********
Overview
********

.. note::
    All VyOS versions built after 2023-10-22 (VyOS 1.4 and 1.5) support
    this feature.

This section provides information on firewall configuration for the
zone-based firewall. This section covers the following configuration
commands:

.. cfgcmd:: set firewall zone ...

To learn about the general traffic flow in VyOS firewalls,
see :doc:`Firewall </configuration/firewall/index>`.

.. code-block:: none

   - set firewall
       * zone
            - custom_zone_name
               + ...

In zone-based policy, you assign interfaces to zones and apply inspection
policy to traffic moving between zones. The firewall acts on traffic
according to rules. A zone is a group of interfaces that have similar
functions or features. It establishes the security borders of a network.
A zone defines a boundary where the system subjects traffic to policy
restrictions as it crosses to another region of a network.

Key Points:

* A zone must be configured before you assign an interface to it, and you
  can assign an interface to only a single zone.
* All traffic to and from an interface within a zone flows freely.
* Existing policies affect all traffic between zones.
* Traffic cannot flow between a zone member interface and any interface that
  is not a zone member.
* You must define 2 separate firewalls to define traffic: one for each
  direction.

.. note:: In :vytask:`T2199` the syntax of the zone configuration was changed.
   The zone configuration moved from ``zone-policy zone <name>`` to ``firewall
   zone <name>``.

*************
Configuration
*************

As an alternative to applying policy to an interface directly, you can
create a zone-based firewall to simplify configuration when multiple
interfaces belong to the same security zone. Instead of applying rule-sets
to interfaces, you apply them to source-destination zone pairs.

You can find a basic introduction to zone-based firewalls in the
`VyOS Knowledge Base
<https://support.vyos.io/en/kb/articles/a-primer-to-zone-based-firewall>`_,
and an example at :ref:`examples-zone-policy`.

The following steps are required to create a zone-based firewall:

1. Define both the source and destination zones
2. Define the rule-set
3. Apply the rule-set to the zones

Define a Zone
=============

To define a zone, set up either one with interfaces or as the local zone.

.. cfgcmd:: set firewall zone <name> interface <interface>

   Assign interfaces as a member of a zone.

   .. note::

      * An interface can only be a member of one zone.
      * You can have multiple interfaces in a zone. Traffic between
        interfaces in the same zone follows the intra-zone-filtering
        policy (allowed by default).

.. cfgcmd:: set firewall zone <name> local-zone

   Define the zone as the local zone for traffic that originates from or is
   destined to the router itself.

   .. note::

      * A local zone cannot have any member interfaces
      * You cannot have multiple local zones

.. cfgcmd:: set firewall zone <name> default-action [drop | reject]

   Modify the zone default-action, which applies to traffic destined to this
   zone that does not match any of the source zone rulesets applied.

.. cfgcmd:: set firewall zone <name> default-log

   Enable logging of packets that match this zone's default-action (disabled
   by default).

.. cfgcmd:: set firewall zone <name> description

   Add a meaningful description.

Defining a Rule-Set
=============================

Zone-based firewall rule-sets define traffic from a *Source Zone* to a
*Destination Zone*.

You create rule-sets as a custom firewall chain using the commands below
(refer to the firewall IPv4/IPv6 sections for the full syntax):

* For :ref:`IPv4<configuration/firewall/ipv4:Firewall - IPv4 Rules>`:
  ``set firewall ipv4 name <name> ...``
* For :ref:`IPv6<configuration/firewall/ipv6:Firewall - IPv6 Rules>`:
  ``set firewall ipv6 name <name> ...``

It is helpful to name the rule-sets in the format
``<Source Zone>-<Destination Zone>-<v4 | v6>`` to make them easily
identifiable.

Applying a Rule-Set to a Zone
=============================

After you define a rule-set, apply it to the source and destination zones.
The configuration syntax anchors to the destination zone, with each of the
source zone rule-sets listed against the destination.

.. cfgcmd::  set firewall zone <Destination Zone> from <Source Zone>
   firewall name <ipv4-rule-set-name>

.. cfgcmd::  set firewall zone <Destination Zone> from <Source Zone>
   firewall ipv6-name <ipv6-rule-set-name>

You should create two rule-sets for each source-destination zone
pair.

.. code-block:: none

   set firewall zone DMZ from LAN firewall name LAN-DMZ-v4
   set firewall zone LAN from DMZ firewall name DMZ-LAN-v4

Applying a Default Rule-Set to a Zone
=====================================

When a destination zone shares a common rule-set for multiple source zones,
or when you require a complex set of default policies, you can apply an
optional default rule-set. The default rule-set applies to all zones that do
not have a rule-set configured as defined in
:ref:`IPv4<configuration/firewall/zone:Applying a Rule-Set to a Zone>`

.. cfgcmd:: set firewall zone <Destination Zone> default-firewall name
   <ipv4-rule-set-name>

.. cfgcmd:: set firewall zone <Destination Zone> default-firewall ipv6-name
   <ipv6-rule-set-name>

**************
Operation-mode
**************

.. opcmd:: show firewall zone-policy

   Display a basic summary of the zone configuration.

   .. code-block:: none

      vyos@vyos:~$ show firewall zone-policy
      Zone    Interfaces    From Zone    Firewall IPv4    Firewall IPv6
      ------  ------------  -----------  ---------------  ---------------
      LAN     eth1          WAN          WAN-LAN-v4
              eth2
      LOCAL   LOCAL         LAN          LAN-LOCAL-v4
                            WAN          WAN-LOCAL-v4     WAN-LOCAL-v6
      WAN     eth3          LAN          LAN-WAN-v4
              eth0          LOCAL        LOCAL-WAN-v4

.. opcmd:: show firewall zone-policy zone <zone>

   Display a basic summary of a particular zone.

   .. code-block:: none

      vyos@vyos:~$ show firewall zone-policy zone WAN
      Zone    Interfaces    From Zone    Firewall IPv4    Firewall IPv6
      ------  ------------  -----------  ---------------  ---------------
      WAN     eth3          LAN          LAN-WAN-v4
              eth0          LOCAL        LOCAL-WAN-v4

      vyos@vyos:~$ show firewall zone-policy zone LOCAL
      Zone    Interfaces    From Zone    Firewall IPv4    Firewall IPv6
      ------  ------------  -----------  ---------------  ---------------
      LOCAL   LOCAL         LAN          LAN-LOCAL-v4
                            WAN          WAN-LOCAL-v4     WAN-LOCAL-v6
