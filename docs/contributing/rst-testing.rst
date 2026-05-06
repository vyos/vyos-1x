:lastproofread: 2025-12-02

.. _testing:

#######
Testing
#######

One of the major features introduced in VyOS 1.3 is an automated test
framework. When you assemble an ISO image, several things can go wrong.
VyOS uses this framework to detect issues before they cause downstream problems.

This section describes how the automated testing process at VyOS works.

Smoketests
==========

Smoketests execute predefined VyOS CLI commands and check if the desired
daemon or service configuration is rendered.

When an ISO image is assembled by the `VyOS CI`_, the ``BUILD_SMOKETEST``
parameter is enabled by default. This extends the ISO configuration line
with the following packages:

.. code-block:: python

  def CUSTOM_PACKAGES = ''
    if (params.BUILD_SMOKETESTS)
      CUSTOM_PACKAGES = '--custom-package vyos-1x-smoketest'

If you plan to build your own custom ISO image and want to use VyOS's
smoketests, ensure that you have the `vyos-1x-smoketest` package installed.

The ``make test`` command from the vyos-build_ repository launches a new
QEMU instance, and the ISO image is first installed to the virtual hard disk.

After the first boot into the newly installed system, the main Smoketest script
is executed. It can be found at `/usr/bin/vyos-smoketest`.

The script searches for executable test cases under
``/usr/libexec/vyos/tests/smoke/cli/`` and executes them one by one.

.. note:: Smoketests will alter the system configuration. If you are logged
  in remotely, you may lose your connection to the system.

.. note:: To enable smoketest debugging (print the CLI set commands used),
  run: ``touch /tmp/vyos.smoketest.debug``.

Manual Smoketest Run
--------------------

Each test is contained in its own file, so you can execute a single Smoketest
manually by running the Python test script.

Example:

.. code-block:: none

  vyos@vyos:~$ /usr/libexec/vyos/tests/smoke/cli/test_protocols_bgp.py
  test_bgp_01_simple (__main__.TestProtocolsBGP) ... ok
  test_bgp_02_neighbors (__main__.TestProtocolsBGP) ... ok
  test_bgp_03_peer_groups (__main__.TestProtocolsBGP) ... ok
  test_bgp_04_afi_ipv4 (__main__.TestProtocolsBGP) ... ok
  test_bgp_05_afi_ipv6 (__main__.TestProtocolsBGP) ... ok
  test_bgp_06_listen_range (__main__.TestProtocolsBGP) ... ok
  test_bgp_07_l2vpn_evpn (__main__.TestProtocolsBGP) ... ok
  test_bgp_08_zebra_route_map (__main__.TestProtocolsBGP) ... ok
  test_bgp_09_distance_and_flowspec (__main__.TestProtocolsBGP) ... ok
  test_bgp_10_vrf_simple (__main__.TestProtocolsBGP) ... ok
  test_bgp_11_confederation (__main__.TestProtocolsBGP) ... ok
  test_bgp_12_v6_link_local (__main__.TestProtocolsBGP) ... ok
  test_bgp_13_solo (__main__.TestProtocolsBGP) ... ok

  ----------------------------------------------------------------------
  Ran 13 tests in 348.191s

  OK

Interface-based tests
---------------------

Our smoketests not only test daemons and services, but also check if interface
configuration works as expected. There is a common base class named
``base_interfaces_test.py`` that holds all the common code for interface tests.

These common tests consist of:

* Add one or more IP addresses
* DHCP client and DHCPv6 prefix delegation
* MTU size
* IP and IPv6 options
* Port description
* Port disable
* VLANs (QinQ and regular 802.1q)
* ...

.. note:: When you are working on interface configuration and want to test
  if the Smoketests pass, you would normally lose the remote SSH connection
  to your :abbr:`DUT (Device Under Test)`. To handle this, some interface-based
  tests can be called with an environment variable beforehand to limit the
  number of interfaces used in the test. By default, all interfaces (e.g., all
  Ethernet interfaces) are used.

