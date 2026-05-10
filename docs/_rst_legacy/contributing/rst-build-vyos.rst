:lastproofread: 2025-12-05

.. _build:

##########
Build VyOS
##########

*************
Prerequisites
*************

There are different ways you can build VyOS. Building using a
:ref:`build_docker`
container is the easiest way because all dependencies are managed for you.
Alternatively, you can set up your own build machine and run a
:ref:`build_native` build.

.. note:: Starting with VyOS 1.4, only source code and Debian package
   repositories of the rolling release (the **current** branch) are publicly
   available.

   The source code and pre-built Debian package repositories of LTS releases
   are only available to subscription holders (customers and active community
   members with contributors subscriptions).

   The following includes the build process for VyOS rolling release.

This will guide you through the process of building a VyOS ISO using Docker_.
This process has been tested on clean installs of Debian Bookworm.

.. _build_native:

Native Build
============

To build VyOS natively, you need a properly configured build host with
Debian Bookworm installed.

To get started, clone the repository to your local machine:

.. code-block:: none

  $ sudo make clean
  $ sudo ./build-vyos-image --architecture amd64 --build-by "j.randomhacker@vyos.io" generic

For required packages, refer to the ``docker/Dockerfile`` file in the
repository_. The ``./build-vyos-image`` script will also warn you if any
dependencies are missing.

.. _build_docker:

Docker
======

Installing Docker_ and prerequisites:

.. hint:: Docker versions are updated frequently. The following examples may
   become outdated.

.. code-block:: none

  # Add Docker's official GPG key:
  sudo apt-get update
  sudo apt-get install ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  # Add the repository to Apt sources:
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt-get update
  sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

To use Docker without ``sudo``, add your current non-root user to the ``docker``
group: ``sudo usermod -aG docker yourusername``.

.. hint:: Adding a user to the ``docker`` group grants privileges equivalent to
   ``root``. It is recommended to remove the non-root user from the ``docker``
   group after building the VyOS ISO. See also `Docker as non-root`_.

.. note:: The build process must run on a local file system. Building on SMB or
   NFS shares will cause the container to fail. VirtualBox shared folders are
   also not supported because block device operations are not implemented.

Build Container
---------------

The container can be built by hand or by fetching the pre-built one from
DockerHub. It is recommended to use the pre-built containers from the 
`VyOS DockerHub`organization_
The container is built from Docker packages automatically after every commit
to the ``vyos-build`` repository (this process may take 2-3 hours).

.. note:: If you use the pre-built container, it will be automatically
   downloaded from DockerHub if it is not found on your local machine when
   you build the ISO.

Dockerhub
^^^^^^^^^

To manually download the container from DockerHub, run:

.. code-block:: none

  $ docker pull vyos/vyos-build:current  # For VyOS rolling release

Build from source
^^^^^^^^^^^^^^^^^

The container can also be built directly from source:

.. code-block:: none

  $ git clone -b current --single-branch https://github.com/vyos/vyos-build
  
  $ cd vyos-build
  $ docker build -t vyos/vyos-build:current docker

.. note:: VyOS switched to Debian Bookworm (12) in its ``current`` branch.
   Due to software version updates, it is recommended to use the official
   Docker Hub image to build VyOS ISO.
   
Tips and Tricks
---------------

You can create Bash aliases to easily launch the latest container per release
train (``current``). Add the following to your ``.bash_aliases`` file:

.. code-block:: none

  alias vybld='docker pull vyos/vyos-build:current && docker run --rm -it \
      -v "$(pwd)":/vyos \
      -v "$HOME/.gitconfig":/etc/gitconfig \
      -v "$HOME/.bash_aliases":/home/vyos_bld/.bash_aliases \
      -v "$HOME/.bashrc":/home/vyos_bld/.bashrc \
      -w /vyos --privileged --sysctl net.ipv6.conf.lo.disable_ipv6=0 \
      -e GOSU_UID=$(id -u) -e GOSU_GID=$(id -g) \
      vyos/vyos-build:current bash'

Now you have a new alias ``vybld`` that launches development containers in
your current working directory.

