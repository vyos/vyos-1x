---
myst:
  html_meta:
    description: |
      The VyOS TFTP server lets clients download files from a
      configured directory over UDP. Uploads are disabled by default
      and can be enabled. The server can listen on multiple addresses
      and inside a non-default VRF.
    keywords: tftp, tftp-server, trivial file transfer protocol, file
      transfer, network boot
---

(tftp-server)=

# TFTP server

{abbr}`TFTP (Trivial File Transfer Protocol)` is a simple, UDP-based
file-transfer protocol defined in
[RFC 1350](https://datatracker.ietf.org/doc/html/rfc1350) that lets
clients upload files to and download files from a remote host. One of
its main uses is during the early stages of network boot, where
devices fetch a boot image or initial configuration from a TFTP server
before they are fully operational.

VyOS ships a TFTP server that lets clients download files from a
configured directory. Uploads are disabled by default but can be
enabled. The TFTP server is configured under `service tftp-server`.

## Configuration

```{cfgcmd} set service tftp-server directory \<directory\>

**Configure the directory from which clients download files and, when
uploads are enabled, upload files to.**

The directory is created if it does not exist, and its owner and
group are set to the `tftp` system user. This value is mandatory.
```

```{note}
This setting is mandatory. The commit fails if no directory is configured.
```

```{note}
Choose the location carefully, or the contents will be lost on image
upgrade. Any path under `/config` is preserved and migrated across
image upgrades.
```

Example:

```none
set service tftp-server directory /config/tftpboot
```

```{cfgcmd} set service tftp-server listen-address \<address\>

**Configure a local IPv4 or IPv6 address on which the TFTP server
accepts incoming requests.**

Repeat the command to listen on multiple IP addresses. The IP address must
be assigned to a local interface. Otherwise, the commit succeeds with
a warning, and the TFTP server does not accept connections on that IP
address.
```

```{note}
At least one listen address must be set whenever `service tftp-server`
is configured. Otherwise, the commit is rejected.
```

Example:

```none
set service tftp-server listen-address 192.0.2.1
set service tftp-server listen-address 2001:db8::1
```

```{cfgcmd} set service tftp-server listen-address \<address\> vrf \<name\>

**Expose the TFTP server on the specified IP address within a non-default VRF.**

The {abbr}`VRF (Virtual Routing and Forwarding instance)` must already
be configured under `vrf name <name>`. Otherwise, the commit is
rejected.
```

Example:

```none
set service tftp-server listen-address 192.0.2.1 vrf MGMT
```

```{cfgcmd} set service tftp-server port \<1-65535\>

**Configure the UDP port on which the TFTP server listens.**

The default is 69, the port assigned to TFTP by the
{abbr}`IANA (Internet Assigned Numbers Authority)`.
```

Example:

```none
set service tftp-server port 6969
```

```{cfgcmd} set service tftp-server allow-upload

**Enable client uploads (TFTP write requests) to the server.**

By default, the server operates in read-only mode and rejects write
requests.
```

Example:

```none
set service tftp-server allow-upload
```

## Example

The following example configures a TFTP server that uses
`/config/tftpboot` as its file directory, listens on both IPv4 and
IPv6 addresses, and accepts client uploads.

```none
set service tftp-server directory '/config/tftpboot'
set service tftp-server listen-address '192.0.2.1'
set service tftp-server listen-address '2001:db8::1'
set service tftp-server allow-upload
```

## Verification

Upload a file from a TFTP client to the server (write request):

```none
vyos@client:~$ tftp -p -l /config/config.boot -r backup 192.0.2.1
backup              100% |******************************|   723  0:00:00 ETA
```

On the server, the uploaded file appears in the configured directory,
owned by the `tftp` user:

```none
vyos@vyos:~$ ls -ltr /config/tftpboot/
total 1
-rw-rw-rw- 1 tftp tftp 723 May 19 16:02 backup
```
