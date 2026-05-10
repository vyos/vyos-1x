:lastproofread: 2024-01-05

.. include:: /_include/need_improvement.txt

.. _pki:

###
PKI
###

VyOS 1.4 changed the way in how encryption keys or certificates are stored on the
system. In the pre VyOS 1.4 era, certificates got stored under /config and every
service referenced a file. That made copying a running configuration from system
A to system B a bit harder, as you had to copy the files and their permissions
by hand.

:vytask:`T3642` describes a new CLI subsystem that serves as a "certstore" to
all services requiring any kind of encryption key(s). In short, public and
private certificates are now stored in PKCS#8 format in the regular VyOS CLI.
Keys can now be added, edited, and deleted using the regular set/edit/delete
CLI commands.

VyOS not only can now manage certificates issued by 3rd party Certificate
Authorities, it can also act as a CA on its own. You can create your own root
CA and sign keys with it by making use of some simple op-mode commands.

Don't be afraid that you need to re-do your configuration. Key transformation is
handled, as always, by our migration scripts, so this will be a smooth transition
for you!

Key Generation
==============

Certificate Authority (CA)
--------------------------

VyOS now also has the ability to create CAs, keys, Diffie-Hellman and other
keypairs from an easy to access operational level command.

.. opcmd:: generate pki ca

  Create a new :abbr:`CA (Certificate Authority)` and output the CAs public and
  private key on the console.

.. opcmd:: generate pki ca install <name>

  Create a new :abbr:`CA (Certificate Authority)` and output the CAs public and
  private key on the console.

  .. include:: pki_cli_import_help.txt

.. opcmd:: generate pki ca sign <ca-name>

  Create a new subordinate :abbr:`CA (Certificate Authority)` and sign it using
  the private key referenced by `ca-name`.

.. opcmd:: generate pki ca sign <ca-name> install <name>

  Create a new subordinate :abbr:`CA (Certificate Authority)` and sign it using
  the private key referenced by `name`.

  .. include:: pki_cli_import_help.txt

Certificates
------------

.. opcmd:: generate pki certificate

  Create a new public/private keypair and output the certificate on the console.

.. opcmd:: generate pki certificate install <name>

  Create a new public/private keypair and output the certificate on the console.

  .. include:: pki_cli_import_help.txt

.. opcmd:: generate pki certificate self-signed

  Create a new self-signed certificate. The public/private is then shown on the
  console.

.. opcmd:: generate pki certificate self-signed install <name>

  Create a new self-signed certificate. The public/private is then shown on the
  console.

  .. include:: pki_cli_import_help.txt

.. opcmd:: generate pki certificate sign <ca-name>

  Create a new public/private keypair which is signed by the CA referenced by
  `ca-name`. The signed certificate is then output to the console.

.. opcmd:: generate pki certificate sign <ca-name> install <name>

  Create a new public/private keypair which is signed by the CA referenced by
  `ca-name`. The signed certificate is then output to the console.

  .. include:: pki_cli_import_help.txt

Diffie-Hellman parameters
-------------------------

.. opcmd:: generate pki dh

  Generate a new set of :abbr:`DH (Diffie-Hellman)` parameters. The key size
  is requested by the CLI and defaults to 2048 bit.

  The generated parameters are then output to the console.

.. opcmd:: generate pki dh install <name>

  Generate a new set of :abbr:`DH (Diffie-Hellman)` parameters. The key size
  is requested by the CLI and defaults to 2048 bit.

  .. include:: pki_cli_import_help.txt

OpenVPN
-------

.. opcmd:: generate pki openvpn shared-secret

  Generate a new OpenVPN shared secret. The generated secret is the output to
  the console.

.. opcmd:: generate pki openvpn shared-secret install <name>

  Generate a new OpenVPN shared secret. The generated secret is the output to
  the console.

  .. include:: pki_cli_import_help.txt

WireGuard
---------

.. opcmd:: generate pki wireguard key-pair

  Generate a new WireGuard public/private key portion and output the result to
  the console.

.. opcmd:: generate pki wireguard key-pair install <interface>

  Generate a new WireGuard public/private key portion and output the result to
  the console.

  .. note:: In addition to the command above, the output is in a format which can
    be used to directly import the key into the VyOS CLI by simply copy-pasting
    the output from op-mode into configuration mode.

    ``interface`` is used for the VyOS CLI command to identify the WireGuard
    interface where this private key is to be used.

.. opcmd:: generate pki wireguard preshared-key

  Generate a WireGuard pre-shared secret used for peers to communicate.

