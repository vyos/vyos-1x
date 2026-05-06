:lastproofread: 2026-01-26

.. _installation:

############
Installation
############

VyOS installation requires a VyOS .iso file. This file is a live installation
image that you can use to boot a live VyOS system. From there, you can proceed
with a permanent installation on a hard drive or other storage device.

.. list-table:: Comparison of VyOS image releases
   :header-rows: 1
   :widths: 15 35 15 25 15 15

   * - Release Type
     - Description
     - Release Cycle
     - Intended Use
     - Access to Images
     - Access to Source

   * - Nightly (Current)
     - Automatically built from the current branch. Always up to date
       with cutting edge development but guaranteed to contain bugs.
     - Every night
     - Developing VyOS, testing new features, experimenting.
     - Everyone
     - Everyone

   * - Stream
     - VyOS Stream serves as a technology preview and a quality gate
       for the upcoming LTS release. Allows everyone to try new features
       and check if they work well or need improvements.
     - Every quarter
     - Non-critical production environments, preparing for the LTS
       release.
     - Everyone
     - Everyone

   * - Release Candidate
     - Rather stable. All development focuses on testing and hunting
       down remaining bugs following the feature freeze.
     - Irregularly until EPA comes out
     - Labs, small offices and non-critical production systems backed
       by a high-availability setup.
     - Everyone
     - Everyone

   * - Early Production Access
     - Highly stable with no known bugs. Needs to be tested repeatedly
       under different conditions before it can become the final
       release.
     - Irregularly until LTS comes out
     - Non-critical production environments, preparing for the LTS
       release.
     - Everyone
     - Everyone

   * - Long-Term Support
     - Guaranteed to be stable and carefully maintained for several
       years after the release. No features are introduced but security
       updates are released in a timely manner.
     - Every major version
     - Large-scale enterprise networks, internet service providers,
       critical production environments that call for minimum downtime.
     - Subscribers, contributors, non-profits, emergency services,
       academic institutions
     - Subscribers, contributors, non-profits, emergency services,
       academic institutions

Hardware requirements
=====================

The minimum system requirements for VyOS are 4 GB RAM and 10 GB storage.
Depending on your use case, you might need additional RAM and CPU resources. 

Download
========

Registered Subscribers
----------------------

Registered subscribers can log into https://support.vyos.io/ to access
a variety of different downloads via the "Downloads" link. These
downloads include LTS (Long-Term Support), the associated hot-fix releases,
early public access releases, pre-built VM images, as well as device
specific installation ISOs. See this article_ for more information on
downloads.

.. note:: The ``.qcow2`` image provided for Proxmox deployment can also be
   used to deploy VyOS on KVM environments. This image includes cloud-init
   support. See :ref:`cloud-init` for more information.

.. figure:: /_static/images/vyosnew-downloads.*

Building from source
--------------------

Subscribers can download the source code for the LTS release from the
"Downloads" link. Non-subscribers can access the source code for the
Rolling release. For instructions, see the :ref:`build` section. The
VyOS source code repository is available at
https://github.com/vyos/vyos-build.

Rolling Release
---------------

Everyone can download bleeding-edge VyOS rolling images from:
https://downloads.vyos.io/

.. note:: Rolling releases contain the latest enhancements and fixes.
   This means there may be new bugs. If you encounter a bug, follow the
   guide at :ref:`bug_report`. We depend on your feedback to improve VyOS.

The following link contains the most recent VyOS builds for AMD64
systems from the ``current`` branch: https://vyos.net/get/nightly-builds/


Download Verification
---------------------

LTS images are signed with the VyOS lead package maintainer's private key.
You can verify the authenticity of the package using the official public key
and Minisign.

.. _minisign-verification:

Minisign verification
^^^^^^^^^^^^^^^^^^^^^

VyOS uses `Minisign <https://github.com/jedisct1/minisign>`__ for release
signing. Minisign is a tool for signing files and verifying signatures.

