.. _cli:

######################
Command Line Interface
######################

The VyOS :abbr:`CLI (Command-Line Interface)` comprises an operational and a
configuration mode.

Operational Mode
################

Operational mode allows for commands to perform operational system tasks and
view system and service status, while configuration mode allows for the
modification of system configuration.

The CLI provides a built-in help system. In the CLI the ``?`` key may be used
to display available commands. The ``TAB`` key can be used to auto-complete
commands and will present the help system upon a conflict or unknown value.

For example typing ``sh`` followed by the ``TAB`` key will complete to
``show``. Pressing ``TAB`` a second time will display the possible
sub-commands of the ``show`` command.

.. code-block:: none

  vyos@vyos:~$ s[tab]
  set   show

Example showing possible show commands:

.. code-block:: none

  vyos@vyos:~$ show [tab]
  Possible completions:
    arp           Show Address Resolution Protocol (ARP) information
    bridge        Show bridging information
    cluster       Show clustering information
    configuration Show running configuration
    conntrack     Show conntrack entries in the conntrack table
    conntrack-sync
                  Show connection syncing information
    date          Show system date and time
    dhcp          Show Dynamic Host Configuration Protocol (DHCP) information
    dhcpv6        Show status related to DHCPv6
    disk          Show status of disk device
    dns           Show Domain Name Server (DNS) information
    file          Show files for a particular image
    firewall      Show firewall information
    flow-accounting
                  Show flow accounting statistics
    hardware      Show system hardware details
    history       show command history
    host          Show host information
    incoming      Show ethernet input-policy information
  : q

You can scroll up with the keys ``[Shift]+[PageUp]`` and scroll down with
``[Shift]+[PageDown]``.

When the output of a command results in more lines than can be displayed on the
terminal screen the output is paginated as indicated by a ``:`` prompt.

When viewing in page mode the following commands are available:
 * ``q`` key can be used to cancel output
 * ``space`` will scroll down one page
 * ``b`` will scroll back one page
 * ``return`` will scroll down one line
 * ``up-arrow`` and ``down-arrow`` will scroll up or down one line at a
   time respectively
 * ``left-arrow`` and ``right-arrow`` can be used to scroll left or right
   in the event that the output has lines which exceed the terminal size.

Operational mode command families
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Many operational mode commands in VyOS are placed in families such as
``show``, ``clear``, or ``reset``. Every such family has a specific
meaning to allow the user to guess how the command is going to behave —
in particular, whether it will be disruptive to the system or not.

Note that this convention was not always followed with perfect
consistency and some commands may still be in wrong families, so you
should always check the command help and documentation if you are not
sure what exactly it does.

clear
'''''

"Clear" commands are completely non-disruptive to any system operations.
Generally, they can be used freely without hesitation.

Most often their purpose is to remove or reset various debug and
diagnostic information such as system logs and packet counters.

Examples:

-  ``clear console`` — clears the screen.
-  ``clear interfaces ethernet eth0 counters`` — zeroes packet counters
   on ``eth0``.
-  ``clear log`` — deletes all system log entries.

reset
'''''

"Reset" commands can be locally-disruptive. They may, for example,
terminate a single user session or a session with a dynamic routing
protocol peer.

They should be used with caution since they may have a significant
impact on a particular users in the network.

-  ``reset pppoe-server username jsmith`` — terminate all PPPoE sessions
   from user ``jsmith``.
-  ``reset bgp 192.0.2.54`` — terminates the BGP session with neighbor
   192.0.2.54.
-  ``reset vpn ipsec site-to-site peer vpn.example.com`` — terminates
   IPsec tunnels to ``vpn.example.com``.
-  ``reset session tty1`` — terminates the TTY user session ``tty1``

restart
'''''''

"Restart" operations may disrupt an entire subsystem. Most often they
initiate a restart of a server process, which causes it to be
unavailable for a brief period and resets all the process state.

They should be used with extreme caution.

-  ``restart dhcp server`` — restarts the IPv4 DHCP server process (DHCP
   requests are not served while it is restarting).
-  ``restart ipsec`` — restarts the IPsec process (which forces all
   sessions and all IPsec process state to reset).

force
'''''

"Force" commands force the system to perform an action that it might
perform by itself at a later point.

Examples:

-  ``force arp request interface eth1 address 10.3.0.2`` — send a
   gratuitious ARP request.
-  ``force root-partition-auto-resize`` — grow the root filesystem to
   the size of the system partition (this is also done on startup, but
   this command can do it without a reboot).

execute
'''''''

"Execute" commands are for executing various diagnostic and auxilliary
actions that the system would never perform by itself.

Examples:

-  ``execute wake-on-lan interface <intf> host <MAC>`` — send a
   Wake-On-LAN packet to a host.

show
''''

"Show" commands display various system information. They may
occasionally use a pager for long outputs, that you can quit by pressing
the Q button. Their output is always finite, however.

Examples:

-  ``show system login`` — displays current system users.
-  ``show ip route`` — displays the IPv4 routing table.

monitor
'''''''

"Monitor" commands initiate various monitoring operations that may
output information continuously, until terminated with ``Ctrl-C`` or
disabled.

Examples:

-  ``monitor log`` — continuously outputs latest system logs.


Configuration Mode
##################

To enter configuration mode use the ``configure`` command:

.. code-block:: none

  vyos@vyos:~$ configure
  [edit]
  vyos@vyos:~#

.. note:: Prompt changes from ``$`` to ``#``. To exit configuration mode,
   type ``exit``.

.. code-block:: none

  vyos@vyos:~# exit
  exit
  vyos@vyos:~$

See the configuration section of this document for more information on
configuration mode.


.. _configuration-overview:

######################
Configuration Overview
######################

VyOS makes use of a unified configuration file for the entire system's
configuration: ``/config/config.boot``. This allows easy template
creation, backup, and replication of system configuration. A system can
thus also be easily cloned by simply copying the required configuration
files.

Terminology
###########

A VyOS system has three major types of configurations:

* **Active** or **running configuration** is the system configuration
  that is loaded  and currently active (used by VyOS). Any change in
  the configuration will have to be committed to belong to the
  active/running configuration.

* **Working configuration** is the one that is currently being modified
  in configuration mode. Changes made to the working configuration do
  not go into effect until the changes are committed with the
  :cfgcmd:`commit` command. At which time the working configuration will
  become the active or running configuration.

* **Saved configuration** is the one saved to a file using the
  :cfgcmd:`save` command. It allows you to keep safe a configuration for
  future uses. There can be multiple configuration files. The default or
  "boot" configuration is saved and loaded from the file
  ``/config/config.boot``.

Seeing and navigating the configuration
=======================================

.. opcmd:: show configuration

   View the current active configuration, also known as the running
   configuration, from the operational mode.

   .. code-block:: none

     vyos@vyos:~$ show configuration
     interfaces {
         ethernet eth0 {
             address dhcp
             hw-id 00:53:00:00:aa:01
         }
         loopback lo {
         }
     }
     service {
         ssh {
             port 22
         }
     }
     system {
         config-management {
             commit-revisions 20
         }
         console {
             device ttyS0 {
                 speed 9600
             }
         }
         login {
             user vyos {
                 authentication {
                     encrypted-password ****************
                 }
                 level admin
             }
         }
         ntp {
             server 0.pool.ntp.org {
             }
             server 1.pool.ntp.org {
             }
             server 2.pool.ntp.org {
             }
         }
         syslog {
             global {
                 facility all {
                     level notice
                 }
                 facility protocols {
                     level debug
                 }
             }
         }
     }

By default, the configuration is displayed in a hierarchy like the above
example, this is only one of the possible ways to display the
configuration. When the configuration is generated and the device is
configured, changes are added through a collection of :cfgcmd:`set` and
:cfgcmd:`delete` commands.

.. opcmd:: show configuration commands

   Get a collection of all the set commands required which led to the
   running configuration.

   .. code-block:: none

     vyos@vyos:~$ show configuration commands
     set interfaces ethernet eth0 address 'dhcp'
     set interfaces ethernet eth0 hw-id '00:53:dd:44:3b:0f'
     set interfaces loopback 'lo'
     set service ssh port '22'
     set system config-management commit-revisions '20'
     set system console device ttyS0 speed '9600'
     set system login user vyos authentication encrypted-password '$6$Vt68...QzF0'
     set system login user vyos level 'admin'
     set system ntp server '0.pool.ntp.org'
     set system ntp server '1.pool.ntp.org'
     set system ntp server '2.pool.ntp.org'
     set system syslog global facility all level 'notice'
     set system syslog global facility protocols level 'debug'

