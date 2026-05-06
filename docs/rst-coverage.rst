:lastproofread: 2025-11-14

########
Coverage
########

Overview over all commands that are documented in the
``.. cfgcmd::`` or ``.. opcmd::`` directives.

The build process takes all XML definition files
from the `vyos-1x <https://github.com/vyos/vyos-1x>`_ repository  and a
periodical export of all VyOS commands and extracts each leaf command, or
executable command.
The script compares only the fixed part of a command.
All variables and values are removed and the string of the commands
are compared.

For example, take the following two commands:

  * documentation: ``interfaces ethernet <interface> address
    <address | dhcp | dhcpv6>``
  * xml: ``interfaces ethernet <ethernet> address <address>``
  * VyOS: ``interfaces ethernet <text> address <value>``

**There are 3 kinds of issues with commands in the following tables:**

``Not documented yet``

  * An XML command is not found in ``.. cfgcmd::`` or ``.. opcmd::`` directives.
  * The command should be documented.

``Nothing found in XML Definitions``

  * ``.. cfgcmd::`` or ``.. opcmd::`` The command is not found in the XML
    definition.
  * The command location may have changed in the XML definition, the feature
    is no longer supported in VyOS, or there is a typo in the command.

``Nothing found in VyOS``

  * ``.. cfgcmd::`` or ``.. opcmd::`` The command is not found in VyOS
    documentation or the XML definition.
  * The command location may have changed in the XML definition, the feature
    is no longer supported in VyOS, or there is a typo in the command.


The final list of commands are shown in
the following two tables:

Configuration Commands
======================

.. cfgcmdlist::
    :show-coverage:


Operational Commands
====================

.. opcmdlist::
    :show-coverage: