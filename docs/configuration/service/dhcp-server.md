(dhcp-server)=

# DHCP Server

VyOS uses Kea DHCP server for both IPv4 and IPv6 address assignment.

## IPv4 server

The network topology is declared by shared-network-name and the subnet
declarations. The DHCP service can serve multiple shared networks, with each
shared network having 1 or more subnets. Each subnet must be present on an
interface. A range can be declared inside a subnet to define a pool of dynamic
addresses. Multiple ranges can be defined and can contain holes. Static
mappings can be set to assign "static" addresses to clients based on their MAC
address.

### Configuration

```{cfgcmd} set service dhcp-server hostfile-update

   Create DNS record per client lease, by adding clients to /etc/hosts file.
   Entry will have format: `<shared-network-name>_<hostname>.<domain-name>`
```


#### Shared network options


The following DHCP options apply to an entire shared network. All subnets
inherit these values unless the same option is set locally.


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option bootfile-name \<filename\>

Bootstrap file name (DHCP Option 67).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option bootfile-server \<address\>

Server from which the initial boot file is to be loaded (DHCP siaddr
field).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option bootfile-size \<size\>

Bootstrap file size in 512-octet blocks (DHCP Option 13).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option captive-portal \<url\>

Captive portal API endpoint (DHCP Option 114).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option capwap-controller \<address\>

IP address of CAPWAP access controller (DHCP Option 138).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option client-prefix-length \<prefix-length\>

Specifies the client subnet mask as per RFC 950. If unset, the subnet
declaration is used (DHCP Option 1).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option default-router \<address\>

IP address of default router (DHCP Option 3).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option domain-name \<domain-name\>

The domain-name parameter should be the domain name that will be appended to
the client's hostname to form a fully-qualified domain-name (FQDN) (DHCP
Option 15).

This is the configuration parameter for the entire shared network definition.
All subnets will inherit this configuration item if not specified locally.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option domain-search \<domain-name\>

The domain-name parameter should be the domain name used when completing DNS
request where no full FQDN is passed. This option can be given multiple times
if you need multiple search domains (DHCP Option 119).

This is the configuration parameter for the entire shared network definition.
All subnets will inherit this configuration item if not specified locally.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option interface-mtu \<mtu\>

Client interface MTU (DHCP Option 26).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option ip-forwarding

Enable IP forwarding on the client (DHCP Option 19).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option ipv6-only-preferred \<seconds\>

Disable IPv4 on IPv6-only hosts for the specified number of seconds
(RFC 8925, DHCP Option 108).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option name-server \<address\>

Inform client that the DNS server can be found at `<address>` (DHCP Option 6).

This is the configuration parameter for the entire shared network definition.
All subnets will inherit this configuration item if not specified locally.
Multiple DNS servers can be defined.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option ntp-server \<address\>

IP address of NTP server (DHCP Option 42). This option can be specified
multiple times.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option pop-server \<address\>

IP address of POP3 server (DHCP Option 70). This option can be specified
multiple times.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option server-identifier \<address\>

Address for DHCP server identifier (DHCP Option 54).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option smtp-server \<address\>

IP address of SMTP server (DHCP Option 69). This option can be specified
multiple times.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option static-route \<subnet\> next-hop \<address\>

Classless static route destination subnet (DHCP Options 121 and 249). This
option can be specified multiple times.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option tftp-server-name \<server-name\>

TFTP server name (DHCP Option 66).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option time-offset \<seconds\>

Client subnet offset in seconds from Coordinated Universal Time (UTC)
(DHCP Option 2).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option time-server \<address\>

IP address of time server (DHCP Option 4). This option can be specified
multiple times.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option time-zone \<timezone\>

Time zone to send to clients (DHCP Options 100 and 101, `pcode` and
`tcode`, RFC 4833).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option vendor-option \<vendor\> \<option-name\> \<value\>

This configuration parameter lets you specify a vendor-option for the
entire shared network definition. All subnets will inherit this
configuration item if not specified locally (DHCP Option 43). An example
for Ubiquiti is shown below:
```

**Example:**


Pass address of Unifi controller at `172.16.100.1` to all clients of `NET1`

```none
set service dhcp-server shared-network-name 'NET1' option vendor-option
ubiquiti unifi-controller '172.16.100.1'
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option wins-server \<address\>

IP address for Windows Internet Name Service (WINS) server (DHCP Option 44).
This option can be specified multiple times.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> option wpad-url \<url\>

Web Proxy Autodiscovery (WPAD) URL (DHCP Option 252).
```


```{cfgcmd} set service dhcp-server listen-address \<address\>

This configuration parameter lets the DHCP server to listen for DHCP
requests sent to the specified address, it is only realistically useful for
a server whose only clients are reached via unicasts, such as via DHCP relay
agents.
```

```{cfgcmd} set service dhcp-server log-level \<fatal | error | warn | info | debug\>

Set the logging verbosity of the Kea DHCP server. The default level is
`info`.
```

#### Individual Client Subnet

```{cfgcmd} set service dhcp-server shared-network-name \<name\> authoritative

This says that this device is the only DHCP server for this network. If other
devices are trying to offer DHCP leases, this machine will send 'DHCPNAK' to
any device trying to request an IP address that is not valid for this
network.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> subnet-id \<id\>

This configuration parameter is required and must be unique to each subnet.
It is required to map subnets to lease file entries.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> option default-router \<address\>