.. opcmd:: generate pki wireguard preshared-key install <peer>

  Generate a WireGuard pre-shared secret used for peers to communicate.

  .. note:: In addition to the command above, the output is in a format which can
    be used to directly import the key into the VyOS CLI by simply copy-pasting
    the output from op-mode into configuration mode.

    ``peer`` is used for the VyOS CLI command to identify the WireGuard peer where
    this secret is to be used.

Key usage (CLI)
===============

CA (Certificate Authority)
--------------------------

.. cfgcmd:: set pki ca <name> certificate

  Add the public CA certificate for the CA named `name` to the VyOS CLI.

  .. note:: When loading the certificate you need to manually strip the
    ``-----BEGIN CERTIFICATE-----`` and ``-----END CERTIFICATE-----`` tags.
    Also, the certificate/key needs to be presented in a single line without
    line breaks (``\n``), this can be done using the following shell command:

    ``$ tail -n +2 ca.pem | head -n -1 | tr -d '\n'``

.. cfgcmd:: set pki ca <name> crl

  Certificate revocation list in PEM format.

.. cfgcmd:: set pki ca <name> description

  A human readable description what this CA is about.

.. cfgcmd:: set pki ca <name> private key

  Add the CAs private key to the VyOS CLI. This should never leave the system,
  and is only required if you use VyOS as your certificate generator as
  mentioned above.

  .. note:: When loading the certificate you need to manually strip the
    ``-----BEGIN KEY-----`` and ``-----END KEY-----`` tags. Also, the
    certificate/key needs to be presented in a single line without line
    breaks (``\n``), this can be done using the following shell command:

    ``$ tail -n +2 ca.key | head -n -1 | tr -d '\n'``

.. cfgcmd:: set pki ca <name> private password-protected

  Mark the CAs private key as password protected. User is asked for the password
  when the key is referenced.

Server Certificate
------------------

After we have imported the CA certificate(s) we can now import and add
certificates used by services on this router.

.. cfgcmd:: set pki certificate <name> certificate

  Add public key portion for the certificate named `name` to the VyOS CLI.

  .. note:: When loading the certificate you need to manually strip the
    ``-----BEGIN CERTIFICATE-----`` and ``-----END CERTIFICATE-----`` tags.
    Also, the certificate/key needs to be presented in a single line without
    line breaks (``\n``), this can be done using the following shell command:

    ``$ tail -n +2 cert.pem | head -n -1 | tr -d '\n'``

.. cfgcmd:: set pki certificate <name> description

  A human readable description what this certificate is about.

.. cfgcmd:: set pki certificate <name> private key

  Add the private key portion of this certificate to the CLI. This should never
  leave the system as it is used to decrypt the data.

  .. note:: When loading the certificate you need to manually strip the
    ``-----BEGIN KEY-----`` and ``-----END KEY-----`` tags. Also, the
    certificate/key needs to be presented in a single line without line
    breaks (``\n``), this can be done using the following shell command:

    ``$ tail -n +2 cert.key | head -n -1 | tr -d '\n'``

.. cfgcmd:: set pki certificate <name> private password-protected

  Mark the private key as password protected. User is asked for the password
  when the key is referenced.

.. cfgcmd:: set pki certificate <name> revoke

  If CA is present, this certificate will be included in generated CRLs

Import files to PKI format
-------------------------- 
VyOS provides this utility to import existing certificates/key files directly 
into PKI from op-mode. Previous to VyOS 1.4, certificates were stored under the 
/config folder permanently and will be retained post upgrade.

.. opcmd:: import pki ca <name> file <Path to CA certificate file>

  Import the public CA certificate from the defined file to VyOS CLI.

.. opcmd:: import pki ca <name> key-file <Path to private key file> 

  Import the CAs private key portion to the CLI. This should never leave the 
  system as it is used to decrypt the data. The key is required if you use 
  VyOS as your certificate generator.

.. opcmd:: import pki certificate <name> file <path to certificate>

  Import the certificate from the file to VyOS CLI.

.. opcmd:: import pki certificate <name> key-file <path to private key>

  Import the private key of the certificate to the VyOS CLI. This should never
  leave the system as it is used to decrypt the data.

.. opcmd:: import pki openvpn shared-secret <name> file <path to OpenVPN secret key>

  Import the OpenVPN shared secret stored in file to the VyOS CLI.

ACME
^^^^

The VyOS PKI subsystem can also be used to automatically retrieve Certificates
using the :abbr:`ACME (Automatic Certificate Management Environment)` protocol.

