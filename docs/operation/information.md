---
lastproofread: '2025-11-19'
---

(information)=

# System Information

VyOS features a rich set of operational level commands to retrieve arbitrary
information about your running system. For more information on the VyOS command
line interface (CLI), see {ref}`cli`.

# Hardware

(hardware_usb)=

## USB

In the past, serial interfaces were defined as `ttySx` and `ttyUSBx` where
`x` was the instance number. However, the mapping of USB-based
serial interfaces can change from one system boot to another, depending on
which driver the operating system loads first.
This inconsistency can be problematic when you
use multiple serial interfaces.
For example, both console-server connections and a serial-backed
{ref}`wwan-interface`.

To address this issue, and because many low-cost USB-to-serial converters
do not have a programmed serial number, VyOS now identifies USB-to-serial
interfaces by the USB root bridge and the bus they connect to.
This approach is similar to the network interface naming conventions used in
recent Linux distributions.

```{opcmd} show hardware usb

Retrieve a tree-like representation of all connected USB devices.

:::{note}
If a device is unplugged and plugged in again, it is assigned a new
``Port``, ``Dev``, and ``If``.
:::
```

```{opcmd} show hardware usb serial

Retrieve a list and description of all connected USB serial devices. The
device name displayed, (for example ``usb0b2.4p1.0``), can be used
directly when accessing the serial console as console-server device.
```

(information-version)=

# Version

```{opcmd} show version

Return the currently running VyOS version and build information. This
includes the name of the release train, e.g., ``sagitta`` on VyOS 1.4,
and ``circinus`` on VyOS 1.5.

:::{code-block} none
vyos@vyos:~$ show version

Version:          VyOS 1.4-rolling-202106270801
Release Train:    sagitta

Built by:         autobuild@vyos.net
Built on:         Sun 27 Jun 2021 09:50 UTC
Build UUID:       ab43e735-edcb-405a-9f51-f16a1b104e52
Build Commit ID:  f544d75eab758f

Architecture:     x86_64
Boot via:         installed image
System type:      KVM guest

Hardware vendor:  QEMU
Hardware model:   Standard PC (i440FX + PIIX, 1996)
Hardware S/N:
Hardware UUID:    Unknown

Copyright:        VyOS maintainers and contributors
:::
```

```{opcmd} show version kernel

Return the version number of the currently running Linux kernel.

:::{code-block} none
vyos@vyos:~$ show version kernel
5.10.46-amd64-vyos
:::
```

```{opcmd} show version frr

Return the version number of FRR (Free Range Routing - <https://frrouting.org/>)
used in this release. This is the routing control plane and a successor to GNU
Zebra and Quagga.

:::{code-block} none
vyos@vyos:~$ show version frr
  FRRouting 7.5.1-20210625-00-gf07d935a2 (vyos).
  Copyright 1996-2005 Kunihiro Ishiguro, et al.
:::
```
