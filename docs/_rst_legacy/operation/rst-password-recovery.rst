:lastproofread: 2026-02-04

.. _password-recovery:

#################
Password Recovery
#################

Restart VyOS from the console. The GRUB menu appears.
Select **Boot options**.

.. figure:: /_static/images/reset-password-step-1.*
   :width: 600


Next, select **Select boot mode**.

.. figure:: /_static/images/reset-password-step-2.*
   :width: 600

Select **Password reset**.

.. figure:: /_static/images/reset-password-step-3.*
   :width: 600

Boot the desired VyOS version.

.. figure:: /_static/images/reset-password-step-4.*
   :width: 600

The standalone user password recovery tool runs and prompts you to reset the
local system user password. VyOS automatically reboots after you reset your
password.


.. code-block:: console

   Do you wish to reset the admin password? (y or n)
   y
   Which admin account do you want to reset?[vyos]
   my_username
   Enter my_username password:
   Retype my_username password:
   System will reboot in 10 seconds...
