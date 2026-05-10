:lastproofread: 2025-11-20

.. _upgrade_recovery:


##############################
Recovery after Failed Upgrades
##############################

Use **VyOS upgrade recovery** to restore the system to the last working
version after a failed upgrade.

* :ref:`Configuration:  <configuration>` How to enable upgrade recovery
* :ref:`How it works: <how_it_works>` Overview of the recovery process
* :ref:`Cancelling recovery: <cancelling_recovery>` Overview of the recovery
  process
 
.. _configuration:

*************
Configuration
*************
.. warning:: Upgrade recovery is disabled by default. To use it, 
  **enable it first**.

To enable upgrade recovery, run the following command:

.. cfgcmd::

   set system option reboot-on-upgrade-failure [timeout <min>]

* ``timeout <min>:`` The time in minutes (5 - 30) to cancel upgrade
  recovery before VyOS reboots.
  See :ref:`Cancelling Recovery <cancelling_recovery>`.
 
.. _how_it_works:

************
How it works
************
After a VyOS upgrade, the system monitors the boot process. Upon detecting a
boot failure, VyOS initiates a revert to the last working version and displays
the following warning:

.. code-block:: none

   Booting failed, reverting to previous image
   Automatic reboot in xx minutes
   Use "reboot cancel" to cancel

If no action is taken, the reboot happens automatically after the configured
timeout. Upon successful recovery and reboot, the following message appears: 
 
.. code-block:: none

   WARNING: Image update to "VyOS 1.5.xxxx" failed
   Please check the logs:
   /usr/lib/live/mount/persistence/boot/NAME/rw/var/log
   Message is cleared on next reboot!
     
.. _cancelling_recovery:

*******************
Cancelling recovery
*******************
Upon detecting a boot failure, you have the predefined timeout to cancel
upgrade recovery. This is useful if you want to troubleshoot the faulty VyOS
version on your own.

To cancel upgrade recovery, run the following command:

.. code-block:: none

   reboot cancel