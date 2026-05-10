.. _sysctl:

######
Sysctl
######

.. note:: This page is a stub and needs expansion. Contributions
   welcome via the `VyOS documentation repository
   <https://github.com/vyos/vyos-documentation>`_.

This chapter describes how to configure kernel parameters at runtime.

``sysctl`` is used to modify kernel parameters at runtime.  The parameters
available are those listed under /proc/sys/. 

.. cfgcmd:: set system sysctl parameter <parameter> value <value>
