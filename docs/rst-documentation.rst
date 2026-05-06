:lastproofread: 2021-06-25

.. _documentation:

###################
Write Documentation
###################

We encourage every VyOS user to help us improve our documentation as we have
a deficit like most software projects.  This not only helps you when reading
but also everyone else.

.. warning::

  Please read and sign the
  :doc:`Contributor License Agreement<contributing/cla>` before submitting any
  documentation updates.

If you are willing to contribute to our documentation this is the definite
guide how to do so.

.. note:: In contrast to submitting code patches, there is no requirement that
   you open up a Phabricator_ task prior to submitting a Pull-Request to the
   documentation.

VyOS documentation is written in reStructuredText and generated to Read the Docs
pages with Sphinx, as per the Python tradition. We welcome all sorts of
contributions to the documentation.
Not just new additions but also corrections to existing documentation.

The documentation source is kept in the Git repository at
https://github.com/vyos/vyos-documentation and you can follow the instructions
in the README.md_ to build and test your changes.

You can either install Sphinx and build the documentation locally,
or use the Dockerfile_ to build it in a container.

Guidelines
==========

There are a few things to keep in mind when contributing to the
documentation, for the sake of consistency and readability.


The following is a quick summary of the rules:

- Use American English at all times. It's always a good idea to run
  your text through a grammar and spell checker, such as `Grammarly`_.
- Don't forget to update ``index.rst`` when adding a new node.
- Try not to exceed 80 characters per line, but don't break URLs over this.
- Properly quote commands, filenames and brief code snippets with double backticks.
- Use literal blocks for longer snippets.
- Leave a newline before and after a header.
- Indent with two spaces.
- When in doubt, follow the style of existing documentation.

And finally, remember that the reStructuredText files aren't
exclusively for generating HTML and PDF. They should be human-readable
and easily perused from a console.

Page content
============

All RST files must follow the same TOC Level syntax and have to start with

.. code-block::

   #####
   Title
   #####

The configuration mode folder and the articles cover the specific level of
the commands. The exact level depends on the command. This should provide
stability for URLs used in the forum or blogpost.

For example:

  * ``set firewall zone`` is written in ``firewall/zone.rst``
  * ``set interfaces ethernet`` is written in ``interfaces/ethernet.rst``

In the configuration part of the page, all possible configuration options
should be documented. Use ``.. cfgcmd::`` described above.

Related operation command must be documented in the next part of the article.
Use ``::opcmd..`` for these commands.

Each page must contain the following parts:

1. Theoretical information
--------------------------

Theoretical information required for users to understand the next document sections:

  - a simple explanation of what is this page about, why or when it is required to be used
  - references to standards, RFCs

2. Configuration description
----------------------------

    Describe CLI items related to the service or use case. Each config line
    or section must be explained, using information provided in the 1st part
    of the page.

3. Configuration examples
-------------------------

    Practical examples of the service or use case configuration. They must
    contain topology maps (if applicable) and short descriptions.

4. Known issues
---------------

This section must contain a list of:

  - known issues or potential problems for the service or use case
  - workarounds for known issues (if any exist)

5. Debugging
------------

Described procedures for debugging a service:

  - how to collect logs or other debugging information (like `show` commands output)
  - how to read and what to search for in logs and collected information
  - what are indicators of good and bad states in debugging outputs



Style Guide
===========

Formatting and Sphinxmarkup
---------------------------

TOC Level
^^^^^^^^^^

We use the following syntax for Headlines.

