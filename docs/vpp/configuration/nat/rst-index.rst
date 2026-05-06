:lastproofread: 2026-03-05

.. _vpp_config_nat_index:

.. include:: /_include/need_improvement.txt


#####################
VPP NAT Configuration
#####################

.. toctree::
   :maxdepth: 1
   :includehidden:

   cgnat
   nat44

VPP Dataplane in VyOS supports two types of NAT:

NAT44
=====

This type is a classic NAT implementation where you can configure static
and dynamic NAT rules. It supports both source and destination NAT. While the
configuration may look a bit unusual compared to traditional NAT
implementations, it provides flexibility in network configurations.

CGNAT
=====

CGNAT is a special type of NAT44, which is highly useful when you have
multiple local customers and a limited number of public IP addresses. It
shares the public IP address space fairly between customers by using a
combination of IP address and port number to distinguish between them.

ISPs often use this NAT type to provide internet access to customers.

It supports only source NAT.

CGNAT also supports exclude rules (identity mappings) to bypass translation
for selected local addresses or protocol/port tuples.
