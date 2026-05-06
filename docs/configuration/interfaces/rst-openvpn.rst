.. _openvpn:

#######
OpenVPN
#######

Traditionally, hardware routers use IPsec exclusively because it is easy to 
implement in hardware, and their CPUs lack sufficient power for software-based 
encryption. This limitation is less relevant for VyOS, as it is a software 
router.

OpenVPN has been widely used on UNIX platforms for a long time and is a popular 
choice for remote-access VPNs. It also supports site-to-site connections.

OpenVPN offers the following advantages:

* It uses a single TCP or UDP connection and does not rely on packet source 
  addresses, so it works even through double NAT. This makes it well-suited for 
  public hotspots.

* It is easy to set up and offers very flexible split tunneling.

* A variety of client GUI frontends are available for any platform.

Disadvantages include:

* It is slower than IPsec due to higher protocol overhead and because it runs 
  in user mode, while IPsec on Linux runs in kernel mode.

* No operating system includes OpenVPN client software by default.

In the VyOS CLI, OpenVPN is configured as a network interface using ``set 
interfaces openvpn`` rather than ``set vpn``, which is often overlooked.

*************
Configuration
*************

.. cfgcmd:: set interfaces openvpn <interface> authentication password <text> 

   **Configure the password for the** ``auth-user-pass`` **authentication method.** 

   This option applies only to OpenVPN clients.

.. cfgcmd:: set interfaces openvpn <interface> authentication username <text>

   **Configure the username for the** ``auth-user-pass`` **authentication method.** 

   This option applies only to OpenVPN clients.

.. cfgcmd:: set interfaces openvpn <interface> description <description>

   Configure the description for the OpenVPN interface.

.. cfgcmd:: set interfaces openvpn <interface> device-type <tap | tun>
 
   **Configure the virtual network device type for the OpenVPN interface:**

   * ``tun`` **(default)**: Operates at Layer 3, encapsulating IPv4 or IPv6 packets.
   * ``tap``: Operates at Layer 2, encapsulating Ethernet 802.3 frames.
 
.. cfgcmd:: set interfaces openvpn <interface> disable

   Disable the specific OpenVPN interface. 

.. cfgcmd:: set interfaces openvpn <interface> encryption cipher < 3des | aes128 | aes128gcm | aes192 | aes192gcm | aes256 | aes256gcm | none >

   **Configure the static encryption cipher for the OpenVPN tunnel.**

   The ``cipher`` option maps to OpenVPN’s ``--cipher`` directive and specifies 
   the symmetric encryption algorithm for both control and data channels.

   This was previously the default encryption method in all OpenVPN modes. In 
   newer OpenVPN versions, the ``--cipher`` directive is considered **legacy** 
   and should be used only in compatibility scenarios.

.. cfgcmd:: set interfaces openvpn <interface> encryption data-ciphers < 3des | aes128 | aes128gcm | aes192 | aes192gcm | aes256 | aes256gcm | none >

   **Configure a prioritized list of negotiated ciphers for OpenVPN in** 
   ``client`` **or** ``server`` **mode.**

   The ``data-ciphers`` option represents a list of supported encryption 
   algorithms. It corresponds to OpenVPN’s ``--data-ciphers`` directive and 
   enables cipher negotiation, where both peers automatically agree on a mutually 
   supported cipher during session startup.

   .. note:: This option is not compatible with ``site-to-site`` mode.

.. cfgcmd:: set interfaces openvpn <interface> encryption data-ciphers-fallback < 3des | aes128 | aes128gcm | aes192 | aes192gcm | aes256 | aes256gcm | none >

   **Configure the fallback cipher for** ``site-to-site`` **mode.**

   The ``data-ciphers-fallback`` option maps to OpenVPN’s ``--data-ciphers-
   fallback`` directive. It defines the cipher to use if negotiation is **not 
   supported**.
   
   .. note:: This option ensures consistent encryption between two static peers 
             without cipher negotiation capability.

.. cfgcmd:: set interfaces openvpn <interface> hash <md5 | sha1 | sha256 | ...> 

   Configure the hashing algorithm for the OpenVPN interface.

.. cmdinclude:: /_include/interface-ip.txt
   :var0: openvpn
   :var1: vtun0

.. cmdinclude:: /_include/interface-ipv6.txt
   :var0: openvpn
   :var1: vtun0

.. cfgcmd:: set interfaces openvpn <interface> keep-alive failure-count <value>

   **Configure the number of tolerated keepalive packet failures.**

   Default: 60 consecutive failures.

