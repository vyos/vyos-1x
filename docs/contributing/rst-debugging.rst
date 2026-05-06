:lastproofread: 2025-12-05

.. _debugging:

#########
Debugging
#########

Two flags are available to help debug configuration scripts. Configuration
loading issues manifest during boot, so these flags are passed as kernel boot
parameters.

ISO image build
===============

If you have trouble compiling your own ISO image or debugging Jenkins issues,
follow the steps at :ref:`iso_build_issues`.

System Startup
==============

Debug system startup by examining the configuration file loading from
``/config/config.boot``. Extend the kernel command-line in the bootloader to
enable this.

Kernel
------

* ``vyos-debug`` - Add this parameter to the Linux boot line to produce
  timing results for script execution during commit. If you see an unexpected
  delay during manual or boot commit, this parameter helps identify bottlenecks.
  The internal flag is ``VYOS_DEBUG``, found in vyatta-cfg_. Output is directed
  to ``/var/log/vyatta/cfg-stdout.log``.

* ``vyos-config-debug`` - During development, coding errors can cause commit
  failures on boot, potentially preventing CLI initialization. This kernel boot
  parameter ensures access to the system as user ``vyos`` and logs a Python
  stack trace to ``/tmp/boot-config-trace``. The file is created only if the
  configuration load fails.

Live System
===========

Several flags can be set to change VyOS behavior at runtime. Toggle these flags
using environment variables or by creating files.

For each feature, create a file called ``vyos.feature.debug`` to enable it.
If a parameter is required, place it as the first line inside the file.

Place the file in ``/tmp`` for one-time debugging (the file is removed on
reboot) or in ``/config`` to persist permanently.

For example, ``/tmp/vyos.ifconfig.debug`` can be created to enable
interface debugging.

You can also enable debugging using environment variables.
The environment variable name follows the convention ``VYOS_FEATURE_DEBUG``.

For example, ``export VYOS_IFCONFIG_DEBUG=""`` in your vbash has the same effect
as ``touch /tmp/vyos.ifconfig.debug``.

* ``ifconfig`` - Display all commands and their responses from the OS on
  screen for inspection.

* ``command`` - Display all commands and their responses from the OS on screen
  for inspection.

* ``developer`` - When a command fails, start a PDB post-mortem session instead
  of showing a standard error message. This allows developers to debug issues
  interactively. Because the debugger waits for input, it can prevent the router
  from booting, so only enable this permanently on production systems if you are
  ready for potential boot failures.

* ``log`` - Send all commands used by VyOS to a log file for inspection. This
  is useful in rare cases when you need to see what the OS is doing, including
  during boot. The default file is ``/tmp/full-log``, but you can change it.

.. note:: To retrieve debug output on the command line, disable ``vyos-configd``
  in addition. You can do this one-time with
  ``sudo systemctl stop vyos-configd``
  or permanently with ``sudo systemctl disable vyos-configd``.

FRR
---

Recent versions use the ``vyos.frr`` framework. The Python class is located in
``vyos-1x:python/vyos/frr.py``. It includes an embedded debugger similar to the
one in ``vyos.ifconfig``.

Enable debugging by running: ``touch /tmp/vyos.frr.debug``

Debug Python code with PDB
------------------------------

Sometimes it is useful to debug Python code interactively on the live system
rather than in an IDE. You can do this using pdb.

Assuming you want to debug a Python script called by an op-mode command, find
the script by looking up the op-mode definitions, then edit it on the live
system using vi:
``vi /usr/libexec/vyos/op_mode/show_xyz.py``

Insert the following statement right before the section where you want to
investigate a problem (for example, a statement you see in a backtrace):
``import pdb; pdb.set_trace()``

Optionally, surround this statement with an ``if`` condition that triggers only
for the conditions you are interested in.

When you run ``show xyz`` and your condition triggers, you enter the Python
debugger:


.. code-block:: none

   > /usr/libexec/vyos/op_mode/show_nat_translations.py(109)process()
   -> rule_type = rule.get('type', '')
   (Pdb)

You can type ``help`` to get an overview of the available commands, and
``help command`` to get more information on each command.

Common useful commands include:

* examine variables using ``pp(var)``
* continue execution using ``cont``
* get a backtrace using ``bt``

Config Migration Scripts
------------------------

Starting with VyOS 1.5, a new mechanism is used for config migration that
improves migration performance. New migrators use only the new format with a
``migration()`` function.

.. code-block:: python

  from vyos.configtree import ConfigTree
  base = ['vpn', 'ipsec']
  def migrate(config: ConfigTree) -> None:
      if not config.exists(base):
          # Nothing to do
          return
      # do your stuff here

New-style migration scripts can no longer run on their own. However, the new
migration subsystem handler includes a test kit:

.. code-block:: none

  vyos@vyos:~$ /usr/libexec/vyos/run-config-migration.py --help
  usage: run-config-migration.py [-h] [--test-script TEST_SCRIPT] [--output-file OUTPUT_FILE] [--force] config_file

  positional arguments:
    config_file           configuration file to migrate

  options:
    -h, --help            show this help message and exit
    --test-script TEST_SCRIPT
                          test named script
    --output-file OUTPUT_FILE
                          write to named output file instead of config file
    --force               force run of all migration scripts


To test your migration, run:

.. code-block:: none

  vyos@vyos:~$ /usr/libexec/vyos/run-config-migration.py --test-script /opt/vyatta/etc/config-migrate/migrate/quagga/11-to-12 --output-file /tmp/foo /tmp/static-route-basic
  vyos@vyos:~$ cat /tmp/foo

The file ``/tmp/foo`` contains the migrated configuration.

Configuration Error on System Boot
----------------------------------

Running the latest rolling releases sometimes exposes bugs due to edge cases
missed in design. File these bugs via Phabricator_, but you can help narrow
down the issue by following these steps:

1. Log in to your VyOS system.
2. Enter configuration mode: ``configure``
3. Reload your boot configuration: ``load``

You should see a Python backtrace that helps identify the issue. Attach it to
the Phabricator_ task.

Boot Timing
-----------

During the migration and rewrite of functionality from Perl to Python, system
boot time increased significantly. You can analyze and graph boot time to see
detailed call sequences during startup.

This uses the ``systemd-bootchart`` package, which is installed by default on
VyOS 1.3 (equuleus) and later. Configuration is versioned for comparable
results.  Refer to bootchart.conf_ for the configuration file.

To enable boot time graphing, add the following to the kernel command line:
``init=/usr/lib/systemd/systemd-bootchart``

You can also make this permanent by editing ``/boot/grub/grub.cfg``.

Priorities
==========

VyOS CLI depends heavily on priorities. Every CLI node has a corresponding
``node.def`` file and possibly an attached script. Nodes can have priorities,
and on system bootup or any ``commit`` to the configuration, scripts execute
from lowest to highest priority. This provides deterministic behavior.

To debug priority issues or see script execution order, use the
``/opt/vyatta/sbin/priority.pl`` script, which lists the execution order of
scripts.

.. stop_vyoslinter

.. _vyatta-cfg: https://github.com/vyos/vyatta-cfg
.. _bootchart.conf: https://github.com/vyos/vyos-build/blob/current/data/live-build-config/includes.chroot/etc/systemd/bootchart.conf
.. include:: /_include/common-references.txt

.. start_vyoslinter
