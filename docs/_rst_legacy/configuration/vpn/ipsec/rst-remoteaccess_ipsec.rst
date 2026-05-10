.. _remoteaccess_ipsec:

############################
IPSec IKEv2 Remote Access VPN
############################

.. TODO:: Convert raw command blocks in this file to cfgcmd/opcmd
   directives for command coverage tracking.

Internet Key Exchange version 2 (IKEv2) is a tunneling protocol, based on IPsec,
that establishes a secure VPN communication between VPN devices, and defines
negotiation and authentication processes for IPsec security associations (SAs).
It is often known as IKEv2/IPSec or IPSec IKEv2 remote-access — or road-warriors
as others call it.

Key exchange and payload encryption is done using IKE and ESP proposals as known
from IKEv1 but the connections are faster to establish, more reliable, and also
support roaming from IP to IP (called MOBIKE which makes sure your connection
does not drop when changing networks from e.g. WIFI to LTE and back).
Authentication can be achieved with X.509 certificates.

Setting up certificates:
^^^^^^^^^^^^^^^^^^^^^^^^
First of all, we need to create a CA root certificate and server certificate
on the server side.

.. code-block:: none

  vyos@vpn.vyos.net# run generate pki ca install ca_root
  Enter private key type: [rsa, dsa, ec] (Default: rsa)
  Enter private key bits: (Default: 2048)
  Enter country code: (Default: GB)
  Enter state: (Default: Some-State)
  Enter locality: (Default: Some-City)
  Enter organization name: (Default: VyOS)
  Enter common name: (Default: vyos.io)
  Enter how many days certificate will be valid: (Default: 1825)
  Note: If you plan to use the generated key on this router, do not encrypt the private key.
  Do you want to encrypt the private key with a passphrase? [y/N] N
  2 value(s) installed. Use "compare" to see the pending changes, and "commit" to apply.
  [edit]


  vyos@vpn.vyos.net# comp
  [pki ca]
  + ca_root {
  +     certificate "MIIDnTCCAoWgAwI…."
  +     private {
  +         key "MIIEvAIBADANBgkqhkiG9….”

  vyos@vpn.vyos.net# run generate pki certificate sign ca_root install server_cert
  Do you already have a certificate request? [y/N] N
  Enter private key type: [rsa, dsa, ec] (Default: rsa)
  Enter private key bits: (Default: 2048)
  Enter country code: (Default: GB)
  Enter state: (Default: Some-State)
  Enter locality: (Default: Some-City)
  Enter organization name: (Default: VyOS)
  Enter common name: (Default: vyos.io) vpn.vyos.net
  Do you want to configure Subject Alternative Names? [y/N] N
  Enter how many days certificate will be valid: (Default: 365)
  Enter certificate type: (client, server) (Default: server)
  Note: If you plan to use the generated key on this router, do not encrypt the private key.
  Do you want to encrypt the private key with a passphrase? [y/N] N
  2 value(s) installed. Use "compare" to see the pending changes, and "commit" to apply.

  vyos@vpn.vyos.net# comp
  [pki certificate]
  + server_cert {
  +     certificate "MIIDuzCCAqOgAwIBAgIUaSrCPWx………"
  +     private {
  +         key "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBK….."
  +     }
  + }


Once the command is completed, it will add the certificate to the configuration
session, to the pki subtree. You can then review the proposed changes and
commit them.

Setting up IPSec:
^^^^^^^^^^^^^^^^^

After the PKI certs are all set up we can start configuring our IPSec/IKE
proposals used for key-exchange end data encryption. The used encryption ciphers
and integrity algorithms vary from operating system to operating system. The
ones used in this example are validated to work on Windows 10.

.. code-block:: none

  set vpn ipsec esp-group ESP-RW lifetime '3600'
  set vpn ipsec esp-group ESP-RW pfs 'disable'
  set vpn ipsec esp-group ESP-RW proposal 10 encryption 'aes128gcm128'
  set vpn ipsec esp-group ESP-RW proposal 10 hash 'sha256'

  set vpn ipsec ike-group IKE-RW key-exchange 'ikev2'
  set vpn ipsec ike-group IKE-RW lifetime '7200'
  set vpn ipsec ike-group IKE-RW proposal 10 dh-group '14'
  set vpn ipsec ike-group IKE-RW proposal 10 encryption 'aes128gcm128'
  set vpn ipsec ike-group IKE-RW proposal 10 hash 'sha256'

Every connection/remote-access pool we configure also needs a pool where we
can draw our client IP addresses from. We provide one IPv4 and IPv6 pool.
Authorized clients will receive an IPv4 address from the configured IPv4 prefix
and an IPv6 address from the IPv6 prefix. We can also send some DNS nameservers
down to our clients used on their connection.

.. code-block:: none

  set vpn ipsec remote-access pool ra-rw-ipv4 name-server '192.0.2.1'
  set vpn ipsec remote-access pool ra-rw-ipv4 prefix '192.0.2.128/25'

  set vpn ipsec remote-access pool ra-rw-ipv6 name-server '2001:db8:1000::1'
  set vpn ipsec remote-access pool ra-rw-ipv6 prefix '2001:db8:2000::/64'

Setting up tunnel:
^^^^^^^^^^^^^^^^^^

.. code-block:: none

  set vpn ipsec remote-access connection rw authentication local-id '192.0.2.1'
  set vpn ipsec remote-access connection rw authentication server-mode 'x509'
  set vpn ipsec remote-access connection rw authentication x509 ca-certificate 'ca_root'
  set vpn ipsec remote-access connection rw authentication x509 certificate 'server_cert'
  set vpn ipsec remote-access connection rw esp-group 'ESP-RW'
  set vpn ipsec remote-access connection rw ike-group 'IKE-RW'
  set vpn ipsec remote-access connection rw local-address '192.0.2.1'
  set vpn ipsec remote-access connection rw pool 'ra-rw-ipv4'
  set vpn ipsec remote-access connection rw pool 'ra-rw-ipv6'

VyOS also supports two different modes of authentication, local and RADIUS.
To create a new local user named "vyos" with a password of "vyos" use the
following commands.

.. code-block:: none

  set vpn ipsec remote-access connection rw authentication client-mode 'eap-mschapv2'
  set vpn ipsec remote-access connection rw authentication local-users username vyos password 'vyos'

Some client operating systems like to see the servers certificate. The following
option causes the server to voluntarily send its certificate, even if it wasn't
requested.

.. code-block:: none

  set vpn ipsec remote-access connection rw authentication always-send-cert

Client Configuration
^^^^^^^^^^^^^^^^^^^^

Most operating systems include native client support for IPsec IKEv2 VPN
connections, and others typically have an app or add-on package which adds the
capability.
This section covers IPsec IKEv2 client configuration for Windows 10.

VyOS provides a command to generate a connection profile used by Windows clients
that will connect to the "rw" connection on our VyOS server.

.. note:: Windows expects the server name to be also used in the server's
   certificate common name, so it's best to use this DNS name for your VPN
   connection.

.. code-block:: none

  vyos@vpn.vyos.net:~$ generate ipsec profile windows-remote-access rw remote vpn.vyos.net


  ==== <snip> ====
  Add-VpnConnection -Name "VyOS IKEv2 VPN" -ServerAddress "vpn.vyos.net" -TunnelType "Ikev2"

  Set-VpnConnectionIPsecConfiguration -ConnectionName "VyOS IKEv2 VPN" -AuthenticationTransformConstants GCMAES128 -CipherTransformConstants
  GCMAES128 -EncryptionMethod GCMAES128 -IntegrityCheckMethod SHA256128 -PfsGroup None -DHGroup "Group14" -PassThru -Force
  ==== </snip> ====

Add the commands from Snippet in the Windows side via PowerShell.
Also import the root CA cert to the Windows “Trusted Root Certification
Authorities” and establish the connection.

Verification:
^^^^^^^^^^^^^

.. code-block:: none

  vyos@vpn.vyos.net:~$ show vpn ipsec remote-access summary
    Connection ID  Username    Protocol    State    Uptime    Tunnel IP    Remote Host    Remote ID    IKE Proposal                                IPSec Proposal
  ---------------  ----------  ----------  -------  --------  -----------  -------------  -----------  ------------------------------------------  ------------------
                5  vyos        IKEv2       UP       37s       192.0.2.129  10.0.0.2       10.0.0.2     AES_GCM_16-128/PRF_HMAC_SHA2_256/MODP_2048  ESP:AES_GCM_16-128
