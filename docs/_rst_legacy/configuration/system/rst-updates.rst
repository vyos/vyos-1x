#######
Updates
#######

VyOS supports online checking for updates

Configuration
=============

.. cfgcmd:: set system update-check auto-check

   Configure auto-checking for new images


.. cfgcmd:: set system update-check url <url>

   Configure a URL that contains information about images.


Example
=======

.. code-block:: none

  set system update-check auto-check
  set system update-check url 'https://raw.githubusercontent.com/vyos/vyos-rolling-nightly-builds/main/version.json'

Check:

.. code-block:: none

  vyos@r4:~$ show system updates 
  Current version: 1.5-rolling-202312220023

  Update available: 1.5-rolling-202312250024
  Update URL: https://github.com/vyos/vyos-rolling-nightly-builds/releases/download/1.5-rolling-202312250024/1.5-rolling-202312250024-amd64.iso
  vyos@r4:~$

  vyos@r4:~$ add system image latest