Both these ``show`` commands should be executed when in operational
mode, they do not work directly in configuration mode. There is a
special way on how to :ref:run_opmode_from_config_mode.

.. hint:: Use the ``show configuration commands | strip-private``
   command when you want to hide private data. You may want to do so if
   you want to share your configuration on the `forum`_.

.. _`forum`: https://forum.vyos.io

.. opcmd:: show configuration json

   View the current active configuration in JSON format.

   .. code-block:: none

     {"interfaces": {"ethernet": {"eth0": {"address": ["192.0.2.11/24", "192.0.2.35/24"], "hw-id": "52:54:00:48:a0:c6"}, "eth1": {"address": ["203.0.113.1/24"], "hw-id": "52:54:00:fc:50:0b"}}, "loopback": {"lo": {}}}, "protocols": {"static": {"route": {"0.0.0.0/0": {"next-hop": {"192.0.2.254": {}}}}}}, "service": {"ssh": {"disable-host-validation": {}}}, "system": {"config-management": {"commit-revisions": "100"}, "console": {"device": {"ttyS0": {"speed": "115200"}}}, "host-name": "r11-vyos", "login": {"user": {"vyos": {"authentication": {"encrypted-password": "$6$Vt68...F0", "plaintext-password": "", "public-keys": {"vyos@vyos": {"key": "AAAAxxx=", "type": "ssh-rsa"}}}}}}, "name-server": ["203.0.113.254"], "ntp": {"server": {"time1.vyos.net": {}, "time2.vyos.net": {}, "time3.vyos.net": {}}}, "syslog": {"global": {"facility": {"all": {"level": "info"}, "protocols": {"level": "debug"}}}}, "time-zone": "America/New_York"}}

.. opcmd:: show configuration json pretty

   View the current active configuration in readable JSON format.

   .. code-block:: none

     {
         "interfaces": {
             "ethernet": {
                 "eth0": {
                     "address": [
                         "192.0.2.11/24",
                         "192.0.2.35/24"
                     ],
                     "hw-id": "52:54:00:48:a0:c6"
                 },
                 "eth1": {
                     "address": [
                         "203.0.113.1/24"
                     ],
                     "hw-id": "52:54:00:fc:50:0b"
                 }
             },
             "loopback": {
                 "lo": {}
             }
         },
         "protocols": {
             "static": {
                 "route": {
                     "0.0.0.0/0": {
                         "next-hop": {
                             "192.0.2.254": {}
                         }
                     }
                 }
             }
         },
         "service": {
             "ssh": {
                 "disable-host-validation": {}
             }
         },
         "system": {
             "config-management": {
                 "commit-revisions": "100"
             },
             "console": {
                 "device": {
                     "ttyS0": {
                         "speed": "115200"
                     }
                 }
             },
             "host-name": "r11-vyos",
             "login": {
                 "user": {
                     "vyos": {
                         "authentication": {
                             "encrypted-password": "$6$Vt68...F0",
                             "plaintext-password": "",
                             "public-keys": {
                                 "vyos@vyos": {
                                     "key": "AAAAxxx=",
                                     "type": "ssh-rsa"
                                 }
                             }
                         }
                     }
                 }
             },
             "name-server": [
                 "203.0.113.254"
             ],
             "ntp": {
                 "server": {
                     "time1.vyos.net": {},
                     "time2.vyos.net": {},
                     "time3.vyos.net": {}
                }
             },
             "syslog": {
                 "global": {
                     "facility": {
                         "all": {
                             "level": "info"
                         },
                         "protocols": {
                             "level": "debug"
                         }
                     }
                 }
             },
             "time-zone": "America/New_York"
         }
     }


The config mode
---------------

When entering the configuration mode you are navigating inside a tree
structure, to enter configuration mode enter the command
:opcmd:`configure` when in operational mode.

.. code-block:: none

  vyos@vyos$ configure
  [edit]
  vyos@vyos#


.. note:: When going into configuration mode, prompt changes from
   ``$`` to ``#``.


All commands executed here are relative to the configuration level you
have entered. You can do everything from the top level, but commands
will be quite lengthy when manually typing them.

The current hierarchy level can be changed by the :cfgcmd:`edit`
command.

