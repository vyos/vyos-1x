:lastproofread: 2026-02-06

##########
Amazon AWS
##########

Deploy VM
---------

Deploy VyOS on Amazon :abbr:`AWS (Amazon Web Services)`.

1. Click **Instances** and then click **Launch Instance**.

.. figure:: /_static/images/cloud-aws-01.*

2. Search for "VyOS" in the Marketplace.

.. figure:: /_static/images/cloud-aws-02.*

3. Choose the instance type. The recommended minimum is ``m3.medium``.

.. figure:: /_static/images/cloud-aws-03.*

4. Configure the instance for your requirements. Select the number of
   instances, network, and subnet.

.. figure:: /_static/images/cloud-aws-04.*

5. Configure additional storage. You can remove the additional storage
   ``/dev/sdb``. The root device will be ``/dev/xvda``. You can skip this step.

.. figure:: /_static/images/cloud-aws-05.*

6. Configure the security group. We recommend configuring SSH access
   only from specific sources, or you can permit any IP address (the default).

.. figure:: /_static/images/cloud-aws-06.*

7. Select the SSH key pair and click **Launch Instances**.

.. figure:: /_static/images/cloud-aws-07.*

8. Note your public IP address.

.. figure:: /_static/images/cloud-aws-08.*

9. Connect to the instance using your SSH key.

  .. code-block:: none

    ssh -i ~/.ssh/amazon.pem vyos@203.0.113.3
    vyos@ip-192-0-2-10:~$

Amazon CloudWatch Agent Usage
-----------------------------

To use the Amazon CloudWatch agent, configure it in the Amazon Systems Manager
Parameter Store. For instructions on creating a configuration, see
:ref:`configuration_creation`.

1. Create an :abbr:`IAM (Identity and Access Management)` role for the
   :abbr:`EC2 (Elastic Compute Cloud)` instance to access CloudWatch service,
   and name it CloudWatchAgentServerRole. The role should contain two default
   policies: ``CloudWatchAgentServerPolicy`` and
   ``AmazonSSMManagedInstanceCore``.

2. Attach the created role to your VyOS :abbr:`EC2 (Elastic Compute Cloud)`
   instance.

3. Ensure the amazon-cloudwatch-agent package is installed. 

  .. code-block:: none

    $ sudo apt list --installed | grep amazon-cloudwatch-agent

  .. note:: The amazon-cloudwatch-agent package is normally included in
     VyOS 1.3.3+ and 1.4+

4. Retrieve an existing CloudWatch Agent configuration from the
   :abbr:`SSM (Systems Manager)` Parameter Store.

  .. code-block:: none

    $ sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c ssm:<your-configuration-name>

  This step also enables systemd service and runs it.

  .. note:: The VyOS platform-specific scripts feature is under development.
     Thus, this step should be repeated manually after changing system image
     (:doc:`/installation/update`)

.. _configuration_creation:

CloudWatch SSM Configuration creation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Creating the Amazon Cloudwatch Agent Configuration in Amazon
:abbr:`SSM (Systems Manager)` Parameter Store.

1. Create an :abbr:`IAM (Identity and Access Management)` role for your
   :abbr:`EC2 (Elastic Compute Cloud)` instance to access the CloudWatch
   service. Name it ``CloudWatchAgentAdminRole``. The role must contain at
   least two policies: ``CloudWatchAgentAdminPolicy`` and
   ``AmazonSSMManagedInstanceCore``.

  .. note:: CloudWatchAgentServerRole is too permissive and should be used only
     for
     creating and deploying a single configuration. After step 3, we recommend
     replacing the ``CloudWatchAgentAdminRole`` with the 
     ``CloudWatchAgentServerRole``.

2. Run the CloudWatch configuration wizard.

  .. code-block:: none

    $ sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard

3. When prompted, enter "yes" to the question "Do you want to store the
   config in the SSM parameter store?".

AWS Gateway Load Balancer
--------------------------

VyOS supports the AWS Gateway Load Balancer (GWLB) tunnel handler (``gwlbtun``),
which enables VyOS to act as an inspection or processing target for GWLB. GWLB
uses Geneve encapsulation with custom metadata to deliver traffic to VyOS for
packet filtering, shaping, deep packet inspection, NAT, or other traffic
manipulation functions. The tunnel handler automatically creates Linux tunnel
interfaces (``gwi-*`` for ingress and ``gwo-*`` for egress) per endpoint,
allowing you to use standard Linux utilities like iptables, tc, and netfilter
to implement your inspection or processing logic. This enables VyOS to serve as
a centralized appliance for traffic inspection in your AWS infrastructure,
supporting both single-endpoint (1-arm) and multi-endpoint (2-arm) deployment
modes.

.. stop_vyoslinter
For more information about integrating with AWS Gateway Load Balancer, see
the following article from AWS:
`How to integrate Linux instances with AWS Gateway Load Balancer <https://aws.amazon.com/blogs/networking-and-content-delivery/how-to-integrate-linux-instances-with-aws-gateway-load-balancer/>`__.

.. start_vyoslinter
Configuration Example
^^^^^^^^^^^^^^^^^^^^^

Configure the AWS GWLB service with the following commands:

.. code-block:: none

  set service aws glb script on-create '/config/scripts/glb-create.sh'
  set service aws glb script on-destroy '/config/scripts/glb-destroy.sh'
  set service aws glb status format 'simple'
  set service aws glb status port '8282'
  set service aws glb threads tunnel '4'
  set service aws glb threads tunnel-affinity '1-2'
  set service aws glb threads udp '4'
  set service aws glb threads udp-affinity '0-3'

.. stop_vyoslinter
References
----------
- https://console.aws.amazon.com/
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/create-iam-roles-for-cloudwatch-agent.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/install-CloudWatch-Agent-on-EC2-Instance-fleet.html
- https://aws.amazon.com/blogs/networking-and-content-delivery/how-to-integrate-linux-instances-with-aws-gateway-load-balancer/

.. start_vyoslinter
