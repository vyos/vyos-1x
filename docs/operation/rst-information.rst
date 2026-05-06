:lastproofread: 2025-11-19

.. _information:

##################
System Information
##################

VyOS features a rich set of operational level commands to retrieve arbitrary
information about your running system. For more information on the VyOS command
line interface (CLI), see :ref:`cli`.

########
Hardware
########

.. _hardware_usb:

USB
===

In the past, serial interfaces were defined as ``ttySx`` and ``ttyUSBx`` where
``x`` was the instance number. However, the mapping of USB-based
serial interfaces can change from one system boot to another, depending on
which driver the operating system loads first.
This inconsistency can be problematic when you
use multiple serial interfaces.
For example, both console-server connections and a serial-backed
:ref:`wwan-interface`.

To address this issue, and because many low-cost USB-to-serial converters
do not have a programmed serial number, VyOS now identifies USB-to-serial
interfaces by the USB root bridge and the bus they connect to.
This approach is similar to the network interface naming conventions used in
recent Linux distributions.


.. opcmd:: show hardware usb

  Retrieve a tree-like representation of all connected USB devices.

  .. note:: If a device is unplugged and plugged in again, it is assigned a new
    ``Port``, ``Dev``, and ``If``.

.. stop_vyoslinter

  .. code-block:: none

    vyos@vyos:~$ show hardware usb
    /:  Bus 03.Port 1: Dev 1, Class=root_hub, Driver=ehci-pci/2p, 480M
        |__ Port 1: Dev 2, If 0, Class=Hub, Driver=hub/4p, 480M
            |__ Port 3: Dev 4, If 0, Class=Vendor Specific Class, Driver=qcserial, 480M
            |__ Port 3: Dev 4, If 2, Class=Vendor Specific Class, Driver=qcserial, 480M
            |__ Port 3: Dev 4, If 3, Class=Vendor Specific Class, Driver=qcserial, 480M
            |__ Port 3: Dev 4, If 8, Class=Vendor Specific Class, Driver=qmi_wwan, 480M
    /:  Bus 02.Port 1: Dev 1, Class=root_hub, Driver=xhci_hcd/2p, 5000M
    /:  Bus 01.Port 1: Dev 1, Class=root_hub, Driver=xhci_hcd/2p, 480M
        |__ Port 1: Dev 2, If 0, Class=Vendor Specific Class, Driver=pl2303, 12M
        |__ Port 2: Dev 3, If 0, Class=Hub, Driver=hub/4p, 480M
            |__ Port 4: Dev 5, If 2, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
            |__ Port 4: Dev 5, If 0, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
            |__ Port 4: Dev 5, If 3, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
            |__ Port 4: Dev 5, If 1, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
            |__ Port 3: Dev 4, If 0, Class=Hub, Driver=hub/4p, 480M
                |__ Port 3: Dev 6, If 0, Class=Hub, Driver=hub/4p, 480M
                    |__ Port 4: Dev 8, If 2, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
                    |__ Port 4: Dev 8, If 0, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
                    |__ Port 4: Dev 8, If 3, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
                    |__ Port 4: Dev 8, If 1, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
                |__ Port 4: Dev 7, If 3, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
                |__ Port 4: Dev 7, If 1, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
                |__ Port 4: Dev 7, If 2, Class=Vendor Specific Class, Driver=ftdi_sio, 480M
                |__ Port 4: Dev 7, If 0, Class=Vendor Specific Class, Driver=ftdi_sio, 480M

.. start_vyoslinter


.. opcmd:: show hardware usb serial

  Retrieve a list and description of all connected USB serial devices. The
  device name displayed, (for example ``usb0b2.4p1.0``), can be used
  directly when accessing the serial console as console-server device.

.. stop_vyoslinter

  .. code-block:: none

    vyos@vyos$ show hardware usb serial
    Device           Model               Vendor
    ------           ------              ------
    usb0b1.3p1.0     MC7710              Sierra Wireless, Inc.
    usb0b1.3p1.2     MC7710              Sierra Wireless, Inc.
    usb0b1.3p1.3     MC7710              Sierra Wireless, Inc.
    usb0b1p1.0       USB-Serial_Controller_D Prolific Technology, Inc.
    usb0b2.3.3.4p1.0 Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.3.3.4p1.1 Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.3.3.4p1.2 Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.3.3.4p1.3 Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.3.4p1.0   Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.3.4p1.1   Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.3.4p1.2   Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.3.4p1.3   Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.4p1.0     Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.4p1.1     Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.4p1.2     Quad_RS232-HS       Future Technology Devices International, Ltd
    usb0b2.4p1.3     Quad_RS232-HS       Future Technology Devices International, Ltd

.. start_vyoslinter

.. _information_version:

########
Version
########

.. opcmd:: show version

  Return the currently running VyOS version and build information. This
  includes the name of the release train, e.g., ``sagitta`` on VyOS 1.4,
  and ``circinus`` on VyOS 1.5.

  .. code-block:: none
  
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

.. opcmd:: show version kernel

  Return the version number of the currently running Linux kernel.

  .. code-block:: none

    vyos@vyos:~$ show version kernel
    5.10.46-amd64-vyos

.. opcmd:: show version frr

  Return the version number of FRR (Free Range Routing - https://frrouting.org/)
  used in this release. This is the routing control plane and a successor to GNU
  Zebra and Quagga.

    .. code-block:: none

      vyos@vyos:~$ show version frr
      FRRouting 7.5.1-20210625-00-gf07d935a2 (vyos).
      Copyright 1996-2005 Kunihiro Ishiguro, et al.

