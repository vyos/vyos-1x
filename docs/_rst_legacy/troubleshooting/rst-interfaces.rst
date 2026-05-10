###############
Interface Names
###############

If you find the names of your interfaces have changed, this could be because
your MAC addresses have changed.

* For example, you have a VyOS VM with 4 Ethernet interfaces named
  eth0, eth1, eth2 and eth3. Then, you migrate your VyOS VM to a different
  host and find your interfaces now are eth4, eth5, eth6 and eth7.

  One way to fix this issue **taking control of the MAC addresses** is:

  Log into VyOS and run this command to display your interface settings.

  .. code-block:: none

     show interfaces detail

  Take note of MAC addresses.

  Now, in order to update a MAC address in the configuration, run this command
  specifying the interface name and MAC address you want.

  .. code-block:: none

     set interfaces ethernet eth0 hw-id 00:0c:29:da:a4:fe

  If it is a VM, go into the settings of the host and set the MAC address to
  the settings found in the config.boot file. You can also set the MAC to
  static if the host allows so.


* Another example could be when cloning VyOS VMs in GNS3 and you get into the
  same issue: interface names have changed.

  And **a more generic way to fix it** is just deleting every MAC address at
  the configuration file of the cloned machine. They will be correctly
  regenerated automatically.
