:lastproofread: 2026-01-30

.. _upstream_packages:

#################
Upstream Packages
#################

Many base system packages are pulled straight from Debian's ``main`` and
``contrib`` repositories, but there are exceptions. If you only want to build
a fresh ISO image, you can skip
this section. This information may be useful for a deeper dive into VyOS.


.. stop_vyoslinter

System packages that are not directly pulled from Debian are built through a 
separate build system, ``build.py`` in the `vyos-build <https://github.com/vyos/vyos-build/tree/current/scripts/package-build>`__ repository.

.. start_vyoslinter


Overview
========

Previously, VyOS used Jenkins for building upstream packages. With the move away 
from Jenkins, the build system was replaced with a Python-based solution using 
``build.py`` and ``package.toml`` configuration files.

Each package directory contains:

- A ``package.toml`` configuration file that defines how the package is built.
- A symlink to the common ``build.py`` script in the build system.


Building Packages
=================

To build a package, navigate to the package directory and execute the 
build script:

.. code-block:: console

   cd package-build/<package-name>
   ./build.py

The script will:

1. Check out the source code from the configured repository.
2. Apply any patches defined in the configuration.
3. Execute pre-build hooks (if configured).
4. Build the package using the specified build command.
5. Generate both binary (``.deb``) packages and source tarballs.


Package Configuration (package.toml)
====================================

Each package directory contains a ``package.toml`` file that defines the build 
parameters. The key configuration fields are:

**name**
   The package name (e.g., ``frr``)

**commit_id**
   The specific commit, tag, or branch to check out from the source repository
   (e.g., ``stable/10.5``)

**scm_url**
   The Git URL of the upstream source repository
   (e.g., ``https://github.com/FRRouting/frr.git``)

.. stop_vyoslinter
**build_cmd**
   The command to execute for building the package. This replaces what was 
   previously defined in the Jenkins ``Jenkinsfile``.

   Default if not specified: ``dpkg-buildpackage -uc -us -tc -F --source-option=--tar-ignore=.git --source-option=--tar-ignore=.github``

   Example with custom build command:

   .. code-block:: toml

      build_cmd = "sudo dpkg -i ../*.deb; dpkg-buildpackage -us -uc -tc -b -Ppkg.frr.rtrlib,pkg.frr.lua"
.. start_vyoslinter

**pre_build_hook** (Optional)
   A shell command or script that executes after the repository is checked out 
   and before the build process begins. This allows you to perform preparatory 
   tasks such as:

   - Creating directories
   - Copying files
   - Running custom setup scripts
   - Installing dependencies

   Single command example:

   .. code-block:: toml

      pre_build_hook = "echo 'Preparing build environment'"

   Multi-line commands example:

   .. code-block:: toml

      pre_build_hook = """
        mkdir -p ../hello/vyos
        mkdir -p ../vyos
        cp example.txt ../vyos
      """

   Combined commands and scripts:

   .. code-block:: toml

      pre_build_hook = "ls -l; ./script.sh"

**apply_patches** (Optional)
   Boolean flag to control whether patches should be applied. Defaults to
   ``True``.

   .. code-block:: toml

      apply_patches = false

**prepare_package** (Optional)
   Boolean flag to enable package preparation. When set to ``True``, the 
   ``install_data`` configuration is used.

**install_data** (Optional)
   Data used for package preparation when ``prepare_package`` is enabled.


Example package.toml file
===========================

Here's an example configuration for the FRRouting (FRR) package:

.. code-block:: toml

   name = "frr"
   commit_id = "stable/10.5"
   scm_url = "https://github.com/FRRouting/frr.git"
   build_cmd = "sudo dpkg -i ../*.deb; dpkg-buildpackage -us -uc -tc -b -Ppkg.frr.rtrlib,pkg.frr.lua"


Build Output
============

After running ``./build.py``, the following artifacts are generated in the 
package directory:

- ``.deb`` files - Binary Debian packages ready for installation
- ``.tar.gz`` files - Source tarballs of the checked-out repositories
- Additional build artifacts as produced by the Debian build system

The build script also creates build dependency packages (`*build-deps*.deb`), 
which are automatically cleaned up after the build completes.
