:lastproofread: 2026-04-13

.. _cloud-init:

###############
VyOS cloud-init
###############

VyOS instances in cloud and virtualized environments are initialized using the 
industry-standard ``cloud-init``. Through ``cloud-init``, VyOS injects SSH 
keys, configures network settings, and applies custom configurations during the 
initial instance boot.

*********************
Configuration sources
*********************

VyOS ``cloud-init`` obtains configuration data from the following sources:

* ``meta-data``: Instance-specific details provided by the cloud platform or 
  hypervisor. In some cloud environments, this data is available via an HTTP 
  endpoint at ``http://169.254.169.254``.
* ``network configuration``: Network settings such as IP addresses, routes, and 
  DNS (only available on certain cloud and virtualization platforms). 
* ``user-data``: User-supplied CLI configuration commands. 

*********
User-data
*********

Major cloud providers support injecting ``user-data`` as plain text or base64 
encoding text during initial instance boot. As ``user-data`` has a strict size 
limit of ~16384 bytes, long configuration command lists can be compressed using 
``gzip``.

The recommended method for configuring VyOS instances via ``user-data`` is to 
use the ``cloud-config`` syntax described below.

********************
Cloud-config modules
********************

By default, VyOS enables only two ``cloud-config`` modules:

* ``write_files``: Inserts user-provided files such as encryption keys, 
  certificates, or ``config.boot`` into the filesystem during the initial 
  instance boot. See `Cloud-init-write_files`_ for file syntax and file format 
  requirements.
* ``vyos_userdata``: Executes user-provided CLI configuration commands during 
  the initial instance boot.

The files to insert and the CLI commands to execute must be provided in a 
``cloud-config`` YAML file.

************************
Cloud-config file format
************************

``cloud-config`` files are written in YAML and must begin with the 
``#cloud-config`` line. Only ``vyos_config_commands`` and ``write_files`` are 
supported as top-level keys. The use of these keys is described in the 
following two sections.

************************
Vyos_config_commands key
************************

Use the ``vyos_config_commands`` key to define configuration commands for 
initializing your VyOS instance. Commands must follow the set-style syntax 
and can include both ``set`` and ``delete`` statements.

Syntax requirements:

* Place one command per line.
* Enclose values in single quotes.
* Avoid single quotes within commands or values.

Applying commands from ``cloud-config`` overrides both settings configured via 
``meta-data`` and default VyOS settings. After commands are applied, 
``cloud-init`` automatically performs ``commit`` and ``save``.

The following is an example of a ``cloud-config`` file: 

.. code-block:: yaml

   #cloud-config
   vyos_config_commands:
     - set system host-name 'vyos-prod-ashburn'
     - set service ntp server 1.pool.ntp.org
     - set service ntp server 2.pool.ntp.org
     - delete interfaces ethernet eth1 address 'dhcp'
     - set interfaces ethernet eth1 address '192.0.2.247/24'
     - set protocols static route 198.51.100.0/24 next-hop '192.0.2.1'

---------------------------
Instance defaults/fallbacks
---------------------------

If no external configuration data is provided, VyOS applies the following 
defaults:

* **SSH:** port 22.
* **Credentials:** ``vyos``/``vyos``.
* **Networking:** DHCP is enabled on the first Ethernet interface.

All defaults can be overridden via ``user-data`` configurations.


***************
Write_files key
***************

VyOS allows you to run custom scripts during the initial instance boot to 
execute operational, configuration, and standard Linux commands. 

Use the ``write_files`` key to insert these scripts into the 
``/opt/vyatta/etc/config/scripts/`` directory.

Depending on when your commands need to run, use one of the following paths:

* ``/opt/vyatta/etc/config/scripts/vyos-preconfig-bootup.script``: Commands 
  defined here are executed before the system configuration is applied.
* ``/opt/vyatta/etc/config/scripts/vyos-postconfig-bootup.script``: Commands 
  defined here are executed after the system configuration is applied.

In both cases, commands are executed with ``root`` privileges.

.. note::
   
   Use the ``/opt/vyatta/etc/config/`` path instead of ``/config/scripts/`` as 
   referenced in the :ref:`command-scripting` section. The ``/config/scripts/`` 
   directory is not mounted when the ``write_files`` module runs.

The following example shows how to use ``write_files`` to execute an 
operational command **after** the initial configuration is complete:

.. code-block:: yaml

   #cloud-config
   write_files:
     - path: /opt/vyatta/etc/config/scripts/vyos-postconfig-bootup.script
       owner: root:vyattacfg
       permissions: '0775'
       content: |
         #!/bin/vbash
         source /opt/vyatta/etc/functions/script-template
         filename=/tmp/bgp_status_`date +"%Y_%m_%d_%I_%M_%p"`.log
         run show ip bgp summary >> $filename

