:lastproofread: 2026-03-30

########
Firewall
########

.. warning:: Due to a boot-time race condition, all interfaces initialize
   before the firewall. This temporarily leaves the system open to all traffic
   and poses a security risk.

VyOS uses Netfilter. The Netfilter
project developed ``iptables`` and its successor ``nftables`` for the Linux
kernel to process packet data flows directly. This extends the concept of
zone-based security to let you manipulate data at multiple stages after the
network interface and driver accept it, and before sending it to its
destination (for example, a web server or another device).

The following is a simplified traffic flow diagram based on Netfilter
packet flow.
This diagram provides an overview of how packets are processed and the
possible paths traffic can take.

.. figure:: /_static/images/firewall-gral-packet-flow.*

The main points regarding packet flow and terminology in VyOS firewall
are:

   * **Bridge Port?**: Choose the appropriate path based on whether the
     interface where the packet was received is part of a bridge.

If the interface where the packet was received is not part of a bridge, the
packet is processed at the **IP Layer**:

   * **Prerouting**: The router processes all packets in this stage,
     regardless of the destination. You can perform several actions in
     this stage, and these actions are also defined in different parts of the
     VyOS configuration. Order is important. The relevant configuration that
     applies in this stage includes:

      * **Firewall prerouting**: Rules you define under ``set firewall
        [ipv4 | ipv6] prerouting raw...``. The system processes all rules in
        this section before the connection tracking subsystem.

      * **Conntrack Ignore**: Rules you define under ``set system conntrack
        ignore [ipv4 | ipv6] ...``. You can configure this section with
        ``firewall [ipv4 | ipv6] prerouting ...``. For compatibility reasons,
        this feature is supported, but will be deprecated in the future.

      * **Policy Route**: Rules you define under ``set policy [route |
        route6] ...``.

      * **Destination NAT**: Rules you define under ``set [nat | nat66]
        destination...``.

   * **Destination is the router?**: Choose the appropriate path based on the
     destination IP address. Transit traffic continues to **forward**, while
     traffic destined for the router continues to **input**.

   * **Input**: The stage where you filter and control traffic destined for
     the router itself. This is where you enforce all rules for securing the
     router. This includes IPv4 and IPv6 filtering rules, defined in:

     * ``set firewall ipv4 input filter ...``.

     * ``set firewall ipv6 input filter ...``.

   * **Forward**: The stage where you filter and control transit traffic.
     This includes IPv4 and IPv6 filtering rules, defined in:

     * ``set firewall ipv4 forward filter ...``.

     * ``set firewall ipv6 forward filter ...``.

   * **Output**: The stage where you filter and control traffic that the
     router originates. Note that this traffic comes from either a new
     connection that an internal process on the VyOS router (such as NTP)
     originates or a response to traffic the router receives externally through
     **input** (for example, a response to an SSH login attempt). This includes
     IPv4 and IPv6 rules, and two different sections apply:

     * **Output Prerouting**: ``set firewall [ipv4 | ipv6] output
       filter ...``. As described in **Prerouting**, the system processes
       rules in this section before the connection tracking subsystem.

     * **Output Filter**: ``set firewall [ipv4 | ipv6] output filter ...``.

   * **Postrouting**: As in **Prerouting**, you can perform several actions
     defined in different parts of VyOS configuration in this stage. This
     includes:

     * **Source NAT**: Rules you define under ``set [nat | nat66]
       destination...``.

If the interface where the packet was received is part of a bridge, the
packet is processed at the **Bridge Layer**:

   * **Prerouting (Bridge)**: The bridge processes all packets it receives in
     this stage, regardless of the destination. First, you can apply filters
     here, or you can configure rules that ignore the connection tracking
     system. The relevant configuration that applies:

     * ``set firewall bridge prerouting filter ...``.

   * **Forward (Bridge)**: The stage where you filter and control traffic
     that passes through the bridge:

     * ``set firewall bridge forward filter ...``.

   * **Input (Bridge)**: The stage where you filter and control traffic
     destined for the bridge itself:

     * ``set firewall bridge input filter ...``.

   * **Output (Bridge)**: The stage where you filter and control traffic that
     the bridge originates:

     * ``set firewall bridge output filter ...``.