.. cfgcmd:: set pki certificate <name> acme domain-name <name>

  Domain names to apply, multiple domain-names can be specified.

  This is a mandatory option

.. cfgcmd:: set pki certificate <name> acme email <address>

  Email used for registration and recovery contact.

  This is a mandatory option

.. cfgcmd:: set pki certificate <name> acme listen-address <address>

  The address the server listens to during http-01 challenge

.. cfgcmd:: set pki certificate <name> acme rsa-key-size <2048 | 3072 | 4096>

  Size of the RSA key.

  This options defaults to 2048

.. cfgcmd:: set pki certificate <name> acme url <url>

  ACME Directory Resource URI.

  This defaults to https://acme-v02.api.letsencrypt.org/directory

  .. note:: During initial deployment we recommend using the staging API
    of LetsEncrypt to prevent and blacklisting of your system. The API
    endpoint is https://acme-staging-v02.api.letsencrypt.org/directory

Operation
=========

VyOS operational mode commands are not only available for generating keys but
also to display them.

.. opcmd:: show pki ca

  Show a list of installed :abbr:`CA (Certificate Authority)` certificates.

  .. code-block:: none

    vyos@vyos:~$ show pki ca
    Certificate Authorities:
    Name            Subject                                                  Issuer CN          Issued               Expiry               Private Key    Parent
    --------------  -------------------------------------------------------  -----------------  -------------------  -------------------  -------------  --------------
    DST_Root_CA_X3  CN=ISRG Root X1,O=Internet Security Research Group,C=US  CN=DST Root CA X3  2021-01-20 19:14:03  2024-09-30 18:14:03  No             N/A
    R3              CN=R3,O=Let's Encrypt,C=US                               CN=ISRG Root X1    2020-09-04 00:00:00  2025-09-15 16:00:00  No             DST_Root_CA_X3
    vyos_rw         CN=VyOS RW CA,O=VyOS,L=Some-City,ST=Some-State,C=GB      CN=VyOS RW CA      2021-07-05 13:46:03  2026-07-04 13:46:03  Yes            N/A

.. opcmd:: show pki ca <name>

  Show only information for specified Certificate Authority.

.. opcmd:: show pki certificate

  Show a list of installed certificates

  .. code-block:: none

    vyos@vyos:~$ show pki certificate
    Certificates:
    Name       Type    Subject CN             Issuer CN      Issued               Expiry               Revoked    Private Key    CA Present
    ---------  ------  ---------------------  -------------  -------------------  -------------------  ---------  -------------  -------------
    ac2        Server  CN=ac2.vyos.net        CN=R3          2021-07-05 07:29:59  2021-10-03 07:29:58  No         Yes            Yes (R3)
    rw_server  Server  CN=VyOS RW             CN=VyOS RW CA  2021-07-05 13:48:02  2022-07-05 13:48:02  No         Yes            Yes (vyos_rw)

.. opcmd:: show pki certificate <name>

  Show only information for specified certificate.

.. opcmd:: show pki crl

  Show a list of installed :abbr:`CRLs (Certificate Revocation List)`.

.. opcmd:: renew certbot

  Manually trigger certificate renewal. This will be done twice a day.

Examples
========

Create a CA chain and leaf certificates
---------------------------------------

This configuration generates & installs into the VyOS PKI system a root
certificate authority, alongside two intermediary certificate authorities for
client & server certificates. These CAs are then used to generate a server
certificate for the router, and a client certificate for a user.


* ``vyos_root_ca`` is the root certificate authority.

* ``vyos_client_ca`` and ``vyos_server_ca`` are intermediary certificate authorities,
  which are signed by the root CA.

* ``vyos_cert`` is a leaf server certificate used to identify the VyOS router,
  signed by the server intermediary CA.

* ``vyos_example_user`` is a leaf client certificate used to identify a user,
  signed by client intermediary CA.


First, we create the root certificate authority.

.. code-block:: none

    [edit]
    vyos@vyos# run generate pki ca install vyos_root_ca
    Enter private key type: [rsa, dsa, ec] (Default: rsa) rsa
    Enter private key bits: (Default: 2048) 2048
    Enter country code: (Default: GB) GB
    Enter state: (Default: Some-State) Some-State
    Enter locality: (Default: Some-City) Some-City
    Enter organization name: (Default: VyOS) VyOS
    Enter common name: (Default: vyos.io) VyOS Root CA
    Enter how many days certificate will be valid: (Default: 1825) 1825
    Note: If you plan to use the generated key on this router, do not encrypt the private key.
    Do you want to encrypt the private key with a passphrase? [y/N] n
    2 value(s) installed. Use "compare" to see the pending changes, and "commit" to apply.

