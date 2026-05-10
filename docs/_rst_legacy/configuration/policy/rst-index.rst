:lastproofread: 2021-07-12

.. include:: /_include/need_improvement.txt

######
Policy
######

Policies are used for filtering and traffic management. With policies, network
administrators could filter and treat traffic
according to their needs.

There could be a wide range of routing policies. Some examples are listed
below:

* Filter traffic based on source/destination address.
* Set some metric to routes learned from a particular neighbor.
* Set some attributes (like AS PATH or Community value) to advertised routes
  to neighbors.
* Prefer a specific routing protocol routes over another routing protocol
  running on the same router.

Policies, in VyOS, are implemented using FRR filtering and route maps. Detailed
information of FRR could be found in http://docs.frrouting.org/

***************
Policy Sections
***************

.. toctree::
  :maxdepth: 1
  :includehidden:

  access-list
  prefix-list
  route
  route-map
  local-route
  as-path-list
  community-list
  extcommunity-list
  large-community-list

********
Examples
********

Examples of policies usage:

.. toctree::
   :maxdepth: 1
   :includehidden:
 
   examples