The following is the overall structure of the VyOS firewall CLI:

.. code-block:: none

   - set firewall
       * bridge
            - forward
               + filter
            - input
               + filter
            - output
               + filter
            - prerouting
               + filter
            - name
               + custom_name
       * flowtable
            - custom_flow_table
               + ...
       * global-options
            + all-ping
            + broadcast-ping
            + ...
       * group
            - address-group
            - ipv6-address-group
            - network-group
            - ipv6-network-group
            - interface-group
            - mac-group
            - port-group
            - domain-group
       * ipv4
            - forward
               + filter
            - input
               + filter
            - output
               + filter
               + raw
            - prerouting
               + raw
            - name
               + custom_name
       * ipv6
            - forward
               + filter
            - input
               + filter
            - output
               + filter
               + raw
            - prerouting
               + raw
            - ipv6-name
               + custom_name
       * zone
            - custom_zone_name
               + ...

Here is a list of VyOS firewall CLI subcommands and their
corresponding pages in the documentation:

.. cfgcmd:: set firewall bridge ...

   Configure bridge firewall rules for traffic at the bridge layer. For detailed
   information, see 
   :doc:`Bridge Firewall Configuration</configuration/firewall/bridge>`.

.. cfgcmd:: set firewall flowtable ...

   Configure firewall flowtables for stateful connection tracking and rules.
   For detailed information, see
   :doc:`Flowtables Firewall Configuration </configuration/firewall/flowtables>`
   .

.. cfgcmd:: set firewall global-options ...

   Configure global firewall options such as ``all-ping``, ``broadcast-ping``,
   ``syn-cookies``, and other system-wide firewall settings. For detailed
   information, see
   :doc:`Global Firewall Options</configuration/firewall/global-options>`.

.. cfgcmd:: set firewall group ...

   Organize firewall rules by creating reusable address, network, interface,
   MAC, port, and domain groups. Use groups in multiple rules to simplify
   configuration and maintenance. For detailed information, see
   :doc:`Firewall Groups</configuration/firewall/groups>`.

.. cfgcmd:: set firewall ipv4 ...

   Configure IPv4-specific firewall rules. For detailed information, see
   :doc:`IPv4 Firewall Configuration</configuration/firewall/ipv4>`.

.. cfgcmd:: set firewall ipv6 ...

   Configure IPv6-specific firewall rules. For detailed information, see
   :doc:`IPv6 Firewall Configuration</configuration/firewall/ipv6>`.

.. cfgcmd:: set firewall zone ...

   Configure zone-based firewall policies for controlling traffic between
   different network zones. For detailed information, see
   :doc:`Zone-Based Firewall Configuration</configuration/firewall/zone>`.

For more information on firewall configuration, see the following pages:

.. toctree::
   :maxdepth: 1
   :includehidden:

   global-options
   groups
   bridge
   ipv4
   ipv6
   flowtables

.. note::
   For more information on Netfilter hooks and Linux networking packet flows,
   see the `Netfilter-Hooks
   <https://wiki.nftables.org/wiki-nftables/index.php/Netfilter_hooks>`_
   documentation.


Zone-Based firewall
^^^^^^^^^^^^^^^^^^^

.. toctree::
   :maxdepth: 1
   :includehidden:

   zone

With zone-based firewalls, a new concept applies. In addition to the standard
in and out traffic flows, a local flow enables traffic originating from and
destined to the router itself. This means you must configure additional rules to
secure the firewall from the network, in addition to the existing inbound and
outbound rules.

To configure VyOS with zone-based firewall, see
:doc:`Zone-Based Firewall Configuration </configuration/firewall/zone>`.

As the following example image shows, you must configure rules to allow or block
traffic to or from the services running on the device that have open
connections on that interface.

.. figure:: /_static/images/firewall-zonebased.*
