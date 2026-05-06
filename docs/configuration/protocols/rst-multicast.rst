.. _routing-static:

#########
Multicast
#########

In order to influence Multicast :abbr:`RPF (Reverse Path Forwarding)` lookup,
it is possible to insert into zebra routes for the Multicast
:abbr:`RIB (Routing Information Base)`. These routes are only used for RPF
lookup and will not be used by ZEBRA for insertion into the kernel or for
normal RIB processing. As such it is possible to create weird states with
these commands.

Use with caution. Most of the time this will not be necessary.

.. cfgcmd:: set protocols static mroute <subnet> next-hop <address>
    [distance <distance>]

   Insert into the Multicast RIB Route `<subnet>` with specified next-hop.
   The distance can be specified as well if desired.

.. cfgcmd:: set protocols static mroute <subnet> next-hop <address> disable

   Do not install route for `<subnet>` into the Multicast RIB.

.. cfgcmd:: set protocols static mroute <subnet> interface <interface>
   [distance <distance>]

   Insert into the Multicast RIB Route `<subnet>` with specified `<interface>`.
   The distance can be specified as well if desired.

.. cfgcmd:: set protocols static mroute <subnet> interface <interface> disable

   Do not install route for `<subnet>` into the Multicast RIB.
