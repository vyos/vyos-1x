:lastproofread: 2026-02-09

#####
Azure
#####

Deploy VM
---------

Deploy VyOS on Azure.

1. Go to Azure services and click **Add new Virtual machine**.

2. Choose a VM name, resource group, and region, then click **Browse all public 
   and private images**.

.. figure:: /_static/images/cloud-azure-01.*

3. Search for "VyOS" in the marketplace and choose the appropriate 
   subscription.

.. figure:: /_static/images/cloud-azure-02.*

4. Generate new SSH key pair or use existing.

.. figure:: /_static/images/cloud-azure-03.*

5. Configure the network, subnet, and public IP. Or use the defaults.

.. figure:: /_static/images/cloud-azure-04.*

6. Click **Review + create**. Your deployment completes in a few seconds.

.. figure:: /_static/images/cloud-azure-05.*

7. Select your new VM and note your public IP address.

.. figure:: /_static/images/cloud-azure-06.*

8. Connect to the instance with your SSH key.

  .. code-block:: none

    ssh -i ~/.ssh/vyos_azure vyos@203.0.113.3
    vyos@vyos-doc-r1:~$

Add interface
-------------

If your instance was deployed with one **eth0** (``WAN``) interface and you
want to add another, you must shut down the instance. To add a new interface,
such as **eth1** (``LAN``), attach it in the Azure portal and then restart the
instance.

.. note:: Azure doesn't allow you to attach an interface while the instance is
   running.

Absorbing Routes
----------------

If you're using the VM as a router, you can use a route table to absorb some or
all traffic from your virtual network (VNET) with your LAN interface.

1. Create a route table and navigate to **Configuration**.

2. Add one or more routes for the networks you want to route through the VyOS
   VM. For **Next hop type**, select **Virtual Appliance** and set the **Next
   Hop Address** to the VyOS ``LAN`` interface.

.. note:: To create a default route for VMs on the subnet, use
   **Address Prefix** ``0.0.0.0/0``. For a typical edge device configuration,
   configure masquerade NAT on the ``WAN`` interface.

Serial Console
--------------

VyOS includes serial console support by default. However, if you replace the
``config.boot`` file and reboot, ensure this configuration is present:

``set system console device ttyS0 speed '9600'``

References
----------
https://azure.microsoft.com
