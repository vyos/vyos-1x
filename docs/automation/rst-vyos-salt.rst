:lastproofread: 2023-01-16

.. _vyos-salt:

.. include:: /_include/need_improvement.txt

####
Salt
####

VyOS supports op-mode and configuration via salt_.

Without proxy it requires VyOS minion configuration
and supports op-mode data:

.. code-block:: none

  set service salt-minion id 'r14'
  set service salt-minion master '192.0.2.250'

Check salt-keys on the salt master

.. code-block:: none

  / # salt-key --list-all
  Accepted Keys:
  r11
  Denied Keys:
  Unaccepted Keys:
  r14
  Rejected Keys:

Accept minion key

.. code-block:: none

  / # salt-key --accept r14
  The following keys are going to be accepted:
  Unaccepted Keys:
  r14
  Proceed? [n/Y] y
  Key for minion r14 accepted.



Check that salt master can communicate with minions

.. code-block:: none

  / # salt '*' test.ping
  r14:
      True
  r11:
      True

At this step we can get some op-mode information from VyOS nodes:

.. code-block:: none

  / # salt '*' network.interface eth0
  r11:
      |_
        ----------
        address:
            192.0.2.11
        broadcast:
            192.0.2.255
        label:
            eth0
        netmask:
            255.255.255.0
  r14:
      |_
        ----------
        address:
            192.0.2.14
        broadcast:
            192.0.2.255
        label:
            eth0
        netmask:
            255.255.255.0


  / # salt r14 network.arp
  r14:
      ----------
      aa:bb:cc:dd:f3:db:
          192.0.2.1
      aa:bb:cc:dd:2e:80:
          203.0.113.1




Netmiko-proxy
-------------

It is possible to configure VyOS via netmiko_ proxy module.
It requires a minion with installed packet  ``python3-netmiko`` module
who has a connection to VyOS nodes. Salt-minion have to communicate
with salt master

Configuration
^^^^^^^^^^^^^

Salt master configuration:

.. code-block:: none

  / # cat /etc/salt/master
  file_roots:
    base:
      - /srv/salt/states

  pillar_roots:
    base:
      - /srv/salt/pillars

Structure of /srv/salt:

.. code-block:: none

  / # tree /srv/salt/
  /srv/salt/
  |___ pillars
  |      |__ r11-proxy.sls
  |      |__ top.sls
  |___ states
         |__ commands.txt

top.sls

.. code-block:: none

  / # cat /srv/salt/pillars/top.sls
  base:
    r11-proxy:
      - r11-proxy


r11-proxy.sls Includes parameters for connecting to salt-proxy minion

.. code-block:: none

  / # cat /srv/salt/pillars/r11-proxy.sls 
  proxy:
    proxytype: netmiko # how to connect to proxy minion, change it
    device_type: vyos  # 
    host: 192.0.2.250
    username: user
    password: secret_passwd

commands.txt

.. code-block:: none

  / # cat /srv/salt/states/commands.txt 
  set interfaces ethernet eth0 description 'WAN'
  set interfaces ethernet eth1 description 'LAN'

Check that proxy minion is alive:

.. code-block:: none

  / # salt r11-proxy test.ping
  r11-proxy:
      True
  / #

Examples
^^^^^^^^

Example of op-mode:

.. stop_vyoslinter

.. code-block:: none

  / # salt r11-proxy netmiko.send_command 'show interfaces ethernet eth0 brief' host=192.0.2.14 device_type=vyos username=vyos password=vyos
  r11-proxy:
      Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
      Interface        IP Address                        S/L  Description
      ---------        ----------                        ---  -----------
      eth0             192.0.2.14/24                     u/u  Upstream
  / #

.. start_vyoslinter

Example of configuration:

.. stop_vyoslinter

.. code-block:: none

  / # salt r11-proxy netmiko.send_config config_commands=['set interfaces ethernet eth0 description Link_to_WAN'] commit=True host=192.0.2.14 device_type=vyos username=vyos password=vyos
  r11-proxy:
      configure
      set interfaces ethernet eth0 description Link_to_WAN
      [edit]
      vyos@r14# commit
      [edit]
      vyos@r14#
  / #

.. start_vyoslinter

Example of configuration commands from the file
"/srv/salt/states/commands.txt"

.. stop_vyoslinter

.. code-block:: none

  / # salt r11-proxy netmiko.send_config config_file=salt://commands.txt commit=True host=192.0.2.11 device_type=vyos username=vyos password=vyos
  r11-proxy:
      configure
      set interfaces ethernet eth0 description 'WAN'
      [edit]
      vyos@r1# set interfaces ethernet eth1 description 'LAN'
      [edit]
      vyos@r1# commit
      [edit]
      vyos@r1#
  / #

.. start_vyoslinter

.. _salt: https://docs.saltproject.io/en/latest/contents.html
.. stop_vyoslinter
.. _netmiko: https://docs.saltproject.io/en/latest/ref/modules/all/salt.modules.netmiko_mod.html#module-salt.modules.netmiko_mod
.. start_vyoslinter