You can combine standard Linux commands to fetch data and VyOS configuration 
commands (like ``set`` and ``commit``) in the same script.

The following example sets the ``hostname`` based on the instance identifier 
obtained from the EC2 Instance Metadata Service (IMDS).

.. code-block:: yaml


   #cloud-config
   write_files:
     - path: /opt/vyatta/etc/config/scripts/vyos-postconfig-bootup.script
       owner: root:vyattacfg
       permissions: '0775'
       content: |
         #!/bin/vbash
         source /opt/vyatta/etc/functions/script-template
         hostname=`curl -s http://169.254.169.254/latest/meta-data/instance-id`
         configure
         set system host-name $hostname
         commit
         exit

*******
NoCloud
*******

Injecting configuration data is not limited to cloud platforms. The NoCloud 
data source allows you to inject ``user-data`` and ``meta-data`` on 
virtualization platforms such as VMware, Hyper-V, and KVM.

The simplest way to use the NoCloud data source is to create a ``seed.iso`` 
file and attach it to the virtual machine as a CD drive. The volume must be 
formatted as a VFAT or ISO 9660 file system with the label ``cidata`` or 
``CIDATA``.

Create text files named ``user-data`` and ``meta-data``. On Linux-based 
systems, use the ``mkisofs`` utility to create the ``seed.iso`` file. The 
following syntax adds these files to the ISO 9660 file system:

.. code-block:: none

  mkisofs -joliet -rock -volid "cidata" -output seed.iso meta-data user-data

Once generated, attach the ``seed.iso`` file to your virtual machine. The 
following example shows how to attach the file as a CD drive using KVM:

.. code-block:: none

  $ virt-install -n vyos_r1 \
     --ram 4096 \
     --vcpus 2 \
     --cdrom seed.iso \
     --os-type linux \
     --os-variant debian10 \
     --network network=default \
     --graphics vnc \
     --hvm \
     --virt-type kvm \
     --disk path=/var/lib/libvirt/images/vyos_kvm.qcow2,bus=virtio \
     --import \
     --noautoconsole

For more information on the NoCloud data source, visit the `NoCloud`_ page in 
the ``cloud-init`` documentation.

***************
Troubleshooting
***************

If your configuration does not apply as expected, follow these troubleshooting 
steps:

1. **Validate your YAML**: Ensure your ``cloud-config`` file follows proper 
   YAML syntax. Online resources such as `YAML Lint <https://www.yamllint.com/>`_ 
   provide simple validation tools.
2. **Check the logs**: ``cloud-init`` writes logs to ``/var/log/cloud-init.log``. 
   Filter for VyOS-specific entries using:


.. code-block:: none

    sudo grep vyos /var/log/cloud-init.log

*********************
Cloud-init on Proxmox
*********************

Before you begin, review the ``cloud-init`` `network-config-docs`_ to 
understand how to import user and network configuration data.

Key considerations:

* Define VyOS configuration commands in the ``user-data`` file.
* Avoid including network configuration data in the ``user-data`` file.
* If no network configuration data is provided, the DHCP client is enabled on 
  the first interface. This happens at the OS level and is not reflected in the 
  VyOS CLI.

The following example shows how to disable the DHCP client on ``eth0`` to 
address this behavior.  

In this example:

* **Proxmox IP address**: ``192.168.0.253/24``.
* **Storage**: The ``local`` volume is mounted at ``/var/lib/vz`` and contains 
  all content types, including snippets.

The goal is to remove the default DHCP client from the first interface and 
apply a custom configuration during the initial instance boot using 
``cloud-init``.

---------------------
Generate .qcow2 image
---------------------

First, generate a VyOS ``.qcow2`` image with ``cloud-init`` support from the 
`vyos-vm-images`_ repository:

#. Clone the ``vyos-vm-images`` repository and comment out the ``download-iso`` 
   role in ``qemu.yml``.
#. Download your preferred VyOS ``.iso`` file and save it as ``/tmp/vyos.iso``.
#. Generate the ``.qcow2`` image (using a 10G disk size for this example):

.. code-block:: sh

  sudo ansible-playbook qemu.yml -e disk_size=10 \
   -e iso_local=/tmp/vyos.iso -e grub_console=serial -e vyos_version=1.5.0 \
   -e cloud_init=true -e cloud_init_ds=NoCloud

This generates your new image at ``/tmp/vyos-1.5.0-cloud-init-10G-qemu.qcow2``.