This is a configuration parameter for the `<subnet>`, saying that as part of
the response, tell the client that the default gateway can be reached at
`<address>` (DHCP Option 3).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> option name-server \<address\>

This is a configuration parameter for the subnet, saying that as part of the
response, tell the client that the DNS server can be found at `<address>`
(DHCP Option 6).

Multiple DNS servers can be defined.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> lease \<time\>

Assign the IP address to this machine for `<time>` seconds.

The default value is 86400 seconds which corresponds to one day.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> range \<n\> start \<address\>

Create DHCP address range with a range id of `<n>`. DHCP leases are taken
from this pool. The pool starts at address `<address>`.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> range \<n\> stop \<address\>

Create DHCP address range with a range id of `<n>`. DHCP leases are taken
from this pool. The pool stops with address `<address>`.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> exclude \<address\>

Always exclude this address from any defined range. This address will never
be assigned by the DHCP server.

This option can be specified multiple times.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> option domain-name \<domain-name\>

The domain-name parameter should be the domain name that will be appended to
the client's hostname to form a fully-qualified domain-name (FQDN) (DHCP
Option 15).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> option domain-search \<domain-name\>

The domain-name parameter should be the domain name used when completing DNS
request where no full FQDN is passed. This option can be given multiple times
if you need multiple search domains (DHCP Option 119).
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> option vendor-option \<vendor\> \<option-name\> \<value\>

This configuration parameter lets you specify a vendor-option for the
subnet specified within the shared network definition (DHCP Option 43).
An example for Ubiquiti is shown below:
```

**Example:**


Create `172.18.201.0/24` as a subnet within `NET1` and pass address of
Unifi controller at `172.16.100.1` to clients of that subnet.

```none
set service dhcp-server shared-network-name 'NET1' subnet
'172.18.201.0/24' option vendor-option ubiquiti unifi-controller '172.16.100.1'
```

#### Dynamic DNS Update (RFC 2136)


VyOS DHCP service supports RFC-2136 DDNS protocol. Based on DHCP lease change
events, DHCP server generates DDNS update requests (defines as NameChangeRequests
or NCRs) and posts them to a compliant DNS server, that will update its name
database accordingly.


VyOS built-in DNS Forwarder does not support DDNS, you will need an external DNS
server with RFC-2136 DDNS support.

```{cfgcmd} set service dhcp-server dynamic-dns-update

Enables DDNS globally.
```

**Behavioral settings**


These settings can be configured on the global level and overridden on the scope
level, i.e. for individual shared networks or subnets. See examples below.

```{cfgcmd} set service dhcp-server dynamic-dns-update send-updates \<enable | disable\>

If set to ``enable`` on global level, updates for all scopes will be enabled,
except if explicitly set to ``disable`` on the scope level. If set to ``disable``,
updates will only be sent for scopes, where ``send-updates`` is explicitly
set to ``enable``.

This model is followed for a few behavioral settings below: if the option is
not set, the setting is inherited from the parent scope. You can override the
parent scope setting by setting the option explicitly.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update override-no-update \<enable | disable\>

VyOS will ignore client request not to update DNS records and send DDNS
update requests regardless.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update override-client-update \<enable | disable\>

VyOS will override client DDNS request settings and always update both
forward and reverse DNS records.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update update-on-renew \<enable | disable\>

Issue DDNS update requests on DHCP lease renew. In busy networks this may
generate a lot of traffic.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update conflict-resolution \<enable | disable\>

Use RFC-4703 conflict resolution. This algorithm helps in situation when
multiple clients reserve same IP addresses or advertise identical hostnames.
Should be used in most situations.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update replace-client-name [ never | always | when-present | when-not-present ]

* **never**: use the name sent by the client. If the client didn't provide any,
do not generate one. This is the default behavior

* **always**: always generate a name for the client

* **when-present**: replace the name the client sent with a generated one, if
the client didn't send any, do not generate one

* **when-not-present**: use the name sent by the client. If the client didn't
send any, generate one for the client

The names are generated using ``generated-prefix``, ``qualifying-suffix`` and the
client's IP address string.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update generated-prefix \<prefix\>

Prefix used in client name generation.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update qualifying-suffix \<suffix\>

DNS suffix used in client name generation.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update ttl-percent \<0-100\>

TTL of the DNS record as a percentage of the DHCP lease time.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update hostname-char-set \<character string\>

Characters, that are considered invalid in the client name. They will be replaced
with ``hostname-char-replacement`` string.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update hostname-char-replacement \<character string\>

Replacement string for the invalid characters defined by ``hostname-char-set``.
```

**TSIG keys definition**


This is the global list of TSIG keys for DDNS updates. They need to be specified by
the name in the DNS domain definitions.

```{cfgcmd} set service dhcp-server dynamic-dns-update tsig-key \<key-name\> algorithm \<algorithm\>

Sets the algorithm for the TSIG key. Supported algorithms are ``hmac-md5``,
``hmac-sha1``, ``hmac-sha224``, ``hmac-sha256``, ``hmac-sha384``, ``hmac-sha512``
```


```{cfgcmd} set service dhcp-server dynamic-dns-update tsig-key \<key-name\> secret \<key-secret\>

base64-encoded TSIG key secret value
```

**DNS domains definition**


This is global configuration of DNS servers for the updatable forward and reverse
DNS domains. For every domain multiple DNS servers can be specified.

```{cfgcmd} set service dhcp-server dynamic-dns-update [forward|reverse]-domain \<domain-name\> key-name \<tsig-key-name\>

