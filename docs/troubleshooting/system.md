# System Information

(boot-steps)=

## Boot Steps

VyOS 1.2 uses [Debian Jessie] as the base Linux operating system. Jessie was
the first version of Debian that uses [systemd] as the default init system.

These are the boot steps for VyOS 1.2

1. The BIOS loads Grub (or isolinux for the Live CD)
2. Grub then starts the Linux boot and loads the Linux Kernel `/boot/vmlinuz`
3. Kernel Launches Systemd `/lib/systemd/systemd`
4. Systemd loads the VyOS service file
   `/lib/systemd/system/vyos-router.service`
5. The service file launches the VyOS router init script
   `/usr/libexec/vyos/init/vyos-router` - this is part of the [vyatta-cfg]
   Debian package

> 1. Starts [FRR] - successor to [GNU Zebra] and [Quagga]
> 2. Initialises the boot configuration file - copies over
>    `config.boot.default` if there is no configuration
> 3. Runs the configuration migration, if the configuration is for an older
>    version of VyOS
> 4. Runs The pre-config script, if there is one
>    `/config/scripts/vyos-preconfig-bootup.script`
> 5. If the config file was upgraded, runs any post upgrade scripts
>    `/config/scripts/post-upgrade.d`
> 6. Starts `rl-system` and `firewall`
> 7. Mounts the `/boot` partition
> 8. The boot configuration file is then applied by `/opt/vyatta/sbin/vyatta-boot-config-loader/opt/vyatta/etc/config/config.boot`
>
> > 1. The config loader script writes log entries to
> >    `/var/log/vyatta-config-loader.log`
>
> 09. Runs `telinit q` to tell the init system to reload `/etc/inittab`
> 10. Finally it runs the post-config script
>     `/config/scripts/vyos-postconfig-bootup.script`

[debian jessie]: https://www.debian.org/releases/jessie/
[frr]: https://frrouting.org/
[gnu zebra]: https://www.gnu.org/software/zebra/
[pcap filter expressions]: http://www.tcpdump.org/manpages/pcap-filter.7.html
[quagga]: https://www.quagga.net/
[systemd]: https://freedesktop.org/wiki/Software/systemd/
[tshark]: https://www.wireshark.org/docs/man-pages/tshark.html
[vyatta-cfg]: https://github.com/vyos/vyatta-cfg