.. code-block:: none

  [edit]
  vyos@vyos# edit interfaces ethernet eth0

  [edit interfaces ethernet eth0]
  vyos@vyos#

You are now in a sublevel relative to ``interfaces ethernet eth0``, all
commands executed from this point on are relative to this sublevel. Use
either the :cfgcmd:`top` or :cfgcmd:`exit` command to go back to the top
of the hierarchy. You can also use the :cfgcmd:`up` command to move only
one level up at a time.

.. cfgcmd:: show

The :cfgcmd:`show` command within configuration mode will show the
working configuration indicating line changes with ``+`` for additions,
``>`` for replacements and ``-`` for deletions.

**Example:**

.. code-block:: none

 vyos@vyos:~$ configure
 [edit]
 vyos@vyos# show interfaces
  ethernet eth0 {
      description MY_OLD_DESCRIPTION
      disable
      hw-id 00:53:dd:44:3b:03
  }
  loopback lo {
  }
 [edit]
 vyos@vyos# set interfaces ethernet eth0 address dhcp
 [edit]
 vyos@vyos# set interfaces ethernet eth0 description MY_NEW_DESCRIPTION
 [edit]
 vyos@vyos# delete interfaces ethernet eth0 disable
 [edit]
 vyos@vyos# show interfaces
  ethernet eth0 {
 +    address dhcp
 >    description MY_NEW_DESCRIPTION
 -    disable
      hw-id 00:53:dd:44:3b:03
  }
  loopback lo {
  }

It is also possible to display all :cfgcmd:`set` commands within configuration
mode using :cfgcmd:`show | commands`

.. code-block:: none

  vyos@vyos# show interfaces ethernet eth0 | commands
  set address dhcp
  set hw-id 00:53:ad:44:3b:03

These commands are also relative to the level you are inside and only
relevant configuration blocks will be displayed when entering a
sub-level.

.. code-block:: none

  [edit interfaces ethernet eth0]
  vyos@vyos# show
   address dhcp
   hw-id 00:53:ad:44:3b:03

Exiting from the configuration mode is done via the :cfgcmd:`exit`
command from the top level, executing :cfgcmd:`exit` from within a
sub-level takes you back to the top level.

.. code-block:: none

  [edit interfaces ethernet eth0]
  vyos@vyos# exit
  [edit]
  vyos@vyos# exit
  Warning: configuration changes have not been saved.


Editing the configuration
=========================

The configuration can be edited by the use of :cfgcmd:`set` and
:cfgcmd:`delete` commands from within configuration mode.

.. cfgcmd:: set

   Use this command to set the value of a parameter or to create a new
   element.

Configuration commands are flattened from the tree into 'one-liner'
commands shown in :opcmd:`show configuration commands` from operation
mode. Commands are relative to the level where they are executed and all
redundant information from the current level is removed from the command
entered.

.. code-block:: none

  [edit]
  vyos@vyos# set interface ethernet eth0 address 192.0.2.100/24


.. code-block:: none

  [edit interfaces ethernet eth0]
  vyos@vyos# set address 203.0.113.6/24


These two commands above are essentially the same, just executed from
different levels in the hierarchy.

.. cfgcmd:: delete

   To delete a configuration entry use the :cfgcmd:`delete` command,
   this also deletes all sub-levels under the current level you've
   specified in the :cfgcmd:`delete` command. Deleting an entry will
   also result in the element reverting back to its default value if one
   exists.

   .. code-block:: none

     [edit interfaces ethernet eth0]
     vyos@vyos# delete address 192.0.2.100/24

.. cfgcmd:: commit

  Any change you do on the configuration, will not take effect until
  committed using the :cfgcmd:`commit` command in configuration mode.

  .. code-block:: none

    vyos@vyos# commit
    [edit]
    vyos@vyos# exit
    Warning: configuration changes have not been saved.
    vyos@vyos:~$

.. hint:: You can specify a commit message with
  :cfgcmd:`commit comment <message>`.

.. _save:

.. cfgcmd:: save

   Use this command to preserve configuration changes upon reboot. By
   default it is stored at */config/config.boot*. In the case you want
   to store the configuration file somewhere else, you can add a local
   path, a SCP address, a FTP address or a TFTP address.

   .. code-block:: none

     vyos@vyos# save
     Saving configuration to '/config/config.boot'...
     Done

   .. code-block:: none

     vyos@vyos# save [tab]
     Possible completions:
       <Enter>       Save to system config file
       <file>        Save to file on local machine
       scp://<user>:<passwd>@<host>:/<file> Save to file on remote machine
       ftp://<user>:<passwd>@<host>/<file> Save to file on remote machine
       tftp://<host>/<file>      Save to file on remote machine
     vyos@vyos# save tftp://192.168.0.100/vyos-test.config.boot
     Saving configuration to 'tftp://192.168.0.100/vyos-test.config.boot'...
     ######################################################################## 100.0%
     Done

.. cfgcmd:: exit [discard]

   Configuration mode can not be exited while uncommitted changes exist.
   To exit configuration mode without applying changes, the
   :cfgcmd:`exit discard` command must be used.

   All changes in the working config will thus be lost.

   .. code-block:: none

     vyos@vyos# exit
     Cannot exit: configuration modified.
     Use 'exit discard' to discard the changes and exit.
     [edit]
     vyos@vyos# exit discard


.. cfgcmd:: commit-confirm <minutes>

   Use this command to temporarily commit your changes and set the
   number of minutes available for confirmation. ``confirm`` must
   be entered within those minutes, otherwise the system will revert
   into a previous configuration. The default value is 10 minutes.

   The definition of 'revert' and 'a previous configuration' depends on
   the setting:

   .. code-block:: none

     vyos@vyos# set system config-management commit-confirm action
     Possible completions:
     reload               Reload previous configuration if not confirmed
     reboot               Reboot to saved configuration if not confirmed (default)

   Note that 'reload' loads the most recent completed configuration and does
   not require a reboot.

   What if you are doing something dangerous? Suppose you want to setup
   a firewall, and you are not sure there are no mistakes that will lock
   you out of your system. You can use confirmed commit. If you issue
   the ``commit-confirm`` command, your changes will be committed, and if
   you don't issue  the ``confirm`` command in 10 minutes, your
   system will reboot into previous config revision.

   .. code-block:: none

      vyos@router# set firewall interface eth0 local name FromWorld
      vyos@router# commit-confirm
      commit confirm will be automatically reboot in 10 minutes unless confirmed
      Proceed? [confirm]y
      [edit]
      vyos@router# confirm
      [edit]

.. cfgcmd:: copy

   Copy a configuration element.

   You can copy and remove configuration subtrees. Suppose you set up a
   firewall ruleset ``FromWorld`` with one rule that allows traffic from
   specific subnet. Now you want to setup a similar rule, but for
   different subnet. Change your edit level to
   ``firewall name FromWorld`` and use ``copy rule 10 to rule 20``, then
   modify rule 20.


   .. code-block:: none

      vyos@router# show firewall name FromWorld
       default-action drop
       rule 10 {
           action accept
           source {
               address 203.0.113.0/24
           }
       }
      [edit]
      vyos@router# edit firewall name FromWorld
      [edit firewall name FromWorld]
      vyos@router# copy rule 10 to rule 20
      [edit firewall name FromWorld]
      vyos@router# set rule 20 source address 198.51.100.0/24
      [edit firewall name FromWorld]
      vyos@router# commit
      [edit firewall name FromWorld]


.. cfgcmd:: rename

   Rename a configuration element.

   You can also rename config subtrees:

   .. code-block:: none

      vyos@router# rename rule 10 to rule 5
      [edit firewall name FromWorld]
      vyos@router# commit
      [edit firewall name FromWorld]

   Note that ``show`` command respects your edit level and from this
   level you can view the modified firewall ruleset with just ``show``
   with no parameters.

   .. code-block:: none

      vyos@router# show
       default-action drop
       rule 5 {
           action accept
           source {
               address 203.0.113.0/24
           }
       }
       rule 20 {
           action accept
           source {
               address 198.51.100.0/24
           }
       }


