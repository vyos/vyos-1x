:lastproofread: 2026-01-26

#################################
Installation and Image Management
#################################

.. note:: This information applies primarily to virtual installations:

   When installing VyOS, ensure that the MAC address you select for your NICs
   is not a locally administered MAC address. Locally administered addresses are
   distinguished from universally administered addresses by setting the
   second-least-significant bit of the first octet to 1:

   Example: ``02:00:00:00:00:01``, where the second-least-significant bit
   (``02`` in hexadecimal) is set to ``1``.

.. toctree::
   :maxdepth: 2
   :caption: Content

   install
   virtual/index
   cloud/index
   bare-metal
   update
   image
   secure-boot
