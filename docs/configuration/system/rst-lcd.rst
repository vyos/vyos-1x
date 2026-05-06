.. _system-display:

####################
System Display (LCD)
####################

The system LCD :abbr:`LCD (Liquid-crystal display)` option is for users running
VyOS on hardware that features an LCD display. This is typically a small display
built in an 19 inch rack-mountable appliance. Those displays are used to show
runtime data.

To configure your LCD display you must first identify the used hardware, and
connectivity of the display to your system. This can be any serial port
(`ttySxx`) or serial via USB or even old parallel port interfaces.

Configuration
=============

.. cfgcmd:: set system lcd device <device>

   This is the name of the physical interface used to connect to your LCD
   display. Tab completion is supported and it will list you all available
   serial interface.

   For serial via USB port information please refor to: :ref:`hardware_usb`.

.. cfgcmd:: set system lcd model <model>

   This is the LCD model used in your system.

   At the time of this writing the following displays are supported:

   * Crystalfontz CFA-533

   * Crystalfontz CFA-631

   * Crystalfontz CFA-633

   * Crystalfontz CFA-635

   .. note:: We can't support all displays from the beginning. If your display
      type is missing, please create a feature request via Phabricator_.

.. include:: /_include/common-references.txt

