---
myst:
  html_meta:
    description: |
      Console server is a VyOS service that lets a router act as an
      out-of-band management device, providing SSH-based remote access
      to the serial consoles of directly attached devices. It supports
      both on-board UARTs and USB-to-serial adapters.
    keywords: console-server, out-of-band, oob, serial console, ssh, usb-to-serial
---

(console-server)=

# Console server

VyOS can serve as an
{abbr}`OOB (Out-of-Band)` management device, providing SSH-based
remote access to the serial consoles of directly attached devices.


The following serial interfaces are supported:

- On-board
  {abbr}`UARTs (Universal Asynchronous Receiver-Transmitters)`,
  exposed by the Linux kernel as `/dev/ttyS<N>`.
- USB-to-serial adapters supported by the Linux USB serial driver,
  including Prolific PL2303 and FTDI FT232/FT4232 based chips.


You can view available devices in the Tab completion of `set service console-server device`.

See {ref}`hardware_usb` for more details on the naming scheme.

## Configuration

A console server only works when its serial port is configured to
match the framing the attached device uses. The framing consists of
three parameters that the device's documentation will specify: data
bits per character (typically 8, sometimes 7), parity (none, even, or
odd), and stop bits (1 or 2), conventionally written together as a
line, such as 8N1 (eight data bits, no parity, one stop bit).

8N1 is the default framing for most network equipment, so VyOS also
defaults to it. For an 8N1 device, only the line rate (`speed`) must
be configured. The `data-bits`, `parity`, and `stop-bits` commands
below are needed only for devices that use a different framing.

```{cfgcmd} set service console-server device \<device\> speed \<300 | 1200 | 2400 | 4800 | 9600 | 19200 | 38400 | 57600 | 115200\>

**Configure the line rate, in baud, for the specified serial device.**
```

```{note}
This setting is mandatory for each serial device. Otherwise, the
commit is rejected.
```

```{note}
A serial device already in use by VyOS's system console (configured
via `set system console device <device>`) cannot be configured as a
console server device. Configuring the same device under both
`system console` and `console-server` causes a commit failure.
```


Example:

```none
set service console-server device usb0b2.4p1.0 speed 9600
```

```{cfgcmd} set service console-server device \<device\> data-bits \<7 | 8\>

**Configure the number of data bits per character for the specified
serial device.**

The default is 8.
```

Example:

```none
set service console-server device usb0b2.4p1.0 data-bits 8
```

```{cfgcmd} set service console-server device \<device\> stop-bits \<1 | 2\>

**Configure the number of stop bits that mark the end of each
character for the specified serial device.**

The default is 1.
```

Example:

```none
set service console-server device usb0b2.4p1.0 stop-bits 1
```

```{cfgcmd} set service console-server device \<device\> parity \<even | odd | none\>

**Configure the parity mode for the specified serial device.**

The default is `none`.
```

Example:

```none
set service console-server device usb0b2.4p1.0 parity none
```

```{cfgcmd} set service console-server device \<device\> description \<description\>

**Configure a description for the specified serial device.**

Limited to 255 characters.
```

Example:

```none
set service console-server device usb0b2.4p1.0 description 'core-sw-1 console'
```

```{cfgcmd} set service console-server device \<device\> alias \<alias\>

**Configure an alias for the specified serial device.**

The alias can be used in place of the device name in the
`connect console` operational command. Aliases must be unique across
all configured serial devices and are restricted to the character
class `[-_a-zA-Z0-9.]`, with a maximum length of 128 characters.
```

Example:

```none
set service console-server device usb0b2.4p1.0 alias core-sw-1
```

### Remote access

Each configured console device can be exposed for direct SSH access on
a dedicated TCP port. This SSH access is served by a separate SSH
instance, independent of the main `service ssh` daemon.

```{cfgcmd} set service console-server device \<device\> ssh port \<1-65535\>

**Configure a dedicated TCP port on which SSH access to the specified
serial device is exposed.**

After successful authentication, the user is connected directly to the
device's serial console.
```

```{note}
Multiple users can SSH to the same serial device simultaneously, but
only one can type at a time. The others see the same output in
read-only mode.
```

Example:

```none
set service console-server device usb0b2.4p1.0 ssh port 2201
```

## Operation

```{opcmd} show console-server ports

Show each configured console device together with its line rate.
```

```none
vyos@vyos:~$ show console-server ports
usb0b2.4p1.0             on /dev/serial/by-bus/usb0b2.4p1.0@ at   9600n
```

```{opcmd} show console-server user

Show each configured console device, its up/down state, and the
user currently typing in the console, if any.
```

```none
vyos@vyos:~$ show console-server user
usb0b2.4p1.0               up   vyos@localhost
```

```{opcmd} connect console \<device | alias\>

Connect to the specified serial device's console from the VyOS
CLI.

If an alias is configured for the device, it can be used in place of
the device name.
```

```{note}
Multiple users can connect to the same serial device simultaneously,
but only one can type at a time. The others see the same output in
read-only mode.
```

```{note}
Press the keys in sequence: `Ctrl+E c ?` to list in-session commands,
`Ctrl+E c .` to disconnect from the session. Both escape sequences
are interpreted by the console-server client locally and are not sent
to the attached device.
```

```none
vyos@vyos-r1:~$ connect console usb0b2.4p1.0
[Enter `^Ec?' for help]
[-- MOTD -- VyOS Console Server]

vyos-r2 login:
```

```{opcmd} show log console-server

Show the console server log since the most recent boot, in live
mode.

Use `Ctrl+C` to exit.
```
