.. _host-information:

################
Host Information
################

This section describes the system's host information and how to configure them,
it covers the following topics:

* Host name
* Domain
* IP address
* Aliases

Hostname
========

A hostname is the label (name) assigned to a network device (a host) on a
network and is used to distinguish one device from another on specific networks
or over the internet. On the other hand this will be the name which appears on
the command line prompt.

.. cfgcmd:: set system host-name <hostname>

   The hostname can be up to 63 characters. A hostname
   must start and end with a letter or digit, and have as interior characters
   only letters, digits, or a hyphen.

   The default hostname used is `vyos`.

Domain Name
===========

A domain name is the label (name) assigned to a computer network and is thus
unique. VyOS appends the domain name as a suffix to any unqualified name. For
example, if you set the domain name `example.com`, and you would ping the
unqualified name of `crux`, then VyOS qualifies the name to `crux.example.com`.

.. cfgcmd:: set system domain-name <domain>

   Configure system domain name. A domain name must start and end with a letter
   or digit, and have as interior characters only letters, digits, or a hyphen.

Static Hostname Mapping
=======================

How an IP address is assigned to an interface in :ref:`ethernet-interface`.
This section shows how to statically map an IP address to a hostname for local
(meaning on this VyOS instance) name resolution. This is the VyOS equivalent to
`/etc/hosts` file entries.

.. note:: Do *not* manually edit `/etc/hosts`. This file will automatically be
   regenerated on boot based on the settings in this section, which means you'll
   lose all your manual edits. Instead, configure static host mappings as follows.

.. cfgcmd:: set system static-host-mapping host-name <hostname> inet <address>

   Create a static hostname mapping which will always resolve the name
   `<hostname>` to IP address `<address>`.


.. cfgcmd:: set system static-host-mapping host-name <hostname> alias <alias>

   Create named `<alias>` for the configured static mapping for `<hostname>`.
   Thus the address configured as :cfgcmd:`set system static-host-mapping
   host-name <hostname> inet <address>` can be reached via multiple names.

   Multiple aliases can be specified per host-name.
