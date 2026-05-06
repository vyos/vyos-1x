:lastproofread: 2025-09-04

.. _vpp_config_sflow:

.. include:: /_include/need_improvement.txt

#######################
VPP sFlow Configuration
#######################

VPP Dataplane in VyOS support sFlow for traffic monitoring and analysis.

The VPP Dataplane integration works hand-in-hand with normal kernel sFlow agent, which is responsible for collecting and exporting sFlow samples. VPP itself is responsible for generating the samples.

To enable sFlow in VPP, you first need to configure the service using the same steps as for normal kernel sFlow agent, as described in :doc:`/configuration/system/sflow`. Then you can enable sFlow on VPP interfaces.

Then, you need to enable sFlow on the VPP interfaces you want to monitor. This is done using the following commands:

.. cfgcmd::

   set vpp sflow interface <interface-name>

This will enable sFlow on the specified interface. You can repeat this command for each interface you want to monitor.

.. note::

   sFlow collects statistics only for traffic *received* on the interface. If you want to monitor traffic *sent* on the interface, you need to enable sFlow on the corresponding interface in the opposite direction.

Optionally, you can specify the number of bytes from each packet that should be included in the sFlow sample using the following command:

.. cfgcmd::

   set vpp sflow header-bytes <bytes>

This defines the size of the packet header (in bytes) captured for each sFlow sample.

The sampling rate is configured globally under the ``system sflow`` section and automatically applied to VPP sFlow.
This ensures consistent sampling behavior between the system and VPP, and prevents configuration conflicts.

Finally, you need to enable integration between VPP and the kernel sFlow agent using the following command:

.. cfgcmd::

   set system sflow vpp

After this, collecting and exporting sFlow samples will be handled by the kernel sFlow agent, while VPP will generate the samples.