.. cfgcmd:: set interfaces openvpn <interface> keep-alive interval <value>

   **Configure the frequency, in seconds, at which keepalive packets are sent.**

   Default: 10 seconds.

.. cfgcmd:: set interfaces openvpn <interface> local-address <address>
 
   Configure the local tunnel IP address for ``site-to-site`` mode.

.. cfgcmd:: set interfaces openvpn <interface> local-host <address>

   **Configure the local IP address to accept connections.** 

   If configured, OpenVPN binds to this IP address only. 

   By default, OpenVPN binds to all interfaces.

.. cfgcmd:: set interfaces openvpn <interface> local-port <port>

   Configure the local port to accept connections.

.. cfgcmd:: set interfaces openvpn <interface> mirror egress <monitor-interface>

   Configure mirroring of outgoing traffic from this OpenVPN interface to the 
   designated monitor interface.

.. cfgcmd:: set interfaces openvpn <interface> mirror ingress <monitor-interface>

   Configure mirroring of incoming traffic from this OpenVPN interface to the 
   designated monitor interface.

.. cfgcmd:: set interfaces openvpn <interface> mode <site-to-site | server | client>

   **Configure OpenVPN operation mode:** 

   * ``site-to-site``: Establishes a site-to-site VPN connection.
   * ``client``: Operates as a client in server-client mode.
   * ``server``: Operates as a server in server-client mode.


OpenVPN Data Channel Offload (DCO)
==================================

OpenVPN :abbr:`DCO (Data Channel Offload)` improves the performance of 
encrypted OpenVPN data processing by keeping most data handling in the kernel 
and avoiding frequent context switches between the kernel and user space.

As a result, packet processing becomes more efficient and may utilize hardware 
encryption offload support available in the kernel.
   
.. note:: 
      
   * :abbr:`DCO (Data Channel Offload)` is an **experimental**, not fully supported 
     OpenVPN feature. Some OpenVPN features and deployment scenarios are **not 
     compatible** with :abbr:`DCO (Data Channel Offload)`.

     For a complete list of supported features, visit:

     https://community.openvpn.net/openvpn/wiki/DataChannelOffload/Features

   * :abbr:`DCO (Data Channel Offload)` is configured per tunnel and disabled 
     by default. Existing tunnels operate without :abbr:`DCO (Data Channel 
     Offload)` unless it is explicitly enabled.

   * Enabling :abbr:`DCO (Data Channel Offload)` resets the interface.

**Best practice:** Create a new tunnel with :abbr:`DCO (Data Channel Offload)` 
enabled to avoid compatibility issues with existing clients.

.. cfgcmd:: set interfaces openvpn <interface> offload dco

   **Enable** :abbr:`DCO (Data Channel Offload)` **for the specified OpenVPN 
   interface.**

   Example:

   .. code-block:: none

     set interfaces openvpn vtun0 offload dco

   This command enables :abbr:`DCO (Data Channel Offload)` and loads the required 
   kernel module.
    
.. cfgcmd:: set interfaces openvpn <interface> openvpn-option <text>
 
   **Add raw OpenVPN configuration options to the openvpn.conf file.**
   
   OpenVPN provides many configuration options, but not all are available in the 
   VyOS CLI. 

   If a required option is missing, you may submit a feature request at 
   Phabricator so all users can benefit from it (see :ref:`issues_features`). 

   Alternatively, use ``openvpn-option`` to pass raw OpenVPN configuration options 
   to the openvpn.conf file. 

   .. warning:: Use this option only as a last resort. Invalid options or syntax 
      may prevent OpenVPN from starting. Check system logs for errors after applying 
      changes.

   Example:

   .. code-block:: none 

     set interfaces openvpn vtun0 openvpn-option 'persist-key'

   This command adds ``persist-key`` to the configuration file. This solves the 
   problem by persisting keys across resets, so they do not need to be re-read.

   .. code-block:: none

     set interfaces openvpn vtun0 openvpn-option 'route-up &quot;/config/auth/tun_up.sh arg1&quot;'

   This command adds ``route-up "/config/auth/tun_up.sh arg1"`` to the 
   configuration file. This option is executed after connection authentication, 
   either immediately or after a short delay, as defined. 

   Ensure the path and arguments are enclosed in single or double quotes.

   .. note:: Some raw configuration options require quotes. To include them, use 
      the &quot; statement.

.. cfgcmd:: set interfaces openvpn <interface> persistent-tunnel

   **Enable always-active mode for the TUN/TAP device.**

   When enabled, the TUN/TAP device remains active upon connection resets or 
   daemon reloads.

