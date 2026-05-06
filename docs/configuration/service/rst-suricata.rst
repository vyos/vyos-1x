.. _suricata:

########
suricata
########

Suricata and VyOS are powerful tools for ensuring network security and traffic management. 
Suricata is an open-source intrusion detection and prevention system (IDS/IPS) that analyzes network packets in real-time. 


Suricata Features
=================

Intrusion Detection (IDS): Analyzes network traffic and detects suspicious activities, attacks, and malicious traffic.
Intrusion Prevention (IPS): Blocks or modifies suspicious traffic in real-time, preventing attacks before they penetrate the network.
Network Security Monitoring (NSM): Collects and analyzes network data to detect anomalies and identify threats.
Multi-Protocol Support: Suricata supports analysis of various network protocols such as HTTP, FTP, SMB, and many others.
In configuration mode, the commands are as follows:

.. code-block:: none

   vyos@vyos# set service suricata
   Possible completions:
   +> address-group        Address group name
   +  interface            Interface to use
    > log                  Suricata log outputs
   +> port-group           Port group name

These commands create a flexible interface for configuring the Suricata service, allowing users to specify addresses, ports, 
and logging parameters.

After completing the service configuration in configuration mode, the main configuration file suricata.yaml is created, 
into which all specified parameters are added. Then, to ensure proper operation, the command :opcmd:`update suricata` must be run 
from operational mode, waiting for Suricata to update all its rules, which are used for analyzing traffic for threats and attacks.


Configuration
=============

.. cfgcmd::  set service suricata address-group <text> <address | group>

   Address groups are useful when you need to create rules that apply to specific IP addresses. 
   For example, if you want to create a rule that monitors traffic going to or from a specific IP address, 
   you can use the group name instead of the actual IP address. This simplifies rule management and makes the 
   configuration more flexible.

   * ``address`` IP address or subnet.

   * ``group``  Address group.

.. cfgcmd:: set service suricata port-group <text> <address | group>

   Port groups are useful when you need to create rules that apply to specific ports. 
   For example, if you want to create a rule that monitors traffic directed to a specific port or group of ports, 
   you can use the group name instead of the actual port. This also simplifies rule management and makes 
   the configuration more flexible.

   * ``port``  Port number.

   * ``group``  Port group.

.. cfgcmd::  set service suricata interface <text>

   The interface that will be monitored by the Suricata service.


.. cfgcmd:: set service suricata log eve <filename | filetype | type>

   Configuration of the logging file.

   * ``filename``  Log file (default: eve.json).

   * ``filetype``  EVE logging destination (default: regular).
   
   * ``type``  Log types.

Operation Mode
==============

.. cfgcmd::  update suricata

   Checks for the existence of the Suricata configuration file, updates the service, 
   and then restarts it. If the configuration file is not found, a message indicates that Suricata is not configured.


.. cfgcmd:: restart suricata

   Restarts the service. It checks if the Suricata service is active before attempting to restart it. 
   If it is not active, a message indicates that the service is not configured. This command is used when adding new rules manually.

Conclusion
==============

Using address and port groups allows you to make your Suricata configuration more flexible and manageable. 
Instead of specifying IP addresses and ports directly in each rule, you can define them once in the vars section and then 
reference them by group names. This is especially useful in large networks and complex configurations where multiple IP addresses 
and ports need to be monitored.
   
   
   
   