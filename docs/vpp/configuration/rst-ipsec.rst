:lastproofread: 2025-09-04

.. _vpp_config_ipsec:

.. include:: /_include/need_improvement.txt

#######################
VPP IPsec Configuration
#######################

VPP Dataplane in VyOS can offload IPSec processing from kernel. This allows to speed-up IPSec traffic handling significantly, when necessary conditions are met.

.. note::
   VPP IPsec implementation is not as feature rich as Linux kernel IPsec. It supports only a subset of algorithms and modes.

Requirements
============

To make IPSec offloading work, following requirements must be met:

* VPP dataplane must be configured.
* VPP :doc:`IPsec settings </vpp/configuration/dataplane/ipsec>` should be configured as needed.
* IPSec should be configured in the VPN configuration section, see :doc:`/configuration/vpn/ipsec/index`.
* Both source and destination of the IPSec traffic must be reachable via VPP interfaces, so it can perform both encryption and decryption of the traffic.

Integration Details
===================

VPP Dataplane offloads IPSec processing from kernel, but does not handle IPSec configuration itself. IPSec configuration management and control-plane operation, like IKE negotiation, is still done by the kernel and other daemons.

After an IPSec tunnel is configured in the kernel, VPP receives the necessary information via netlink messages and creates a corresponding SAs and policies to be able to offload the traffic.

When VPP is used for offloading IPsec, it creates a virtual interface of a specific type to connect to a peer. The type of the interface can be configured using the ``interface-type`` parameter in the dataplane settings.

Supported IPsec Modes
=====================

VPP supports offloading IPsec connections in the following IPsec modes:

* Tunnel mode
* Transport mode

Supported Encryption and Integrity Algorithms
=============================================

.. warning::

    Since VPP dataplane is used only to offload IPsec traffic processing, algorithms mentioned below are applicable to ESP profiles in the IPsec configuration. IKE profiles are not affected by these limitations and can use any algorithms supported by the kernel.

VPP **supports** only the following **encryption algorithms**:

* AES-CBC
* AES-GCM with ICV

VPP **does not** support the following **encryption algorithms**:

* Null encryption
* AES-CTR
* AES-CCM with ICV
* Null encryption with AES-GMAC
* 3DES-EDE-CBC
* Blowfish-CBC
* Camellia-CBC
* Camellia-COUNTER
* Camellia-CCM with ICV
* Serpent-CBC
* Twofish-CBC
* CAST-CBC
* ChaCha20/Poly1305 with ICV

VPP **supports** the following **integrity algorithms**:

* MD5 HMAC
* SHA1 HMAC
* SHA2_256_128 HMAC
* SHA2_384_192 HMAC
* SHA2_512_256 HMAC

VPP **does not** support the following **integrity algorithms**:

* MD5_128 HMAC
* SHA1_160 HMAC
* SHA2_256_96 HMAC
* AES XCBC
* AES CMAC
* AES-GMAC

If you have configured ESP profiles with algorithms not supported by VPP and the traffic for such peers flows trough VPP interfaces, such traffic will be dropped.

Configuration Examples
======================

**ACL for VPP IPsec Traffic**

When using VPP for offloading IPsec traffic, you may need to adjust your firewall rules to allow the necessary protocols and ports. Below is an example of how to configure ACLs for VPP IPsec traffic:

.. code-block:: none

    set vpp acl ip interface <interface-name> input acl-tag 10 tag-name 'IPSEC'
    set vpp acl ip tag-name IPSEC description 'Allow IPsec traffic'
    set vpp acl ip tag-name IPSEC rule 10 action 'permit'
    set vpp acl ip tag-name IPSEC rule 10 destination port '500'
    set vpp acl ip tag-name IPSEC rule 10 protocol 'tcp'
    set vpp acl ip tag-name IPSEC rule 20 action 'permit'
    set vpp acl ip tag-name IPSEC rule 20 destination port '500'
    set vpp acl ip tag-name IPSEC rule 20 protocol 'udp'
    set vpp acl ip tag-name IPSEC rule 30 action 'permit'
    set vpp acl ip tag-name IPSEC rule 30 destination port '4500'
    set vpp acl ip tag-name IPSEC rule 30 protocol 'tcp'
    set vpp acl ip tag-name IPSEC rule 40 action 'permit'
    set vpp acl ip tag-name IPSEC rule 40 destination port '4500'
    set vpp acl ip tag-name IPSEC rule 40 protocol 'udp'
    set vpp acl ip tag-name IPSEC rule 50 action 'permit'
    set vpp acl ip tag-name IPSEC rule 50 protocol 'esp'

Pay attention to the order of the rules, as they are processed sequentially. Make sure to place IPsec-related rules before any other rules that might deny traffic to ensure that IPsec traffic is allowed.