TSIG key used for the domain.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update [forward|reverse]-domain \<domain-name\> dns-server \<number\> address \<ip-address\>

IP address of the DNS server.
```


```{cfgcmd} set service dhcp-server dynamic-dns-update [forward|reverse]-domain \<domain-name\> dns-server \<number\> port \<port\>

UDP port of the DNS server. ``53`` is the default.
```

**Example:**


Global configuration you will most likely want:

```none
set service dhcp-server dynamic-dns-update send-updates enable
set service dhcp-server dynamic-dns-update conflict-resolution enable
```

Override the above configuration for a shared network NET1:

```none
set service dhcp-server shared-network-name 'NET1' dynamic-dns-update replace-client-name when-not-present
set service dhcp-server shared-network-name 'NET1' dynamic-dns-update generated-prefix ip
set service dhcp-server shared-network-name 'NET1' dynamic-dns-update qualifying-suffix mybigdomain.net
```

And in a subnet within the same shared network:

```none
set service dhcp-server shared-network-name 'NET1' subnet '172.18.201.0/24' dynamic-dns-update qualifying-suffix mydomain.net
```

Configure TSIG keys:

```none
set service dhcp-server dynamic-dns-update tsig-key mydomain-net algorithm hmac-sha256
set service dhcp-server dynamic-dns-update tsig-key mydomain-net secret eWF5YW15bGl0dGxla2V5IQ==
set service dhcp-server dynamic-dns-update tsig-key reverse-172-18-201 algorithm hmac-sha256
set service dhcp-server dynamic-dns-update tsig-key reverse-172-18-201 secret eWF5YW15YW5vdGhlcmxpdHRsZWtleSE=
```

Configure DDNS domains:

```none
set service dhcp-server dynamic-dns-update forward-domain mydomain.net key-name mydomain-net
set service dhcp-server dynamic-dns-update forward-domain mydomain.net dns-server 1 address '172.18.0.254'
set service dhcp-server dynamic-dns-update forward-domain mydomain.net dns-server 1 port 1053
set service dhcp-server dynamic-dns-update forward-domain mydomain.net dns-server 2 address '192.168.124.254'
set service dhcp-server dynamic-dns-update forward-domain mydomain.net dns-server 2 port 53
set service dhcp-server dynamic-dns-update forward-domain 201.18.172.in-addr.arpa key-name reverse-172-18-201
set service dhcp-server dynamic-dns-update reverse-domain 201.18.172.in-addr.arpa dns-server 1 address '172.18.0.254'
set service dhcp-server dynamic-dns-update reverse-domain 201.18.172.in-addr.arpa dns-server 1 port 1053
set service dhcp-server dynamic-dns-update reverse-domain 201.18.172.in-addr.arpa dns-server 2 address '192.168.124.254'
set service dhcp-server dynamic-dns-update reverse-domain 201.18.172.in-addr.arpa dns-server 2 port 53
```

#### High Availability


VyOS provides High Availability support for DHCP server. DHCP High
Availability can act in two different modes:


- **Active-active**: both DHCP servers will respond to DHCP requests. If
  `mode` is not defined, this is the default behavior.
- **Active-passive**: only `primary` server will respond to DHCP requests.
  If this server goes offline, then `secondary` server will take place.


DHCP High Availability must be configured explicitly by the following
statements on both servers:

```{cfgcmd} set service dhcp-server high-availability mode [active-active | active-passive]

Define operation mode of High Availability feature. Default value if command
is not specified is `active-active`
```


```{cfgcmd} set service dhcp-server high-availability source-address \<address\>

Local IP `<address>` used when communicating to the HA peer.
```


```{cfgcmd} set service dhcp-server high-availability remote \<address\>

Remote peer IP `<address>` of the second DHCP server in this HA
cluster.
```


```{cfgcmd} set service dhcp-server high-availability name \<name\>

Define the name of the peer server to establish and identify the HA (High Availability) connection.

:::{note}
Make sure the specified value does not conflict with the system host-name.
:::
```


```{cfgcmd} set service dhcp-server high-availability status \<primary | secondary\>

The primary and secondary statements determines whether the server is primary
or secondary.

:::{note}
In order for the primary and the secondary DHCP server to keep
their lease tables in sync, they must be able to reach each other on TCP
port 647. If you have firewall rules in effect, adjust them accordingly.
:::
:::{hint}
The dialogue between HA partners is neither encrypted nor
authenticated. Since most DHCP servers exist within an organisation's own
secure Intranet, this would be an unnecessary overhead. However, if you
have DHCP HA peers whose communications traverse insecure networks,
then we recommend that you consider the use of VPN tunneling between them
to ensure that the HA partnership is immune to disruption
(accidental or otherwise) via third parties.
:::
```

(dhcp-server-v4-static-mapping)=

#### Static mappings


You can specify a static DHCP assignment on a per-host basis (DHCP Reservations).
You will need the MAC address of the station and your desired IP address. The
address must be inside the subnet definition but can be outside the range statement.

```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> static-mapping \<hostname\> mac \<address\>

Create a new DHCP static mapping named `<hostname>` which is valid for
the host identified by its MAC `<address>`.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> static-mapping \<hostname\> duid \<identifier\>

Create a new DHCP static mapping named `<hostname>` which is valid for
the host identified by its DHCP unique identifier (DUID) `<identifier>`.
```


```{cfgcmd} set service dhcp-server shared-network-name \<name\> subnet \<subnet\> static-mapping \<hostname\> ip-address \<address\>

