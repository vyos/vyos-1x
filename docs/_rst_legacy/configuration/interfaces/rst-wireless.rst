:lastproofread: 2026-03-23

.. _wireless-interface:

####################
Wireless LAN / Wi-Fi
####################

:abbr:`WLAN (Wireless LAN)` interfaces provide 802.11 (a/b/g/n/ac) wireless
connectivity, referred to as Wi-Fi, and operate in one of the following
modes:

* :abbr:`WAP (Wireless Access-Point)` mode provides network access to connecting
  stations if the physical hardware supports acting as a WAP

* Station mode acts as a Wi-Fi client accessing the network through an available
  WAP

* Monitor mode lets the system passively monitor wireless traffic

If the system detects an unconfigured wireless device, it will be automatically
added to the configuration tree, specifying any detected settings (for example,
its MAC address) and configured to run in monitor mode.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-common-with-dhcp.txt
   :var0: wireless
   :var1: wlan0

System-wide configuration
=========================

.. cfgcmd:: set system wireless country-code <cc>

  Country code (ISO/IEC 3166-1). Used to set regulatory domain. Set as needed
  to indicate country in which device is operating. This can limit available
  channels and transmit power.

  .. note:: This option is mandatory in ``access-point`` mode.

Wireless options
================

.. cfgcmd:: set interfaces wireless <interface> channel <number>

  Configure the IEEE 802.11 wireless radio channel for the interface.
  Channel allocation depends on the frequency band:

  * **2.4 GHz** (802.11b/g/n/ax): Channels range from 1 to 14.
  * **5 GHz** (802.11a/h/j/n/ac/ax): Channels range from 34 to 177.
  * **6 GHz** (802.11ax): Channels range from 1 to 233.
  * **Automatic channel selection:** 0.

.. cfgcmd:: set interfaces wireless <interface> disable-broadcast-ssid

  Send empty SSID in beacons and ignore probe request frames that do not specify
  full SSID, i.e., require stations to know the SSID.

.. cfgcmd:: set interfaces wireless <interface> expunge-failing-stations

  Disassociate stations based on excessive transmission failures or other
  indications of connection loss.

  This depends on the driver capabilities and may not be available with all
  drivers.

.. cfgcmd:: set interfaces wireless <interface> isolate-stations

  Client isolation can be used to prevent low-level bridging of frames between
  associated stations in the BSS.

  By default, this bridging is allowed.

.. cfgcmd:: set interfaces wireless <interface> max-stations <count>

  Maximum number of stations allowed in station table. New stations will be
  rejected after the station table is full. IEEE 802.11 has a limit of 2007
  different association IDs, so this number should not be larger than that.

  This defaults to 2007.

.. cfgcmd:: set interfaces wireless <interface> mgmt-frame-protection

  Management Frame Protection (MFP) according to IEEE 802.11w

  .. note:: :abbr:`MFP (Management Frame Protection)` is required for WPA3.

.. cfgcmd:: set interfaces wireless <interface> enable-bf-protection

  Beacon Protection: management frame protection for Beacon frames.

  .. note:: This option requires :abbr:`MFP (Management Frame Protection)` 
    to be enabled.

.. cfgcmd:: set interfaces wireless <interface> mode <a | b | g | n | ac | ax>

  Operation mode of wireless radio.

  * ``a`` - 802.11a - 54 Mbits/sec
  * ``b`` - 802.11b - 11 Mbits/sec
  * ``g`` - 802.11g - 54 Mbits/sec (default)
  * ``n`` - 802.11n - 600 Mbits/sec
  * ``ac`` - 802.11ac - 1300 Mbits/sec
  * ``ax`` - 802.11ax - exceeds 1GBit/sec

  .. note:: In VyOS, 802.11ax is only implemented for 2.4GHz and 6GHz.

.. cfgcmd:: set interfaces wireless <interface> physical-device <device>

  Wireless hardware device used as underlay radio.

  This defaults to phy0.

.. cfgcmd:: set interfaces wireless <interface> reduce-transmit-power <number>

  Adds the Power Constraint information element to Beacon and Probe Response
  frames.

  This option adds the Power Constraint information element when applicable
  and the Country information element is configured. The Power Constraint 
  element is required by Transmit Power Control.

  Valid values are 0..255.

.. cfgcmd:: set interfaces wireless <interface> ssid <ssid>

  SSID to be used in IEEE 802.11 management frames