.. note:: Some VyOS packages (namely vyos-1x) come with build-time tests which
   verify some of the internal library calls that they work as expected. Those
   tests are carried out through the Python Unittest module. If you want to
   build the ``vyos-1x`` package (which is our main development package) you
   need to start your Docker container using the following argument:
   ``--sysctl net.ipv6.conf.lo.disable_ipv6=0``, otherwise those tests will
   fail.


.. _build_iso:

*********
Build ISO
*********

Now that you understand the prerequisites, you can build a VyOS ISO from source.
First, fetch the latest source code from GitHub:

.. code-block:: none

  $ git clone -b current --single-branch https://github.com/vyos/vyos-build


Now you can begin a fresh VyOS ISO build. Change to the ``vyos-build``
directory and run:

.. code-block:: none

  $ cd vyos-build
  $ docker run --rm -it --privileged -v $(pwd):/vyos -w /vyos vyos/vyos-build:current bash
    
Start the build:

.. code-block:: none

  vyos_bld@8153428c7e1f:/vyos$ sudo make clean
  vyos_bld@8153428c7e1f:/vyos$ sudo ./build-vyos-image --architecture amd64 --build-by "j.randomhacker@vyos.io" generic

When the build is successful, find the resulting ISO in the ``build`` directory
as ``live-image-[architecture].hybrid.iso``.

.. _build source:


.. _customize:

Customize
=========

You can customize the ISO with the following configure options. Generate the
full and current list with ``./build-vyos-image --help``:

.. code-block:: none

  $ vyos_bld@8153428c7e1f:/vyos$ sudo ./build-vyos-image --help
    I: Checking if packages required for VyOS image build are installed
    usage: build-vyos-image [-h] [--architecture ARCHITECTURE]
    [--build-by BUILD_BY] [--debian-mirror DEBIAN_MIRROR]
    [--debian-security-mirror DEBIAN_SECURITY_MIRROR]
    [--pbuilder-debian-mirror PBUILDER_DEBIAN_MIRROR]
    [--vyos-mirror VYOS_MIRROR] [--build-type BUILD_TYPE]
    [--version VERSION] [--build-comment BUILD_COMMENT] [--debug] [--dry-run]
    [--custom-apt-entry CUSTOM_APT_ENTRY] [--custom-apt-key CUSTOM_APT_KEY]
    [--custom-package CUSTOM_PACKAGE]
        [build_flavor]

    positional arguments:
    build_flavor          Build flavor

    optional arguments:
    -h, --help            show this help message and exit
    --architecture ARCHITECTURE
                            Image target architecture (amd64 or arm64)
    --build-by BUILD_BY   Builder identifier (e.g. jrandomhacker@example.net)
    --debian-mirror DEBIAN_MIRROR
                            Debian repository mirror
    --debian-security-mirror DEBIAN_SECURITY_MIRROR
                            Debian security updates mirror
    --pbuilder-debian-mirror PBUILDER_DEBIAN_MIRROR
                            Debian repository mirror for pbuilder env bootstrap
    --vyos-mirror VYOS_MIRROR
                            VyOS package mirror
    --build-type BUILD_TYPE
                            Build type, release or development
    --version VERSION     Version number (release builds only)
    --build-comment BUILD_COMMENT
                            Optional build comment
    --debug               Enable debug output
    --dry-run             Check build configuration and exit
    --custom-apt-entry CUSTOM_APT_ENTRY
                            Custom APT entry
    --custom-apt-key CUSTOM_APT_KEY
                            Custom APT key file
    --custom-package CUSTOM_PACKAGE
                            Custom package to install from repositories


.. _iso_build_issues:

ISO Build Issues
----------------

There are (rare) situations where building an ISO image is not possible at all
due to a broken package feed in the background. APT is not very good at
reporting the root cause of the issue. Your ISO build will likely fail with a
more or less similar looking error message:

.. code-block:: none

  The following packages have unmet dependencies:
   vyos-1x : Depends: accel-ppp but it is not installable
  E: Unable to correct problems, you have held broken packages.
  P: Begin unmounting filesystems...
  P: Saving caches...
  Reading package lists...
  Building dependency tree...
  Reading state information...
  Del frr-pythontools 7.5-20210215-00-g8a5d3b7cd-0 [38.9 kB]
  Del accel-ppp 1.12.0-95-g59f8e1b [475 kB]
  Del frr 7.5-20210215-00-g8a5d3b7cd-0 [2671 kB]
  Del frr-snmp 7.5-20210215-00-g8a5d3b7cd-0 [55.1 kB]
  Del frr-rpki-rtrlib 7.5-20210215-00-g8a5d3b7cd-0 [37.3 kB]
  make: *** [Makefile:30: iso] Error 1
  (10:13) vyos_bld ece068908a5b:/vyos [current] #

To debug the build process and gain additional information of what could be the
root cause, you need to use `chroot` to change into the build directory. This is
explained in the following step by step procedure:

.. code-block:: none

  vyos_bld ece068908a5b:/vyos [current] # sudo chroot build/chroot /bin/bash

We now need to mount some required, volatile filesystems

.. code-block:: none

  (live)root@ece068908a5b:/# mount -t proc none /proc
  (live)root@ece068908a5b:/# mount -t sysfs none /sys
  (live)root@ece068908a5b:/# mount -t devtmpfs none /dev

We now are free to run any command we would like to use for debugging, e.g.
re-installing the failed package after updating the repository.

.. code-block:: none

  (live)root@ece068908a5b:/# apt-get update; apt-get install vyos-1x
  Get:1 file:/root/packages ./ InRelease
  Ign:1 file:/root/packages ./ InRelease
  Get:2 file:/root/packages ./ Release [1235 B]
  Get:2 file:/root/packages ./ Release [1235 B]
  Get:3 file:/root/packages ./ Release.gpg
  Ign:3 file:/root/packages ./ Release.gpg
  Hit:4 http://repo.powerdns.com/debian buster-rec-43 InRelease
  Hit:5 http://repo.saltstack.com/py3/debian/10/amd64/archive/3002.2 buster InRelease
  Hit:6 http://deb.debian.org/debian bullseye InRelease
  Hit:7 http://deb.debian.org/debian buster InRelease
  Hit:8 http://deb.debian.org/debian-security buster/updates InRelease
  Hit:9 http://deb.debian.org/debian buster-updates InRelease
  Hit:10 http://deb.debian.org/debian buster-backports InRelease
  Hit:11 http://dev.packages.vyos.net/repositories/current current InRelease
  Reading package lists... Done
  N: Download is performed unsandboxed as root as file '/root/packages/./InRelease' couldn't be accessed by user '_apt'. - pkgAcquire::Run (13: Permission denied)
  Reading package lists... Done
  Building dependency tree
  Reading state information... Done
  Some packages could not be installed. This may mean that you have
  requested an impossible situation or if you are using the unstable
  distribution that some required packages have not yet been created
  or been moved out of Incoming.
  The following information may help to resolve the situation:

  The following packages have unmet dependencies:
   vyos-1x : Depends: accel-ppp but it is not installable
  E: Unable to correct problems, you have held broken packages.

Now it's time to fix the package mirror and rerun the last step until the
package installation succeeds again!

.. _build_custom_packages:

Linux Kernel
============

The Linux kernel used by VyOS is heavily tied to the ISO build process. The
file ``data/defaults.json`` hosts a JSON definition of the kernel version used
``kernel_version`` and the ``kernel_flavor`` of the kernel which represents the
kernel's LOCAL_VERSION. Both together form the kernel version variable in the
system:

.. code-block:: none

  vyos@vyos:~$ uname -r
  6.1.52-amd64-vyos

* Accel-PPP
* Intel NIC drivers
* Intel QAT

Each of those modules holds a dependency on the kernel version and if you are
lucky enough to receive an ISO build error which sounds like:

.. code-block:: none

  I: Create initramfs if it does not exist.
  Extra argument '6.1.52-amd64-vyos'
  Usage: update-initramfs {-c|-d|-u} [-k version] [-v] [-b directory]
  Options:
   -k version     Specify kernel version or 'all'
   -c             Create a new initramfs
   -u             Update an existing initramfs
   -d             Remove an existing initramfs
   -b directory   Set alternate boot directory
   -v             Be verbose
  See update-initramfs(8) for further details.
  E: config/hooks/live/17-gen_initramfs.chroot failed (exit non-zero). You should check for errors.