.. cfgcmd:: comment <config node> "comment text"

   Add comment as an annotation to a configuration node.

   The ``comment`` command allows you to insert a comment above the
   ``<config node>`` configuration section. When shown, comments are
   enclosed with ``/*`` and ``*/`` as open/close delimiters. Comments
   need to be committed, just like other config changes.

   To remove an existing comment from your current configuration,
   specify an empty string enclosed in double quote marks (``""``) as
   the comment text.

   Example:

   .. code-block:: none

     vyos@vyos# comment firewall all-ping "Yes I know this VyOS is cool"
     vyos@vyos# commit
     vyos@vyos# show
      firewall {
          /* Yes I know this VyOS is cool */
          all-ping enable
          broadcast-ping disable
          ...
      }

   .. note:: An important thing to note is that since the comment is
      added on top of the section, it will not appear if the ``show
      <section>`` command is used. With the above example, the `show
      firewall` command would return starting after the ``firewall
      {`` line, hiding the comment.

.. _run_opmode_from_config_mode:

Access opmode from config mode
==============================

When inside configuration mode you are not directly able to execute
operational commands.

.. cfgcmd:: run

  Access to these commands are possible through the use of the
  ``run [command]`` command. From this command you will have access to
  everything accessible from operational mode.

  Command completion and syntax help with ``?`` and ``[tab]`` will also
  work.

  .. code-block:: none

    [edit]
    vyos@vyos# run show interfaces
    Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
    Interface        IP Address                        S/L  Description
    ---------        ----------                        ---  -----------
    eth0             0.0.0.0/0                         u/u

Managing configurations
=======================

VyOS comes with an integrated versioning system for the system
configuration. It automatically maintains a backup of every previous
configuration which has been committed to the system. The configurations
are versioned locally for rollback but they can also be stored on a
remote host for archiving/backup reasons.

Local Archive
-------------

Revisions are stored on disk. You can view, compare and rollback them to
any previous revisions if something goes wrong.

.. opcmd:: show system commit

   View all existing revisions on the local system.

   .. code-block:: none

     vyos@vyos:~$ show system commit
     0   2015-03-30 08:53:03 by vyos via cli
     1   2015-03-30 08:52:20 by vyos via cli
     2   2015-03-26 21:26:01 by root via boot-config-loader
     3   2015-03-26 20:43:18 by root via boot-config-loader
     4   2015-03-25 11:06:14 by root via boot-config-loader
     5   2015-03-25 01:04:28 by root via boot-config-loader
     6   2015-03-25 00:16:47 by vyos via cli
     7   2015-03-24 23:43:45 by root via boot-config-loader


.. cfgcmd:: set system config-management commit-revisions <N>

   You can specify the number of revisions stored on disk. N can be in
   the range of 0 - 65535. When the number of revisions exceeds the
   configured value, the oldest revision is removed. The default setting
   for this value is to store 100 revisions locally.


Compare configurations
----------------------

VyOS lets you compare different configurations.

.. cfgcmd:: compare <saved | N> <M>

   Use this command to spot what the differences are between different
   configurations.

   .. code-block:: none

     vyos@vyos# compare [tab]
     Possible completions:
       <Enter>  Compare working & active configurations
       saved        Compare working & saved configurations
       <N>      Compare working with revision N
       <N> <M>  Compare revision N with M
       Revisions:
         0     2013-12-17 20:01:37 root by boot-config-loader
         1     2013-12-13 15:59:31 root by boot-config-loader
         2     2013-12-12 21:56:22 vyos by cli
         3     2013-12-12 21:55:11 vyos by cli
         4     2013-12-12 21:27:54 vyos by cli
         5     2013-12-12 21:23:29 vyos by cli
         6     2013-12-12 21:13:59 root by boot-config-loader
         7     2013-12-12 16:25:19 vyos by cli
         8     2013-12-12 15:44:36 vyos by cli
         9     2013-12-12 15:42:07 root by boot-config-loader
         10   2013-12-12 15:42:06 root by init

   The command :cfgcmd:`compare` allows you to compare different type of
   configurations. It also lets you compare different revisions through
   the :cfgcmd:`compare N M` command, where N and M are revision
   numbers. The output will describe how the configuration N is when
   compared to M indicating with a plus sign (``+``) the additional
   parts N has when compared to M, and indicating with a minus sign
   (``-``) the lacking parts N misses when compared to M.

   .. code-block:: none

     vyos@vyos# compare 0 6
     [edit interfaces]
     +dummy dum1 {
     +    address 10.189.0.1/31
     +}
     [edit interfaces ethernet eth0]
     +vif 99 {
     +    address 10.199.0.1/31
     +}
     -vif 900 {
     -    address 192.0.2.4/24
     -}


.. opcmd:: show system commit diff <number>

   Show commit revision difference.


The command above also lets you see the difference between two commits.
By default the difference with the running config is shown.

.. code-block:: none

   vyos@router# run show system commit diff 4
   [edit system]
   +ipv6 {
   +    disable-forwarding
   +}

This means four commits ago we did ``set system ipv6 disable-forwarding``.


Rollback Changes
----------------

You can rollback configuration changes using the rollback command. This
will apply the selected revision and trigger a system reboot.

.. cfgcmd:: rollback <N>

   Rollback to revision N (currently requires reboot)

   .. code-block:: none

     vyos@vyos# compare 1
     [edit system]
     >host-name vyos-1
     [edit]

     vyos@vyos# rollback 1
     Proceed with reboot? [confirm][y]
     Broadcast message from root@vyos-1 (pts/0) (Tue Dec 17 21:07:45 2013):
     The system is going down for reboot NOW!

Remote Archive
--------------

VyOS can upload the configuration to a remote location after each call
to :cfgcmd:`commit`. You will have to set the commit-archive location.
TFTP, FTP, SCP and SFTP servers are supported. Every time a
:cfgcmd:`commit` is successful the ``config.boot`` file will be copied
to the defined destination(s). The filename used on the remote host will
be ``config.boot-hostname.YYYYMMDD_HHMMSS``.

.. cfgcmd:: set system config-management commit-archive location <URI>

  Specify remote location of commit archive as any of the below
  :abbr:`URI (Uniform Resource Identifier)`

  * ``http://<user>:<passwd>@<host>:/<dir>``
  * ``https://<user>:<passwd>@<host>:/<dir>``
  * ``ftp://<user>:<passwd>@<host>/<dir>``
  * ``sftp://<user>:<passwd>@<host>/<dir>``
  * ``scp://<user>:<passwd>@<host>:/<dir>``
  * ``tftp://<host>/<dir>``
  * ``git+https://<user>:<passwd>@<host>/<path>``

  Since username and password are part of the URI, they need to be
  properly url encoded if containing special characters.

  .. note:: The number of revisions don't affect the commit-archive.

  .. note:: When using Git as destination for the commit archive the
     ``source-address`` CLI option has no effect.

  .. note:: You may find VyOS not allowing the secure connection because
     it cannot verify the legitimacy of the remote server. You can use
     the workaround below to quickly add the remote host's SSH
     fingerprint to your ``~/.ssh/known_hosts`` file:

  .. code-block:: none

    vyos@vyos# ssh-keyscan <host> >> ~/.ssh/known_hosts

.. cfgcmd:: set system config-management commit-archive vrf <name>

  Specify name of the :abbr:`VRF (Virtual Routing and Forwarding)` instance
  used to upload the configuration to the remote system.

Saving and loading manually
---------------------------

You can use the ``save`` and ``load`` commands if you want to manually
manage specific configuration files.

When using the save_ command, you can add a specific location where
to store your configuration file. And, when needed it, you will be able
to load it with the ``load`` command:

.. cfgcmd:: load <URI>

   Use this command to load a configuration which will replace the
   running configuration. Define the location of the configuration file
   to be loaded. You can use a path to a local file, an SCP address, an
   SFTP address, an FTP address, an HTTP address, an HTTPS address or a
   TFTP address.

  .. code-block:: none

     vyos@vyos# load
     Possible completions:
       <Enter>                      Load from system config file
       <file>                       Load from file on local machine
       scp://<user>:<passwd>@<host>:/<file> Load from file on remote machine
       sftp://<user>:<passwd>@<host>/<file> Load from file on remote machine
       ftp://<user>:<passwd>@<host>/<file>  Load from file on remote machine
       http://<host>/<file>         Load from file on remote machine
       https://<host>/<file>            Load from file on remote machine
       tftp://<host>/<file>         Load from file on remote machine



Restore Default
---------------

In the case you want to completely delete your configuration and restore
the default one, you can enter the following command in configuration
mode:

.. code-block:: none

  load /opt/vyatta/etc/config.boot.default

You will be asked if you want to continue. If you accept, you will have
to use :cfgcmd:`commit` if you want to make the changes active.

Then you may want to :cfgcmd:`save` in order to delete the saved
configuration too.

.. note:: If you are remotely connected, you will lose your connection.
   You may want to copy first the config, edit it to ensure
   connectivity, and load the edited config.
