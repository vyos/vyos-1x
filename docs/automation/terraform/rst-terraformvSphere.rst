:lastproofread: 2026-03-23

.. _terraformvSphere:

Deploy VyOS on VMware vSphere with Terraform and Ansible
========================================================

You can use Terraform to quickly deploy VyOS-based infrastructure
on VMware vSphere (hereafter referred to as *vSphere*) and remove
infrastructure when it's no longer needed.
Additionally, you can use Ansible for provisioning.

On this page you'll learn how to:

* Create the necessary files for Terraform and Ansible.
* Use Terraform to create a single instance on Azure and use Ansible for
  provisioning.

Prepare to deploy VyOS with Terraform on vSphere
------------------------------------------------

To create a single instance and install your configuration using
Terraform, Ansible, and vSphere, follow these steps:

vSphere
^^^^^^^


.. stop_vyoslinter

1. Add all necessary data to the ``terraform.tfvars``
   `file <https://github.com/vyos/vyos-automation/blob/main/TerraformCloud/Vsphere_terraform_ansible_single_vyos_instance-main/terraform.tfvars>`__
   and create resources.

.. start_vyoslinter

Terraform
^^^^^^^^^


1. Create an UNIX or Windows instance.

2. Download and install
   `Terraform <https://developer.hashicorp.com/terraform/install>`__.

3. Create the folder for example ``/root/vsphereterraform``.

.. code-block:: none

 mkdir /root/vsphereterraform
 

4. Copy all files into your Terraform project ``/root/vsphereterraform``
   (``vyos.tf``, ``var.tf``, ``terraform.tfvars``, ``version.tf``).
   For more details,
   see `Structure of files in Terraform for vSphere`_

5. Run the following commands:

.. code-block:: none

   cd /<your folder> 
   terraform init


Ansible
^^^^^^^


1. Create an UNIX instance either locally or in the cloud.

2. Download and install Ansible.

3. Create the folder. For example, ``/root/vsphereterraform/``.

4. Copy all files into your Ansible project ``/root/vsphereterraform/``
   (``ansible.cfg``, ``instance.yml``, ``all``). For more details, see
   `Structure of files in Ansible for vSphere`_


Deploy with Terraform
^^^^^^^^^^^^^^^^^^^^^


Run the following commands on your Terraform instance:
   
.. code-block:: none

   cd /<your folder>
   terraform plan  
   terraform apply  
   yes


After executing these commands, your VyOS instance is deployed to
vSphere with your configuration.
If you need to delete the instance, run the following command:
.. code-block:: none

   terraform destroy

   
Structure of files in Terraform for vSphere
-------------------------------------------

.. code-block:: none

 .
 ├── vyos.tf				    # The main script.
 ├── versions.tf			  # File for Terraform version.
 ├── var.tf				      # File for Terraform version.
 └── terraform.tfvars		# Values for all variables (passwords,
                        # login, IP addresses, etc.).


File contents of Terraform for vSphere
--------------------------------------

``vyos.tf``

.. code-block:: none

  provider "vsphere" {
    user           = var.vsphere_user
    password       = var.vsphere_password
    vsphere_server = var.vsphere_server
    allow_unverified_ssl = true
  }
  
  data "vsphere_datacenter" "datacenter" {
    name = var.datacenter
  }
  
  data "vsphere_datastore" "datastore" {
    name          = var.datastore
    datacenter_id = data.vsphere_datacenter.datacenter.id
  }
  
  data "vsphere_compute_cluster" "cluster" {
    name          = var.cluster
    datacenter_id = data.vsphere_datacenter.datacenter.id
  }
  
  data "vsphere_resource_pool" "default" {
    name          = format("%s%s", data.vsphere_compute_cluster.cluster.name, "/Resources/terraform")  # set as you need
    datacenter_id = data.vsphere_datacenter.datacenter.id
  }
  
  data "vsphere_host" "host" {
    name          = var.host
    datacenter_id = data.vsphere_datacenter.datacenter.id
  }
  
  data "vsphere_network" "network" {
    name          = var.network_name
    datacenter_id = data.vsphere_datacenter.datacenter.id
  }
  
  # Deployment of VM from Remote OVF
  resource "vsphere_virtual_machine" "vmFromRemoteOvf" {
    name                 = var.remotename
    datacenter_id        = data.vsphere_datacenter.datacenter.id
    datastore_id         = data.vsphere_datastore.datastore.id
    host_system_id       = data.vsphere_host.host.id
    resource_pool_id     = data.vsphere_resource_pool.default.id
    network_interface {
      network_id = data.vsphere_network.network.id
    }
    wait_for_guest_net_timeout = 2
    wait_for_guest_ip_timeout  = 2
  
    ovf_deploy {
      allow_unverified_ssl_cert = true
      remote_ovf_url            = var.url_ova
      disk_provisioning         = "thin"
      ip_protocol               = "IPv4"
      ip_allocation_policy = "dhcpPolicy"
      ovf_network_map = {
        "Network 1" = data.vsphere_network.network.id
        "Network 2" = data.vsphere_network.network.id
      }
    }
    vapp {
      properties = {
         "password"          = "12345678",
         "local-hostname"    = "terraform_vyos"
      }
    }
  }
  
  output "ip" {
    description = "default ip address of the deployed VM"
    value       = vsphere_virtual_machine.vmFromRemoteOvf.default_ip_address
  }
  
  # IP of vSphere instance copied to a file ip.txt in local system
  
  resource "local_file" "ip" {
      content  = vsphere_virtual_machine.vmFromRemoteOvf.default_ip_address
      filename = "ip.txt"
  }
  
  #Connecting to the Ansible control node using SSH connection
  
  resource "null_resource" "nullremote1" {
  depends_on = ["vsphere_virtual_machine.vmFromRemoteOvf"]
  connection {
   type     = "ssh"
   user     = "root"
   password = var.ansiblepassword
   host = var.ansiblehost
  
  }
  
  # Copying the ip.txt file to the Ansible control node from local system
  
   provisioner "file" {
      source      = "ip.txt"
      destination = "/root/vsphere/ip.txt"
         }
  }
  
  resource "null_resource" "nullremote2" {
  depends_on = ["vsphere_virtual_machine.vmFromRemoteOvf"]
  connection {
          type     = "ssh"
          user     = "root"
          password = var.ansiblepassword
          host = var.ansiblehost
  }
  
  # Command to run ansible playbook on remote Linux OS
  
  provisioner "remote-exec" {
  
      inline = [
          "cd /root/vsphere/",
          "ansible-playbook instance.yml"
  ]
  }
  }


