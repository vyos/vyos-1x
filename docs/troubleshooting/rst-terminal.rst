################
Terminal/Console
################

Sometimes you need to clear counters or statistics to troubleshoot better.

To do this use the ``clear`` command in Operational mode.

to clear the console output

.. code-block:: none

  vyos@vyos:~$ clear console

to clear interface counters

.. code-block:: none

  # clear all interfaces
  vyos@vyos:~$ clear interface ethernet counters
  # clear specific interface
  vyos@vyos:~$ clear interface ethernet eth0 counters

The command follows the same logic as the ``set`` command in configuration mode.

.. code-block:: none

  # clear all counters of an interface type
  vyos@vyos:~$ clear interface <interface_type> counters
  # clear counter of an interface in interface_type
  vyos@vyos:~$ clear interface <interface_type> <interface_name> counters


to clear counters on firewall rulesets or single rules

.. code-block:: none

  vyos@vyos:~$ clear firewall name <ipv4 ruleset name> counters
  vyos@vyos:~$ clear firewall name <ipv4 ruleset name> rule <rule#> counters

  vyos@vyos:~$ clear firewall ipv6-name <ipv6 ruleset name> counters
  vyos@vyos:~$ clear firewall ipv6-name <ipv6 ruleset name> rule <rule#> counters