Static DHCP IP address assigned to the host identified by `<hostname>`.
IP address must be inside the `<subnet>` which is defined but can be outside
the dynamic range created with `{cfgcmd} set service dhcp-server
shared-network-name <name> subnet <subnet> range <n>`. If no ip-address is
specified, an IP address from the dynamic pool is used.

This is useful, for example, in combination with hostfile update.

:::{hint}
This is the equivalent of the host block in dhcpd.conf of
isc-dhcpd.
:::
```

**Example:**


- IP address `192.168.1.100` shall be statically mapped to client named `client1`

```none
set service dhcp-server shared-network-name 'NET1' subnet 192.168.1.0/24 subnet-id 1
set service dhcp-server shared-network-name 'NET1' subnet 192.168.1.0/24 static-mapping client1 ip-address 192.168.1.100
set service dhcp-server shared-network-name 'NET1' subnet 192.168.1.0/24 static-mapping client1 mac aa:bb:11:22:33:00
```

The configuration will look as follows:

```none
show service dhcp-server shared-network-name NET1
 subnet 192.168.1.0/24 {
     static-mapping client1 {
         ip-address 192.168.1.100
         mac aa:bb:11:22:33:00
     }
     subnet-id 1
 }
```

#### Relay agent information (Option 82)


Some DHCP relays support the injection of information into a DHCP request, depending on
where the request originated from. This is commonly used to determine the
behaviour of the DHCP server, based on the port/switch combination where the
request was first detected. I.e. the device plugged into a particular port (or
set of ports) always gets the same IP address (or range of IP addresses). This
information is usually included in the request using Option 82, hence this
is what we call this part of the configuration.


This behaviour is controlled in two parts. First, "client classes" are defined
which determine which inputs match. Once a positive match has been found the
request is "tagged" with this client class. Second, when the DHCP server
processes the request it checks to see if the configuration has a client class
defined. If it does then that part of the configuration will override the others


Client classes can be applied at either the subnet or range level, depending on
how you want the server to behave.


**Client Class definition**

```{cfgcmd} set service dhcp-server client-class \<name\> relay-agent-information circuit-id \<value\>

Create a new client class (if not already defined) and set it to match on
the "Circuit ID" part of the Option 82 field in the DHCP request. This is
sub option "1" as specified by RFC 3046. The value specified here is either
interpreted as a raw hex value, if it starts with the prefix 0x, or ASCII text
otherwise. e.g. ``e1-5`` and ``0x65312d35`` are the same
```


```{cfgcmd} set service dhcp-server client-class \<name\> relay-agent-information remote-id \<value\>

Create a new client class (if not already defined) and set it to match on
the "Remote ID" part of the Option 82 field in the DHCP request. This is
sub option "2" as specified by RFC 3046. The value specified here is either
interpreted as a raw hex value, if it starts with the prefix 0x, or ASCII text
otherwise. e.g. ``10.100.0.41`` and ``0x31302e3130302e302e3431`` are the
same
```

**Client Class application**

```{cfgcmd} set service dhcp-server shared-network-name \<subnet-name\> subnet \<CIDR\> client-class \<class-name\>

Applies the Client Class with the name `<class-name>` to the subnet `<subnet-name>`.
This means that whenever the client class matches a request it is always
routed to this subnet definition first.
```


```{cfgcmd} set service dhcp-server shared-network-name \<subnet-name\> subnet \<CIDR\> range \<range-name\> client-class \<class-name\>

