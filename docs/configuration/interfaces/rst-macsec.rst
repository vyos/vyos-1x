:lastproofread: 2026-02-13

.. _macsec-interface:

######
MACsec
######

MACsec is an IEEE standard (IEEE 802.1AE) for MAC security, introduced in 
2006. It enables protocol-independent connectivity between two hosts, providing 
data confidentiality, authenticity, and integrity using GCM-AES ciphers. MACsec 
operates at the Ethernet layer as a Layer 2 protocol and secures traffic within 
Layer 2 networks, including DHCP and ARP requests. It does not compete with 
other security solutions, such as IPsec (Layer 3) or TLS (Layer 4), as each 
addresses distinct use cases.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-common-with-dhcp.txt
   :var0: macsec
   :var1: macsec0

MACsec options
==============

.. cfgcmd:: set interfaces macsec <interface> security cipher <gcm-aes-128|gcm-aes-256>

  **Configure the cipher suite for the MACsec interface.**

  This configuration parameter is mandatory.

.. cfgcmd:: set interfaces macsec <interface> security encrypt

  **Enable encryption on the MACsec interface.**

  By default, MACsec interfaces only provide authentication; encryption is 
  optional.

  When enabled, outgoing packets are encrypted using the configured cipher suite.

.. cfgcmd:: set interfaces macsec <interface> source-interface <physical-source>

  **Configure a physical source interface for the MACsec interface.** 

  Traffic transmitted through this interface is authenticated and, if configured, 
  encrypted.

MACsec key management
---------------------

**Static** :abbr:`SAK (Secure Authentication Key)` **mode**

In static SAK mode, administrators must manually configure and update SAKs on 
each MACsec peer. :abbr:`MKA (MACsec Key Agreement protocol)` cannot be used in 
this mode.

.. cfgcmd:: set interfaces macsec <interface> security static key <key>

  **Configure the Transmit (TX) SAK for the MACsec interface.**

  The key must be a 16-byte (GCM-AES-128) or 64-byte (GCM-AES-256) hexadecimal 
  string.

.. cfgcmd:: set interfaces macsec <interface> security static peer <peer> mac <mac address>

  **Configure the MAC address associated with the MACsec peer.**

.. cfgcmd:: set interfaces macsec <interface> security static peer <peer> key <key>

  **Configure the RX SAK for traffic from the MACsec peer.**

  The key must be a 16-byte (GCM-AES-128) or 64-byte (GCM-AES-256) hexadecimal 
  string.

.. cfgcmd:: set interfaces macsec <interface> security static peer <peer> disable

  Disable the specific MACsec peer. 


**Dynamic** :abbr:`MKA (MACsec Key Agreement protocol)` **mode**

In this mode, the :abbr:`MKA (MACsec Key Agreement protocol)` protocol is used 
to generate, distribute, and update :abbr:`CAKs (MACsec Connectivity 
Association Keys)`, and to authenticate MACsec peers.


.. cfgcmd:: set interfaces macsec <interface> security mka cak <key>

  **Configure the** :abbr:`CAK (MACsec Connectivity Association Key)` **for the 
  MACsec interface.**

  The :abbr:`CAK (MACsec Connectivity Association Key)` and its :abbr:`CKN 
  (MACsec Connectivity Association Key Name)` form the pre-shared master key pair 
  used to authenticate MACsec peers.

.. cfgcmd:: set interfaces macsec <interface> security mka ckn <key>

  Configure the :abbr:`CKN (MACsec Connectivity Association Key Name)` for the 
  MACsec interface.

.. cfgcmd:: set interfaces macsec <interface> security mka priority <priority>

  Configure the MKA key server priority for the MACsec interface. 

  The peer with the lowest priority is elected as the key server.

Replay protection
-----------------

.. cfgcmd:: set interfaces macsec <interface> security replay-window <window>

  The replay protection window defines how many out-of-order frames can be 
  received before they are dropped as a potential replay attack.

  The following values are valid: 

  - ``0``: Any out-of-order frame is immediately dropped. 
  - ``1-4294967295``: Allows the specified number of out-of-order frames. 

*********
Operation
*********

.. opcmd:: run generate macsec mka cak <gcm-aes-128|gcm-aes-256>

  Generate a 128-bit (GCM-AES-128) or 256-bit (GCM-AES-256) :abbr:`MKA (MACsec 
  Key Agreement protocol)` :abbr:`CAK (MACsec Connectivity Association Key)`.

  .. code-block:: none

    vyos@vyos:~$ generate macsec mka cak gcm-aes-128
    20693b6e08bfa482703a563898c9e3ad

.. opcmd:: run generate macsec mka ckn

  Generate an :abbr:`MKA (MACsec Key Agreement protocol)` :abbr:`CAK (MACsec 
  Connectivity Association Key)`.

  .. code-block:: none

    vyos@vyos:~$ generate macsec mka ckn
    88737efef314ee319b2cbf30210a5f164957d884672c143aefdc0f5f6bc49eb2