``versions.tf``

.. code-block:: none

  # Copyright (c) HashiCorp, Inc.
  # SPDX-License-Identifier: MPL-2.0
  
  terraform {
    required_providers {
      vsphere = {
        source  = "hashicorp/vsphere"
        version = "2.4.0"
      }
    }
  }

``var.tf``

.. code-block:: none

  # Copyright (c) HashiCorp, Inc.
  # SPDX-License-Identifier: MPL-2.0
  
  variable "vsphere_server" {
    description = "vSphere server"
    type        = string
  }
  
  variable "vsphere_user" {
    description = "vSphere username"
    type        = string
  }
  
  variable "vsphere_password" {
    description = "vSphere password"
    type        = string
    sensitive   = true
  }
  
  variable "datacenter" {
    description = "vSphere data center"
    type        = string
  }
  
  variable "cluster" {
    description = "vSphere cluster"
    type        = string
  }
  
  variable "datastore" {
    description = "vSphere datastore"
    type        = string
  }
  
  variable "network_name" {
    description = "vSphere network name"
    type        = string
  }
  
  variable "host" {
    description = "Name of your host"
    type        = string
  }
  
  variable "remotename" {
    description = "The name of your VM"
    type        = string
  }
  
  variable "url_ova" {
    description = "The URL to the .OVA file or cloud storage"
    type        = string
  }
  
  variable "ansiblepassword" {
    description = "Ansible password"
    type        = string
  }
  
  variable "ansiblehost" {
    description = "Ansible host name or IP"
    type        = string
  }

``terraform.tfvars``

.. code-block:: none

  vsphere_user       = ""
  vsphere_password   = ""
  vsphere_server     = ""
  datacenter         = ""
  datastore          = ""
  cluster            = ""
  network_name       = ""
  host               = ""
  url_ova            = ""
  ansiblepassword    = ""
  ansiblehost        = ""
  remotename         = ""


Structure of files in Ansible for vSphere
-----------------------------------------

.. code-block:: none

 .
 ├── group_vars
     └── all
 ├── ansible.cfg
 └── instance.yml


File contents of Ansible for vSphere
------------------------------------

``ansible.cfg``

.. code-block:: none

  [defaults]
  inventory = /root/vsphere/ip.txt
  host_key_checking= False
  remote_user=vyos


``instance.yml``

.. code-block:: none

  ##############################################################################
  # About tasks:
  # "Wait 300 seconds, but only start checking after 60 seconds" - try to make ssh connection every 60 seconds until 300 seconds
  # "Configure general settings for the VyOS hosts group" - make provisioning into vSphere VyOS node
  # You have to add all necessary cammans of VyOS under the block "lines:"
  ##############################################################################


  - name: integration of terraform and ansible
    hosts: all
    gather_facts: 'no'
  
    tasks:
  
      - name: "Wait 300 seconds, but only start checking after 60 seconds"
        wait_for_connection:
          delay: 60
          timeout: 300
  
      - name: "Configure general settings for the VyOS hosts group"
        vyos_config:
          lines:
            - set system name-server 192.0.2.1
            - set system name-server 192.0.2.1
          save:
            true


``group_vars/all``

.. code-block:: none

  ansible_connection: ansible.netcommon.network_cli
  ansible_network_os: vyos.vyos.vyos
  
  # user and password gets from terraform variables "admin_username" and "admin_password"
  ansible_user: vyos
  # get from vyos.tf "vapp"
  ansible_ssh_pass: 12345678


Source files on GitHub
----------------------

All files related to deploying VyOS on vSpherewith Terraform and Ansible
can be found in the vyos-automation_ repository.


.. stop_vyoslinter
.. _vyos-automation: https://github.com/vyos/vyos-automation/tree/main/TerraformCloud/Vsphere_terraform_ansible_single_vyos_instance-main

.. start_vyoslinter