.. cfgcmd:: set interfaces openvpn <interface> protocol <udp | tcp-passive | tcp-active >

   **Configure the protocol for OpenVPN communication with a remote host:**

   * ``udp`` **(default)**: Uses the UDP protocol.
   * ``tcp-passive``: Uses the TCP protocol and accepts connections passively.
   * ``tcp-active``: Uses the TCP protocol and initiates connections actively.

.. cfgcmd:: set interfaces openvpn <interface> redirect <interface>

   Enable redirection of incoming packets to the specified interface.

.. cfgcmd:: set interfaces openvpn <interface> remote-address <address>

   Configure the remote tunnel IP address for site-to-site mode.

.. cfgcmd:: set interfaces openvpn <interface> remote-host <address | host>

   **Configure the IPv4/IPv6 address or hostname for a server device if OpenVPN 
   runs in client mode.**

   This setting is not used in server mode.

.. cfgcmd:: set interfaces openvpn <interface> remote-port <port>

   Configure the remote port to connect to the server.

.. cfgcmd:: set interfaces openvpn <interface> replace-default-route 

   Configure the OpenVPN tunnel as the default route.    

.. cfgcmd:: set interfaces openvpn <interface> server bridge disable

   Disable the given instance.

.. cfgcmd:: set interfaces openvpn <interface> server bridge gateway <ipv4 address>

   Configure the gateway IP address.

.. cfgcmd:: set interfaces openvpn <interface> server bridge start <ipv4 address>

   Configure the first IP address in the pool to allocate to connecting clients.

.. cfgcmd:: set interfaces openvpn <interface> server bridge stop <ipv4 address>

   Configure the last IP address in the pool to allocate to connecting clients.

.. cfgcmd:: set interfaces openvpn <interface> server bridge subnet-mask <ipv4 subnet mask>

   Configure the subnet mask pushed to dynamic clients.

.. cfgcmd:: set interfaces openvpn <interface> server client <name>

   Configure the Common Name (CN) specified in the client certificate.

.. cfgcmd:: set interfaces openvpn <interface> server client <name> disable

   Disable the client connection.

.. cfgcmd:: set interfaces openvpn <interface> server client <name> ip <address>

   Configure the IPv4/IPv6 address for the client.

.. cfgcmd:: set interfaces openvpn <interface> server client <name> push-route <subnet>

   Configure a route to be pushed to the specific client. 

.. cfgcmd:: set interfaces openvpn <interface> server client <name> subnet <subnet>

   **Configure a fixed subnet to be routed from the server to the specified 
   client.** 

   Used as OpenVPN’s ``iroute`` directive.

.. cfgcmd:: set interfaces openvpn <interface> server client-ip-pool start <address>

   Configure the first IP address in the subnet's IPv4 pool to be dynamically 
   allocated to connecting clients.   

.. cfgcmd:: set interfaces openvpn <interface> server client-ip-pool stop <address>

   Configure the last IP address in the subnet's IPv4 pool to be dynamically 
   allocated to connecting clients.

.. cfgcmd:: set interfaces openvpn <interface> server client-ip-pool subnet <netmask>

   **Configure the subnet mask pushed to dynamic clients.** 

   Use this command only for the TAP device type. Do not use it for bridged 
   interfaces.

.. cfgcmd:: set interfaces openvpn <interface> server client-ipv6-pool base <ipv6addr/bits>

   Configure the IPv6 address pool for dynamic assignment to clients.

.. cfgcmd:: set interfaces openvpn <interface> server domain-name <name>

   Configure the DNS suffix to be pushed to all clients.

.. cfgcmd:: set interfaces openvpn <interface> server max-connections <1-4096>

   Configure the maximum number of client connections.

.. cfgcmd:: set interfaces openvpn <interface> server mfa totp challenge <enable | disable>

   If enabled, openvpn-otp expects a password as a result of the challenge/
   response protocol.

.. cfgcmd:: set interfaces openvpn <interface> server mfa totp digits <1-65535>

   **Configure the number of digits to use for the** :abbr:`TOTP (Time-based 
   One-Time Password)` **hash.** 

   Default: 6.

.. cfgcmd:: set interfaces openvpn <interface> server mfa totp drift <1-65535>

   **Configure the time drift in seconds.** 

   Default: 0.

.. cfgcmd:: set interfaces openvpn <interface> server mfa totp slop <1-65535>

   **Configure the allowed clock slop in seconds.**

   Default: 180.