OpenBSD introduced signify in 2015. Minisign is an alternative
implementation of the same protocol, available for Windows, macOS, and
most GNU/Linux distributions. Minisign is portable, lightweight, and
uses the Ed25519 public-key signature system.

:vytask:`T2108` switched the validation system to prefer Minisign over GPG keys.

To verify a VyOS image starting with VyOS ``1.3.0-rc6``, run:

.. code-block:: none

  $ minisign -V -P RWSIhkR/dkM2DSaBRniv/bbbAf8hmDqdbOEmgXkf1RxRoxzodgKcDyGq -m vyos-1.5-rolling-202409250007-generic-amd64.iso vyos-1.5-rolling-202409250007-generic-amd64.iso.minisig
  
  Signature and comment signature verified
  Trusted comment: timestamp:1727223408 file:vyos-1.5-rolling-202409250007-generic-amd64.iso    hashed

During an image upgrade, VyOS runs the following command:

.. code-block:: none

  $ minisign -V -p /usr/share/vyos/keys/vyos-release.minisign.pub -m vyos-1.3.0-rc6-amd64.iso vyos-1.3.0-rc6-amd64.iso.minisig
  Signature and comment signature verified
  Trusted comment: timestamp:1629997936   file:vyos-1.3.0-rc6-amd64.iso

.. note:: Starting with version ``1.4.3``, VyOS uses Minisign exclusively.
   If you see an unexpected verification error, update your system to version
   ``1.4.2`` first. Support for GnuPG signatures has been
   removed (:vytask:`T7301`).

.. _live_installation:

Live installation
=================

.. note:: To permanently install VyOS, you must first complete a live
   installation.

You can test VyOS without installing it on your hard drive. **Using your
downloaded VyOS .iso file, you can create a bootable USB drive to boot
into a fully functional VyOS system**. After testing it, you can start a
:ref:`permanent_installation` on your hard drive or power off your system
and remove the USB drive.


If you have a GNU/Linux system, you can create a bootable VyOS USB drive using
the ``dd`` command:

 1. Open your terminal emulator.

 2. Find the device name of your USB drive (use the ``lsblk`` command).

 3. Unmount the USB drive. Replace ``X`` with your device letter and keep the
    asterisk (*) to unmount all partitions.

 .. code-block:: none

  $ umount /dev/sdX*

 1. Write the image (your VyOS .iso file) to the USB drive. Use the device
    name (for example, ``/dev/sdb``), not the partition name
    (for example, ``/dev/sdb1``).

  **Warning**: This will destroy all data on the USB drive!

 .. code-block:: none

   # dd if=/path/to/vyos.iso of=/dev/sdX bs=8M; sync

 1. Wait for the operation to complete (bytes copied). On some systems, this
    may take more than one minute.

 2. Once ``dd`` has finished, pull the USB drive out and plug it into
    the powered-off computer where you want to install (or test) VyOS.

 3. Power on the computer and ensure it boots from the USB drive
    (you may need to select the boot device or change boot settings).

 4. When VyOS finishes loading, sign in using the default credentials 
    (login: ``vyos``, password: ``vyos``).


If you encounter issues with this method, prefer a different operating
system, or want a GUI program, you can use other tools to create a
bootable USB drive, such as balenaEtcher_ (GNU/Linux, macOS, and Windows),
Rufus_ (Windows), and `many others`_. Follow their instructions to create
a bootable USB drive from an ``.iso`` file.

.. hint:: The default username and password for the live system is *vyos*.


.. _permanent_installation:

Permanent installation
======================

.. note:: Before a permanent installation, VyOS requires a
   :ref:`live_installation`.

Unlike general-purpose Linux distributions, VyOS uses "image installation",
which mimics the user experience of traditional hardware routers and allows
you to keep multiple VyOS versions installed simultaneously. This lets you
switch to a previous version if something breaks or misbehaves after an
image upgrade.

Each version is contained in its own squashfs image mounted in a union
filesystem along with a directory for mutable data such as configurations,
keys, and custom scripts.