Applies the Client Class with the name `<class-name>` to the range
`<range-name>` which belongs to subnet `<subnet-name>`. This means that whenever the
client class matches a request it is always routed to this range definition
first.
```

NB: Kea (the DHCP server used by VyOS) is programmed to offer as many
alternatives as it can to repeated DHCP Discover requests. Some operating
systems (Notably Microsoft Windows) make multiple DHCP Discover requests before
settling on an address. This particularly seems to happen when the DHCP server
isn't set to authoritative. This may explain why the address you expect isn't
being chosen. Wireshark is helpful in these situations.


**Example:**


The following configuration example will classify requests coming in on port
`e1-5` from DHCP Relay `192.0.2.1` and make sure that they are allocated the
address `192.0.2.4`. Any requests which do not match the circuit and remote ID
will, instead, be allocated from the range otherRange in the usual manner.


NB: Both the Circuit ID and Remote ID fields are arbitrary free text. *Most*
switches set the Remote ID to the IP address of the management interface but
that should not be relied upon. Check the documentation of your DHCP Relay for
more detail or, as a measure of last resort, inspect the DHCP requests in
Wireshark.

```none
service {
    dhcp-server {
        client-class className {
            relay-agent-information {
                circuit-id e1-5
                remote-id 192.0.2.1
            }
        }
        shared-network-name test {
            subnet 192.0.2.0/24 {
                range classNameRange {
                    client-class className
                    start 192.0.2.4
                    stop 192.0.2.4
                }
                range otherRange {
                    start 192.0.2.5
                    stop 192.0.2.100
                }
                subnet-id 1
            }
        }
    }
}
```

(dhcp-server-v4-options)=

### Options


The following DHCP options can be set under
`set service dhcp-server shared-network-name <name> option ...` or
`set service dhcp-server shared-network-name <name> subnet <subnet> option ...`.



:::{list-table}
:header-rows: 1
:stub-columns: 0
:widths: 12 7 23 40 20

* - Setting name
  - Option number
  - DHCP option name
  - Option description
  - Multi
* - bootfile-name
  - 67
  - boot-file-name
  - Bootstrap file name
  - N
* - bootfile-server
  - siaddr
  - next-server
  - Server from which the initial boot file is to be loaded
  - N
* - bootfile-size
  - 13
  - boot-size
  - Bootstrap file size
  - N
* - captive-portal
  - 114
  - v4-captive-portal
  - Captive portal API endpoint
  - N
* - capwap-controller
  - 138
  - capwap-ac-v4
  - IPv4 address of CAPWAP access controller
  - N
* - client-prefix-length
  - 1
  - subnet-mask
  - Specifies the clients subnet mask as per RFC 950. If unset,
    subnet declaration is used.
  - N
* - default-router
  - 3
  - routers
  - IPv4 address of router on the client's subnet
  - N
* - domain-name
  - 15
  - domain-name
  - Client domain name
  - N
* - domain-search
  - 119
  - domain-search
  - Client domain name search list
  - Y
* - interface-mtu
  - 26
  - interface-mtu
  - Client interface MTU
  - N
* - ip-forwarding
  - 19
  - ip-forwarding
  - Enable IP forwarding on client
  - N
* - ipv6-only-preferred
  - 108
  - v6-only-preferred
  - Disable IPv4 on IPv6-only hosts (RFC 8925)
  - N
* - name-server
  - 6
  - domain-name-servers
  - Domain Name Servers (DNS) addresses
  - Y
* - ntp-server
  - 42
  - ntp-servers
  - IPv4 address of NTP server
  - Y
* - pop-server
  - 70
  - pop-server
  - IPv4 address of POP3 server
  - Y
* - server-identifier
  - 54
  - dhcp-server-identifier
  - IPv4 address for DHCP server identifier
  - N
* - smtp-server
  - 69
  - smtp-server
  - IPv4 address of SMTP server
  - Y
* - static-route
  - 121, 249
  - classless-static-route, ms-classless-static-route
  - Classless static route destination subnet
  - Y
* - tftp-server-name
  - 66
  - tftp-server-name
  - TFTP server name
  - N
* - time-offset
  - 2
  - time-offset
  - Client subnet offset in seconds from Coordinated Universal Time
    (UTC)
  - N
* - time-server
  - 4
  - time-servers
  - IPv4 address of time server
  - Y
* - time-zone
  - 100, 101
  - pcode, tcode
  - Time zone to send to clients (RFC 4833)
  - N
* - vendor-option
  - 43
  - vendor-encapsulated-options
  - Vendor-specific options
  - Y
* - wins-server
  - 44
  - netbios-name-servers
  - IPv4 address for Windows Internet Name Service (WINS) server
  - Y
* - wpad-url
  - 252
  - wpad-url
  - Web Proxy Autodiscovery (WPAD) URL
  - N
:::


Multi: can be specified multiple times.


### Example


Please see the {ref}`dhcp-dns-quick-start` configuration.


(dhcp-server-v4-example-failover)=


#### High Availability


Configuration of a DHCP HA pair:


- Setup DHCP HA for network 192.0.2.0/24
- Use active-active HA mode.
- Default gateway and DNS server is at `192.0.2.254`
- The primary DHCP server named dhcp-primary uses address `192.168.189.252`
- The secondary DHCP server with named dhcp-secondary uses address `192.168.189.253`
- DHCP range spans from `192.168.189.10` - `192.168.189.250`


Common configuration, valid for both primary and secondary node.

```none
set service dhcp-server shared-network-name NET-VYOS subnet 192.0.2.0/24 option default-router '192.0.2.254'
set service dhcp-server shared-network-name NET-VYOS subnet 192.0.2.0/24 option name-server '192.0.2.254'
set service dhcp-server shared-network-name NET-VYOS subnet 192.0.2.0/24 option domain-name 'vyos.net'
set service dhcp-server shared-network-name NET-VYOS subnet 192.0.2.0/24 range 0 start '192.0.2.10'
set service dhcp-server shared-network-name NET-VYOS subnet 192.0.2.0/24 range 0 stop '192.0.2.250'
set service dhcp-server shared-network-name NET-VYOS subnet 192.0.2.0/24 subnet-id '1'
```

**Primary**

```none
set service dhcp-server high-availability mode 'active-active'
set service dhcp-server high-availability source-address '192.168.189.252'
set service dhcp-server high-availability name 'dhcp-secondary'
set service dhcp-server high-availability remote '192.168.189.253'
set service dhcp-server high-availability status 'primary'
```

**Secondary**

```none
set service dhcp-server high-availability mode 'active-active'
set service dhcp-server high-availability source-address '192.168.189.253'
set service dhcp-server high-availability name 'dhcp-primary'
set service dhcp-server high-availability remote '192.168.189.252'
set service dhcp-server high-availability status 'secondary'
```

(dhcp-server-v4-example-raw)=


### Operation Mode

```{opcmd} show log dhcp server

Show DHCP server daemon log file
```


```{opcmd} show log dhcp client

Show logs from all DHCP client processes.
```


```{opcmd} show log dhcp client interface \<interface\>

Show logs from specific `interface` DHCP client process.
```


```{opcmd} restart dhcp server

Restart the DHCP server
```


```{opcmd} show dhcp server statistics

Show the DHCP server statistics:
```


```none
vyos@vyos:~$ show dhcp server statistics
Pool           Size    Leases    Available  Usage
-----------  ------  --------  -----------  -------
dhcpexample      99         2           97  2%
```


```{opcmd} show dhcp server statistics pool \<pool\>