.. code-block:: none

  vyos@vyos:~$ TEST_ETH="eth1 eth2" /usr/libexec/vyos/tests/smoke/cli/test_interfaces_bonding.py
  test_add_multiple_ip_addresses (__main__.BondingInterfaceTest) ... ok
  test_add_single_ip_address (__main__.BondingInterfaceTest) ... ok
  test_bonding_hash_policy (__main__.BondingInterfaceTest) ... ok
  test_bonding_lacp_rate (__main__.BondingInterfaceTest) ... ok
  test_bonding_min_links (__main__.BondingInterfaceTest) ... ok
  test_bonding_remove_member (__main__.BondingInterfaceTest) ... ok
  test_dhcpv6_client_options (__main__.BondingInterfaceTest) ... ok
  test_dhcpv6pd_auto_sla_id (__main__.BondingInterfaceTest) ... ok
  test_dhcpv6pd_manual_sla_id (__main__.BondingInterfaceTest) ... ok
  test_interface_description (__main__.BondingInterfaceTest) ... ok
  test_interface_disable (__main__.BondingInterfaceTest) ... ok
  test_interface_ip_options (__main__.BondingInterfaceTest) ... ok
  test_interface_ipv6_options (__main__.BondingInterfaceTest) ... ok
  test_interface_mtu (__main__.BondingInterfaceTest) ... ok
  test_ipv6_link_local_address (__main__.BondingInterfaceTest) ... ok
  test_mtu_1200_no_ipv6_interface (__main__.BondingInterfaceTest) ... ok
  test_span_mirror (__main__.BondingInterfaceTest) ... ok
  test_vif_8021q_interfaces (__main__.BondingInterfaceTest) ... ok
  test_vif_8021q_lower_up_down (__main__.BondingInterfaceTest) ... ok
  test_vif_8021q_mtu_limits (__main__.BondingInterfaceTest) ... ok
  test_vif_8021q_qos_change (__main__.BondingInterfaceTest) ... ok
  test_vif_s_8021ad_vlan_interfaces (__main__.BondingInterfaceTest) ... ok
  test_vif_s_protocol_change (__main__.BondingInterfaceTest) ... ok

  ----------------------------------------------------------------------
  Ran 23 tests in 244.694s

  OK

This will limit the `bond` interface test to use only `eth1` and `eth2`
as member ports.

Config Load Tests
=================

The other part of our tests are called "config load tests." Config load tests
sequentially load arbitrary configuration files to verify that configuration
migration scripts work as designed and that a given set of functionality can
still be loaded with a fresh VyOS ISO image.

The configurations are all derived from production systems and can act as
test cases or as references for enabling certain features. The configurations
can be found here:
https://github.com/vyos/vyos-1x/tree/current/smoketest/configs

The entire test is controlled by the main wrapper script
``/usr/bin/vyos-configtest``.
It behaves in the same way as the main smoketest script. It scans the folder
for potential configuration files and issues a ``load`` command for each file.

Manual config load test
-----------------------

You do not have to load all configurations sequentially; you can also load
individual test configurations manually.

.. code-block:: none

  vyos@vyos:~$ configure
  load[edit]

  vyos@vyos# load /usr/libexec/vyos/tests/config/ospf-small
  Loading configuration from '/usr/libexec/vyos/tests/config/ospf-small'
  Load complete. Use 'commit' to make changes effective.
  [edit]
  vyos@vyos# compare
  [edit interfaces ethernet eth0]
  -hw-id 00:50:56:bf:c5:6d
  [edit interfaces ethernet eth1]
  +duplex auto
  -hw-id 00:50:56:b3:38:c5
  +speed auto
  [edit interfaces]
  -ethernet eth2 {
  -    hw-id 00:50:56:b3:9c:1d
  -}
  -vti vti1 {
  -    address 192.0.2.1/30
  -}
  ...

  vyos@vyos# commit
  vyos@vyos#

.. note:: Some configurations have preconditions that must be met. These most
  likely include generation of cryptographic keys before the config can be
  applied; otherwise, you will get a commit error. If you are interested in
  how those preconditions are fulfilled, check the vyos-build_ repository and
  the ``scripts/check-qemu-install`` file.

.. include:: /_include/common-references.txt