.. code-block:: none

  #####
  Title
  #####

  ********
  Chapters
  ********

  Sections
  ========

  Subsections
  -----------

  Subsubsections
  ^^^^^^^^^^^^^^

  Paragraphs
  """"""""""

Cross-References
^^^^^^^^^^^^^^^^

A plugin will be used to generate a reference label for each headline.
To reference a page or a section in the documentation use the
``:ref:`` command.

For example, you want to reference the headline **VLAN** in the
**ethernet.rst** page. The plugin generates the label based on
the headline and the file path.

``:ref:`configuration/interfaces/ethernet:vlan``

to use an alternative hyperlink use it this way:

``:ref:`Check out VLAN<configuration/interfaces/ethernet:vlan>``

handle build errors
"""""""""""""""""""

The plugin will warn on build if a headline has a duplicate name in the
same document. To prevent this warning, you have to put a custom link on
top of the headline.

.. code-block:: none

   Section A
   ==========

   Lorem ipsum dolor sit amet, consetetur sadipscing elitr

   Example
   -------

   Lorem ipsum dolor sit amet, consetetur sadipscing elitr

   Section B
   ==========

   Lorem ipsum dolor sit amet, consetetur sadipscing elitr

   .. _section B example:

   Example
   -------

   Lorem ipsum dolor sit amet, consetetur sadipscing elitr


Address space
^^^^^^^^^^^^^

Note the following RFCs (:rfc:`5737`, :rfc:`3849`, :rfc:`5389` and
:rfc:`7042`), which describe the reserved public IP addresses and autonomous
system numbers for the documentation:

  * ``192.0.2.0/24``
  * ``198.51.100.0/24``
  * ``203.0.113.0/24``
  * ``2001:db8::/32``
  * 16bit ASN: ``64496 - 64511``
  * 32bit ASN: ``65536 - 65551``
  * Unicast MAC Addresses: ``00-53-00`` to ``00-53-FF``
  * Multicast MAC-Addresses: ``90-10-00`` to ``90-10-FF``

Please do not use other public address space.


Line length
^^^^^^^^^^^

Limit all lines to a maximum of 80 characters.

Except in ``.. code-block::`` because it uses the html tag ``<pre>`` and
renders the same line format from the source rst file.


Autolinter
^^^^^^^^^^

Each GitHub pull request is automatically linted to check the address space and
line length.

Sometimes it is necessary to provide real IP addresses like in the
:ref:`examples`. For this, please use the sphinx comment syntax
``.. stop_vyoslinter`` to stop the linter and ``.. start_vyoslinter`` to start.


Custom Sphinx-doc Markup
^^^^^^^^^^^^^^^^^^^^^^^^

Custom commands have been developed for writing the documentation. Please
make yourself comfortable with those commands as this eases the way we
render the documentation.

cfgcmd
""""""

When documenting CLI commands, use the ``.. cfgcmd::`` directive
for all configuration mode commands. An explanation of the described command
should be added below this statement.
Replace all variable contents with <value> or something similar.

With those custom commands, it will be possible to render them in a more
descriptive way in the resulting HTML/PDF manual.

.. code-block:: none

  .. cfgcmd:: protocols static arp <ipaddress> hwaddr <macaddress>

     This will configure a static ARP entry, always resolving `192.0.2.100` to
     `00:53:27:de:23:aa`.

For an inline configuration level command, use ``:cfgcmd:``

.. code-block:: none

  :cfgcmd:`set interface ethernet eth0`


To extract a defaultvalue from the XML definitions add a ``:defaultvalue:``
to ``.. cfgcmd::`` directive.
To have this feature locally, the vyos-1x submodule must be initialized before.
Please be aware to not update the submodule in your PR.

.. code-block:: none

  .. cfgcmd:: set system conntrack table-size <1-50000000>
      :defaultvalue:

      The connection tracking table contains one entry for each connection being
      tracked by the system.


opcmd
"""""

When documenting operational level commands, use the ``.. opcmd::`` directive.
An explanation of the described command should be added below this statement.

With those custom commands, it is possible to render them in a more
descriptive way in the resulting HTML/PDF manual.

.. code-block:: none

  .. opcmd:: show protocols static arp

     Display all known ARP table entries spanning across all interfaces

For an inline operational level command, use ``:opcmd:``

.. code-block:: none

  :opcmd:`add system image`