Show the DHCP server statistics for the specified pool.
```


```{opcmd} show dhcp server leases

Show statuses of all active leases:
```


```none
vyos@vyos:~$ show dhcp server leases
IP Address      MAC address        State    Lease start          Lease expiration     Remaining    Pool      Hostname    Origin
--------------  -----------------  -------  -------------------  -------------------  -----------  --------  ----------  --------
192.168.11.134  00:50:79:66:68:09  active   2023/11/29 09:51:05  2023/11/29 10:21:05  0:24:10      LAN       VPCS1       local
192.168.11.133  50:00:00:06:00:00  active   2023/11/29 09:51:38  2023/11/29 10:21:38  0:24:43      LAN       VYOS-6      local
10.11.11.108    50:00:00:05:00:00  active   2023/11/29 09:51:43  2023/11/29 10:21:43  0:24:48      VIF-1001  VYOS5       local
192.168.11.135  00:50:79:66:68:07  active   2023/11/29 09:55:16  2023/11/29 09:59:16  0:02:21                            remote
vyos@vyos:~$
```

:::{hint}
Static mappings aren't shown. To show all states, use
`show dhcp server leases state all`.
:::

```{opcmd} show dhcp server leases origin [local | remote]

Show statuses of all active leases granted by local (this server) or
remote (failover server):
```


```none
vyos@vyos:~$ show dhcp server leases origin remote
IP Address      MAC address        State    Lease start          Lease expiration     Remaining    Pool      Hostname    Origin
--------------  -----------------  -------  -------------------  -------------------  -----------  --------  ----------  --------
192.168.11.135  00:50:79:66:68:07  active   2023/11/29 09:55:16  2023/11/29 09:59:16  0:02:21                            remote
vyos@vyos:~$
```


```{opcmd} show dhcp server leases pool \<pool\>

Show only leases in the specified pool.
```


```none
vyos@vyos:~$ show dhcp server leases pool LAN
IP Address      MAC address        State    Lease start          Lease expiration     Remaining    Pool    Hostname    Origin
--------------  -----------------  -------  -------------------  -------------------  -----------  ------  ----------  --------
192.168.11.134  00:50:79:66:68:09  active   2023/11/29 09:51:05  2023/11/29 10:21:05  0:23:55      LAN     VPCS1       local
192.168.11.133  50:00:00:06:00:00  active   2023/11/29 09:51:38  2023/11/29 10:21:38  0:24:28      LAN     VYOS-6      local
vyos@vyos:~$
```


```{opcmd} show dhcp server leases sort \<key\>

Sort the output by the specified key. Possible keys: ip, hardware_address,
state, start, end, remaining, pool, hostname (default = ip)
```


```{opcmd} show dhcp server leases state \<state\>

Show only leases with the specified state. Possible states: all, active,
free, expired, released, abandoned, reset, backup (default = active)
```

## IPv6 server

The network topology is declared by shared-network-name and subnet
declarations. The DHCPv6 service can serve multiple shared networks, with each
shared network having one or more subnets. Each subnet must be present on an
interface. A range can be declared inside a subnet to define a pool of dynamic
addresses. Prefix delegation and static mappings can assign prefixes or fixed
addresses to clients based on their DUID.

(dhcp-server-v6-config)=

### Configuration

```{cfgcmd} set service dhcpv6-server preference \<preference value\>

Clients receiving advertise messages from multiple servers choose the server
with the highest preference value. The range for this value is ``0...255``.
```

```{cfgcmd} set service dhcpv6-server log-level \<fatal | error | warn | info | debug\>

Set the logging verbosity of the Kea DHCPv6 server. The default level is
`info`.
```


#### Shared network options


The following DHCPv6 options apply to an entire shared network. All subnets
inherit these values unless the same option is set locally.


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option captive-portal \<url\>

Captive portal API endpoint (DHCPv6 Option 103).
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option capwap-controller \<address\>

IP address of CAPWAP access controller (DHCPv6 Option 52).
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option domain-search \<domain-name\>

Domain name used when completing DNS requests where no full FQDN is passed.
This option can be given multiple times if you need multiple search domains
(DHCPv6 Option 24).
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option info-refresh-time \<seconds\>

Time in seconds that stateless clients should wait between refreshing the
information they were given (DHCPv6 Option 32).
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option name-server \<address\>

Inform the client that the DNS server can be found at `<address>` (DHCPv6
Option 23). Multiple DNS servers can be defined.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option nis-domain \<domain-name\>

A {abbr}`NIS (Network Information Service)` domain name for clients to use
(DHCPv6 Option 29).
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option nis-server \<address\>

IPv6 address of a NIS server (DHCPv6 Option 27). This option can be specified
multiple times.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option nisplus-domain \<domain-name\>

A {abbr}`NIS+ (Network Information Service Plus)` domain name for clients to
use (DHCPv6 Option 30).
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option nisplus-server \<address\>

IPv6 address of a NIS+ server (DHCPv6 Option 28). This option can be specified
multiple times.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option sip-server \<address\>

IPv6 address of {abbr}`SIP (Session Initiation Protocol)` server (DHCPv6
Option 21 and 22, `sip-server-dns` and `sip-server-addr`). This option can be
specified multiple times.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option sntp-server \<address\>

IPv6 address of an SNTP server for clients to use (DHCPv6 Option 31). This
option can be specified multiple times.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option time-zone \<timezone\>

Time zone to send to clients (DHCPv6 Options 41 and 42,
`new-posix-timezone` and `new-tzdb-timezone`, RFC 4833).
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> option vendor-option \<vendor\> \<option-name\> \<value\>

Specify a vendor-specific DHCPv6 option for the shared network (DHCPv6
Option 17). This option can be specified multiple times.
```


