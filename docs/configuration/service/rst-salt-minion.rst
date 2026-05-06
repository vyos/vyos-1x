.. _saltminion:

###########
Salt-Minion
###########

SaltStack_ is Python-based, open-source
software for event-driven IT automation, remote task execution, and 
configuration management. Supporting the "infrastructure as code" 
approach to data center system and network deployment and management, 
configuration automation, SecOps orchestration, vulnerability remediation,
and hybrid cloud control.


************
Requirements
************

To use the Salt-Minion, a running Salt-Master is required. You can find more
in the `Salt Project Documentation
<https://docs.saltproject.io/en/latest/contents.html>`_

*************
Configuration
*************

.. cfgcmd:: set service salt-minion hash <type>

   The hash type used when discovering file on master server (default: sha256)

.. cfgcmd:: set service salt-minion id <id>

   Explicitly declare ID for this minion to use (default: hostname)

.. cfgcmd:: set service salt-minion interval <1-1440>

   Interval in minutes between updates (default: 60)

.. cfgcmd:: set service salt-minion master <hostname | IP>

    The hostname or IP address of the master

.. cfgcmd:: set service salt-minion master-key <key>

    URL with signature of master for auth reply verification


Please take a look in the Automation section to find some usefull
Examples.



.. _SaltStack: https://saltproject.io/