.. opcmd:: show interfaces macsec

  Show all MACsec interfaces.

  .. code-block:: none

    vyos@vyos:~$ show interfaces macsec
    17: macsec1: protect on validate strict sc off sa off encrypt on send_sci on end_station off scb off replay off
        cipher suite: GCM-AES-128, using ICV length 16
        TXSC: 005056bfefaa0001 on SA 0
    20: macsec0: protect on validate strict sc off sa off encrypt off send_sci on end_station off scb off replay off
        cipher suite: GCM-AES-128, using ICV length 16
        TXSC: 005056bfefaa0001 on SA 0

.. opcmd:: show interfaces macsec <interface>

  Show information for a specific MACsec interface.

  .. code-block:: none

    vyos@vyos:~$ show interfaces macsec macsec1
    17: macsec1: protect on validate strict sc off sa off encrypt on send_sci on end_station off scb off replay off
        cipher suite: GCM-AES-128, using ICV length 16
        TXSC: 005056bfefaa0001 on SA 0

********
Examples
********

**Site-to-site MACsec with dynamic MKA over an untrusted network**

In the following example, two routers (R1 and R2) are connected via an 
untrusted switch, using their ``eth1`` interfaces as the underlay. The MACsec 
interface (``macsec1``) with dynamic MKA encrypts traffic between them.

Topology details:

* R1 IP addresses: ``192.0.2.1/24`` and ``2001:db8::1/64``.
* R2 IP addresses: ``192.0.2.2/24`` and ``2001:db8::2/64``.

**R1**

.. code-block:: none

  set interfaces macsec macsec1 address '192.0.2.1/24'
  set interfaces macsec macsec1 address '2001:db8::1/64'
  set interfaces macsec macsec1 security cipher 'gcm-aes-128'
  set interfaces macsec macsec1 security encrypt
  set interfaces macsec macsec1 security mka cak '232e44b7fda6f8e2d88a07bf78a7aff4'
  set interfaces macsec macsec1 security mka ckn '40916f4b23e3d548ad27eedd2d10c6f98c2d21684699647d63d41b500dfe8836'
  set interfaces macsec macsec1 source-interface 'eth1'

**R2**

.. code-block:: none

  set interfaces macsec macsec1 address '192.0.2.2/24'
  set interfaces macsec macsec1 address '2001:db8::2/64'
  set interfaces macsec macsec1 security cipher 'gcm-aes-128'
  set interfaces macsec macsec1 security encrypt
  set interfaces macsec macsec1 security mka cak '232e44b7fda6f8e2d88a07bf78a7aff4'
  set interfaces macsec macsec1 security mka ckn '40916f4b23e3d548ad27eedd2d10c6f98c2d21684699647d63d41b500dfe8836'
  set interfaces macsec macsec1 source-interface 'eth1'

Pinging (IPv6) the other host and intercepting traffic on ``eth1`` confirm that 
the content is encrypted.

