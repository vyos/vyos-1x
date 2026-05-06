:lastproofread: 2026-03-23

##############
VyOS Terraform
##############


VyOS supports development infrastructure via Terraform and provisioning
via Ansible.
Terraform allows you to automate the deployment of instances on a number of
cloud and virtual platforms. This section shows how to deploy VyOS on
multiple platforms: AWS, Microsoft Azure, Google Cloud Platform (GCP),
and VMware vSphere.
For more information, see the
official documentation for Terraform_ and Ansible_.

   

.. toctree::
   :maxdepth: 1
   :caption: Guides
   
   terraformvyos
   terraformAWS
   terraformAZ
   terraformGoogle
   terraformvSphere

.. stop_vyoslinter
.. _Terraform: https://developer.hashicorp.com/terraform/intro
.. _Ansible: https://docs.ansible.com
.. _install: https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli
.. start_vyoslinter