#. Copy the resulting image to the Proxmox server:

.. code-block:: sh
  
  sudo scp /tmp/vyos-1.5.0-cloud-init-10G-qemu.qcow2 root@192.168.0.253:/tmp/


------------------------
Prepare cloud-init files
------------------------

Create the following files on your Proxmox server to proceed with this setup:

* ``user-data``: Contains VyOS configuration commands.
* ``network-config``: Disables the DHCP client on the first interface.
* ``meta-data``: An empty file (required by ``cloud-init``).

All files must be placed in the ``/tmp/`` directory.

Follow these steps to create the required files:

1. Navigate to the ``/tmp/`` directory:

   .. code-block:: sh
  
     cd /tmp/

2. Create the ``user-data`` file. Begin the file with ``#cloud-config`` and 
   include VyOS configuration commands.

   .. code-block:: none

      #cloud-config
      vyos_config_commands:
        - set system host-name 'vyos-BRAS'
        - set service ntp server '1.pool.ntp.org'
        - set service ntp server '2.pool.ntp.org'
        - delete interfaces ethernet eth0 address 'dhcp'
        - set interfaces ethernet eth0 address '198.51.100.2/30'
        - set interfaces ethernet eth0 description 'WAN - ISP01'
        - set interfaces ethernet eth1 address '192.168.25.1/24'
        - set interfaces ethernet eth1 description 'Coming through VLAN 25'
        - set interfaces ethernet eth2 address '192.168.26.1/24'
        - set interfaces ethernet eth2 description 'Coming through VLAN 26'
        - set protocols static route 0.0.0.0/0 next-hop '198.51.100.1'

3. Create the ``network-config`` file. Include the following:

   .. code-block:: none

      version: 2
      ethernets:
        eth0:
          dhcp4: false
          dhcp6: false

4. Create the required empty ``meta-data`` file.
   

---------------
Create seed.iso
---------------

Once you have created the necessary files, generate the ``seed.iso`` image and 
mount it as a CD drive to the new VM.

.. code-block:: sh
  
  mkisofs -joliet -rock -volid "cidata" -output seed.iso meta-data \
  user-data network-config

.. note::

   Be careful while copying and pasting the above commands. Double quotes may need 
   to be corrected.

-------------
Create the VM
-------------

Note that the following settings apply to this particular example and may 
require adjustment for other setups:

* **VM ID**: ``555``.
* **VM and .iso file storage**: The local volume (``directory`` type, 
  mounted at ``/var/lib/vz``).
* **VM resources**: Can be modified as needed.

The ``seed.iso`` file was previously created in the ``/tmp/`` directory. Move 
it to ``/var/lib/vz/template/iso``:

.. code-block:: sh

  mv /tmp/seed.iso /var/lib/vz/template/iso/

On the Proxmox server:

.. code-block:: none

   ## Create VM, import disk and define boot order
   qm create 555 --name vyos-1.5.0-cloudinit --memory 1024 --net0 virtio,bridge=vmbr0
   qm importdisk 555 vyos-1.5.0-cloud-init-10G-qemu.qcow2 local
   qm set 555 --virtio0 local:555/vm-555-disk-0.raw
   qm set 555 --boot order=virtio0
   
   ## Import seed.iso for cloud init
   qm set 555 --ide2 media=cdrom,file=local:iso/seed.iso
   
   ## Since this server has 1 nic, lets add network intefaces (vlan 25 and 26)
   qm set 555 --net1 virtio,bridge=vmbr0,firewall=1,tag=25
   qm set 555 --net2 virtio,bridge=vmbr0,firewall=1,tag=26
   
--------------------------
Power on and verify the VM
--------------------------

Power on the VM using the CLI or GUI. After it boots, verify the configuration.

----------
References
----------

* Cloud-init `network-config-docs`_.

* Proxmox `Cloud-init-Support`_.

.. stop_vyoslinter

.. _network-config-docs: https://cloudinit.readthedocs.io/en/latest/topics/network-config.html
.. _vyos-vm-images: https://github.com/vyos/vyos-vm-images
.. _cloud-init-docs: https://docs.vyos.io/en/equuleus/automation/cloud-init.html?highlight=cloud-init#vyos-cloud-init
.. _Cloud-init-Support: https://pve.proxmox.com/pve-docs/pve-admin-guide.html#qm_cloud_init
.. _Cloud-init-write_files: https://cloudinit.readthedocs.io/en/latest/topics/examples.html#writing-out-arbitrary-files
.. _nocloud: https://cloudinit.readthedocs.io/en/latest/reference/datasources/nocloud.html
.. start_vyoslinter
