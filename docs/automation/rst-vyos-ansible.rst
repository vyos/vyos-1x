:lastproofread: 2026-04-13

.. _vyos-ansible:

#######
Ansible
#######

VyOS can be configured using Ansible. To use it, install the ``ansible`` 
package and the ``python3-paramiko`` module.

Directory structure
-------------------

Arrange your Ansible project directory as follows:

.. code-block:: none

 .
 ├── ansible.cfg
 ├── files
 │   └── id_rsa_docker.pub
 ├── hosts
 └── main.yml


File contents
-------------

* ``ansible.cfg``

.. code-block:: none

  [defaults]
  host_key_checking = no
  retry_files_enabled = False
  ANSIBLE_INVENTORY_UNPARSED_FAILED = true

* ``id_rsa_docker.pub`` 

Contains only the SSH public key.

.. code-block:: none

  AAAAB3NzaC1yc2EAAAADAQABAAABAQCoDgfhQJuJRFWJijHn7ZinZ3NWp4hWVrt7HFcvn0kgtP/5PeCtMt


* ``hosts``

Defines the target VyOS devices and the connection parameters required to reach 
them.

.. code-block:: none

  [vyos_hosts]
  r11 ansible_ssh_host=192.0.2.11

  [vyos_hosts:vars]
  ansible_python_interpreter=/usr/bin/python3
  ansible_user=vyos
  ansible_ssh_pass=vyos
  ansible_network_os=vyos
  ansible_connection=network_cli

* ``main.yml``

Defines the configuration tasks to be applied to the target VyOS devices.

.. code-block:: none

  ---

  - hosts: r11

    connection: network_cli
    gather_facts: 'no'

    tasks:
      - name: Configure remote r11
        vyos_config:
          lines:
            - set system host-name r11
            - set system name-server 203.0.113.254
            - set service ssh disable-host-validation
            - set system login user vyos authentication public-keys docker@work type ssh-rsa
            - set system login user vyos authentication public-keys docker@work key "{{ lookup('file', 'id_rsa_docker.pub') }}"
            - set system time-zone America/Los_Angeles
            - set interfaces ethernet eth0 description WAN

Run Ansible
-----------

To apply the configuration, use the following command:

.. code-block:: none

  $ ansible-playbook -i hosts main.yml 

  PLAY [r11] **************************************************************************************************************

  TASK [Configure remote r11] *********************************************************************************************

  PLAY RECAP **************************************************************************************************************
  r11                         : ok=1    changed=1    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0