The most obvious reasons could be:

* ``vyos-build`` repo is outdated, please ``git pull`` to update to the latest
  release kernel version from us.

* You have your own custom kernel `*.deb` packages in the `packages` folder but
  neglected to create all required out-of tree modules like Accel-PPP, Intel
  QAT or Intel NIC drivers

Building The Kernel
-------------------

The kernel build is quite easy, most of the required steps can be found in the
``vyos-build/packages/linux-kernel/Jenkinsfile`` but we will walk you through
it.

Clone the kernel source to `vyos-build/packages/linux-kernel/`:

.. code-block:: none

  $ cd vyos-build/packages/linux-kernel/
  $ git clone https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git

Check out the required kernel version - see ``vyos-build/data/defaults.json``
file (example uses kernel 4.19.146):

.. code-block:: none

  $ cd vyos-build/packages/linux-kernel/linux
  $ git checkout v4.19.146
  Checking out files: 100% (61536/61536), done.
  Note: checking out 'v4.19.146'.

  You are in 'detached HEAD' state. You can look around, make experimental
  changes and commit them, and you can discard any commits you make in this
  state without impacting any branches by performing another checkout.

  If you want to create a new branch to retain commits you create, you may
  do so (now or later) by using -b with the checkout command again. Example:

    git checkout -b <new-branch-name>

  HEAD is now at 015e94d0e37b Linux 4.19.146

Now you can use the helper script ``build-kernel.sh``, which completes all
the necessary steps: applying required patches from the
``vyos-build/packages/linux-kernel/patches`` folder, copying the kernel
configuration ``x86_64_vyos_defconfig`` to the correct location, and building
the Debian packages.

.. note:: Building the kernel will take some time depending on the speed and
   quantity of your CPU/cores and disk speed. Expect 20 minutes
   (or even longer) on lower end hardware.

