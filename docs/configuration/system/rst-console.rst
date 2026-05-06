.. _serial-console:

##############
Serial Console
##############

For the average user a serial console has no advantage over a console offered
by a directly attached keyboard and screen. Serial consoles are much slower,
taking up to a second to fill a 80 column by 24 line screen. Serial consoles
generally only support non-proportional ASCII text, with limited support for
languages other than English.

There are some scenarios where serial consoles are useful. System administration
of remote computers is usually done using :ref:`ssh`, but there are times when
access to the console is the only way to diagnose and correct software failures.
Major upgrades to the installed distribution may also require console access.


.. cfgcmd:: set system console device <device>

   Defines the specified device as a system console. Available console devices
   can be (see completion helper):

   * ``ttySN`` - Serial device name
   * ``ttyAMAN``- Serial device name for some arm64 systems
   * ``ttyUSBX`` - USB Serial device name
   * ``hvc0`` - Xen console

.. cfgcmd:: set system console device <device> kernel

   When set, the selected serial console is used as the kernel boot console.
   When removed, the kernel boot console falls back to tty0.

   .. note:: Only one serial console can carry the ``kernel`` option.
     When VyOS is installed via serial console, this option is set automatically
     for the serial interface used during installation; usually ``ttyS0`` or
     ``ttyAMA0``.

.. cfgcmd:: set system console device <device> speed <speed>

   The speed (baudrate) of the console device. Supported values are:

   * ``1200`` - 1200 bps
   * ``2400`` - 2400 bps
   * ``4800`` - 4800 bps
   * ``9600`` - 9600 bps
   * ``19200`` - 19,200 bps
   * ``38400`` - 38,400 bps (default for Xen console)
   * ``57600`` - 57,600 bps
   * ``115200`` - 115,200 bps (default for serial console)

   .. note:: If you use USB to serial converters for connecting to your VyOS
     appliance please note that most of them use software emulation without flow
     control. This means you should start with a common baud rate (most likely
     9600 baud) as otherwise you probably can not connect to the device using
     high speed baud rates as your serial converter simply can not process this
     data rate.
