:lastproofread: 2026-02-02

.. _vyos-on-gns3:

###############
Run VyOS on GNS3
###############

You may want to test VyOS in a lab environment.
`GNS3 <http://www.gns3.com>`__ is a network emulation software that you
can use for this purpose.

This guide will provide the necessary steps for installing
and setting up VyOS on GNS3.

Requirements
------------

The following items are required:

* A VyOS installation image (.iso file). You
  can find how to get it on the :ref:`installation` page

* A working GNS3 installation. For further information see the
  `GNS3 documentation <https://docs.gns3.com/>`__.

.. _vm_setup:

VM setup
--------

First, a virtual machine (VM) for the VyOS installation must be created
in GNS3.

Go to the GNS3 **File** menu, click **New template**, and select
**Manually create a new Template**.

.. figure:: /_static/images/gns3-01.*

Select **Qemu VMs** and then click the ``New`` button.

.. figure:: /_static/images/gns3-02.*

Write a name for your VM, such as "VyOS", and click ``Next``.

.. figure:: /_static/images/gns3-03.*

Select **qemu-system-x86_64** as Quemu binary, then **512MB** of RAM
and click ``Next``.

.. figure:: /_static/images/gns3-04.*

Select **telnet** as your console type and click ``Next``.

.. figure:: /_static/images/gns3-05.*

Select **New image** for the base disk image of your VM and click
``Create``.

.. figure:: /_static/images/gns3-06.*

Use the defaults in the **Binary and format** window and click
``Next``.

.. figure:: /_static/images/gns3-07.*

Use the defaults in the **Qcow2 options** window and click ``Next``.

.. figure:: /_static/images/gns3-08.*

Set the disk size to 2000 MiB, and click ``Finish`` to end the **Quemu
image creator**.

.. figure:: /_static/images/gns3-09.*

Click ``Finish`` to end the **New QEMU VM template** wizard.

.. figure:: /_static/images/gns3-10.*

Now you need to edit the VM settings.

In the **Preferences** window, with **Qemu VMs** selected and your new VM
selected, click the ``Edit`` button.

.. figure:: /_static/images/gns3-11.*

In the **General settings** tab of your **QEMU VM template
configuration**, do the following:

* Click on the ``Browse...`` button to choose the **Symbol** you want to
  have representing your VM.
* In **Category** select in which group you want to find your VM.
* Set the **Boot priority** to **CD/DVD-ROM**.

.. figure:: /_static/images/gns3-12.*

At the **HDD** tab, change the Disk interface to **sata** to speed up
the boot process.

.. figure:: /_static/images/gns3-13.*

At the **CD/DVD** tab click on ``Browse...`` and locate the VyOS image
you want to install.

.. figure:: /_static/images/gns3-14.*

.. note:: You probably will want to accept to copy the .iso file to your
   default image directory when you are asked.

In the **Network** tab, set the number of adapters to **0**, set the
**Name format** to **eth{0}**, and set the **Type** to **Paravirtualized
Network I/O (virtio-net-pci)**.

.. figure:: /_static/images/gns3-15.*

In the **Advanced** tab, unmark the checkbox **Use as a linked base
VM** and click ``OK``, which will save and close the **QEMU VM template
configuration** window.

.. figure:: /_static/images/gns3-16.*

At the general **Preferences** window, click ``OK`` to save and close.

.. figure:: /_static/images/gns3-17.*


.. _vyos_installation:

VyOS installation
-----------------

* Create a new project.
* Drag the newly created VyOS VM into it.
* Start the VM.
* Open a console.
  The console displays the system booting. It prompts for login
  credentials. You're now at the VyOS live system.
* :ref:`Install VyOS <installation>`
  as normal (that is, using the ``install image`` command).

* After successful installation, shut down the VM with the ``poweroff``
  command.

* **Delete the VM** from the GNS3 project.

The *VyOS-hda.qcow2* file now contains a working VyOS image and can be
used as a template. But it still needs some fixes before we can deploy
VyOS in our labs.

.. _vyos_vm_configuration:

VyOS VM configuration
---------------------

To turn the template into a working VyOS machine, further steps are
necessary as outlined below:

**General settings** tab: Set the boot priority to **HDD**

.. figure:: /_static/images/gns3-20.*
  
**CD/DVD** tab: Clear the **Image** entry field to unmount the installation
image.

.. figure:: /_static/images/gns3-21.*

Set the number of required network adapters. For example, set it to **4**.

.. figure:: /_static/images/gns3-215.*

**Advanced** settings tab: Check the **Use as a linked
base VM** checkbox and click ``OK`` to save the changes.

.. figure:: /_static/images/gns3-22.*

The VyOS VM is now ready to be deployed.