In order to proceed with a permanent installation:

 1. Sign in to the VyOS live system using the default credentials
    (login: ``vyos``, password: ``vyos``).

 2. Run the ``install image`` command and follow the wizard:

 .. code-block:: none
 
   vyos@vyos:~$ install image
   Welcome to VyOS installation!
   This command will install VyOS to your permanent storage.
   Would you like to continue? [y/N] y
   What would you like to name this image? (Default: 2025.09.17-0018-rolling)
   Please enter a password for the "vyos" user:
   Please confirm password for the "vyos" user:
   What console should be used by default? (K: KVM, S: Serial)? (Default: S)
   Probing disks
   1 disk(s) found
   The following disks were found:
   Drive: /dev/vda (10.0 GB)
   Which one should be used for installation? (Default: /dev/vda)
   Installation will delete all data on the drive. Continue? [y/N] y
   Searching for data from previous installations
   No previous installation found
   Would you like to use all the free space on the drive? [Y/n] Y
   Creating partition table...
   The following config files are available for boot:
           1: /opt/vyatta/etc/config/config.boot
           2: /opt/vyatta/etc/config.boot.default
   Which file would you like as boot config? (Default: 1)
   Creating temporary directories
   Mounting new partitions
   Creating a configuration file
   Copying system image files
   Installing GRUB configuration files
   Installing GRUB to the drive
   Cleaning up
   Unmounting target filesystems
   Removing temporary files
   The image installed successfully; please reboot now.


 3. After installation completes, remove the live USB drive or CD.

 4. Reboot the system.

 .. code-block:: none

  vyos@vyos:~$ reboot
  Proceed with reboot? (Yes/No) [No] Yes

 You will boot now into a permanent VyOS system.


PXE Boot
========

You can also install VyOS using PXE, a more complex installation method that
allows you to deploy VyOS over the network.

**Requirements**

* A machine (client) with a PXE-enabled NIC. 
* :ref:`dhcp-server`
* :ref:`tftp-server`
* Webserver (HTTP). Optional, but speeds up installation.
* VyOS ISO image (do not use images prior to VyOS ``1.2.3``).
* Files *pxelinux.0* and *ldlinux.c32* from the
  `Syslinux distribution <https://kernel.org/pub/linux/utils/boot/syslinux/>`_.

Configuration
-------------

Step 1: DHCP
^^^^^^^^^^^^

Configure a DHCP server to provide the client with:

* An IP address
* The TFTP server address (DHCP option 66), sometimes referred to as the
  *boot server*
* The *bootfile name* (DHCP option 67): *pxelinux.0*

In this example we configured an existent VyOS as the DHCP server:

.. code-block:: none

  vyos@vyos# show service dhcp-server
   shared-network-name mydhcp {
       subnet 192.168.1.0/24 {
           option {
               bootfile-name pxelinux.0
               bootfile-server 192.168.1.50
               default-router 192.168.1.50
           }
           range 0 {
               start 192.168.1.70
               stop 192.168.1.100
           }
           subnet-id 1
       }
   }

.. _install_from_tftp:

Step 2: TFTP
^^^^^^^^^^^^

Configure a TFTP server to serve the following:

* The *pxelinux.0* file from the Syslinux distribution
* The *ldlinux.c32* file from the Syslinux distribution
* The VyOS kernel you want to deploy (*vmlinuz* file from the
  */live* directory in the extracted ISO file)
* The VyOS initial ramdisk (*initrd.img* file from the */live* directory
  in the extracted ISO file). Do not use an empty (0 bytes) initrd.img
  file; the correct file may have a longer name.
* A directory named *pxelinux.cfg* containing the configuration file.
  By default, the VyOS configuration file is named default_.

In the example you configured your existent VyOS as the TFTP server too:

.. code-block:: none

  vyos@vyos# show service tftp-server
   directory /config/tftpboot
   listen-address 192.168.1.50

Example of the contents of the TFTP server:

.. code-block:: none

  vyos@vyos# ls -hal /config/tftpboot/
  total 29M
  drwxr-sr-x 3 tftp tftp      4.0K Oct 14 00:23 .
  drwxrwsr-x 9 root vyattacfg 4.0K Oct 18 00:05 ..
  -r--r--r-- 1 root vyattacfg  25M Oct 13 23:24 initrd.img-4.19.54-amd64-vyos
  -rwxr-xr-x 1 root vyattacfg 120K Oct 13 23:44 ldlinux.c32
  -rw-r--r-- 1 root vyattacfg  46K Oct 13 23:24 pxelinux.0
  drwxr-xr-x 2 root vyattacfg 4.0K Oct 14 01:10 pxelinux.cfg
  -r--r--r-- 1 root vyattacfg 3.7M Oct 13 23:24 vmlinuz

  vyos@vyos# ls -hal /config/tftpboot/pxelinux.cfg
  total 12K
  drwxr-xr-x 2 root vyattacfg 4.0K Oct 14 01:10 .
  drwxr-sr-x 3 tftp tftp      4.0K Oct 14 00:23 ..
  -rw-r--r-- 1 root root       191 Oct 14 01:10 default

Example of simple (no menu) configuration file:

.. code-block:: none

  vyos@vyos# cat /config/tftpboot/pxelinux.cfg/default
  DEFAULT VyOS123

  LABEL VyOS123
   KERNEL vmlinuz
   APPEND initrd=initrd.img-4.19.54-amd64-vyos boot=live nopersistence noautologin nonetworking fetch=http://address:8000/filesystem.squashfs

Step 3: HTTP
^^^^^^^^^^^^

You also need to provide the *filesystem.squashfs* file. Because this is a
large file and TFTP is slow, you can send it through HTTP to speed up the
transfer. In our example, we do this—see the configuration file above.

1. Start a web server. You can use one like
   `Python's SimpleHTTPServer`_ to serve the `filesystem.squashfs` file.
   The file is in the `/live` directory of the extracted ISO file.

2. Edit the :ref:`install_from_tftp` configuration file to show the correct
   URL: ``fetch=http://<address_of_your_HTTP_server>/filesystem.squashfs``.

.. note:: Do not rename the *filesystem.squashfs* file. If you're working with
   different versions, create different directories instead.

3. restart the TFTP service. If you're using VyOS as your TFTP server, restart
   the service with ``sudo service tftpd-hpa restart``.

.. note:: Ensure the directories and files on both the TFTP and HTTP servers
   have the correct permissions for the booting clients to access them.



Client Boot
-----------

Finally, power on your PXE-enabled clients. They will automatically receive an
IP address from the DHCP server and boot into VyOS live using files from the 
TFTP and HTTP servers.

Once finished you will be able to proceed with the ``install image``
command as in a regular VyOS installation.



Known Issues
============

This is a list of known issues that can arise during installation.

Black screen on install
-----------------------

GRUB redirects all output to a serial port to facilitate installation
on headless hosts. On some hardware that lacks a serial port, this causes
a hard lockup and displays a black screen after you select the
`Live system` option from the installation image.

The workaround is to press `e` when the boot menu appears and edit the
GRUB boot options. Specifically, remove the:

`console=ttyS0,115200`

option, and type CTRL-X to boot.

Installation can then continue as outlined above.


.. stop_vyoslinter

.. _SYSLINUX: http://www.syslinux.org/
.. _balenaEtcher: https://www.balena.io/etcher/
.. _Rufus: https://rufus.ie/
.. _many others: https://en.wikipedia.org/wiki/List_of_tools_to_create_Live_USB_systems
.. _configuration: https://wiki.syslinux.org/wiki/index.php?title=Config
.. _default: https://wiki.syslinux.org/wiki/index.php?title=PXELINUX#Configuration
.. _`Python's SimpleHTTPServer`: https://docs.python.org/2/library/simplehttpserver.html
.. _article: https://customers.support.vyos.com/servicedesk/customer/portal/1/article/159055913

.. start_vyoslinter