.. code-block:: none

  (18:59) vyos_bld 412374ca36b8:/vyos/vyos-build/packages/linux-kernel [current] # ./build-kernel.sh
  I: Copy Kernel config (x86_64_vyos_defconfig) to Kernel Source
  I: Apply Kernel patch: /vyos/vyos-build/packages/linux-kernel/patches/kernel/0001-VyOS-Add-linkstate-IP-device-attribute.patch
  patching file Documentation/networking/ip-sysctl.txt
  patching file include/linux/inetdevice.h
  patching file include/linux/ipv6.h
  patching file include/uapi/linux/ip.h
  patching file include/uapi/linux/ipv6.h
  patching file net/ipv4/devinet.c
  Hunk #1 succeeded at 2319 (offset 1 line).
  patching file net/ipv6/addrconf.c
  patching file net/ipv6/route.c
  I: Apply Kernel patch: /vyos/vyos-build/packages/linux-kernel/patches/kernel/0002-VyOS-add-inotify-support-for-stackable-filesystems-o.patch
  patching file fs/notify/inotify/Kconfig
  patching file fs/notify/inotify/inotify_user.c
  patching file fs/overlayfs/super.c
  Hunk #2 succeeded at 1713 (offset 9 lines).
  Hunk #3 succeeded at 1739 (offset 9 lines).
  Hunk #4 succeeded at 1762 (offset 9 lines).
  patching file include/linux/inotify.h
  I: Apply Kernel patch: /vyos/vyos-build/packages/linux-kernel/patches/kernel/0003-RFC-builddeb-add-linux-tools-package-with-perf.patch
  patching file scripts/package/builddeb
  I: make x86_64_vyos_defconfig
    HOSTCC  scripts/basic/fixdep
    HOSTCC  scripts/kconfig/conf.o
    YACC    scripts/kconfig/zconf.tab.c
    LEX     scripts/kconfig/zconf.lex.c
    HOSTCC  scripts/kconfig/zconf.tab.o
    HOSTLD  scripts/kconfig/conf
  #
  # configuration written to .config
  #
  I: Generate environment file containing Kernel variable
  I: Build Debian Kernel package
    UPD     include/config/kernel.release
  /bin/sh ./scripts/package/mkdebian
  dpkg-buildpackage -r"fakeroot -u" -a$(cat debian/arch) -b -nc -uc
  dpkg-buildpackage: info: source package linux-4.19.146-amd64-vyos
  dpkg-buildpackage: info: source version 4.19.146-1
  dpkg-buildpackage: info: source distribution buster
  dpkg-buildpackage: info: source changed by vyos_bld <christian@poessinger.com>
  dpkg-buildpackage: info: host architecture amd64
  dpkg-buildpackage: warning: debian/rules is not executable; fixing that
   dpkg-source --before-build .
   debian/rules build
  make KERNELRELEASE=4.19.146-amd64-vyos ARCH=x86         KBUILD_BUILD_VERSION=1 KBUILD_SRC=
    SYSTBL  arch/x86/include/generated/asm/syscalls_32.h

  ...

  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: binaries to analyze should already be installed in their package's directory
  dpkg-shlibdeps: warning: package could avoid a useless dependency if /vyos/vyos-build/packages/linux-kernel/linux/debian/toolstmp/usr/bin/trace /vyos/vyos-build/packages/linux-kernel/linux/debian/toolstmp/usr/bin/perf were not linked against libcrypto.so.1.1 (they use none of the library's symbols)
  dpkg-shlibdeps: warning: package could avoid a useless dependency if /vyos/vyos-build/packages/linux-kernel/linux/debian/toolstmp/usr/bin/trace /vyos/vyos-build/packages/linux-kernel/linux/debian/toolstmp/usr/bin/perf were not linked against libcrypt.so.1 (they use none of the library's symbols)
  dpkg-deb: building package 'linux-tools-4.19.146-amd64-vyos' in '../linux-tools-4.19.146-amd64-vyos_4.19.146-1_amd64.deb'.
   dpkg-genbuildinfo --build=binary
   dpkg-genchanges --build=binary >../linux-4.19.146-amd64-vyos_4.19.146-1_amd64.changes
  dpkg-genchanges: warning: package linux-image-4.19.146-amd64-vyos-dbg in control file but not in files list
  dpkg-genchanges: info: binary-only upload (no source code included)
   dpkg-source --after-build .
  dpkg-buildpackage: info: binary-only upload (no source included)


When complete, you will have kernel binary packages to use in your custom ISO
build. Place all ``*.deb`` files in the ``vyos-build/packages`` folder, where
the build process will use them automatically.

Firmware
^^^^^^^^

If you upgrade your kernel or include new drivers you may need new firmware.
This builds a new ``vyos-linux-firmware`` package using the included helper
scripts.

.. code-block:: none

  $ cd vyos-build/packages/linux-kernel
  $ git clone https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git
  $ ./build-linux-firmware.sh
  $ cp vyos-linux-firmware_*.deb ../

The script automatically detects which firmware blobs are needed based on the
built drivers. If detection fails, you can manually add files to
``vyos-build/packages/linux-kernel/build-linux-firmware.sh``:

.. code-block:: bash

  ADD_FW_FILES="iwlwifi* ath11k/QCA6390/*/*.bin"


Building Out-Of-Tree Modules
----------------------------

Building the kernel is one step. You must also build required out-of-tree
modules so the ABIs match. 
Refer to ``vyos-build/packages/linux-kernel/Jenkinsfile``
for all required modules and their versions. We show you how to build the
currently required modules.

Accel-PPP
^^^^^^^^^

First, clone the source code and check out the appropriate version:

.. code-block:: none

  $ cd vyos-build/packages/linux-kernel
  $ git clone https://github.com/accel-ppp/accel-ppp.git

Use the helper script and patches to build the package. Run the following
command:

.. code-block:: none

  $ ./build-accel-ppp.sh
  I: Build Accel-PPP Debian package
  CMake Deprecation Warning at CMakeLists.txt:3 (cmake_policy):
    The OLD behavior for policy CMP0003 will be removed from a future version
    of CMake.

    The cmake-policies(7) manual explains that the OLD behaviors of all
    policies are deprecated and that a policy should be set to OLD only under
    specific short-term circumstances.  Projects should be ported to the NEW
    behavior and not rely on setting a policy to OLD.

  -- The C compiler identification is GNU 8.3.0

  ...

  CPack: Create package using DEB
  CPack: Install projects
  CPack: - Run preinstall target for: accel-ppp
  CPack: - Install project: accel-ppp
  CPack: Create package
  CPack: - package: /vyos/vyos-build/packages/linux-kernel/accel-ppp/build/accel-ppp.deb generated.

After compiling the packages you will find yourself the newly generated `*.deb`
binaries in ``vyos-build/packages/linux-kernel`` from which you can copy them
to the ``vyos-build/packages`` folder for inclusion during the ISO build.

Intel NIC
^^^^^^^^^

The Intel NIC drivers do not come from a Git repository. VyOS fetches the
tarballs from a mirror and compiles them. Use the following wrapper script
to build all driver modules:

.. code-block:: none

  ./build-intel-drivers.sh
    % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                   Dload  Upload   Total   Spent    Left  Speed
  100  490k  100  490k    0     0   648k      0 --:--:-- --:--:-- --:--:--  648k
  I: Compile Kernel module for Intel ixgbe driver

  ...

  I: Building Debian package vyos-intel-iavf
  Doing `require 'backports'` is deprecated and will not load any backport in the next major release.
  Require just the needed backports instead, or 'backports/latest'.
  Debian packaging tools generally labels all files in /etc as config files, as mandated by policy, so fpm defaults to this behavior for deb packages. You can disable this default behavior with --deb-no-default-config-files flag {:level=>:warn}
  Created package {:path=>"vyos-intel-iavf_4.0.1-0_amd64.deb"}
  I: Cleanup iavf source

After compilation, find the generated ``*.deb`` binaries in
``vyos-build/packages/linux-kernel``. Copy them to the ``vyos-build/packages``
folder for inclusion in the ISO build.

Intel QAT
^^^^^^^^^

The Intel QAT (Quick Assist Technology) drivers do not come from a Git
repository. VyOS fetches the tarballs from ``01.org``, Intel's open-source
website.
Use the following wrapper script to build all driver modules:

.. code-block:: none

  $ ./build-intel-qat.sh
    % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                   Dload  Upload   Total   Spent    Left  Speed
  100 5065k  100 5065k    0     0  1157k      0  0:00:04  0:00:04 --:--:-- 1157k
  I: Compile Kernel module for Intel qat driver
  checking for a BSD-compatible install... /usr/bin/install -c
  checking whether build environment is sane... yes
  checking for a thread-safe mkdir -p... /bin/mkdir -p
  checking for gawk... gawk
  checking whether make sets $(MAKE)... yes

  ...

  I: Building Debian package vyos-intel-qat
  Doing `require 'backports'` is deprecated and will not load any backport in the next major release.
  Require just the needed backports instead, or 'backports/latest'.
  Debian packaging tools generally labels all files in /etc as config files, as mandated by policy, so fpm defaults to this behavior for deb packages. You can disable this default behavior with --deb-no-default-config-files flag {:level=>:warn}
  Created package {:path=>"vyos-intel-qat_1.7.l.4.9.0-00008-0_amd64.deb"}
  I: Cleanup qat source


After compiling the packages you will find yourself the newly generated `*.deb`
binaries in ``vyos-build/packages/linux-kernel`` from which you can copy them
to the ``vyos-build/packages`` folder for inclusion during the ISO build.

Packages
========

If you are brave enough to build your own ISO image with any modified package
from VyOS's GitHub organisation, this is the place for you.

Any modified package may be an altered version (e.g., ``vyos-1x``) that you
want to test before filing a pull request on GitHub.

Building an ISO with a customized package is the same as building a regular
ISO image. Place your modified ``*.deb`` package inside the ``packages`` folder
within ``vyos-build``. The build process will automatically use your custom
package during the ISO build.

Troubleshooting
===============

Debian APT does not provide verbose error messages. If your ISO build fails and
you suspect an APT dependencies or installation issue, you can apply this patch
to increase APT verbosity during the ISO build.

.. stop_vyoslinter

.. code-block:: diff

  diff --git i/scripts/live-build-config w/scripts/live-build-config
  index 1b3b454..3696e4e 100755
  --- i/scripts/live-build-config
  +++ w/scripts/live-build-config
  @@ -57,7 +57,8 @@ lb config noauto \
           --firmware-binary false \
           --updates true \
           --security true \
  -        --apt-options "--yes -oAcquire::Check-Valid-Until=false" \
  +        --apt-options "--yes -oAcquire::Check-Valid-Until=false -oDebug::BuildDeps=true -oDebug::pkgDepCache::AutoInstall=true \
  +                             -oDebug::pkgDepCache::Marker=true -oDebug::pkgProblemResolver=true -oDebug::Acquire::gpgv=true" \
           --apt-indices false
           "${@}"
   """

.. start_vyoslinter

.. _build_packages:

********
Packages
********

VyOS comes with specific packages that cannot be found in any
Debian mirror. These packages are located in the `VyOS GitHub project`_ in
source format and can easily be compiled into custom
Debian (``*.deb``) packages.

The easiest way to compile your package is with the :ref:`build_docker`
container mentioned earlier, as it includes all required dependencies for all
VyOS related packages.

Assuming you want to build the ``vyos-1x`` package and modify it for your needs,
first clone the repository from GitHub:

.. code-block:: none

  $ git clone --recurse-submodules https://github.com/vyos/vyos-1x

Build
=====

Launch the Docker container and build the package:

.. code-block:: none

  # For VyOS 1.3 (equuleus, current)
  $ docker run --rm -it --privileged -v $(pwd):/vyos -w /vyos vyos/vyos-build:current bash

  # Change to source directory
  $ cd vyos-1x

  # Build DEB
  $ dpkg-buildpackage -uc -us -tc -b

After a minute or two, the generated DEB packages are located next to the
``vyos-1x`` source directory:

.. code-block:: none

  # ls -al ../vyos-1x*.deb
  -rw-r--r-- 1 vyos_bld vyos_bld 567420 Aug  3 12:01 ../vyos-1x_1.3dev0-1847-gb6dcb0a8_all.deb
  -rw-r--r-- 1 vyos_bld vyos_bld   3808 Aug  3 12:01 ../vyos-1x-vmware_1.3dev0-1847-gb6dcb0a8_amd64.deb

Install
=======

To test your newly created package, you can SCP it to a running VyOS instance
and install the new ``*.deb`` package to replace the current one.

Install the package using the following commands:

.. code-block:: none

  vyos@vyos:~$ dpkg --install /tmp/vyos-1x_1.3dev0-1847-gb6dcb0a8_all.deb
  (Reading database ... 58209 files and directories currently installed.)
  Preparing to unpack .../vyos-1x_1.3dev0-1847-gb6dcb0a8_all.deb ...
  Unpacking vyos-1x (1.3dev0-1847-gb6dcb0a8) over (1.3dev0-1847-gb6dcb0a8) ...
  Setting up vyos-1x (1.3dev0-1847-gb6dcb0a8) ...
  Processing triggers for rsyslog (8.1901.0-1) ...

You can also place the generated ``*.deb`` in your ISO build environment to
include it in a custom ISO. See :ref:`build_custom_packages` for more
information.

.. warning:: Any packages in the ``packages`` directory will be added to the
   ISO during the build, replacing upstream packages. Delete both the source
   directories and built DEB packages if you want to build an ISO from purely
   upstream packages.


.. stop_vyoslinter

.. _Docker: https://docs.docker.com/engine/install/debian/
.. _`Docker as non-root`: https://docs.docker.com/engine/install/linux-postinstall
.. _VyOS DockerHub organisation: https://hub.docker.com/u/vyos
.. _repository: https://github.com/vyos/vyos-build
.. _VyOS GitHub project: https://github.com/vyos

.. start_vyoslinter

