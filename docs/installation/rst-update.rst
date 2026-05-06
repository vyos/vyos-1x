:lastproofread: 2026-01-26

.. _update_vyos:

###########
Update VyOS
###########

New system images can be added using the :opcmd:`add system image` command.
This command extracts the image and prompts you to use the current system
configuration and SSH security keys, allowing the new image to boot with your
current configuration.

.. note:: Only LTS releases are PGP-signed.

.. opcmd:: add system image <url | path> | [latest] [vrf name]
   [username user [password pass]]

   Use this command to install a new system image. You can retrieve the
   image from the web (``http://``, ``https://``) or from your local system.
   For example: /tmp/vyos-1.2.3-amd64.iso.

   The ``add system image`` command also supports installing new VyOS versions
   through an optional VRF. If the URL requires authentication, you can specify
   an optional username and password on the command line, which will be passed
   as "Basic-Auth" to the server.

If there isn't enough free disk space, the installation will be canceled.
To delete images, use the :opcmd:`delete system image` command.

VyOS associates configuration with each image, and each image has its own
unique configuration copy. This differs from traditional network routers where
the configuration is shared across all images.

.. note:: If you have personal files such as scripts that you want to preserve
   during the upgrade, store them in ``/config`` since this directory is always
   copied to newly installed images.

You can access files from a previous installation and copy them to your
current image if they were stored in the ``/config`` directory. Use the
:opcmd:`copy` command to do this. For example, to copy ``/config/config.boot``
from the VyOS ``1.2.1`` image, run:

.. code::

   copy file 1.2.1://config/config.boot to /tmp/config.boot.1.2.1


Example
"""""""

.. code-block:: none

     vyos@vyos:~$ add system image https://s3.amazonaws.com/s3-us.vyos.io/rolling/current/vyos-1.4-rolling-202201120317-amd64.iso
     Trying to fetch ISO file from https://s3.amazonaws.com/s3-us.vyos.io/rolling/current/vyos-1.4-rolling-202201120317-amd64.iso
       % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                      Dload  Upload   Total   Spent    Left  Speed
     100  338M  100  338M    0     0  3837k      0  0:01:30  0:01:30 --:--:-- 3929k
     ISO download succeeded.
     Checking for digital signature file...
       % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                      Dload  Upload   Total   Spent    Left  Speed
       0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
     curl: (22) The requested URL returned error: 404 Not Found

     Unable to fetch digital signature file.
     Do you want to continue without signature check? (yes/no) [yes]
     Checking MD5 checksums of files on the ISO image...OK.
     Done!

     What would you like to name this image? [vyos-1.3-rolling-201912201452]:

     OK.  This image will be named: vyos-1.3-rolling-201912201452

You can use ``latest`` option. It loads the latest available Rolling release.

.. code-block:: none

     vyos@vyos:~$ add system image latest

.. stop_vyoslinter
.. note:: To use the ``latest`` option, "system update-check url" must be
   configured appropriately for your installed release.

   For updates to the Rolling Release for AMD64, the following URL may be used:

   https://raw.githubusercontent.com/vyos/vyos-nightly-build/refs/heads/current/version.json

.. start_vyoslinter

.. hint:: You can access the latest Rolling Release for AMD64 from a web
   browser at:

   https://vyos.net/get/nightly-builds/

After rebooting, verify the version you're running using the
:opcmd:`show version` command.