#### Individual Client Subnet

```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> interface \<interface\>

Bind shared network `<name>` to `<interface>`.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> subnet-id \<id\>

This configuration parameter is required and must be unique to each subnet.
It is required to map subnets to lease file entries.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> lease-time {default | maximum | minimum} \<seconds\>

The default lease time for DHCPv6 leases is 24 hours. This can be changed by
supplying a ``default``, ``maximum`` and ``minimum``. All
values need to be supplied in seconds.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> range \<n\> start \<address\>

Create DHCPv6 address range with a range id of `<n>`. DHCPv6 leases are taken
from this pool. The pool starts at address `<address>`.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> range \<n\> stop \<address\>

Create DHCPv6 address range with a range id of `<n>`. DHCPv6 leases are taken
from this pool. The pool stops at address `<address>`.
```

#### Prefix Delegation


To hand out individual prefixes to your clients the following configuration is
used:

```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> prefix-delegation prefix \<pd-prefix\> prefix-length \<length\>

Delegate prefixes from `<pd-prefix>` to clients in subnet `<prefix>`. Range
is defined by `<length>` in bits, 32 to 64.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> prefix-delegation prefix \<pd-prefix\> delegated-length \<length\>

Hand out prefixes of size `<length>` in bits from `<pd-prefix>` to clients
in subnet `<prefix>` when the request for prefix delegation.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> prefix-delegation prefix \<pd-prefix\> excluded-prefix \<exclude-prefix\>

Exclude `<exclude-prefix>` from `<pd-prefix>`.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> prefix-delegation prefix \<pd-prefix\> excluded-prefix-length \<length\>

Define length of exclude prefix in `<pd-prefix>`.
```

**Example:**
- A shared network named `PD-NET` serves subnet `2001:db8::/64`.
- It is connected to `eth1`.
- Address pool shall be `2001:db8::100` through `2001:db8::199`.
- It hands out prefixes `2001:db8:0:10::/64` through `2001:db8:0:1f::/64`.

```none
set service dhcpv6-server shared-network-name 'PD-NET' interface 'eth1'
set service dhcpv6-server shared-network-name 'PD-NET' subnet 2001:db8::/64 range 1 start 2001:db8::100
set service dhcpv6-server shared-network-name 'PD-NET' subnet 2001:db8::/64 range 1 stop 2001:db8::199
set service dhcpv6-server shared-network-name 'PD-NET' subnet 2001:db8::/64 prefix-delegation prefix 2001:db8:0:10:: delegated-length '64'
set service dhcpv6-server shared-network-name 'PD-NET' subnet 2001:db8::/64 prefix-delegation prefix 2001:db8:0:10:: prefix-length '60'
set service dhcpv6-server shared-network-name 'PD-NET' subnet 2001:db8::/64 subnet-id 1
```

#### Address pools

DHCPv6 address pools must be configured for the system to act as a DHCPv6
server. The following example describes a common scenario.

**Example:**
- A shared network named `NET1` serves subnet `2001:db8::/64`
- It is connected to `eth1`
- DNS server is located at `2001:db8::ffff`
- Address pool shall be `2001:db8::100` through `2001:db8::199`.
- Lease time will be left at the default value which is 24 hours

```none
set service dhcpv6-server shared-network-name 'NET' interface 'eth1'
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 range 1 start 2001:db8::100
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 range 1 stop 2001:db8::199
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 option name-server 2001:db8::ffff
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 subnet-id 1
```

The configuration will look as follows:

```none
show service dhcpv6-server
    shared-network-name NET1 {
        subnet 2001:db8::/64 {
           range 1 {
              start 2001:db8::100
              stop 2001:db8::199
           }
           option {
              name-server 2001:db8::ffff
           }
           subnet-id 1
        }
    }
```

(dhcp-server-v6-static-mapping)=

#### Static mappings

In order to map specific IPv6 addresses to specific hosts static mappings can
be created (DHCPv6 Reservations). The following example explains the process.

```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> static-mapping \<hostname\> duid \<identifier\>

Create a new DHCPv6 static mapping named `<hostname>` which is valid for
the host identified by its DHCP unique identifier (DUID) `<identifier>`.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> static-mapping \<hostname\> ipv6-address \<address\>

Static IPv6 address assigned to the host identified by `<hostname>`. This option can be specified
multiple times.
```


```{cfgcmd} set service dhcpv6-server shared-network-name \<name\> subnet \<prefix\> static-mapping \<hostname\> ipv6-prefix \<delegated-prefix\>

Static IPv6 prefix assigned to the host identified by `<hostname>`.
```

**Example:**
- IPv6 address `2001:db8::101` shall be statically mapped
- IPv6 prefix `2001:db8:0:101::/64` shall be statically mapped
- Host specific mapping shall be named `client1`

:::{hint}
The identifier is the device's DUID: colon-separated hex list (as
used by isc-dhcp option dhcpv6.client-id). If the device already has a
dynamic lease from the DHCPv6 server, its DUID can be found with `show
service dhcpv6 server leases`. The DUID begins at the 5th octet (after the
4th colon) of IAID_DUID.
:::
```none
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 static-mapping client1 ipv6-address 2001:db8::101
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 static-mapping client1 ipv6-prefix 2001:db8:0:101::/64
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 static-mapping client1 duid 00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:ff
```