Secondly, we create the intermediary certificate authorities, which are used to
sign the leaf certificates.

.. code-block:: none

    [edit]
    vyos@vyos# run generate pki ca sign vyos_root_ca install vyos_server_ca
    Do you already have a certificate request? [y/N] n
    Enter private key type: [rsa, dsa, ec] (Default: rsa) rsa
    Enter private key bits: (Default: 2048) 2048
    Enter country code: (Default: GB) GB
    Enter state: (Default: Some-State) Some-State
    Enter locality: (Default: Some-City) Some-City
    Enter organization name: (Default: VyOS) VyOS
    Enter common name: (Default: vyos.io) VyOS Intermediary Server CA
    Enter how many days certificate will be valid: (Default: 1825) 1095
    Note: If you plan to use the generated key on this router, do not encrypt the private key.
    Do you want to encrypt the private key with a passphrase? [y/N] n
    2 value(s) installed. Use "compare" to see the pending changes, and "commit" to apply.


    [edit]
    vyos@vyos# run generate pki ca sign vyos_root_ca install vyos_client_ca
    Do you already have a certificate request? [y/N] n
    Enter private key type: [rsa, dsa, ec] (Default: rsa) rsa
    Enter private key bits: (Default: 2048) 2048
    Enter country code: (Default: GB) GB
    Enter state: (Default: Some-State) Some-State
    Enter locality: (Default: Some-City) Some-City
    Enter organization name: (Default: VyOS) VyOS
    Enter common name: (Default: vyos.io) VyOS Intermediary Client CA
    Enter how many days certificate will be valid: (Default: 1825) 1095
    Note: If you plan to use the generated key on this router, do not encrypt the private key.
    Do you want to encrypt the private key with a passphrase? [y/N] n
    2 value(s) installed. Use "compare" to see the pending changes, and "commit" to apply.

Lastly, we can create the leaf certificates that devices and users will utilise.

.. code-block:: none

    [edit]
    vyos@vyos# run generate pki certificate sign vyos_server_ca install vyos_cert
    Do you already have a certificate request? [y/N] n
    Enter private key type: [rsa, dsa, ec] (Default: rsa) rsa
    Enter private key bits: (Default: 2048) 2048
    Enter country code: (Default: GB) GB
    Enter state: (Default: Some-State) Some-State
    Enter locality: (Default: Some-City) Some-City
    Enter organization name: (Default: VyOS) VyOS
    Enter common name: (Default: vyos.io) vyos.net
    Do you want to configure Subject Alternative Names? [y/N] y
    Enter alternative names in a comma separate list, example: ipv4:1.1.1.1,ipv6:fe80::1,dns:vyos.net
    Enter Subject Alternative Names: dns:vyos.net,dns:www.vyos.net
    Enter how many days certificate will be valid: (Default: 365) 365
    Enter certificate type: (client, server) (Default: server) server
    Note: If you plan to use the generated key on this router, do not encrypt the private key.
    Do you want to encrypt the private key with a passphrase? [y/N] n
    2 value(s) installed. Use "compare" to see the pending changes, and "commit" to apply.


    [edit]
    vyos@vyos# run generate pki certificate sign vyos_client_ca install vyos_example_user
    Do you already have a certificate request? [y/N] n
    Enter private key type: [rsa, dsa, ec] (Default: rsa) rsa
    Enter private key bits: (Default: 2048) 2048
    Enter country code: (Default: GB) GB
    Enter state: (Default: Some-State) Some-State
    Enter locality: (Default: Some-City) Some-City
    Enter organization name: (Default: VyOS) VyOS
    Enter common name: (Default: vyos.io) Example User
    Do you want to configure Subject Alternative Names? [y/N] y
    Enter alternative names in a comma separate list, example: ipv4:1.1.1.1,ipv6:fe80::1,dns:vyos.net,rfc822:user@vyos.net
    Enter Subject Alternative Names: rfc822:example.user@vyos.net
    Enter how many days certificate will be valid: (Default: 365) 365
    Enter certificate type: (client, server) (Default: server) client
    Note: If you plan to use the generated key on this router, do not encrypt the private key.
    Do you want to encrypt the private key with a passphrase? [y/N] n
    2 value(s) installed. Use "compare" to see the pending changes, and "commit" to apply.
