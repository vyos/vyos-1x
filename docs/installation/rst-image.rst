:lastproofread: 2026-01-26

.. _image-mgmt:

################
Image Management
################

VyOS uses an image-based installation that creates a directory for each image
on the storage device you select during installation.

The boot device has the following directory structure:

.. code-block:: none

  /
  /boot
  /boot/grub
  /boot/2025.07.16-0020-rolling.squashfs

The image directory contains the system kernel, a compressed root filesystem
image, and a directory for persistent storage (such as configuration). During
boot, the system extracts the OS image into memory and mounts the appropriate
live-rw subdirectories to provide persistent storage for system configuration.

This process ensures that the system always boots to a known working state,
since the OS image is fixed and non-persistent. You can also install multiple
VyOS releases on the same storage device. You can manually select the image at
boot if needed, but the system boots the default image by default.

.. opcmd:: show system image

   List all available system images which can be booted on the current system.

   .. code-block:: none

     vyos@vyos:~$ show system image
     Name                     Default boot    Running
     -----------------------  --------------  ---------
     2025.07.16-0020-rolling  Yes             Yes
     1.4.1
     1.4.0


.. opcmd:: delete system image [image-name]

   Delete unused images from the system. You can specify an optional image name
   to delete. Use the :opcmd:`show system image` command to list available
   images.

   .. code-block:: none

      vyos@vyos:~$ delete system image
      The following images are installed:
              1: 2025.07.16-0020-rolling (running) (default boot)
              2: 1.4.1
              3: 1.4.0
      Select an image to delete: 3
      Do you really want to delete the image 1.4.0? [y/N] y
      The image "1.4.0" was successfully deleted

.. opcmd:: show version

   Show current system image version.

   .. code-block:: none

      vyos@vyos:~$ show version
      Version:          VyOS 2025.07.16-0020-rolling
      Release train:    current
      Release flavor:   generic

      Built by:         autobuild@vyos.net
      Built on:         Wed 16 Jul 2025 00:21 UTC
      Build UUID:       20d432ee-6d55-4ebc-8462-46fe836246c9
      Build Commit ID:  f7ce0d8a692f2d

      Architecture:     x86_64
      Boot via:         installed image
      System type:      KVM guest
      Secure Boot:      n/a (BIOS)

      Hardware vendor:  QEMU
      Hardware model:   Standard PC (i440FX + PIIX, 1996)
      Hardware S/N:     
      Hardware UUID:    b9831d42-c1fe-b2bd-7d3d-49db9418f5c9

      Copyright:        VyOS maintainers and contributors




System rollback
===============

To roll back to a previous image, first view the available images by using the
:opcmd:`show system image` command, then select your image with the following
command:

.. opcmd:: set system image default-boot [image-name]

   Select the default boot image which will be started on the next boot
   of the system.

Then reboot the system.

.. note:: VyOS automatically associates the configuration with each image,
   so you don't need to manage this separately. Each image has its own unique
   configuration copy.

If you have console access, you can also select the boot image by restarting
the system and using the GRUB menu at startup.
