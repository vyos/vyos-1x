:lastproofread: 2026-02-09

#####################
Google Cloud Platform
#####################

Deploy VM
---------

To deploy VyOS on Google Cloud Platform (GCP):

1. Generate an SSH key pair of type **ssh-rsa** on the host that will connect
   to VyOS.

   Example:

   .. code-block:: none

     ssh-keygen -t rsa -f ~/.ssh/vyos_gcp -C "vyos@mypc"

.. note:: The SSH key comment must begin with ``vyos@`` because that's the
   default VyOS user. GCP uses this value to set the username on the instance.


2. Open the GCP Console and navigate to **Metadata**. Select **SSH Keys** and 
   click **Edit**.

.. figure:: /_static/images/cloud-gcp-01.*


   Click **Add item**, paste your public SSH key, and click **Save**.

.. figure:: /_static/images/cloud-gcp-02.*


3. Search for "VyOS" in the Marketplace.

4. Configure the deployment name, zone, and machine type, then click **Deploy**.

.. figure:: /_static/images/cloud-gcp-03.*

5. After a few seconds, select your **instance**.

.. figure:: /_static/images/cloud-gcp-04.*

6. Note your external IP address.

.. figure:: /_static/images/cloud-gcp-05.*

7. Connect to the instance using the SSH key you generated in step 1.

  .. code-block:: none

    ssh -i ~/.ssh/vyos_gcp vyos@203.0.113.3
    vyos@vyos-r1-vm:~$

References
----------
https://console.cloud.google.com/