.. cfgcmd:: set interfaces wireless <interface> type
   <access-point | station | monitor>

  Wireless device type for this interface

  * ``access-point``: Forwards packets between other nodes.
  * ``station``: Connects to another :abbr:`AP (Access Point)`.
  * ``monitor``: Passively monitors all packets on the frequency/channel.

.. cmdinclude:: /_include/interface-per-client-thread.txt
   :var0: wireless
   :var1: wlan0

PPDU
----

.. cfgcmd:: set interfaces wireless <interface> capabilities require-ht

.. cfgcmd:: set interfaces wireless <interface> capabilities require-vht

.. cfgcmd:: set interfaces wireless <interface> capabilities require-he

HT (High Throughput) capabilities (802.11n)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Configuring HT mode options is required when using 802.11n or
  802.11ax at 2.4GHz.

.. cfgcmd:: set interfaces wireless <interface> capabilities ht 40mhz-incapable

  Device is incapable of 40 MHz, do not advertise. This sets ``[40-INTOLERANT]``

.. cfgcmd:: set interfaces wireless <interface> capabilities ht auto-powersave

  WMM-PS Unscheduled Automatic Power Save Delivery [U-APSD]

.. cfgcmd:: set interfaces wireless <interface> capabilities ht
   channel-set-width <ht20 | ht40+ | ht40->

  Supported channel width set.

  * ``ht20`` - 20 MHz channel width
  * ``ht40-`` - Both 20 MHz and 40 MHz with secondary channel below the primary
    channel
  * ``ht40+`` - Both 20 MHz and 40 MHz with secondary channel above the primary
    channel

  .. note:: Channel availability for HT40- and HT40+ is limited. The following
     table lists channels permitted for HT40- and HT40+ according to IEEE
     802.11n Annex J. Channel availability may vary by location.

    .. code-block:: none

      freq		HT40-		HT40+
      2.4 GHz		5-13		1-7 (1-9 in Europe/Japan)
      5 GHz		40,48,56,64	36,44,52,60

  .. note:: 40 MHz channels may switch their primary and secondary channels if
    needed or creation of 40 MHz channel may be rejected based on overlapping
    BSSes. These changes are done automatically when hostapd is setting up the
    40 MHz channel.

.. cfgcmd:: set interfaces wireless <interface> capabilities ht
   delayed-block-ack

  Enable HT-delayed Block Ack ``[DELAYED-BA]``

.. cfgcmd:: set interfaces wireless <interface> capabilities ht dsss-cck-40

  DSSS/CCK Mode in 40 MHz, this sets ``[DSSS_CCK-40]``

.. cfgcmd:: set interfaces wireless <interface> capabilities ht greenfield

  This enables the greenfield option which sets the ``[GF]`` option

.. cfgcmd:: set interfaces wireless <interface> capabilities ht ldpc

  Enable LDPC coding capability

.. cfgcmd:: set interfaces wireless <interface> capabilities ht lsig-protection

  Enable L-SIG TXOP protection capability

.. cfgcmd:: set interfaces wireless <interface> capabilities ht max-amsdu
   <3839 | 7935>

  Maximum A-MSDU length 3839 (default) or 7935 octets

.. cfgcmd:: set interfaces wireless <interface> capabilities ht
   short-gi <20 | 40>

  Short GI capabilities for 20 and 40 MHz

.. cfgcmd:: set interfaces wireless <interface> capabilities ht
   smps <static | dynamic>

  Spatial Multiplexing Power Save (SMPS) settings

.. cfgcmd:: set interfaces wireless <interface> capabilities ht stbc rx <num>

  Enable receiving PPDU using STBC (Space Time Block Coding)

.. cfgcmd:: set interfaces wireless <interface> capabilities ht stbc tx

  Enable sending PPDU using STBC (Space Time Block Coding)

VHT (Very High Throughput) capabilities (802.11ac)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. stop_vyoslinter

.. cfgcmd:: set interfaces wireless <interface> capabilities vht antenna-count <count>

.. start_vyoslinter

  Number of antennas on this card

.. cfgcmd:: set interfaces wireless <interface> capabilities vht
   antenna-pattern-fixed

  Set if antenna pattern does not change during the lifetime of an association

