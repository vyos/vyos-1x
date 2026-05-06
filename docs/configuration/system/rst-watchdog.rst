.. _system_watchdog:

########
Watchdog
########

VyOS supports hardware watchdog timers to automatically reboot the system if
it becomes unresponsive. This is particularly useful for remote or embedded
systems where physical access is limited.

A watchdog timer is a hardware or software mechanism that automatically resets
the system if the operating system stops responding within a configured timeout
period. The system will periodically notify the watchdog that it is still
running. If the watchdog is not notified within the timeout period, the watchdog
will reset the system.

Configuration
=============

The watchdog feature is configured under the ``system watchdog`` configuration
tree. The presence of the ``system watchdog`` node enables the watchdog feature.

.. cfgcmd:: set system watchdog

   Enable watchdog support.

   The watchdog is enabled only when a watchdog device is available as
   ``/dev/watchdog0``.

   .. note:: If multiple watchdog devices are present, only the first watchdog
      device is supported (VyOS uses ``/dev/watchdog0`` only).

   If ``/dev/watchdog0`` does not exist and no module is configured, commit will
   fail. If a module is configured but ``/dev/watchdog0`` still cannot be
   created, VyOS will emit a warning and will not enable the systemd watchdog.

.. cfgcmd:: set system watchdog module <module-name>

   Specify the kernel watchdog driver module to load for ``/dev/watchdog0``.

   The configured module must be a watchdog driver module, not an arbitrary
   kernel module.

   **In most cases, this option is not required** as the kernel will
   automatically load the appropriate watchdog driver for your system. Use this
   option if the kernel fails to load the required driver, or when you want to
   use the software watchdog (``softdog``).

   Common modules include:

   * ``softdog`` - Software watchdog timer (available on all systems)
   * ``iTCO_wdt`` - Intel TCO watchdog timer
   * ``sp5100_tco`` - AMD SP5100 TCO watchdog timer
   * ``i6300esb`` - Intel 6300ESB watchdog timer
   * ``ipmi_watchdog`` - IPMI watchdog timer

   .. warning:: ``softdog`` is not a hardware watchdog. It is implemented using
      kernel timers and therefore depends on the Linux kernel continuing to run.
      In some fault conditions (for example, a kernel hang), ``softdog`` may not
      be able to trigger a reset.

      Prefer a hardware watchdog driver whenever possible, as hardware watchdogs
      can operate independently of the operating system.

   If no module is specified, VyOS will use an existing ``/dev/watchdog0``
   device if available.

   .. note:: If a module is specified but a different driver is actually bound
      to ``watchdog0``, VyOS will emit a warning during commit.

   Example:

   .. code-block:: none

      set system watchdog module softdog

.. cfgcmd:: set system watchdog timeout <seconds>
   :defaultvalue:

   Set the watchdog timeout for normal runtime operation in seconds.

   Valid range: 1-65535 seconds

   .. note:: Some watchdog drivers expose minimum and maximum supported runtime
      timeouts via sysfs. When available, VyOS validates ``timeout`` against
      those driver limits during commit.

   This is the interval during which the system must respond to the watchdog.
   If the system does not respond within this time, the watchdog will trigger
   a reboot.

   Example:

   .. code-block:: none

      set system watchdog timeout 30

.. cfgcmd:: set system watchdog shutdown-timeout <seconds>
   :defaultvalue:

   Set the watchdog timeout during system shutdown in seconds.

   Valid range: 60-65535 seconds

   This extended timeout allows the system to complete a graceful shutdown
   without triggering the watchdog.

   .. warning:: Setting this value too low (below 120 seconds) may cause
      unclean shutdowns, as the system may not have enough time to properly
      stop all services and flush disk buffers. The recommended minimum value
      is 120 seconds.

   Example:

   .. code-block:: none

      set system watchdog shutdown-timeout 180

.. cfgcmd:: set system watchdog reboot-timeout <seconds>
   :defaultvalue:

   Set the watchdog timeout during system reboot in seconds.

   Valid range: 60-65535 seconds

   This extended timeout allows the system to complete the reboot process
   without triggering the watchdog during the transition.

   .. warning:: Setting this value too low (below 120 seconds) may cause
      unclean reboots, as the system may not have enough time to properly
      stop all services before restarting. The recommended minimum value
      is 120 seconds.

   Example:

   .. code-block:: none

      set system watchdog reboot-timeout 180

Examples
========

Basic Configuration with Software Watchdog
------------------------------------------

This example configures a basic software watchdog with default timeouts:

.. code-block:: none

   set system watchdog module softdog

This will:

* Enable the watchdog feature
* Load the ``softdog`` kernel module
* Use a 10-second runtime timeout (default)
* Use 120-second shutdown and reboot timeouts (default)

Advanced Configuration
----------------------

This example shows a more customized configuration suitable for a production
system:

.. code-block:: none

   set system watchdog module iTCO_wdt
   set system watchdog timeout 30
   set system watchdog shutdown-timeout 300
   set system watchdog reboot-timeout 300

This configuration:

* Enables the watchdog feature
* Loads the Intel TCO hardware watchdog module
* Sets a 30-second runtime timeout
* Allows 5 minutes for shutdown and reboot operations

Best Practices
==============

* **Start with conservative timeouts**: Use longer timeouts initially and
  reduce them as you gain confidence in system stability.

* **Test before deployment**: Verify the watchdog works as expected in a
  non-production environment before deploying to production systems.

* **Choose appropriate modules**: Use hardware watchdog modules (like
  ``iTCO_wdt``) when available, as they are more reliable than software
  watchdogs.

* **Consider shutdown time**: Set ``shutdown-timeout`` and ``reboot-timeout``
  values high enough to allow for normal shutdown procedures, especially on
  systems with many services or slow storage.

* **Monitor watchdog events**: Check system logs after any unexpected reboots
  to determine if the watchdog triggered the reboot.

* **Remote systems**: For systems without physical console access, use
  conservative timeout values to avoid false-positive reboots during high
  load conditions.

.. note:: The watchdog configuration takes effect immediately after commit,
   but systemd must be reloaded. This happens automatically during commit.

.. warning:: Incorrect watchdog configuration on remote systems can result
   in unexpected reboots. Always test watchdog settings in a controlled
   environment before deploying to production systems.