.. cfgcmd:: set interfaces openvpn <interface> server mfa totp step <1-65535>

   **Configure the step value for** :abbr:`TOTP (Time-based One-Time Password)`
   **in seconds.**

   Default: 30.

.. cfgcmd:: set interfaces openvpn <interface> server name-server <address>

   Define the client DNS configuration to be used with the connection.

.. cfgcmd:: set interfaces openvpn <interface> server push-route <subnet>

   Configure the route to be pushed to all clients.   

.. cfgcmd:: set interfaces openvpn <interface> server reject-unconfigured-client

   Reject connections from clients that are not explicitly configured. 

.. cfgcmd:: set interfaces openvpn <interface> server subnet <subnet>

   **Configure the IPv4 or IPv6 network.** 

   This parameter is mandatory when operating in server mode.

.. cfgcmd:: set interfaces openvpn <interface> server topology < net30 | point-to-point | subnet>

   **Configure the virtual addressing topology for** ``tun`` **mode.**

   This command does not affect ``tap`` mode, which always uses the ``subnet`` 
   topology.

   * ``subnet`` **(default)**: Allocates a single IP address to each connecting client. 
     This is the recommended topology.
   * ``net30``: Allocates a /30 subnet to each connecting client. This is a legacy 
     topology used to support Windows clients. It is now effectively deprecated.
   * ``point-to-point``: Creates a point-to-point topology where the remote 
     endpoint of the client’s ``tun`` interface always points to the local endpoint  
     of the server’s ``tun`` interface.

     Like ``subnet``, this topology allocates a single IP address per client. Use it 
     only if no clients run Windows operating systems.


.. cfgcmd:: set interfaces openvpn <interface> shared-secret-key <key>

   Configure the static secret key for a site-to-site OpenVPN connection.

.. cfgcmd:: set interfaces openvpn <interface> tls auth-key <key>

   **Configure the TLS secret key for tls-auth.**

   This adds an HMAC signature to all SSL/TLS handshake packets to verify 
   integrity.

   Use ``run generate pki openvpn shared-secret install <name>`` to generate 
   the key. 

.. cfgcmd:: set interfaces openvpn <interface> tls ca-certificate <name>

   Configure the Certificate Authority chain in the PKI configuration.

.. cfgcmd:: set interfaces openvpn <interface> tls certificate <name>

   Configure the certificate name in the PKI configuration.

.. cfgcmd:: set interfaces openvpn <interface> tls crypt-key

   Configure a shared secret key to provide an additional level of security, 
   a variant similar to tls-auth.

.. cfgcmd:: set interfaces openvpn <interface> tls dh-params

   Configure Diffie-Hellman parameters for server mode. 

.. cfgcmd:: set interfaces openvpn <interface> tls peer-fingerprint <text>

   Configure the peer certificate SHA256 fingerprint for site-to-site mode.

.. cfgcmd:: set interfaces openvpn <interface> tls role <active | passive>

   **Configure the TLS negotiation role, preferably used in site-to-site mode:**

   * ``active``: Initiates TLS negotiation actively.
   * ``passive``: Waits for incoming TLS connections.

.. cfgcmd:: set interfaces openvpn <interface> tls tls-version-min <1.0 | 1.1 | 1.2 | 1.3 >

   Configure the minimum TLS version to be accepted from the peer.

.. cfgcmd:: set interfaces openvpn <interface> use-lzo-compression

   Configure fast LZO compression on this TUN/TAP interface.

.. cfgcmd:: set interfaces openvpn <interface> vrf <name>

   Assign the interface to a specific VRF instance.

**************
Operation mode
**************

.. opcmd:: show openvpn site-to-site

   Show tunnel status for OpenVPN site-to-site interfaces.

.. opcmd:: show openvpn server

   Show tunnel status for OpenVPN server interfaces.

.. opcmd:: show openvpn client

   Show tunnel status for OpenVPN client interfaces.

.. opcmd:: show log openvpn

   Show logs for all OpenVPN interfaces.

.. opcmd:: show log openvpn interface <interface>

   Show logs for the specific OpenVPN interface.

.. opcmd:: reset openvpn client <text>

   Reset the specified OpenVPN client.

.. opcmd:: reset openvpn interface <interface>

   Reset the OpenVPN process on the specified interface.

.. opcmd::  generate openvpn client-config interface <interface> ca <name> certificate <name> 

   Generate an OpenVPN client configuration file in the .ovpn format for client machines.

********
Examples
********

This section covers examples of OpenVPN configurations for various deployments.

.. toctree::
   :maxdepth: 1
   :includehidden:

   openvpn-examples

.. include:: /_include/common-references.txt
