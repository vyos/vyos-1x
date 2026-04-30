---
lastproofread: '2026-03-05'
---

(pseudo-ethernet-interface)=

# MACVLAN (pseudo-Ethernet)

MACVLAN, or pseudo-Ethernet interfaces, operate as logical subinterfaces of
standard Ethernet interfaces. Each subinterface has a unique MAC address but
shares a single physical Ethernet port.
That allows the user to send packets from different source IPv4 or IPv6 addresses
using a different MAC address.

Pseudo-Ethernet interfaces behave like physical Ethernet interfaces. They
support IPv4 and IPv6 addressing, can obtain IP addresses through DHCP or
DHCPv6, and are mapped to a physical Ethernet port. They inherit
characteristics such as speed and duplex from their parent interface and can
be referenced like standard Ethernet interfaces once created.

```{eval-rst}
Pseudo-Ethernet interfaces may not work in environments that require a
   :abbr:`NIC (Network Interface Card)` to have only one MAC address.
   This includes:

   * VMware machines with default settings.
   * Network switches that permit only a single MAC address.
   * xDSL modems that learn the NIC's MAC address.
```

## Configuration

### Common interface configuration

```{cmdincludemd} /_include/interface-common-with-dhcp.txt
:var0: pseudo-ethernet
:var1: peth0
```

### MACVLAN (pseudo-Ethernet) options

```{cfgcmd} set interfaces pseudo-ethernet \<interface\> source-interface \<ethX\>

Assign a physical Ethernet interface to the specified pseudo-Ethernet interface.
```

```{eval-rst}
.. cfgcmd:: set interfaces pseudo-ethernet <interface> anycast-gateway

   **Enable EVPN anycast gateway mode on the specified pseudo-Ethernet interface.**

   In this mode, VyOS installs a local Forwarding Database (FDB) entry on the
   pseudo-Ethernet interface's parent bridge. This ensures traffic destined
   for the pseudo-Ethernet's anycast MAC address is terminated locally rather
   than forwarded across the VXLAN overlay.

   VyOS automatically removes the FDB entry when you disable EVPN anycast
   gateway mode or delete the pseudo-Ethernet interface.

   .. note::

      The following requirements must be met to enable EVPN anycast gateway
      mode:

      * The MAC address must be explicitly configured on the pseudo-Ethernet
        interface.
      * The pseudo-Ethernet interface's ``source-interface`` must be a bridge
        or bridge sub-interface (e.g., ``br0`` or ``br0.100``). VyOS always
        installs the FDB entry on the base bridge (e.g., ``br0``), even if the
        ``source-interface`` is a sub-interface like ``br0.100``.

   Example:

   .. code-block:: none

      set interfaces pseudo-ethernet peth0 anycast-gateway
```

### VLAN

```{cmdincludemd} /_include/interface-vlan-8021q.txt
:var0: pseudo-ethernet
:var1: peth0
```