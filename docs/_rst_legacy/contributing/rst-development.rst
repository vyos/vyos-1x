:lastproofread: 2025-12-12

.. _development:

###########
Development
###########

Learn how to contribute to VyOS.

.. _architecture_overview:

Architecture overview
=====================
VyOS source code is hosted on GitHub in the VyOS organization:
https://github.com/vyos

VyOS is composed of multiple modules spread across different
repositories. Some modules contain forks of upstream
packages and are periodically synced. 
VyOS consolidates most packages into the
`vyos-1x <https://github.com/vyos/vyos-1x>`__
repository while maintaining a consistent structure. 
The base code is being rewritten
from Perl and Bash to Python using an XML-based CLI interface definition.

VyOS ISO build scripts are hosted in the
`vyos-build <https://github.com/vyos/vyos-build>`__ repository. See the
``vyos-build`` repository
`README.md file <https://github.com/vyos/vyos-build/blob/current/README.md>`__
for more information on building VyOS ISO images.

Contributing code
=================

.. warning::

  You must sign the :doc:`Contributor License Agreement<cla>`
  for your contributions to be accepted.

VyOS is open-source and welcomes patches.
All submissions must adhere to these guidelines:

* Each commit addresses a single issue or feature.
* Each commit message references a Phabricator_ task ID
  (for example, ``T1234``).
* Each commit is associated with a username and email address
  to identify the author (see `Configure your Git identity`_).
* Only submit bugfixes in packages other than https://github.com/vyos/vyos-1x.
* Commits follow the `coding guidelines`_ outlined below.


Determining package ownership
-----------------------------

To determine which VyOS package contains a file you want to modify, use Debian's
``dpkg -S`` command on your running VyOS installation.

Submitting your code
--------------------

Fork the repository and submit a GitHub pull request. This is the preferred way
to contribute changes to VyOS.

To fork a VyOS repository:

1. Append ``/fork`` to the repository URL on GitHub. For example, to fork
   ``vyos-1x``, use: https://github.com/vyos/vyos-1x/fork

2. Clone your fork or add it as a remote to your local repository:

   - Clone: ``git clone https://github.com/<user>/vyos-1x.git``
   - Add remote: ``git remote add myfork https://github.com/<user>/vyos-1x.git``

.. _Configure your Git identity:

3. Configure your Git identity:

   .. code-block:: none

     git config --global user.name "J. Random Hacker"
     git config --global user.email "jrhacker@example.net"