.. cfgcmd:: set interfaces wireless <interface> capabilities vht beamform
  <single-user-beamformer | single-user-beamformee | multi-user-beamformer |
  multi-user-beamformee>

  Beamforming capabilities:

  * ``single-user-beamformer`` - Support for operation as 
    single user beamformer
  * ``single-user-beamformee`` - Support for operation as 
    single user beamformee
  * ``multi-user-beamformer`` - Support for operation as 
    multi user beamformer
  * ``multi-user-beamformee`` - Support for operation as 
    multi user beamformee

.. cfgcmd:: set interfaces wireless <interface> capabilities vht
   center-channel-freq <freq-1 | freq-2> <number>

  VHT operating channel center frequency - center freq 1
  (for use with 80, 80+80 and 160 modes)

  VHT operating channel center frequency - center freq 2
  (for use with the 80+80 mode)

  <number> must be from 34 - 173. For 80 MHz channels it should be channel + 6.

.. cfgcmd:: set interfaces wireless <interface> capabilities vht
   channel-set-width <0 | 1 | 2 | 3>

   * ``0`` - 20 or 40 MHz channel width (default)
   * ``1`` - 80 MHz channel width
   * ``2`` - 160 MHz channel width
   * ``3`` - 80+80 MHz channel width

.. cfgcmd:: set interfaces wireless <interface> capabilities vht ldpc

  Enable LDPC (Low Density Parity Check) coding capability

.. cfgcmd:: set interfaces wireless <interface> 
  capabilities vht link-adaptation

  VHT link adaptation capabilities

.. cfgcmd:: set interfaces wireless <interface> capabilities vht
   max-mpdu <value>

  Increase Maximum MPDU length to 7991 or 11454 octets (default 3895 octets)

.. cfgcmd:: set interfaces wireless <interface> capabilities vht
   max-mpdu-exp <value>

  Set the maximum length of A-MPDU pre-EOF padding that the station can 
  receive

.. cfgcmd:: set interfaces wireless <interface> capabilities vht
   short-gi <80 | 160>

  Short GI capabilities

.. cfgcmd:: set interfaces wireless <interface> capabilities vht stbc rx <num>

  Enable receiving PPDU using STBC (Space Time Block Coding)

.. cfgcmd:: set interfaces wireless <interface> capabilities vht stbc tx

  Enable sending PPDU using STBC (Space Time Block Coding)

.. cfgcmd:: set interfaces wireless <interface> capabilities vht tx-powersave

  Enable VHT TXOP Power Save Mode

.. cfgcmd:: set interfaces wireless <interface> capabilities vht vht-cf

  Station supports receiving VHT variant HT Control field

HE (High Efficiency) capabilities (802.11ax)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces wireless <interface> 
  capabilities he antenna-pattern-fixed

  Tell the AP that antenna positions are fixed and will not change
  during the lifetime of an association.

.. cfgcmd:: set interfaces wireless <interface> capabilities he beamform 
  <single-user-beamformer | single-user-beamformee | multi-user-beamformer>

  Beamforming capabilities:

  * ``single-user-beamformer`` - Support for operation as 
    single user beamformer
  * ``single-user-beamformee`` - Support for operation as 
    single user beamformee
  * ``multi-user-beamformer`` - Support for operation as multi
    user beamformer

.. cfgcmd:: set interfaces wireless <interface> 
  capabilities he bss-color <number>

  BSS coloring helps to prevent channel jamming when multiple APs use 
  the same channels.

  Valid values are 1..63

.. cfgcmd:: set interfaces wireless <interface> capabilities he 
  center-channel-freq <freq-1 | freq-2> <number>

  HE operating channel center frequency - center freq 1
  (for use with 80, 80+80 and 160 modes)

  HE operating channel center frequency - center freq 2
  (for use with the 80+80 mode)

  <number> must be within 1..233. For 80 MHz channels it should be 
  channel + 6 and for 160 MHz channels, it should be channel + 14.

.. cfgcmd:: set interfaces wireless <interface> 
  capabilities he channel-set-width <number>

  <number> must be one of:

  * ``81`` - 20 MHz channel width (2.4GHz)
  * ``83`` - 40 MHz channel width, secondary 20MHz channel above primary 
    channel (2.4GHz)
  * ``84`` - 40 MHz channel width, secondary 20MHz channel below primary 
    channel (2.4GHz)
  * ``131`` - 20 MHz channel width (6GHz)
  * ``132`` - 40 MHz channel width (6GHz)
  * ``133`` - 80 MHz channel width (6GHz)
  * ``134`` - 160 MHz channel width (6GHz)
  * ``135`` - 80+80 MHz channel width (6GHz)