**Simple VTI-based IPsec Tunnel**

On the VPP host:

.. code-block:: none

    set interfaces ethernet eth1 address '192.168.1.1/24'
    set interfaces ethernet eth2 address '192.168.100.1/24'

    set interfaces vti vti1
    set protocols static route 192.168.200.0/24 interface vti1

    set vpn ipsec authentication psk psk1 id 'peerA'
    set vpn ipsec authentication psk psk1 id 'peerB'
    set vpn ipsec authentication psk psk1 secret 'AB'

    set vpn ipsec esp-group esp1 mode 'tunnel'
    set vpn ipsec esp-group esp1 pfs 'disable'
    set vpn ipsec esp-group esp1 proposal 10 encryption 'aes256'
    set vpn ipsec esp-group esp1 proposal 10 hash 'sha256'
    set vpn ipsec ike-group ike1 close-action 'none'
    set vpn ipsec ike-group ike1 dead-peer-detection action 'clear'
    set vpn ipsec ike-group ike1 proposal 10 encryption 'aes256'
    set vpn ipsec ike-group ike1 proposal 10 hash 'sha256'

    set vpn ipsec interface 'eth1'

    set vpn ipsec site-to-site peer peerB authentication local-id 'peerA'
    set vpn ipsec site-to-site peer peerB authentication mode 'pre-shared-secret'
    set vpn ipsec site-to-site peer peerB authentication remote-id 'peerB'
    set vpn ipsec site-to-site peer peerB connection-type 'none'
    set vpn ipsec site-to-site peer peerB default-esp-group 'esp1'
    set vpn ipsec site-to-site peer peerB ike-group 'ike1'
    set vpn ipsec site-to-site peer peerB local-address '192.168.1.1'
    set vpn ipsec site-to-site peer peerB remote-address '192.168.1.3'
    set vpn ipsec site-to-site peer peerB vti bind 'vti1'
    set vpn ipsec site-to-site peer peerB vti traffic-selector remote prefix '192.168.200.0/24'

    set vpp settings interface eth1
    set vpp settings interface eth2
    set vpp settings ipsec netlink rx-buffer-size '32000'
    set vpp settings lcp ignore-kernel-routes

Where:

- ``eth1`` is the interface connected to the IPsec peer.
- ``eth2`` is the interface connected to the local subnet, where unencrypted traffic is expected.
- ``192.168.100.0/24`` is the local subnet that will be accessible through the IPsec tunnel.
- ``192.168.200.0/24`` is the remote subnet that will be accessible through the IPsec tunnel.
- ``vti1`` is the VTI interface created by VPP for the IPsec tunnel.
- ``peerA`` and ``peerB`` are the identifiers for the local side and remote peer, respectively.

.. note::

    **What is important in this configuration**

    VPP uses only remote traffic-selector to determine what traffic should be offloaded to the IPsec tunnel. 

    Adding additional routes via VTI interface does not affect actual VPP IPsec operation.

Potential Issues and Troubleshooting
====================================

Improper IPsec configuration can lead to various issues, including:

* **Unidirectional traffic flow or acceleration**

  If kernel has a conflicting route for the remote subnet, such route may take precedence over the policy route created for the IPsec tunnel in VPP. This may lead to unidirectional traffic flow or acceleration only in one direction. This has no security impact because traffic will still be encrypted by the kernel, but it may lead to performance degradation. To avoid this, ensure that no conflicting routes exist in the kernel routing table.

* **Conflicting with kernel routes**

  If the kernel routes synchronization option is enabled, VPP will install all the routes from kernel. If you have there routes configured via VTI interfaces to the IPsec peer, they will conflict with the policy routes created for the IPsec tunnel in VPP. Consider using policy-based IPSec configuration to avoid this or :ref:`disable the kernel routes synchronization <vpp_config_dataplane_lcp_ignore-kernel-routes>`.

* **Unsupported algorithms**

  If you have configured ESP profiles with algorithms not supported by VPP and the traffic for such peers flows through VPP interfaces, such traffic will be dropped. You can check system logs for messages from VPP with ``linux-cp/ipsec: Invalid/Unsupported crypto algo`` or ``linux-cp/ipsec: Invalid/Unsupported integ algo`` line to identify such cases.

* **Connection is established but no traffic flows**

  Even if you use compatible algorithms, there can be other reasons why traffic is not flowing. One of most frequent is blocking traffic between peers - that is especially common in public clouds. Make sure that TCP/UDP ports 500 and 4500 and ESP protocol are allowed between the peers. Alternatively, consider enforcing UDP encapsulation on both sides of the tunnel:

  .. cfgcmd:: set vpn ipsec site-to-site peer <peer-name> force-udp-encapsulation