4. Make your changes and add files to the Git index:

   - Single file: ``git add myfile``
   - Directory: ``git add somedir/*``

5. Commit your changes with a meaningful headline and Phabricator_ reference:

   ``git commit``

6. Push to your fork and create a GitHub pull request:

   ``git push``

Alternatively, you can export commits as patches and send them to
maintainers@vyos.net or attach them directly to the Phabricator_ task:

* Export last commit: ``git format-patch``
* Export last two commits: ``git format-patch -2``

Commit messages
===============

For guidance on writing commit messages, review the file history
with ``git log path/to/file.txt``.

Every change must be associated with a task number (prefixed with **T**) and
a component. If no bug report or feature request exists for your changes,
create a Phabricator_ task first. Reference the task ID in your commit message:

* ``ddclient: T1030: auto create runtime directories``
* ``Jenkins: add current Git commit ID to build description``

If your pull request lacks a Phabricator_ reference, maintainers will request
that you amend the commit message.

Writing good commit messages
-----------------------------

Follow the format described in
the `Git documentation <https://git-scm.com/book/ch5-2.html>`__
and `Chris Beams' guide <https://chris.beams.io/posts/git-commit/>`__.

Commit message format:

1. **Summary line** (50 characters recommended, 80 maximum): Include the
   component
   prefix and Phabricator_ reference (for example, ``snmp: T1111:`` or
   ``ethernet: T2222:``). Concatenate multiple components with colons
   (for example, ``snmp: ethernet: T3333``).

2. **Blank line**: Separate the summary from the body. 
   This blank line is critical.

4. **Message body** with details:

   * Describe what changed, why, and how. This helps with ``git bisect``.
   * Wrap text at 72 characters for readability with ``git log`` on an 80x25
     terminal.
   * Reference previous commits when applicable:
     ``After commit abcd12ef ("snmp: this is a headline")
     a Python import statement is missing, throwing the following exception:
     ABCDEF``

5. **Cherry-pick option**: Always use the ``-x`` option when back-porting or
   forward-porting commits:

   ``git cherry-pick -x <commit>``

   This appends ``(cherry picked from commit <ID>)`` to the commit message,
   making bisecting easier.

6. **Single responsibility**: Each commit must be self-contained. Do not fix
   multiple bugs in a single commit. Use ``git add --patch`` to stage only
   the parts related to one issue.

Constraints:

* Bugfixes are only accepted for packages other than
  https://github.com/vyos/vyos-1x.
  New functionality must use the new XML/Python interface, not old-style
  templates (``node.def`` files and Perl/Bash code).

Coding guidelines
=================

VyOS maintains consistent coding standards to help contributors navigate the
codebase and understand its logic.

Formatting
----------

* **Python**: Use 4 spaces per indentation level. Tabs **must not** be used.
* **XML**: Use 2 spaces per indentation level. Tabs **must not** be used.

Use tools like VIM extensions (xmllint) to enforce correct indentation. Add this
to your ``.vimrc`` file:

.. code-block:: none

  au FileType xml setlocal equalprg=xmllint\ --format\ --recover\ -\ 2>/dev/null

Then use ``gg=G`` in command mode to run the linter.

Text generation
---------------

Use a template processor for generating config files:

* **Jinja2** is the default template processor for VyOS code.
* Built-in string formatting **may** be used for simple line-oriented formats
  (for example, iptables rules) where every line is self-contained.
* Template processors **must** be used for structured, multi-line formats
  (for example, ISC DHCPd configuration).

Python code
-----------

Configuration scripts and operation mode scripts written in Python3 should
follow these guidelines:

* Wrap lines at 80 characters. This improves readability when browsing
  GitHub on mobile devices and reads well in side-by-side diffs.

Structure your scripts with these functions:

.. code-block:: python

  #!/usr/bin/env python3
  #
  # Copyright (C) 2020 VyOS maintainers and contributors
  #
  # This program is free software; you can redistribute it and/or modify
  # it under the terms of the GNU General Public License version 2 or later as
  # published by the Free Software Foundation.
  #
  # This program is distributed in the hope that it will be useful,
  # but WITHOUT ANY WARRANTY; without even the implied warranty of
  # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
  # GNU General Public License for more details.
  #
  # You should have received a copy of the GNU General Public License
  # along with this program.  If not, see <http://www.gnu.org/licenses/>.

  import sys

  from vyos.config import Config
  from vyos import ConfigError

  def get_config(config=None):
      if config:
          conf = config
      else:
          conf = Config()

      # Base path to CLI nodes
      base = ['...', '...']
      # Convert the VyOS config to an abstract internal representation
      config_data = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
      return config_data

  def verify(config):
      # Verify that configuration is valid
      if invalid:
          raise ConfigError("Descriptive message")

  def generate(config):
      # Generate daemon configs
      pass

  def apply(config):
      # Apply the generated configs to the live system
      pass

  try:
      c = get_config()
      verify(c)
      generate(c)
      apply(c)
  except ConfigError as e:
      print(e)
      sys.exit(1)

``get_config()``: This function converts a VyOS config object to an abstract
internal representation. No other function may call the ``vyos.config.Config``
object directly. Limiting config reads to one function makes it easier to
modify the config syntax in the future. Additionally, this design improves
testability since you can construct an internal representation by hand rather
than mocking the entire config subsystem.

``verify()``: This function validates the internal representation. It must
raise ``ConfigError`` with a descriptive message if the config is invalid. It
**must not** make any changes to the system. This design enables future features
like commit dry-run ("commit test" as in JunOS) where the system can abort a
commit before making changes.

``generate()``: This function generates config files for system components.

``apply()``: This function applies the generated configuration to the live
system. Prefer non-disruptive reload when possible. Disruptive operations like
daemon restarts are acceptable only when:

* The component does not support non-disruptive reload, or
* The expected service degradation is minimal (for example, auxiliary services
  like LLDPd)

For high-impact services (VPN daemons, routing protocols), make effort to
determine if changes can be applied non-disruptively before resorting to
restarts.

Never modify active configuration directly unless absolutely necessary. Instead,
generate configuration files and apply them with a single command like service
reload through systemd. For example, save iptables rules to a file and load them
with ``iptables-restore`` rather than executing iptables commands one by one.

The ``apply()`` and ``generate()`` functions may raise ``ConfigError`` if the
daemon fails to start with the updated config. However, this is not a substitute
for proper config validation in the ``verify()`` function. Make reasonable
effort to verify that generated configuration is valid and will be accepted by
the daemon, including cross-checks with other VyOS configuration subtrees when
necessary.

Exceptions like ``VyOSError`` (raised by ``vyos.config.Config`` on improper
operations) should not be silenced or caught. While this may produce less
polished error output for users, it generates better bug reports and helps
maintainers debug issues.

For reference implementations, see ``ntp.py`` or ``interfaces-bonding.py`` (for
tag nodes) in the `vyos-1x <https://github.com/vyos/vyos-1x>`__ repository.

Other considerations: ``vyos-configd``
--------------------------------------

All scripts now run under the config daemon and must conform to these
requirements:

1. The signature and first four lines of ``get_config(...)`` **must** be as
   specified above.

2. Each of ``get_config``, ``verify``, ``apply``, and ``generate`` **must**
   appear
   with the correct signatures, even if they are a no-op.

3. ``Config`` objects other than those in ``get_config`` **must not** appear.

4. The legacy function ``my_set`` **must not** appear. Modifications to active
   config **should not** appear in new code (alternative mechanisms may be used
   if absolutely necessary).

XML for CLI definitions
=======================

XML interface definitions define the VyOS CLI structure. 
Before VyOS ``1.2`` (crux), these
files were created manually. After a redesign, new-style templates are
automatically generated from XML input files.

VyOS interface definitions come with a RelaxNG schema located in the
`vyos-1x <https://github.com/vyos/vyos-1x/tree/current/schema>`__
repository. This schema is a modified version from ``VyConf`` (VyOS ``2.0``).
VyOS ``1.2.x``
interface definitions are reusable in future VyOS versions with minimal changes.

Schemas provide two benefits:

* Complete grammar verification
* Automatic validation against the schema

.. stop_vyoslinter
The `build-command-templates <https://github.com/vyos/vyos-1x/blob/current/scripts/build-command-templates>`__
script converts XML definitions to
old-style templates and verifies them against the schema. A bad definition
causes the package build to fail. While the XML format is verbose, no other
format provides this level of verification. Specialized XML editors can help
manage verbosity.
.. start_vyoslinter

Example XML interface definition:

.. code-block:: xml

  <?xml version="1.0"?>
  <!-- Cron configuration -->
  <interfaceDefinition>
    <node name="system">
      <children>
        <node name="task-scheduler">
          <properties>
            <help>Task scheduler settings</help>
          </properties>
          <children>
            <tagNode name="task" owner="${vyos_conf_scripts_dir}/task_scheduler.py">
              <properties>
                <help>Scheduled task</help>
                <valueHelp>
                  <format>&lt;string&gt;</format>
                  <description>Task name</description>
                </valueHelp>
                <priority>999</priority>
              </properties>
              <children>
                <leafNode name="crontab-spec">
                  <properties>
                    <help>UNIX crontab time specification string</help>
                  </properties>
                </leafNode>
                <leafNode name="interval">
                  <properties>
                    <help>Execution interval</help>
                    <valueHelp>
                      <format>&lt;minutes&gt;</format>
                      <description>Execution interval in minutes</description>
                    </valueHelp>
                    <valueHelp>
                      <format>&lt;minutes&gt;m</format>
                      <description>Execution interval in minutes</description>
                    </valueHelp>
                    <valueHelp>
                      <format>&lt;hours&gt;h</format>
                      <description>Execution interval in hours</description>
                    </valueHelp>
                    <valueHelp>
                      <format>&lt;days&gt;d</format>
                      <description>Execution interval in days</description>
                    </valueHelp>
                    <constraint>
                      <regex>[1-9]([0-9]*)([mhd]{0,1})</regex>
                    </constraint>
                  </properties>
                </leafNode>
                <node name="executable">
                  <properties>
                    <help>Executable path and arguments</help>
                  </properties>
                  <children>
                    <leafNode name="path">
                      <properties>
                        <help>Path to executable</help>
                      </properties>
                    </leafNode>
                    <leafNode name="arguments">
                      <properties>
                        <help>Arguments passed to the executable</help>
                      </properties>
                    </leafNode>
                  </children>
                </node>
              </children>
            </tagNode>
          </children>
        </node>
      </children>
    </node>
  </interfaceDefinition>

XML definitions are purely declarative and contain no logic. All logic for
generating config files, restarting services, and related tasks is implemented
in configuration scripts.

Template Processors
-------------------

XML interface definition files use the ``.xml.in`` file extension (implemented
in :vytask:`T1843`). These files use the GCC preprocessor to reduce code
duplication in common areas:

* VIF (including VIF-S and VIF-C)
* Address configuration
* Description
* Enabled/Disabled state

Instead of repeating XML nodes, use include files with predefined features:

.. stop_vyoslinter

* `IPv4, IPv6, and DHCP(v6) <https://github.com/vyos/vyos-1x/blob/current/interface-definitions/include/interface/address-ipv4-ipv6-dhcp.xml.i>`__
  address assignment.
* `IPv4 and IPv6 <https://github.com/vyos/vyos-1x/blob/current/interface-definitions/include/interface/address-ipv4-ipv6.xml.i>`__
  address assignment.
* `VLAN (VIF) <https://github.com/vyos/vyos-1x/blob/current/interface-definitions/include/accel-ppp/vlan.xml.i>`__
  definition.
* `MAC address <https://github.com/vyos/vyos-1x/blob/current/interface-definitions/include/firewall/mac-address.xml.i>`__
  assignment.


The ``.in`` files are preprocessed and stored in the `interface-definitions <https://github.com/vyos/vyos-1x/tree/current/interface-definitions>`__
folder. The `scripts/build-command-templates <https://github.com/vyos/vyos-1x/blob/current/scripts/build-command-templates>`__
script then operates on this folder to generate all required CLI nodes.

.. start_vyoslinter

Example preprocessor output:

.. code-block:: none

  $ make interface_definitions
  install -d -m 0755 build/interface-definitions
  install -d -m 0755 build/op-mode-definitions
  Generating build/interface-definitions/intel_qat.xml from interface-definitions/intel_qat.xml.in
  Generating build/interface-definitions/interfaces-bonding.xml from interface-definitions/interfaces-bonding.xml.in
  Generating build/interface-definitions/cron.xml from interface-definitions/cron.xml.in
  Generating build/interface-definitions/pppoe-server.xml from interface-definitions/pppoe-server.xml.in
  Generating build/interface-definitions/mdns-repeater.xml from interface-definitions/mdns-repeater.xml.in
  Generating build/interface-definitions/tftp-server.xml from interface-definitions/tftp-server.xml.in
  [...]

Command Definition Guidelines
------------------------------

Use of Numbers
^^^^^^^^^^^^^^

Avoid using numbers in command names unless the number is part of a protocol
name or similar. For example, ``protocols ospfv3`` is appropriate,
but ``server-1`` is questionable.

Help Strings
^^^^^^^^^^^^

Follow these guidelines for consistent, readable help strings:

Capitalization and Punctuation
""""""""""""""""""""""""""""""

* Capitalize the first word of every help string.
* Do not use a period at the end of help strings.

This standard mirrors network device CLIs and improves aesthetics.

Examples:

* Good: "Frobnication algorithm"
* Bad: "frobnication algorithm"
* Bad: "Frobnication algorithm."
* Incorrect: "frobnication algorithm."

Abbreviations and Acronyms
""""""""""""""""""""""""""

* Capitalize all abbreviations and acronyms.

Examples:

* Good: "TCP connection timeout"
* Bad: "tcp connection timeout"
* Bad: "Tcp connection timeout"

* Capitalize acronyms to distinguish them from normal words.

Examples:

* Good: RADIUS (remote authentication for dial-in user services)
* Bad: radius (unless referring to circular distance)

* Follow accepted spelling conventions for mixed-case abbreviations. If it
  contains "over" or "version", use lowercase. Follow RFC or standard spellings
  when they exist.

Examples:

* Good: PPPoE, IPsec
* Bad: PPPOE, IPSEC
* Bad: pppoe, ipsec

Verbs
"""""

* Avoid verbs. If a verb can be omitted, omit it.

Examples:

* Good: "TCP connection timeout"
* Bad: "Set TCP connection timeout"

* When a verb is essential, use it. For example: "Disable IPv6 forwarding on
  all interfaces" for ``set system ipv6 disable-forwarding``.

* Use infinitive form for necessary verbs.

Examples:

* Good: "Disable IPv6 forwarding"
* Bad: "Disables IPv6 forwarding"


C++ Backend Code
================

The VyOS CLI parser combines bash, bash-completion helpers, and the C++ backend
library `vyatta-cfg <https://github.com/vyos/vyatta-cfg>`__. This section
references common CLI commands and their C/C++ entry points:

``set``:

.. stop_vyoslinter

* https://github.com/vyos/vyatta-cfg/blob/0f42786a0b3/src/cstore/cstore.cpp#L352
* https://github.com/vyos/vyatta-cfg/blob/0f42786a0b3/src/cstore/cstore.cpp#L2549

``commit``:

* https://github.com/vyos/vyatta-cfg/blob/0f42786a0b3/src/commit/commit-algorithm.cpp#L1252

.. include:: /_include/common-references.txt

.. start_vyoslinter
