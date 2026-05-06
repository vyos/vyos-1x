.. _snmp:

####
SNMP
####

:abbr:`SNMP (Simple Network Management Protocol)` is an Internet Standard
protocol for collecting and organizing information about managed devices on
IP networks and for modifying that information to change device behavior.
Devices that typically support SNMP include cable modems, routers, switches,
servers, workstations, printers, and more.

SNMP is widely used in network management for network monitoring. SNMP exposes
management data in the form of variables on the managed systems organized in
a management information base (MIB_) which describe the system status and
configuration. These variables can then be remotely queried (and, in some
circumstances, manipulated) by managing applications.

Three significant versions of SNMP have been developed and deployed. SNMPv1 is
the original version of the protocol. More recent versions, SNMPv2c and SNMPv3,
feature improvements in performance, flexibility and security.

SNMP is a component of the Internet Protocol Suite as defined by the Internet
Engineering Task Force (IETF). It consists of a set of standards for network
management, including an application layer protocol, a database schema, and a
set of data objects.

Overview and basic concepts
===========================

In typical uses of SNMP, one or more administrative computers called managers
have the task of monitoring or managing a group of hosts or devices on a
computer network. Each managed system executes a software component called an
agent which reports information via SNMP to the manager.

An SNMP-managed network consists of three key components:

* Managed devices
* Agent - software which runs on managed devices
* Network management station (NMS) - software which runs on the manager

A managed device is a network node that implements an SNMP interface that
allows unidirectional (read-only) or bidirectional (read and write) access to
node-specific information. Managed devices exchange node-specific information
with the NMSs. Sometimes called network elements, the managed devices can be
any type of device, including, but not limited to, routers, access servers,
switches, cable modems, bridges, hubs, IP telephones, IP video cameras,
computer hosts, and printers.

An agent is a network-management software module that resides on a managed
device. An agent has local knowledge of management information and translates
that information to or from an SNMP-specific form.

A network management station executes applications that monitor and control
managed devices. NMSs provide the bulk of the processing and memory resources
required for network management. One or more NMSs may exist on any managed
network.

.. figure:: /_static/images/service_snmp_communication_principles_diagram.*
   :scale: 20 %
   :alt: Principle of SNMP Communication

   Image thankfully borrowed from
   https://en.wikipedia.org/wiki/File:SNMP_communication_principles_diagram.PNG
   which is under the GNU Free Documentation License

.. note:: VyOS SNMP supports both IPv4 and IPv6.

SNMP Protocol Versions
======================

VyOS itself supports SNMPv2_ (version 2) and SNMPv3_ (version 3) where the
later is recommended because of improved security (optional authentication and
encryption).

SNMPv2
------

SNMPv2 is the original and most commonly used version. For authorizing clients,
SNMP uses the concept of communities. Communities may have authorization set
to read only (this is most common) or to read and write (this option is not
actively used in VyOS).

SNMP can work synchronously or asynchronously. In synchronous communication,
the monitoring system queries the router periodically. In asynchronous, the
router sends notification to the "trap" (the monitoring host).

SNMPv2 does not support any authentication mechanisms, other than client source
address, so you should specify addresses of clients allowed to monitor the
router. Note that SNMPv2 also supports no encryption and always sends data in
plain text.

Example
^^^^^^^

.. code-block:: none

  # Define a community
  set service snmp community routers authorization ro

  # Allow monitoring access from the entire network
  set service snmp community routers network 192.0.2.0/24
  set service snmp community routers network 2001::db8:ffff:eeee::/64

  # Allow monitoring access from specific addresses
  set service snmp community routers client 203.0.113.10
  set service snmp community routers client 203.0.113.20

  # Define optional router information
  set service snmp location "UK, London"
  set service snmp contact "admin@example.com"

  # Trap target if you want asynchronous communication
  set service snmp trap-target 203.0.113.10

  # Listen only on specific IP addresses (port defaults to 161)
  set service snmp listen-address 172.16.254.36 port 161
  set service snmp listen-address 2001:db8::f00::1


SNMPv3
------

SNMPv3 (version 3 of the SNMP protocol) introduced a whole slew of new security
related features that have been missing from the previous versions. Security
was one of the biggest weakness of SNMP until v3. Authentication in SNMP
Versions 1 and 2 amounts to nothing more than a password (community string)
sent in clear text between a manager and agent. Each SNMPv3 message contains
security parameters which are encoded as an octet string. The meaning of these
security parameters depends on the security model being used.

The security approach in SNMPv3 targets:

* Confidentiality – Encryption of packets to prevent snooping by an
  unauthorized source.

* Integrity – Message integrity to ensure that a packet has not been tampered
  while in transit including an optional packet replay protection mechanism.

* Authentication – to verify that the message is from a valid source.

.. _snmp:v3_example:

Example
^^^^^^^

* Let SNMP daemon listen only on IP address 192.0.2.1
* Configure new SNMP user named "vyos" with password "vyos12345678"
* New user will use SHA/AES for authentication and privacy

.. code-block:: none

  set service snmp listen-address 192.0.2.1
  set service snmp location 'VyOS Datacenter'
  set service snmp v3 engineid '000000000000000000000002'
  set service snmp v3 group default mode 'ro'
  set service snmp v3 group default view 'default'
  set service snmp v3 user vyos auth plaintext-password 'vyos12345678'
  set service snmp v3 user vyos auth type 'sha'
  set service snmp v3 user vyos group 'default'
  set service snmp v3 user vyos privacy plaintext-password 'vyos12345678'
  set service snmp v3 user vyos privacy type 'aes'
  set service snmp v3 view default oid 1

After commit the plaintext passwords will be hashed and stored in your
configuration. The resulting CLI config will look like:

.. code-block:: none

  vyos@vyos# show service snmp
   listen-address 192.0.2.1 {
   }
   location "VyOS Datacenter"
   v3 {
       engineid 000000000000000000000002
       group default {
           mode ro
           view default
       }
       user vyos {
           auth {
               encrypted-password 4e52fe55fd011c9c51ae2c65f4b78ca93dcafdfe
               type sha
           }
           group default
           privacy {
               encrypted-password 4e52fe55fd011c9c51ae2c65f4b78ca93dcafdfe
               type aes
           }
       }
       view default {
           oid 1 {
           }
       }
   }

You can test the SNMPv3 functionality from any linux based system, just run the
following command: ``snmpwalk -v 3 -u vyos -a SHA -A vyos12345678 -x AES
-X vyos12345678 -l authPriv 192.0.2.1 .1``

VyOS MIBs
=========

All SNMP MIBs are located in each image of VyOS here: ``/usr/share/snmp/mibs/``

You are be able to download the files using SCP, once the SSH service
has been activated like so

.. code-block:: none

  scp -r vyos@your_router:/usr/share/snmp/mibs /your_folder/mibs

SNMP Extensions
===============

To extend SNMP agent functionality, custom scripts can be executed every time
the agent is being called. This can be achieved by using
``arbitrary extensioncommands``. The first step is to create a functional
script of course, then upload it to your VyOS instance via the command
``scp your_script.sh vyos@your_router:/config/user-data``.
Once the script is uploaded, it needs to be configured via the command below.


.. code-block:: none

  set service snmp script-extensions extension-name my-extension script your_script.sh
  commit

.. stop_vyoslinter

The OID ``.1.3.6.1.4.1.8072.1.3.2.3.1.1.4.116.101.115.116``, once called, will
contain the output of the extension.

.. start_vyoslinter

.. code-block:: none

  root@vyos:/home/vyos# snmpwalk -v2c  -c public 127.0.0.1 nsExtendOutput1
  NET-SNMP-EXTEND-MIB::nsExtendOutput1Line."my-extension" = STRING: hello
  NET-SNMP-EXTEND-MIB::nsExtendOutputFull."my-extension" = STRING: hello
  NET-SNMP-EXTEND-MIB::nsExtendOutNumLines."my-extension" = INTEGER: 1
  NET-SNMP-EXTEND-MIB::nsExtendResult."my-extension" = INTEGER: 0

SolarWinds
==========

If you happen to use SolarWinds Orion as NMS you can also use the Device
Templates Management. A template for VyOS can be easily imported.

.. stop_vyoslinter

Create a file named ``VyOS-1.3.6.1.4.1.44641.ConfigMgmt-Commands`` using the
following content:


.. code-block:: none

  <Configuration-Management Device="VyOS" SystemOID="1.3.6.1.4.1.44641">
      <Commands>
          <Command Name="Reset" Value="set terminal width 0${CRLF}set terminal length 0"/>
          <Command Name="Reboot" Value="reboot${CRLF}Yes"/>
          <Command Name="EnterConfigMode" Value="configure"/>
          <Command Name="ExitConfigMode" Value="commit${CRLF}exit"/>
          <Command Name="DownloadConfig" Value="show configuration commands"/>
          <Command Name="SaveConfig" Value="commit${CRLF}save"/>
          <Command Name="Version" Value="show version"/>
          <Command Name="MenuBased" Value="False"/>
          <Command Name="VirtualPrompt" Value=":~"/>
      </Commands>
  </Configuration-Management>

.. _MIB: https://en.wikipedia.org/wiki/Management_information_base
.. _SNMPv2: https://en.wikipedia.org/wiki/Simple_Network_Management_Protocol#Version_2
.. _SNMPv3: https://en.wikipedia.org/wiki/Simple_Network_Management_Protocol#Version_3

.. start_vyoslinter
