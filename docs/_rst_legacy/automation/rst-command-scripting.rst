:lastproofread: 2026-03-16

.. _command-scripting:

Command scripting
=================

VyOS supports executing configuration and operational commands non-interactively
from shell scripts.

To include VyOS-specific functions and aliases, source the 
``/opt/vyatta/etc/functions/script-template`` file at the beginning of your 
script.

.. code-block:: none

  #!/bin/vbash
  source /opt/vyatta/etc/functions/script-template
  exit

Script execute permissions
--------------------------

Simply placing script files in ``/config/scripts/`` does not mean the system 
can execute them.

To make your scripts executable, grant them **execute permissions**. Use the 
following command:

.. code-block:: none

  chmod +x /config/scripts/script-name.sh

Run configuration commands
--------------------------

In scripts, present configuration commands as in a standard configuration 
session. 

For example, to disable a BGP peer during a VRRP transition to the backup 
state, use the following syntax:

.. code-block:: none

  #!/bin/vbash
  source /opt/vyatta/etc/functions/script-template
  configure
  set protocols bgp system-as 65536
  set protocols bgp neighbor 192.168.2.1 shutdown
  commit
  exit

Run operational commands
------------------------

In scripts, **always** prefix operational commands with ``run``.

.. code-block:: none

  #!/bin/vbash
  source /opt/vyatta/etc/functions/script-template
  run show interfaces
  exit

Run commands remotely
---------------------

You can execute multiple **operational commands** on a remote VyOS system by 
passing a script block over SSH.

.. code-block:: none

  ssh 192.0.2.1 'vbash -s' <<EOF
  source /opt/vyatta/etc/functions/script-template
  run show interfaces
  exit
  EOF

Example output:

.. code-block:: none

  Welcome to VyOS
  Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
  Interface        IP Address                        S/L  Description
  ---------        ----------                        ---  -----------
  eth0             192.0.2.1/24                      u/u
  lo               127.0.0.1/8                       u/u
                  ::1/128


Other script languages
----------------------

If you use a scripting language other than bash, configure your script to 
output the relevant commands, and then source that output into a bash script.

The following example demonstrates this two-step process:

.. code-block:: python

  #!/usr/bin/env python3
  print("delete firewall group address-group somehosts")
  print("set firewall group address-group somehosts address '192.0.2.3'")
  print("set firewall group address-group somehosts address '203.0.113.55'")


.. code-block:: none

  #!/bin/vbash
  source /opt/vyatta/etc/functions/script-template
  configure
  source <(/config/scripts/setfirewallgroup.py)
  commit


Execute configuration scripts
-------------------------------

In Linux, it is common practice to prefix system commands with ``sudo``.

In VyOS, if you prefix a script that modifies the configuration with ``sudo`` 
(see the code snippet below), subsequent manual configuration changes fail with 
the ``Set failed`` error. Recovery requires a system reboot.

.. code-block:: none

  sudo ./myscript.sh # Modifies config
  configure
  set ... # Any configuration parameter

To avoid this issue, run scripts under the ``vyattacfg`` group using the ``sg`` 
command:

.. code-block:: none

  sg vyattacfg -c ./myscript.sh

To ensure the script is executed under the ``vyattacfg`` group, safeguard it as 
follows:

.. code-block:: none

  if [ "$(id -g -n)" != 'vyattacfg' ] ; then
      exec sg vyattacfg -c "/bin/vbash $(readlink -f $0) $@"
  fi

Executing pre-hooks/post-hooks scripts
--------------------------------------

VyOS allows you to run custom scripts **before** and **after** each commit.

Place your custom scripts in the following default directories:

.. code-block:: none

  /config/scripts/commit/pre-hooks.d   - Directory with scripts that run before
                                         each commit.

  /config/scripts/commit/post-hooks.d  - Directory with scripts that run after
                                         each commit.

Scripts run in alphabetical order. Filenames must consist only of ASCII letters 
(upper and lowercase), digits (0-9), underscores (_), and hyphens (-). No other 
characters are allowed.

.. note:: Custom scripts are executed **without** root privileges. Prefix 
   specific commands with ``sudo`` in your script when required.

The following example shows the output after executing a post-hook script 
that runs the ``show interfaces`` command:

.. code-block:: none

  vyos@vyos# set interfaces ethernet eth1  address 192.0.2.3/24
  vyos@vyos# commit
  Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
  Interface        IP Address                        S/L  Description
  ---------        ----------                        ---  -----------
  eth0             198.51.100.10/24                  u/u
  eth1             192.0.2.3/24                      u/u
  eth2             -                                 u/u
  eth3             -                                 u/u
  lo               203.0.113.5/24                    u/u

Preconfig script on boot
------------------------

VyOS runs ``/config/scripts/vyos-preconfig-bootup.script`` at boot, **before** 
the system configuration is applied. 

Use this script to apply **pre-configuration** workarounds for unresolved bugs 
or enhancements not yet available in VyOS.

The default script contains the following:

.. code-block:: none

  #!/bin/sh
  # This script is executed at boot time before VyOS configuration is applied.
  # Any modifications required to work around unfixed bugs or use
  # services not available through the VyOS CLI system can be placed here.


Postconfig script on boot
-------------------------

VyOS runs ``/config/scripts/vyos-postconfig-bootup.script`` at boot, **after** 
the system configuration is applied.

Use this script to apply **post-configuration** workarounds for unresolved bugs 
or enhancements not yet available in VyOS.

The default script contains the following:

.. code-block:: none

  #!/bin/sh
  # This script is executed at boot time after VyOS configuration is fully
  # applied. Any modifications required to work around unfixed bugs or use
  # services not available through the VyOS CLI system can be placed here.

.. warning:: For configuration or upgrade management issues, modify this script 
   only as a last resort. Always try CLI-based solutions first.