.. code-block:: none

  17:35:44.586668 00:50:56:bf:ef:aa > 00:50:56:b3:ad:d6, ethertype Unknown (0x88e5), length 150:
          0x0000:  2c00 0000 000a 0050 56bf efaa 0001 d9fb  ,......PV.......
          0x0010:  920a 8b8d 68ed 9609 29dd e767 25a4 4466  ....h...)..g%.Df
          0x0020:  5293 487b 9990 8517 3b15 22c7 ea5c ac83  R.H{....;."..\..
          0x0030:  4c6e 13cf 0743 f917 2c4e 694e 87d1 0f09  Ln...C..,NiN....
          0x0040:  0f77 5d53 ed75 cfe1 54df 0e5a c766 93cb  .w]S.u..T..Z.f..
          0x0050:  c4f2 6e23 f200 6dfe 3216 c858 dcaa a73b  ..n#..m.2..X...;
          0x0060:  4dd1 9358 d9e4 ed0e 072f 1acc 31c4 f669  M..X...../..1..i
          0x0070:  e93a 9f38 8a62 17c6 2857 6ac5 ec11 8b0e  .:.8.b..(Wj.....
          0x0080:  6b30 92a5 7ccc 720b                      k0..|.r.

Disabling encryption on the MACsec interface by removing the ``security 
encrypt`` option shows the unencrypted but authenticated content.

.. code-block:: none

  17:37:00.746155 00:50:56:bf:ef:aa > 00:50:56:b3:ad:d6, ethertype Unknown (0x88e5), length 150:
          0x0000:  2000 0000 0009 0050 56bf efaa 0001 86dd  .......PV.......
          0x0010:  6009 86f3 0040 3a40 2001 0db8 0000 0000  `....@:@........
          0x0020:  0000 0000 0000 0001 2001 0db8 0000 0000  ................
          0x0030:  0000 0000 0000 0002 8100 d977 0f30 0003  ...........w.0..
          0x0040:  1ca0 c65e 0000 0000 8d93 0b00 0000 0000  ...^............
          0x0050:  1011 1213 1415 1617 1819 1a1b 1c1d 1e1f  ................
          0x0060:  2021 2223 2425 2627 2829 2a2b 2c2d 2e2f  .!"#$%&'()*+,-./
          0x0070:  3031 3233 3435 3637 87d5 eed3 3a39 d52b  01234567....:9.+
          0x0080:  a282 c842 5254 ef28                      ...BRT.(

**Site-to-site MACsec with static SAK over an untrusted network**

This example uses the same topology as above, but applies static SAK mode to 
the MACsec interface configuration.

**R1**

.. code-block:: none

  set interfaces macsec macsec1 address '192.0.2.1/24'
  set interfaces macsec macsec1 address '2001:db8::1/64'
  set interfaces macsec macsec1 security cipher 'gcm-aes-128'
  set interfaces macsec macsec1 security encrypt
  set interfaces macsec macsec1 security static key 'ddd6f4a7be4d8bbaf88b26f10e1c05f7'
  set interfaces macsec macsec1 security static peer R2 mac 00:11:22:33:44:02
  set interfaces macsec macsec1 security static peer R2 key 'eadcc0aa9cf203f3ce651b332bd6e6c7'
  set interfaces macsec macsec1 source-interface 'eth1'

**R2**

.. code-block:: none

  set interfaces macsec macsec1 address '192.0.2.2/24'
  set interfaces macsec macsec1 address '2001:db8::2/64'
  set interfaces macsec macsec1 security cipher 'gcm-aes-128'
  set interfaces macsec macsec1 security encrypt
  set interfaces macsec macsec1 security static key 'eadcc0aa9cf203f3ce651b332bd6e6c7'
  set interfaces macsec macsec1 security static peer R1 mac 00:11:22:33:44:01
  set interfaces macsec macsec1 security static peer R1 key 'ddd6f4a7be4d8bbaf88b26f10e1c05f7'
  set interfaces macsec macsec1 source-interface 'eth1'

***************
MACsec over WAN
***************

MACsec offers an alternative to traditional tunneling solutions by securing 
Layer 2 with integrity, origin authentication, and optional encryption. 

While typically deployed between hosts and access switches, MACsec can also 
secure traffic over a WAN. In the following example, we combine VXLAN (for 
transport) and MACsec (for security) to create a secure tunnel between two 
sites.

**R1 MACsec01**

.. code-block:: none

  set interfaces macsec macsec1 address '192.0.2.1/24'
  set interfaces macsec macsec1 address '2001:db8::1/64'
  set interfaces macsec macsec1 security cipher 'gcm-aes-128'
  set interfaces macsec macsec1 security encrypt
  set interfaces macsec macsec1 security static key 'ddd6f4a7be4d8bbaf88b26f10e1c05f7'
  set interfaces macsec macsec1 security static peer SEC02 key 'eadcc0aa9cf203f3ce651b332bd6e6c7'
  set interfaces macsec macsec1 security static peer SEC02 mac '00:11:22:33:44:02'
  set interfaces macsec macsec1 source-interface 'vxlan1'
  set interfaces vxlan vxlan1 mac '00:11:22:33:44:01'
  set interfaces vxlan vxlan1 remote '10.1.3.3'
  set interfaces vxlan vxlan1 source-address '172.16.100.1'
  set interfaces vxlan vxlan1 vni '10'
  set protocols static route 10.1.3.3/32 next-hop 172.16.100.2

**R2 MACsec02**

.. code-block:: none

  set interfaces macsec macsec1 address '192.0.2.2/24'
  set interfaces macsec macsec1 address '2001:db8::2/64'
  set interfaces macsec macsec1 security cipher 'gcm-aes-128'
  set interfaces macsec macsec1 security encrypt
  set interfaces macsec macsec1 security static key 'eadcc0aa9cf203f3ce651b332bd6e6c7'
  set interfaces macsec macsec1 security static peer SEC01 key 'ddd6f4a7be4d8bbaf88b26f10e1c05f7'
  set interfaces macsec macsec1 security static peer SEC01 mac '00:11:22:33:44:01'
  set interfaces macsec macsec1 source-interface 'vxlan1'
  set interfaces vxlan vxlan1 mac '00:11:22:33:44:02'
  set interfaces vxlan vxlan1 remote '10.1.2.2'
  set interfaces vxlan vxlan1 source-address '172.16.100.2'
  set interfaces vxlan vxlan1 vni '10'
  set protocols static route 10.1.2.2/32 next-hop 172.16.100.1
