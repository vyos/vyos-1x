##################
System Information
##################

.. _boot-steps:

**********
Boot Steps
**********

VyOS 1.2 uses `Debian Jessie`_ as the base Linux operating system. Jessie was
the first version of Debian that uses systemd_ as the default init system.

These are the boot steps for VyOS 1.2

1. The BIOS loads Grub (or isolinux for the Live CD)
2. Grub then starts the Linux boot and loads the Linux Kernel ``/boot/vmlinuz``
3. Kernel Launches Systemd ``/lib/systemd/systemd``
4. Systemd loads the VyOS service file
   ``/lib/systemd/system/vyos-router.service``
5. The service file launches the VyOS router init script
   ``/usr/libexec/vyos/init/vyos-router`` - this is part of the vyatta-cfg_
   Debian package

  1. Starts FRR_ - successor to `GNU Zebra`_ and Quagga_

  2. Initialises the boot configuration file - copies over
     ``config.boot.default`` if there is no configuration
  3. Runs the configuration migration, if the configuration is for an older
     version of VyOS
  4. Runs The pre-config script, if there is one
     ``/config/scripts/vyos-preconfig-bootup.script``
  5. If the config file was upgraded, runs any post upgrade scripts
     ``/config/scripts/post-upgrade.d``
  6. Starts ``rl-system`` and ``firewall``
  7. Mounts the ``/boot`` partition
  8. The boot configuration file is then applied by ``/opt/vyatta/sbin/vyatta-boot-config-loader/opt/vyatta/etc/config/config.boot``

    1. The config loader script writes log entries to
       ``/var/log/vyatta-config-loader.log``

  9. Runs ``telinit q`` to tell the init system to reload ``/etc/inittab``
  10. Finally it runs the post-config script
      ``/config/scripts/vyos-postconfig-bootup.script``

.. stop_vyoslinter

.. _Quagga: https://www.quagga.net/
.. _`GNU Zebra`: https://www.gnu.org/software/zebra/
.. _FRR: https://frrouting.org/
.. _vyatta-cfg: https://github.com/vyos/vyatta-cfg
.. _systemd: https://freedesktop.org/wiki/Software/systemd/
.. _`Debian Jessie`: https://www.debian.org/releases/jessie/
.. _tshark: https://www.wireshark.org/docs/man-pages/tshark.html
.. _`PCAP filter expressions`: http://www.tcpdump.org/manpages/pcap-filter.7.html

.. start_vyoslinter
