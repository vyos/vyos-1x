.. _config-sync:

###########
Config Sync
###########

Configuration synchronization (config sync) is a feature of VyOS that 
permits synchronization of the configuration of one VyOS router to 
another in a network. 

The main benefit to configuration synchronization is that it eliminates having  
to manually replicate configuration changes made on the primary router to the  
secondary (replica) router.

The writing of the configuration to the secondary router is performed through 
the VyOS HTTP API. The user can specify which portion(s) of the configuration will 
be synchronized and the mode to use - whether to replace or add. 

To prevent issues with divergent configurations between the pair of routers, 
synchronization is strictly unidirectional from primary to replica. Both 
routers should be online and run the same version of VyOS.

Configuration
-------------

.. cfgcmd:: set service config-sync secondary 
   <address|key|timeout|port>

   Specify the address, API key, timeout and port of the secondary router. 
   You need to enable and configure the HTTP API service on the secondary 
   router for config sync to operate.
   
.. cfgcmd:: set service config-sync section <section>

   Specify the section of the configuration to synchronize. If more than one 
   section is to be synchronized, repeat the command to add additional 
   sections as required.

.. cfgcmd:: set service config-sync mode <load|set>

   Two options are available for `mode`: either `load` and replace or `set`
   the configuration section.

.. code-block:: none

    Supported options for <section> include:
        firewall
        interfaces <interface>
        nat
        nat66
        pki
        policy
        protocols <protocol>
        qos <interface|policy>
        service <service>
        system <conntrack| 
        flow-accounting|option|sflow|static-host-mapping|sysctl|time-zone>
        vpn
        vrf

Operational Commands
--------------------

.. opcmd:: show configuration secondary sync [commands] [running | candidate | saved] [<config-node-path>]

   Display configuration differences between the local node and
   a config-sync secondary node.

   This command allows operators to compare configurations across nodes
   participating in configuration synchronization (e.g., primary and
   secondary routers). It helps detect configuration drift and validate
   intended changes before synchronization.

   **Parameters:**

   .. list-table::
      :widths: 30 70
      :header-rows: 0

      * - ``commands`` (optional)
        - Show output as a list of configuration commands instead of raw diff.
      * - ``running|candidate|saved`` (optional, mutually exclusive)
        - Select which configuration to compare:
          ``running`` (current active configuration, default),
          ``candidate`` (uncommitted changes), or
          ``saved`` (last saved configuration). Only one of these may be
          specified at a time; if omitted, ``running`` is used.

   **Examples:**

   .. code-block:: none

      # compare full running configuration with a secondary node
      show configuration secondary sync

      # compare only interface configuration
      show configuration secondary sync running interfaces dummy

      # compare candidate configuration and display as a list of commands
      show configuration secondary sync commands candidate

Without a built-in cross-node diff, operators may unintentionally push
changes that conflict with the remote configuration (e.g., mismatched
interfaces, firewall policies, or protocol settings).

Example
-------
* Synchronize the time-zone and OSPF configuration from Router A to Router B
* The address of Router B is 10.0.20.112 and the port used is 8443

Configure the HTTP API service on Router B

.. code-block:: none

    set service https listen-address '10.0.20.112'
    set service https port '8443'
    set service https api keys id KID key 'foo'
    set service https api rest

Configure the config-sync service on Router A

.. code-block:: none

    set service config-sync mode 'load'
    set service config-sync secondary address '10.0.20.112'
    set service config-sync secondary port '8443'
    set service config-sync secondary key 'foo'
    set service config-sync section protocols 'ospf'
    set service config-sync section system 'time-zone'

Make config-sync relevant changes to Router A's configuration

.. code-block:: none

   vyos@vyos-A# set system time-zone 'America/Los_Angeles'
   vyos@vyos-A# commit
   INFO:vyos_config_sync:Config synchronization: Mode=load, 
   Secondary=10.0.20.112
   vyos@vyos-A# save

   vyos@vyos-A# set protocols ospf area 0 network '10.0.48.0/30'
   vyos@vyos-A# commit
   INFO:vyos_config_sync:Config synchronization: Mode=load, 
   Secondary=10.0.20.112
   yos@vyos-A# save

Verify configuration changes have been replicated to Router B

.. code-block:: none

   vyos@vyos-B:~$ show configuration commands | match time-zone
   set system time-zone 'America/Los_Angeles'

   vyos@vyos-B:~$ show configuration commands | match ospf
   set protocols ospf area 0 network '10.0.48.0/30'

Known issues
------------
Configuration resynchronization. With the current implementation of `service 
config-sync`, the secondary node must be online.