.. cfgcmd:: set interfaces wireless <interface> 
  capabilities he coding-scheme <number>

  This setting configures Spatial Stream and Modulation Coding Scheme 
  settings for HE mode (HE-MCS). It is usually not needed to set this 
  explicitly, but it might help with some WiFi adapters.

  <number> must be one of:

  * ``0`` - HE-MCS 0-7
  * ``1`` - HE-MCS 0-9
  * ``2`` - HE-MCS 0-11
  * ``3`` - HE-MCS is not supported

Wireless options (Station/Client)
=================================

The example creates a wireless station (commonly referred to as Wi-Fi client)
that accesses the network through the WAP defined in the above example. The
default physical device (``phy0``) is used.

.. code-block:: none

  set system wireless country-code de
  set interfaces wireless wlan0 type station
  set interfaces wireless wlan0 address dhcp
  set interfaces wireless wlan0 ssid 'TEST'
  set interfaces wireless wlan0 security wpa passphrase '12345678'

Resulting configuration:

.. code-block:: none

  system {
    wireless {
      country-code de
    }
  }
  interfaces {
    wireless wlan0 {
      address dhcp
      security {
        wpa {
          passphrase "12345678"
        }
      }
      ssid TEST
      type station
    }

Security
========

:abbr:`WPA (Wi-Fi Protected Access)`, WPA2 Enterprise and WPA3 Enterprise in 
combination with 802.1X based authentication can be used to authenticate 
users or computers in a domain.

The wireless client (supplicant) authenticates against the RADIUS server
(authentication server) using an :abbr:`EAP (Extensible Authentication
Protocol)` method configured on the RADIUS server. The WAP (also referred
to as authenticator) role is to send all authentication messages between the
supplicant and the configured authentication server, thus the RADIUS server
is responsible for authenticating the users.

The WAP in this example has the following characteristics:

* IP address ``192.168.2.1/24``
* Network ID (SSID) ``Enterprise-TEST``
* WPA passphrase ``12345678``
* Use 802.11n protocol
* Wireless channel ``1``
* RADIUS server at ``192.168.3.10`` with shared-secret ``VyOSPassword``

.. stop_vyoslinter
.. code-block:: none

  set system wireless country-code de
  set interfaces wireless wlan0 address '192.168.2.1/24'
  set interfaces wireless wlan0 type access-point
  set interfaces wireless wlan0 channel 1
  set interfaces wireless wlan0 mode n
  set interfaces wireless wlan0 ssid 'Enterprise-TEST'
  set interfaces wireless wlan0 security wpa mode wpa2
  set interfaces wireless wlan0 security wpa cipher CCMP
  set interfaces wireless wlan0 security wpa radius server 192.168.3.10 key 'VyOSPassword'
  set interfaces wireless wlan0 security wpa radius server 192.168.3.10 port 1812

.. start_vyoslinter

Resulting configuration:

.. code-block:: none

  system {
    wireless {
      country-code de
    }
  }
  interfaces {
    [...]
    wireless wlan0 {
          address 192.168.2.1/24
          channel 1
          mode n
          security {
              wpa {
                  cipher CCMP
                  mode wpa2
                  radius {
                      server 192.168.3.10 {
                          key 'VyOSPassword'
                          port 1812
                      }
                  }
              }
          }
          ssid "Enterprise-TEST"
          type access-point
      }
  }

VLAN
====

Regular VLANs (802.1q)
----------------------

.. cmdinclude:: /_include/interface-vlan-8021q.txt
   :var0: wireless
   :var1: wlan0

QinQ (802.1ad)
--------------

.. cmdinclude:: /_include/interface-vlan-8021ad.txt
   :var0: wireless
   :var1: wlan0

*********
Operation
*********

.. opcmd:: show interfaces wireless info

Use this command to view operational status and wireless-specific information
about all wireless interfaces.

.. code-block:: none

  vyos@vyos:~$ show interfaces wireless info
  Interface  Type          SSID                         Channel
  wlan0      access-point  VyOS-TEST-0                        1

.. opcmd:: show interfaces wireless detail

Show the operational status and detailed wireless-specific
information about all wireless interfaces.

.. stop_vyoslinter
.. code-block:: none

  vyos@vyos:~$ show interfaces wireless detail
  wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
      link/ether XX:XX:XX:XX:XX:c3 brd XX:XX:XX:XX:XX:ff
      inet xxx.xxx.99.254/24 scope global wlan0
         valid_lft forever preferred_lft forever
      inet6 fe80::xxxx:xxxx:fe54:2fc3/64 scope link
         valid_lft forever preferred_lft forever

      RX:  bytes    packets     errors    dropped    overrun      mcast
           66072        282          0          0          0          0
      TX:  bytes    packets     errors    dropped    carrier collisions
           83413        430          0          0          0          0

  wlan1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
      link/ether XX:XX:XX:XX:XX:c3 brd XX:XX:XX:XX:XX:ff
      inet xxx.xxx.100.254/24 scope global wlan0
         valid_lft forever preferred_lft forever
      inet6 fe80::xxxx:xxxx:ffff:2ed3/64 scope link
         valid_lft forever preferred_lft forever

      RX:  bytes    packets     errors    dropped    overrun      mcast
           166072      5282          0          0          0          0
      TX:  bytes    packets     errors    dropped    carrier collisions
           183413      5430          0          0          0          0

.. start_vyoslinter

.. opcmd:: show interfaces wireless <wlanX>

This command shows both status and statistics on the specified wireless
interface. The wireless interface identifier can range from wlan0 to wlan999.

.. stop_vyoslinter
.. code-block:: none

  vyos@vyos:~$ show interfaces wireless wlan0
  wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
      link/ether XX:XX:XX:XX:XX:c3 brd XX:XX:XX:XX:XX:ff
      inet xxx.xxx.99.254/24 scope global wlan0
         valid_lft forever preferred_lft forever
      inet6 fe80::xxxx:xxxx:fe54:2fc3/64 scope link
         valid_lft forever preferred_lft forever

      RX:  bytes    packets     errors    dropped    overrun      mcast
           66072        282          0          0          0          0
      TX:  bytes    packets     errors    dropped    carrier collisions
           83413        430          0          0          0          0

.. start_vyoslinter


.. opcmd:: show interfaces wireless <wlanX> brief

This command gives a brief status overview of a specified wireless interface.
The wireless interface identifier can range from wlan0 to wlan999.

.. code-block:: none

  vyos@vyos:~$ show interfaces wireless wlan0 brief
  Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
  Interface        IP Address                        S/L  Description
  ---------        ----------                        ---  -----------
  wlan0            192.168.2.254/24                    u/u


.. opcmd:: show interfaces wireless <wlanX> queue

Use this command to view wireless interface queue information.
The wireless interface identifier can range from wlan0 to wlan999.

.. code-block:: none

  vyos@vyos:~$ show interfaces wireless wlan0 queue
  qdisc pfifo_fast 0: root bands 3 priomap 1 2 2 2 1 2 0 0 1 1 1 1 1 1 1 1
   Sent 810323 bytes 6016 pkt (dropped 0, overlimits 0 requeues 0)
   rate 0bit 0pps backlog 0b 0p requeues 0


.. opcmd:: show interfaces wireless <wlanX> scan

This command is used to retrieve information about WAP within the range of your
wireless interface. This command is useful on wireless interfaces configured
in station mode.

.. note:: Scanning is not supported on all wireless drivers and wireless
   hardware. Refer to your driver and wireless hardware documentation for
   further details.

.. code-block:: none

  vyos@vyos:~$ show interfaces wireless wlan0 scan
  Address            SSID                          Channel  Signal (dbm)
  00:53:3b:88:6e:d8  WLAN-576405                         1  -64.00
  00:53:3b:88:6e:da  Telekom_FON                         1  -64.00
  00:53:00:f2:c2:a4  BabyView_F2C2A4                     6  -60.00
  00:53:3b:88:6e:d6  Telekom_FON                       100  -72.00
  00:53:3b:88:6e:d4  WLAN-576405                       100  -71.00
  00:53:44:a4:96:ec  KabelBox-4DC8                      56  -81.00
  00:53:d9:7a:67:c2  WLAN-741980                         1  -75.00
  00:53:7c:99:ce:76  Vodafone Homespot                   1  -86.00
  00:53:44:a4:97:21  KabelBox-4DC8                       1  -78.00
  00:53:44:a4:97:21  Vodafone Hotspot                    1  -79.00
  00:53:44:a4:97:21  Vodafone Homespot                   1  -79.00
  00:53:86:40:30:da  Telekom_FON                         1  -86.00
  00:53:7c:99:ce:76  Vodafone Hotspot                    1  -86.00
  00:53:44:46:d2:0b  Vodafone Hotspot                    1  -87.00


********
Examples
********

The following example creates a WAP. When configuring multiple WAP interfaces,
you must specify unique IP addresses, channels, Network IDs commonly referred
to as :abbr:`SSID (Service Set Identifier)`, and MAC addresses.

The WAP in this example has the following characteristics:

* IP address ``192.168.2.1/24``
* Network ID (SSID) ``TEST``
* WPA passphrase ``12345678``
* Use 802.11n protocol
* Wireless channel ``1``

.. code-block:: none

  set system wireless country-code de
  set interfaces wireless wlan0 address '192.168.2.1/24'
  set interfaces wireless wlan0 type access-point
  set interfaces wireless wlan0 channel 1
  set interfaces wireless wlan0 mode n
  set interfaces wireless wlan0 ssid 'TEST'
  set interfaces wireless wlan0 security wpa mode wpa2
  set interfaces wireless wlan0 security wpa cipher CCMP
  set interfaces wireless wlan0 security wpa passphrase '12345678'

Resulting configuration:

.. code-block:: none

  system {
    wireless {
      country-code de
    }
  }
  interfaces {
    [...]
    wireless wlan0 {
          address 192.168.2.1/24
          channel 1
          mode n
          security {
              wpa {
                  cipher CCMP
                  mode wpa2
                  passphrase "12345678"
              }
          }
          ssid "TEST"
          type access-point
      }
  }

To enable access point functionality, configure a DHCP server for this
interface's network, or add the interface to an existing local bridge
(see :ref:`bridge-interface` for details).

Wi-Fi 6/6E (802.11ax)
=====================

The following examples configure Wi-Fi 6 (2.4 GHz) and Wi-Fi 6E (6 GHz)
:abbr:`APs (Access Points)` with the following parameters:

* Network ID (SSID): ``test.ax``
* WPA passphrase: ``super-dooper-secure-passphrase``
* Protocol: 802.11ax
* Wireless channel for 2.4 GHz: ``11``
* Wireless channel for 6 GHz: ``5``


Example configuration: Wi-Fi 6 at 2.4 GHz
------------------------------------------

You may expect real throughput around 10 MB/s or higher in crowded areas.

.. stop_vyoslinter

.. code-block:: none

  set system wireless country-code de
  set interfaces wireless wlan0 capabilities he antenna-pattern-fixed
  set interfaces wireless wlan0 capabilities he beamform multi-user-beamformer
  set interfaces wireless wlan0 capabilities he beamform single-user-beamformee
  set interfaces wireless wlan0 capabilities he beamform single-user-beamformer
  set interfaces wireless wlan0 capabilities he bss-color 13
  set interfaces wireless wlan0 capabilities he channel-set-width 81
  set interfaces wireless wlan0 capabilities ht 40mhz-incapable
  set interfaces wireless wlan0 capabilities ht channel-set-width ht20
  set interfaces wireless wlan0 capabilities ht channel-set-width ht40+
  set interfaces wireless wlan0 capabilities ht channel-set-width ht40-
  set interfaces wireless wlan0 capabilities ht short-gi 20
  set interfaces wireless wlan0 capabilities ht short-gi 40
  set interfaces wireless wlan0 capabilities ht stbc rx 2
  set interfaces wireless wlan0 capabilities ht stbc tx
  set interfaces wireless wlan0 channel 11
  set interfaces wireless wlan0 description "802.11ax 2.4GHz"
  set interfaces wireless wlan0 mode ax
  set interfaces wireless wlan0 security wpa cipher CCMP
  set interfaces wireless wlan0 security wpa cipher CCMP-256
  set interfaces wireless wlan0 security wpa cipher GCMP-256
  set interfaces wireless wlan0 security wpa cipher GCMP
  set interfaces wireless wlan0 security wpa mode wpa2
  set interfaces wireless wlan0 security wpa passphrase super-dooper-secure-passphrase
  set interfaces wireless wlan0 ssid test.ax
  set interfaces wireless wlan0 type access-point
  commit

.. start_vyoslinter

Resulting configuration:

.. code-block:: none

  system {
    wireless {
      country-code de
    }
  }
  interfaces {
    [...]
    wireless wlan0 {
          capabilities {
              he {
                  antenna-pattern-fixed
                  beamform {
                      multi-user-beamformer
                      single-user-beamformee
                      single-user-beamformer
                  }
                  bss-color 13
                  channel-set-width 81
              }
              ht {
                  40mhz-incapable
                  channel-set-width ht20
                  channel-set-width ht40+
                  channel-set-width ht40-
                  short-gi 20
                  short-gi 40
                  stbc {
                      rx 2
                      tx
                  }
              }
          }
          channel 11
          description "802.11ax 2.4GHz"
          hw-id [...]
          mode ax
          physical-device phy0
          security {
              wpa {
                  cipher CCMP
                  cipher CCMP-256
                  cipher GCMP-256
                  cipher GCMP
                  mode wpa2
                  passphrase super-dooper-secure-passphrase
              }
          }
          ssid test.ax
          type access-point
      }
  }

Example configuration: Wi-Fi 6E at 6 GHz
-----------------------------------------

You may expect real throughput between 50 MB/s and 150 MB/s, depending on
obstructions from walls, water, metal, or other materials
with high electromagnetic damping at 6 GHz. Best results are achieved
with the AP being in the same room and in line-of-sight.

.. stop_vyoslinter

.. code-block:: none

  set system wireless country-code de
  set interfaces wireless wlan0 capabilities he antenna-pattern-fixed
  set interfaces wireless wlan0 capabilities he beamform multi-user-beamformer
  set interfaces wireless wlan0 capabilities he beamform single-user-beamformee
  set interfaces wireless wlan0 capabilities he beamform single-user-beamformer
  set interfaces wireless wlan0 capabilities he bss-color 13
  set interfaces wireless wlan0 capabilities he channel-set-width 134
  set interfaces wireless wlan0 capabilities he center-channel-freq freq-1 15
  set interfaces wireless wlan0 channel 5
  set interfaces wireless wlan0 description "802.11ax 6GHz"
  set interfaces wireless wlan0 mode ax
  set interfaces wireless wlan0 security wpa cipher CCMP
  set interfaces wireless wlan0 security wpa cipher CCMP-256
  set interfaces wireless wlan0 security wpa cipher GCMP-256
  set interfaces wireless wlan0 security wpa cipher GCMP
  set interfaces wireless wlan0 security wpa mode wpa3
  set interfaces wireless wlan0 security wpa passphrase super-dooper-secure-passphrase
  set interfaces wireless wlan0 mgmt-frame-protection required
  set interfaces wireless wlan0 enable-bf-protection
  set interfaces wireless wlan0 ssid test.ax
  set interfaces wireless wlan0 type access-point
  set interfaces wireless wlan0 stationary-ap
  commit

.. start_vyoslinter

Resulting configuration:

.. code-block:: none

  system {
    wireless {
      country-code de
    }
  }
  interfaces {
    [...]
    wireless wlan0 {
          capabilities {
              he {
                  antenna-pattern-fixed
                  beamform {
                      multi-user-beamformer
                      single-user-beamformee
                      single-user-beamformer
                  }
                  bss-color 13
                  center-channel-freq {
                      freq-1 15
                  }
                  channel-set-width 134
              }
          }
          channel 5
          description "802.11ax 6GHz"
          enable-bf-protection
          hw-id [...]
          mgmt-frame-protection required
          mode ax
          physical-device phy0
          security {
              wpa {
                  cipher CCMP
                  cipher CCMP-256
                  cipher GCMP-256
                  cipher GCMP
                  mode wpa3
                  passphrase super-dooper-secure-passphrase
              }
          }
          ssid test.ax
          stationary-ap
          type access-point
      }
  }

.. _wireless-interface-intel-ax200:

Intel AX200
===========

The Intel AX200 card does not work out of the box in AP mode. You can
still put this card into AP mode using the following configuration:

.. stop_vyoslinter
.. code-block:: none

  set system wireless country-code 'us'
  set interfaces wireless wlan0 channel '1'
  set interfaces wireless wlan0 mode 'n'
  set interfaces wireless wlan0 physical-device 'phy0'
  set interfaces wireless wlan0 ssid 'VyOS'
  set interfaces wireless wlan0 type 'access-point'

.. start_vyoslinter