cmdinclude
""""""""""

To minimize redundancy, there is a special include directive. It includes a txt
file and replace the ``{{ var0 }}`` - ``{{ var9 }}`` with the correct value.

.. code-block:: none

   .. cmdinclude:: /_include/interface-address.txt
      :var0: ethernet
      :var1: eth1

the content of interface-address.txt looks like this

.. code-block:: none

   .. cfgcmd:: set interfaces {{ var0 }} <interface> address <address | dhcp |
      dhcpv6>

      Configure interface `<interface>` with one or more interface
      addresses.

      * **address** can be specified multiple times as IPv4 and/or IPv6
      address, e.g. 192.0.2.1/24 and/or 2001:db8::1/64
      * **dhcp** interface address is received by DHCP from a DHCP server
      on this segment.
      * **dhcpv6** interface address is received by DHCPv6 from a DHCPv6
      server on this segment.

      Example:

      .. code-block:: none

         set interfaces {{ var0 }} {{ var1 }} address 192.0.2.1/24
         set interfaces {{ var0 }} {{ var1 }} address 192.0.2.2/24
         set interfaces {{ var0 }} {{ var1 }} address 2001:db8::ffff/64
         set interfaces {{ var0 }} {{ var1 }} address 2001:db8:100::ffff/64

vytask
""""""

When referencing to VyOS Phabricator Tasks, there is a custom Sphinx Markup
command called ``vytask`` that automatically renders to a proper Phabricator
URL. This is heavily used in the :ref:`release-notes` section.

.. code-block:: none

  * :vytask:`T1605` Fixed regression in L2TP/IPsec server
  * :vytask:`T1613` Netflow/sFlow captures IPv6 traffic correctly


Forking Workflow
================

The Forking Workflow is fundamentally different from other popular Git
workflows. Instead of using a single server-side repository to act as the
"central" codebase, it gives every developer their own server-side repository.
This means that each contributor has not one, but two Git repositories: a
private local one and a public server-side one.

The main advantage of the Forking Workflow is that contributions can be
integrated without the need for everybody to push to a single central
repository. Developers push to their own server-side repositories, and only the
project maintainer can push to the official repository. This allows the
maintainer to accept commits from any developer without giving them write
access to the official codebase.

.. note:: Updates to our documentation should be delivered by a GitHub
   pull-request. This requires you already have a GitHub account.

* Fork this project on GitHub https://github.com/vyos/vyos-documentation/fork

* Clone fork to local machine, then change to that directory
  ``$ cd vyos-documentation``

* Install the requirements ``$ pip install -r requirements.txt``
  (or something similar)

* Create a new branch for your work, use a descriptive name of your work:
  ``$ git checkout -b <branch-name>``

* Make all your changes - please keep our commit rules in mind
  (:ref:`prepare_commit`). This mainly applies to proper commit messages
  describing your change (how and why). Please check out the documentation of
  Sphinx-doc_ or reStructuredText_ if you are not familiar with it. This is used
  for writing our docs. Additional directives how to write in RST can be
  obtained from reStructuredTextDirectives_.

* Check your changes by locally building the documentation ``$ make livehtml``.
  Sphinx will build the html files in the ``docs/_build`` folder. We provide
  you with a Docker container for an easy-to-use user experience. Check the
  README.md_ file of this repository.

* View modified files by calling ``$ git status``. You will get an overview of
  all files modified by you. You can add individual files to the Git Index in
  the next step.

* Add modified files to Git index ``$ git add path/to/filename`` or add all
  unstaged files ``$ git add .``. All files added to the Git index will be part
  of you following Git commit.

* Commit your changes with the message, ``$ git commit -m "<commit message>"``
  or  use ``$ git commit -v`` to have your configured editor launched. You can
  type in a commit message. Again please make yourself comfortable without
  rules (:ref:`prepare_commit`).

* Push commits to your GitHub project: ``$ git push -u origin <branch-name>``

* Submit pull-request. In GitHub visit the main repository and you should
  see a banner suggesting to make a pull request. Fill out the form and
  describe what you do.

* Once pull requests have been approved, you may want to locally update
  your forked repository too. First you'll have to add a second remote
  called `upstream` which points to our main repository. ``$ git remote add
  upstream https://github.com/vyos/vyos-documentation.git``

  Check your configured remote repositories:

  .. code-block:: none

    $ git remote -v
    origin    https://github.com/<username>/vyos-documentation.git (fetch)
    origin    https://github.com/<username>/vyos.documentation.git (push)
    upstream  https://github.com/vyos/vyos-documentation.git (fetch)
    upstream  https://github.com/vyos/vyos-documentation.git (push)

  Your remote repo on Github is called ``origin``, while the original repo you
  have forked is called ``upstream``. Now you can locally update your forked
  repo.

  .. code-block:: none

    $ git fetch upstream
    $ git checkout current
    $ git merge upstream/current

* If you also want to update your fork on GitHub, use the following: ``$ git
  push origin current``

.. stop_vyoslinter

.. _Sphinx-doc: https://www.sphinx-doc.org
.. _reStructuredText: http://www.sphinx-doc.org/en/master/usage/restructuredtext/index.html
.. _reStructuredTextDirectives: https://docutils.sourceforge.io/docs/ref/rst/directives.html
.. _README.md: https://github.com/vyos/vyos-documentation/blob/current/README.md
.. _Dockerfile: https://github.com/vyos/vyos-documentation/blob/current/docker/Dockerfile
.. _Grammarly: https://www.grammarly.com/
.. include:: /_include/common-references.txt

.. start_vyoslinter