The configuration will look as follows:

```none
show service dhcpv6-server shared-network-name NET1
 subnet 2001:db8::/64 {
     static-mapping client1 {
         duid 00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:ff
         ipv6-address 2001:db8::101
         ipv6-prefix 2001:db8:0:101::/64
     }
 }
```

(dhcp-server-v6-options)=

### Options


The following DHCPv6 options can be set under
`set service dhcpv6-server shared-network-name <name> option ...` or under
`subnet <prefix> option ...` within the same shared network.



:::{list-table}
:header-rows: 1
:stub-columns: 0
:widths: 12 7 23 40 20

* - Setting name
  - Option number
  - DHCP option name
  - Option description
  - Multi
* - captive-portal
  - 103
  - v6-captive-portal
  - Captive portal API endpoint
  - N
* - capwap-controller
  - 52
  - capwap-ac-v6
  - IPv6 address of CAPWAP access controller
  - N
* - domain-search
  - 24
  - domain-search
  - Client domain name search list
  - Y
* - info-refresh-time
  - 32
  - information-refresh-time
  - Time in seconds that stateless clients should wait between
    refreshing information
  - N
* - name-server
  - 23
  - dns-servers
  - Domain Name Servers (DNS) addresses
  - Y
* - nis-domain
  - 29
  - nis-domain-name
  - NIS domain name for client to use
  - N
* - nis-server
  - 27
  - nis-servers
  - IPv6 address of a NIS server
  - Y
* - nisplus-domain
  - 30
  - nisp-domain-name
  - NIS+ domain name for client to use
  - N
* - nisplus-server
  - 28
  - nisp-servers
  - IPv6 address of a NIS+ server
  - Y
* - sip-server
  - 21, 22
  - sip-server-dns, sip-server-addr
  - IPv6 address of SIP server
  - Y
* - sntp-server
  - 31
  - sntp-servers
  - IPv6 address of an SNTP server for client to use
  - Y
* - time-zone
  - 41, 42
  - new-posix-timezone, new-tzdb-timezone
  - Time zone to send to clients (RFC 4833)
  - N
* - vendor-option
  - 17
  - vendor-opts
  - Vendor-specific options
  - Y
:::


Multi: can be specified multiple times.


### Example


DHCPv6 address pools must be configured for the system to act as a DHCPv6
server. The following example describes a common scenario.

- A shared network named `NET1` serves subnet `2001:db8::/64`
- It is connected to `eth1`
- DNS server is located at `2001:db8::ffff`
- Address pool shall be `2001:db8::100` through `2001:db8::199`.
- Lease time will be left at the default value which is 24 hours

```none
set service dhcpv6-server shared-network-name 'NET1' interface 'eth1'
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 range 1 start 2001:db8::100
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 range 1 stop 2001:db8::199
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 option name-server 2001:db8::ffff
set service dhcpv6-server shared-network-name 'NET1' subnet 2001:db8::/64 subnet-id 1
```

The configuration will look as follows:

```none
show service dhcpv6-server
    shared-network-name NET1 {
        subnet 2001:db8::/64 {
           range 1 {
              start 2001:db8::100
              stop 2001:db8::199
           }
           option {
              name-server 2001:db8::ffff
           }
           subnet-id 1
        }
    }
```

(dhcp-server-v6-op-cmd)=

### Operation Mode

```{opcmd} show log dhcpv6 server

Show DHCPv6 server daemon log file
```
```{opcmd} show log dhcpv6 client

Show logs from all DHCPv6 client processes.
```
```{opcmd} show log dhcpv6 client interface \<interface\>

Show logs from specific `interface` DHCPv6 client process.
```
```{opcmd} restart dhcpv6 server

To restart the DHCPv6 server
```
```{opcmd} show dhcpv6 server leases

Shows status of all assigned leases:
```
```none
vyos@vyos:~$ show dhcpv6 server leases
IPv6 address      State    Last communication    Lease expiration     Remaining    Type   Pool      DUID
----------------  -------  --------------------  -------------------  -----------  -----  --------  --------------------------------------------
2001:db8::101     active   2019/12/05 19:40:10   2019/12/06 07:40:10  11:45:21     IA_NA  NET1      98:76:54:32:00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:ff
2001:db8::102     active   2019/12/05 14:01:23   2019/12/06 02:01:23  6:06:34      IA_NA  NET1      87:65:43:21:00:01:00:01:11:22:33:44:fa:fb:fc:fd:fe:ff
2001:db8:10::/64  active   2019/12/05 23:20:10   2019/12/06 11:40:10  11:45:21     IA_PD  PD-NET1   98:76:54:32:00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:ff
```

:::{hint}
Static mappings aren't shown. To show all states, use `show dhcp
server leases state all`.
:::

```{opcmd} show dhcpv6 server leases pool \<pool\>

Show only leases in the specified pool.
```
```{opcmd} show dhcpv6 server leases sort \<key\>

Sort the output by the specified key. Possible keys: expires, iaid_duid, ip,
last_comm, pool, remaining, state, type (default = ip)
```
```{opcmd} show dhcpv6 server leases state \<state\>

Show only leases with the specified state. Possible states: abandoned,
active, all, backup, expired, free, released, reset (default = active)
```
